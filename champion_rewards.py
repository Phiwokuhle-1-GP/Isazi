"""Champion registration SMS and separately labelled simulated purchase credits."""

from flask import abort, current_app, flash, g, redirect, request, url_for
from payment_gateway import cents

SCHEMA = '''
CREATE TABLE IF NOT EXISTS champion_sms (
 id INTEGER PRIMARY KEY, agent_id INTEGER NOT NULL UNIQUE REFERENCES agents(id),
 recipient TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Queued',
 provider_id TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS champion_test_credits (
 order_id INTEGER PRIMARY KEY REFERENCES orders(id), agent_id INTEGER NOT NULL REFERENCES agents(id),
 amount INTEGER NOT NULL DEFAULT 0);
CREATE INDEX IF NOT EXISTS idx_champion_test_agent ON champion_test_credits(agent_id);
CREATE TABLE IF NOT EXISTS champion_test_payouts (
 id INTEGER PRIMARY KEY, agent_id INTEGER NOT NULL REFERENCES agents(id),
 amount INTEGER NOT NULL CHECK(amount>0), reference TEXT NOT NULL, event_key TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE(agent_id,reference));
'''


def default_rate(connection):
    row = connection.execute("SELECT value FROM settings WHERE key='champion_default_bps'").fetchone()
    return int(row['value']) if row else 500


def queue_confirmation(connection, agent_id, phone, code):
    test = current_app.testing or current_app.config.get('DEMO_MODE') or current_app.config.get('DEMO_PAYMENTS_ENABLED')
    rate = connection.execute('SELECT rate_bps FROM agents WHERE id=?', (agent_id,)).fetchone()[0] / 100
    body = (f'Welcome to Isazi! Your product champion code is {code}. '
            f'Buyers using your code get 5% off goods. You earn {rate:g}% credit on discounted goods after payment confirmation. '
            'Sign in with your cellphone and PIN to view your balance. Never share your PIN.')
    connection.execute('INSERT OR IGNORE INTO champion_sms(agent_id,recipient,body,status) VALUES(?,?,?,?)',
                       (agent_id, phone, body, 'Test - not sent' if test else 'Queued'))
    g.champion_sms_ids = getattr(g, 'champion_sms_ids', []) + [agent_id]


def initialize(connection):
    connection.executescript(SCHEMA)
    connection.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('champion_default_bps','500')")
    # Upgrade only unissued applications; deliberately paused accounts stay paused.
    from agent_registration import issue_code
    pending = connection.execute('''SELECT a.id,p.phone FROM agents a JOIN agent_phone_accounts p
        ON p.agent_id=a.id WHERE a.approved=0 AND p.code_issued_at IS NULL''').fetchall()
    for row in pending:
        issue_code(connection, row['id'])
        connection.execute('UPDATE agents SET approved=1,rate_bps=?,auth_version=auth_version+1 WHERE id=?',
                           (default_rate(connection), row['id']))
        code = connection.execute('SELECT code FROM agents WHERE id=?', (row['id'],)).fetchone()['code']
        # Migration never dispatches a backlog on startup. Owner can send queued live messages.
        queue_confirmation(connection, row['id'], row['phone'], code)
    g.champion_sms_ids = []


def sync_test_credit(connection, order, extra):
    # Test credits never enter the real commission ledger or payout balance.
    if not extra['payment_test']:
        return
    if not connection.execute('SELECT 1 FROM agent_phone_accounts WHERE agent_id=?', (extra['agent_id'],)).fetchone():
        return
    received = connection.execute('SELECT COALESCE(SUM(amount),0) FROM payments_received WHERE order_id=?', (order['id'],)).fetchone()[0]
    refunded = connection.execute('SELECT COALESCE(SUM(goods),0) FROM refunds WHERE order_id=?', (order['id'],)).fetchone()[0]
    eligible = extra['payment_test'] and order['status'] in ('Paid', 'Ready', 'Completed') and received >= order['total']
    amount = max(0, order['subtotal'] - extra['discount'] - refunded) * extra['rate_bps'] // 10000 if eligible else 0
    connection.execute('''INSERT INTO champion_test_credits(order_id,agent_id,amount) VALUES(?,?,?)
        ON CONFLICT(order_id) DO UPDATE SET amount=excluded.amount''', (order['id'], extra['agent_id'], amount))


