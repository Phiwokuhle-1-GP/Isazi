"""Cellphone/PIN agent applications; immediate champion access with purchase-credit codes."""
import re
import secrets
import sqlite3

from flask import flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from simple_checkout import normalize_phone
import champion_rewards


SCHEMA = '''
CREATE TABLE IF NOT EXISTS agent_phone_accounts (
 agent_id INTEGER PRIMARY KEY REFERENCES agents(id),
 phone TEXT NOT NULL UNIQUE,
 pin_hash TEXT NOT NULL,
 code_issued_at TEXT
);
'''


def issue_code(connection, agent_id):
    # The guarded write makes repeated or concurrent approval preserve the code.
    connection.execute('''UPDATE agents SET code=? WHERE id=? AND EXISTS
        (SELECT 1 FROM agent_phone_accounts WHERE agent_id=? AND code_issued_at IS NULL)''',
        ('ISZ-' + secrets.token_hex(8).upper(), agent_id, agent_id))
    connection.execute("UPDATE agent_phone_accounts SET code_issued_at=datetime('now') WHERE agent_id=? AND code_issued_at IS NULL", (agent_id,))


def register_agent_registration(bp, db, throttled, failure, audit):
    def keys(prefix, phone):
        return [prefix + ':ip:' + (request.remote_addr or 'unknown'),
                prefix + ':phone:' + phone]

    def start_session(agent, pending=False):
        session.clear()
        session.permanent = True
        if pending:
            session['agent_application_id'] = agent['id']
        else:
            session['agent_id'] = agent['id']
            session['agent_version'] = agent['auth_version']

    @bp.route('/agent/register', methods=['GET', 'POST'])
    def agent_register():
        if request.method == 'POST':
            key = 'agent-register:ip:' + (request.remote_addr or 'unknown')
            if throttled(key):
                flash('Too many registrations. Please wait 15 minutes.', 'error')
                return render_template('agent_register.html', title='Become a product champion'), 429
            failure(key)
            name = request.form.get('name', '').strip()
            phone = normalize_phone(request.form.get('phone', ''))
            pin = request.form.get('pin', '')
            if (not 2 <= len(name) <= 120 or not phone or not re.fullmatch(r'[0-9]{4}', pin)
                    or pin != request.form.get('confirm_pin', '') or not request.form.get('consent')):
                flash('Enter your full name, a valid South African cellphone number and matching 4-digit PINs. Agree to the privacy information.', 'error')
                return render_template('agent_register.html', title='Become a product champion'), 400
            try:
                connection = db()
                agent_id = connection.execute('''INSERT INTO agents(name,email,code,rate_bps,approved)
                    VALUES(?,?,?,?,1)''', (name, '', 'ISZ-' + secrets.token_hex(8).upper(), champion_rewards.default_rate(connection))).lastrowid
                connection.execute("INSERT INTO agent_phone_accounts(agent_id,phone,pin_hash,code_issued_at) VALUES(?,?,?,datetime('now'))",
                                   (agent_id, phone, generate_password_hash(pin)))
                code = connection.execute('SELECT code FROM agents WHERE id=?', (agent_id,)).fetchone()['code']
                champion_rewards.queue_confirmation(connection, agent_id, phone, code)
                audit(connection, 'Champion self-registration', agent_id, actor='champion')
                connection.commit()
            except sqlite3.IntegrityError:
                db().rollback()
                flash('Unable to create this registration. If you have registered, sign in with your cellphone and PIN.', 'error')
                return render_template('agent_register.html', title='Become a product champion'), 400
            start_session({'id': agent_id, 'auth_version': 0})
            flash('Registration complete. Your champion code is ready.', 'success')
            return redirect(url_for('eco.agent_portal'))
        return render_template('agent_register.html', title='Become a product champion')

    def phone_login():
        phone = normalize_phone(request.form.get('phone', ''))
        login_keys = keys('agent-pin', phone or 'invalid')
        if any(throttled(key) for key in login_keys):
            flash('Too many attempts. Please wait 15 minutes.', 'error')
            return render_template('agent_login.html', title='Product champion sign in'), 429
        account = db().execute('''SELECT a.*, p.pin_hash FROM agents a
            JOIN agent_phone_accounts p ON p.agent_id=a.id WHERE p.phone=?''', (phone,)).fetchone()
        pin = request.form.get('pin', '')
        if not (account and re.fullmatch(r'[0-9]{4}', pin) and check_password_hash(account['pin_hash'], pin)):
            for key in login_keys:
                failure(key)
            flash('Unable to sign in. Check your cellphone number and PIN.', 'error')
            return render_template('agent_login.html', title='Product champion sign in'), 400
        for key in login_keys:
            db().execute('DELETE FROM login_attempts WHERE ip=?', (key,))
        db().commit()
        start_session(account, pending=not account['approved'])
        return redirect(url_for('eco.agent_portal' if account['approved'] else 'eco.agent_application'))

    @bp.get('/agent/application')
    def agent_application():
        agent = db().execute('''SELECT a.*,p.code_issued_at FROM agents a JOIN agent_phone_accounts p
            ON p.agent_id=a.id WHERE a.id=?''', (session.get('agent_application_id'),)).fetchone()
        if not agent:
            return redirect(url_for('eco.agent_login'))
        if agent['approved']:
            start_session(agent)
            return redirect(url_for('eco.agent_portal'))
        return render_template('agent_application.html', title='Agent application', paused=bool(agent['code_issued_at']))

    return phone_login