def reconcile_test_credits(connection):
    """Recover historical simulated credits once; never create payment receipts."""
    if connection.execute("SELECT 1 FROM settings WHERE key='_champion_test_credit_backfill_v1'").fetchone():
        return
    rows = connection.execute('''SELECT o.*,e.agent_id FROM orders o JOIN order_extra e ON e.order_id=o.id
        JOIN agent_phone_accounts p ON p.agent_id=e.agent_id WHERE e.payment_test=1''').fetchall()
    for order in rows:
        extra = connection.execute('SELECT * FROM order_extra WHERE order_id=?', (order['id'],)).fetchone()
        sync_test_credit(connection, order, extra)
    connection.execute("INSERT INTO settings(key,value) VALUES('_champion_test_credit_backfill_v1','1')")


def test_totals(connection, agent_id):
    earned=connection.execute('SELECT COALESCE(SUM(amount),0) FROM champion_test_credits WHERE agent_id=?',(agent_id,)).fetchone()[0]
    paid=connection.execute('SELECT COALESCE(SUM(amount),0) FROM champion_test_payouts WHERE agent_id=?',(agent_id,)).fetchone()[0]
    return dict(test_earned=earned,test_paid=paid,test_balance=earned-paid)


def portal_context(connection, agent_id):
    phone = connection.execute('SELECT phone FROM agent_phone_accounts WHERE agent_id=?', (agent_id,)).fetchone()
    return dict(is_champion=bool(phone), testing_mode=bool(current_app.config.get('DEMO_MODE') or current_app.config.get('DEMO_PAYMENTS_ENABLED')), sms=connection.execute('SELECT status FROM champion_sms WHERE agent_id=?', (agent_id,)).fetchone(),
                **test_totals(connection, agent_id))


def register(bp, db, admin_only, audit):
    def deliver(agent_id):
        connection = db()
        values = current_app.extensions['simple_checkout']['sms_config']()
        connection.execute('BEGIN IMMEDIATE')
        row = connection.execute('SELECT s.*,a.approved FROM champion_sms s JOIN agents a ON a.id=s.agent_id WHERE s.agent_id=?', (agent_id,)).fetchone()
        if not row or row['status'] != 'Queued' or not row['approved'] or current_app.testing or current_app.config.get('DEMO_MODE') or current_app.config.get('DEMO_PAYMENTS_ENABLED'):
            connection.rollback()
            return 'blocked'
        if values.get('sms_enabled') != '1' or not all(values.get(k) for k in ('sms_sid', 'sms_token', 'sms_from')):
            connection.rollback()
            return 'unconfigured'
        connection.execute("UPDATE champion_sms SET status='Sending - reconcile before retry' WHERE agent_id=?", (agent_id,))
        connection.commit()
        try:
            provider_id = current_app.extensions['simple_checkout']['send_text'](values, row['recipient'], row['body'])
            connection.execute("UPDATE champion_sms SET status='Provider accepted',provider_id=? WHERE agent_id=?", (provider_id, agent_id))
            connection.commit()
            return 'accepted'
        except Exception:
            return 'uncertain'

    @bp.after_app_request
    def send_registration_confirmation(response):
        if response.status_code < 400 and not db().in_transaction:
            for agent_id in dict.fromkeys(getattr(g, 'champion_sms_ids', [])):
                deliver(agent_id)
        return response

    @bp.post('/owner/champions/settings')
    @admin_only
    def champion_settings():
        try:
            rate = cents(request.form.get('rate', ''))
            if not 0 <= rate <= 10000:
                raise ValueError('Enter a credit percentage from 0 to 100.')
            db().execute("INSERT OR REPLACE INTO settings(key,value) VALUES('champion_default_bps',?)", (str(rate),))
            audit(db(), 'Champion default credit rate', 'settings', f'{rate} basis points; new registrations only')
            db().commit()
            flash('Default credit rate saved for new champions. Existing rates can be edited individually.', 'success')
        except ValueError as error:
            db().rollback()
            flash(str(error), 'error')
        return redirect(url_for('eco.owner_agents'))

    @bp.post('/owner/champions/<int:agent_id>/sms')
    @admin_only
    def champion_sms_send(agent_id):
        result = deliver(agent_id)
        if result == 'blocked':
            abort(409, 'This message is test-only, already submitted, unavailable or the account is paused.')
        flash({'accepted': 'Confirmation SMS accepted by the provider; handset delivery is not confirmed.',
               'unconfigured': 'Enable and configure SMS under Cellphone checkout & PEP first.',
               'uncertain': 'SMS outcome uncertain. Reconcile in the provider dashboard before retrying.'}[result],
              'success' if result == 'accepted' else 'error')
        return redirect(url_for('eco.owner_agents'))
