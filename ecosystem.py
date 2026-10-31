"""Connected customer, owner and approved-agent workflows; no external sends on startup."""
import csv
import functools
import hashlib
import io
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import time
from datetime import datetime
from email.message import EmailMessage
from urllib.parse import quote, urlsplit

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash
import payment_gateway as gateway

def valid_email(value):
    return len(value)<=200 and bool(re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)+", value))


SCHEMA = '''
CREATE TABLE IF NOT EXISTS customers (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL COLLATE NOCASE, phone TEXT NOT NULL DEFAULT '',
 password_hash TEXT NOT NULL, auth_version INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS customer_addresses (
 id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id), label TEXT NOT NULL, address TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS saved_products (
 customer_id INTEGER NOT NULL REFERENCES customers(id), product_id INTEGER NOT NULL REFERENCES products(id), PRIMARY KEY(customer_id,product_id));
CREATE TABLE IF NOT EXISTS product_details (
 product_id INTEGER PRIMARY KEY REFERENCES products(id), benefits TEXT NOT NULL DEFAULT '', ingredients TEXT NOT NULL DEFAULT '', directions TEXT NOT NULL DEFAULT '');
CREATE TABLE IF NOT EXISTS product_gallery (
 id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), filename TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS product_reviews (
 id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), customer_id INTEGER NOT NULL REFERENCES customers(id),
 rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5), comment TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending',
 created_at TEXT NOT NULL DEFAULT (datetime('now')), UNIQUE(product_id,customer_id));
CREATE TABLE IF NOT EXISTS coupons (
 id INTEGER PRIMARY KEY, code TEXT UNIQUE NOT NULL, kind TEXT NOT NULL, value INTEGER NOT NULL,
 minimum INTEGER NOT NULL DEFAULT 0, max_uses INTEGER NOT NULL DEFAULT 100, expires TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS order_coupons (
 order_id INTEGER PRIMARY KEY REFERENCES orders(id), coupon_id INTEGER NOT NULL REFERENCES coupons(id), discount INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS agents (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL, code TEXT UNIQUE NOT NULL,
 rate_bps INTEGER NOT NULL CHECK(rate_bps BETWEEN 0 AND 10000), approved INTEGER NOT NULL DEFAULT 0,
 password_hash TEXT, auth_version INTEGER NOT NULL DEFAULT 0, invite_hash TEXT UNIQUE, invite_expires REAL,
 created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS order_extra (
 order_id INTEGER PRIMARY KEY REFERENCES orders(id), customer_id INTEGER REFERENCES customers(id), discount INTEGER NOT NULL DEFAULT 0, agent_id INTEGER REFERENCES agents(id), agent_code TEXT NOT NULL DEFAULT '',
 rate_bps INTEGER NOT NULL DEFAULT 0, delivery_status TEXT NOT NULL DEFAULT 'Not arranged', courier TEXT NOT NULL DEFAULT '',
 tracking_reference TEXT NOT NULL DEFAULT '', tracking_url TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS payments_received (
 id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), event_key TEXT UNIQUE NOT NULL,
 amount INTEGER NOT NULL CHECK(amount>0), method TEXT NOT NULL, reference TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS payment_attempts (
 id TEXT PRIMARY KEY, order_id INTEGER UNIQUE NOT NULL REFERENCES orders(id), amount INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'Initiated', provider_reference TEXT UNIQUE,
 created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS refunds (
 id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), event_key TEXT UNIQUE NOT NULL,
 goods INTEGER NOT NULL CHECK(goods>=0), shipping INTEGER NOT NULL CHECK(shipping>=0), extra INTEGER NOT NULL CHECK(extra>=0),
 reference TEXT NOT NULL, reason TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS commission_snapshots (
 order_id INTEGER PRIMARY KEY REFERENCES orders(id), agent_id INTEGER NOT NULL REFERENCES agents(id), target INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS commission_ledger (
 id INTEGER PRIMARY KEY, agent_id INTEGER NOT NULL REFERENCES agents(id), order_id INTEGER REFERENCES orders(id),
 amount INTEGER NOT NULL, kind TEXT NOT NULL, reference TEXT NOT NULL,
 event_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS notifications (
 id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), event_key TEXT UNIQUE NOT NULL,
 recipient TEXT NOT NULL, subject TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Queued',
 sent_at TEXT, last_error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS customer_notes (email TEXT PRIMARY KEY, notes TEXT NOT NULL);
CREATE UNIQUE INDEX IF NOT EXISTS idx_refund_reference ON refunds(order_id,reference);
CREATE UNIQUE INDEX IF NOT EXISTS idx_payout_reference ON commission_ledger(agent_id,reference) WHERE kind='Payout';
CREATE INDEX IF NOT EXISTS idx_order_extra_customer ON order_extra(customer_id);
CREATE INDEX IF NOT EXISTS idx_order_extra_agent ON order_extra(agent_id);
CREATE INDEX IF NOT EXISTS idx_receipts_order ON payments_received(order_id);
CREATE INDEX IF NOT EXISTS idx_refunds_order ON refunds(order_id);
CREATE INDEX IF NOT EXISTS idx_ledger_agent ON commission_ledger(agent_id);
CREATE INDEX IF NOT EXISTS idx_reviews_product ON product_reviews(product_id,status);
CREATE TABLE IF NOT EXISTS audit_events (
 id INTEGER PRIMARY KEY, actor TEXT NOT NULL, event TEXT NOT NULL, reference TEXT NOT NULL,
 detail TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')));
'''
DELIVERY_STATUSES = ['Not arranged', 'Ready for collection', 'Booked', 'In transit', 'Delivered', 'Collected']


def register_ecosystem(app, db, admin_only):
    bp = Blueprint('eco', __name__)

    def option(key, default=''):
        return current_app.config.get(key, os.environ.get(key, default))

    def public_base():
        raw = str(option('PUBLIC_BASE_URL')).rstrip('/')
        try: parsed = urlsplit(raw)
        except ValueError: return ''
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            return ''
        if parsed.hostname in ('localhost', '127.0.0.1', '::1') or parsed.hostname.endswith('.local'):
            return ''
        return raw

    def payfast_config():
        mode = option('PAYFAST_MODE', 'sandbox')
        ready = option('PAYFAST_ENABLED') == '1' and mode in ('sandbox', 'live') and all(option(k) for k in ('PAYFAST_MERCHANT_ID', 'PAYFAST_MERCHANT_KEY', 'PAYFAST_PASSPHRASE')) and bool(public_base())
        return {'ready': bool(ready), 'mode': mode, 'host': 'sandbox.payfast.co.za' if mode == 'sandbox' else 'www.payfast.co.za'}

    def smtp_ready():
        sender = str(option('SMTP_FROM'))
        return bool(public_base() and option('SMTP_HOST') and valid_email(sender) and (not option('SMTP_USER') or option('SMTP_PASSWORD')) and option('SMTP_SECURITY', 'starttls') in ('starttls', 'ssl'))

    def audit(connection, event, reference, detail='', actor=None):
        actor = actor or ('owner' if session.get('admin') else 'agent:' + str(session['agent_id']) if session.get('agent_id') else 'customer')
        connection.execute('INSERT INTO audit_events(actor,event,reference,detail) VALUES(?,?,?,?)', (actor, event, str(reference), detail[:1000]))

    def financials(connection, order_id):
        order = connection.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
        received = connection.execute('SELECT COALESCE(SUM(amount),0) FROM payments_received WHERE order_id=?', (order_id,)).fetchone()[0]
        returned = connection.execute('SELECT COALESCE(SUM(goods),0),COALESCE(SUM(shipping),0),COALESCE(SUM(extra),0) FROM refunds WHERE order_id=?', (order_id,)).fetchone()
        refunded = sum(returned)
        state = 'Refunded' if received > 0 and refunded >= received else 'Partially refunded' if refunded else 'Paid' if received >= order['total'] else 'Awaiting payment'
        return dict(received=received, refunded=refunded, goods_refunded=returned[0], shipping_refunded=returned[1], extra_refunded=returned[2], net=received-refunded, state=state, overpaid=max(0,received-order['total']), outstanding=max(0,order['total']-received))

    def extra_for(connection, order_id):
        return connection.execute('SELECT * FROM order_extra WHERE order_id=?', (order_id,)).fetchone()

    def queue_update(connection, order_id, event, message):
        test_order=connection.execute('SELECT payment_test FROM order_extra WHERE order_id=?',(order_id,)).fetchone()
        if test_order and test_order['payment_test']:
            return
        order = connection.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
        if order['email'].endswith('@phone.invalid'):
            return
        link = public_base() + url_for('confirmation', token=order['token']) if public_base() else ''
        body = f"Hello {order['name']},\n\nOrder ISZ-{order_id:05d}\n{message}\nOrder status: {order['status']}\n"
        if link:
            body += '\nView your private order receipt and tracking details:\n' + link + '\n'
        body += '\nIsazi Herbal Shop\n'
        connection.execute('INSERT OR IGNORE INTO notifications(order_id,event_key,recipient,subject,body) VALUES(?,?,?,?,?)', (order_id, event, order['email'], f'Isazi order ISZ-{order_id:05d} update', body))

    def sync_commission(connection, order_id):
        order = connection.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
        extra = extra_for(connection, order_id)
        if not extra or not extra['agent_id']:
            return
        info = financials(connection, order_id)
        eligible = not extra['payment_test'] and order['status'] in ('Paid', 'Ready', 'Completed') and info['received'] >= order['total']
        target = max(0,order['subtotal']-extra['discount']-info['goods_refunded']) * extra['rate_bps'] // 10000 if eligible else 0
        previous = connection.execute('SELECT target FROM commission_snapshots WHERE order_id=?', (order_id,)).fetchone()
        delta = target - (previous['target'] if previous else 0)
        connection.execute('INSERT INTO commission_snapshots(order_id,agent_id,target) VALUES(?,?,?) ON CONFLICT(order_id) DO UPDATE SET target=excluded.target', (order_id, extra['agent_id'], target))
        if delta:
            connection.execute('INSERT INTO commission_ledger(agent_id,order_id,amount,kind,reference,event_key) VALUES(?,?,?,?,?,?)', (extra['agent_id'],order_id,delta,'Accrual' if delta>0 else 'Reversal',f'ISZ-{order_id:05d}',secrets.token_hex(24)))

    def current_referral():
        if time.time() - session.get('referral_at', 0) > 30*86400:
            return ''
        return session.get('referral', '')

    def resolve_agent(code):
        if not code:
            return None
        return db().execute('SELECT * FROM agents WHERE code=? AND approved=1', (code.strip().upper(),)).fetchone()

    def capture_order(connection, order_id, form, coupon=None):
        agent = resolve_agent(form.get('agent_code', current_referral()).strip())
        code=form.get('agent_code',current_referral()).strip()
        if code and not agent:
            raise ValueError('The selected agent code is no longer available.')
        customer=current_customer()
        discount=coupon['discount'] if coupon else 0
        connection.execute('INSERT INTO order_extra(order_id,customer_id,discount,agent_id,agent_code,rate_bps) VALUES(?,?,?,?,?,?)', (order_id,customer['id'] if customer else None,discount,agent['id'] if agent else None,agent['code'] if agent else '',agent['rate_bps'] if agent else 0))
        if app.config.get('DEMO_MODE') or app.config.get('DEMO_PAYMENTS_ENABLED'):
            connection.execute('UPDATE order_extra SET payment_test=1 WHERE order_id=?',(order_id,))
            if not app.config.get('DEMO_MODE'):
                connection.execute("UPDATE order_extra SET stock_pool='presentation' WHERE order_id=?",(order_id,))
        if coupon and coupon['coupon']:
            connection.execute('INSERT INTO order_coupons(order_id,coupon_id,discount) VALUES(?,?,?)',(order_id,coupon['coupon']['id'],discount))
        queue_update(connection,order_id,'created:'+str(order_id),'Your order has been received. Payment and delivery will be confirmed by our team.')
        audit(connection,'Order created',order_id)

    def order_changed(connection, order_id, previous):
        order = connection.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
        if order['status']=='Paid' and financials(connection,order_id)['received'] == 0:
            connection.execute('INSERT OR IGNORE INTO payments_received(order_id,event_key,amount,method,reference) VALUES(?,?,?,?,?)',(order_id,'manual:'+str(order_id),order['total'],'Owner confirmation',f'ISZ-{order_id:05d}'))
        sync_commission(connection,order_id)
        if previous != order['status']:
            queue_update(connection,order_id,'status:'+secrets.token_hex(16),'Your order status was updated by our team.')
            audit(connection,'Order status',order_id,previous+' -> '+order['status'])

    def initialize():
        db().executescript(SCHEMA)
        if 'stock_pool' not in {row[1] for row in db().execute('PRAGMA table_info(order_extra)')}:
            db().execute("ALTER TABLE order_extra ADD COLUMN stock_pool TEXT NOT NULL DEFAULT 'store'")
        if 'payment_test' not in {row[1] for row in db().execute('PRAGMA table_info(order_extra)')}:
            db().execute('ALTER TABLE order_extra ADD COLUMN payment_test INTEGER NOT NULL DEFAULT 0')
        db().execute('INSERT OR IGNORE INTO order_extra(order_id) SELECT id FROM orders')
        db().execute("UPDATE order_extra SET payment_test=1 WHERE order_id IN (SELECT order_id FROM payments_received WHERE method LIKE 'CLIENT DEMO / %')")
        if app.config.get('DEMO_MODE'):
            db().execute('UPDATE order_extra SET payment_test=1')
        if not db().execute("SELECT 1 FROM settings WHERE key='_eco_finance_backfill_v1'").fetchone():
            db().execute("INSERT OR IGNORE INTO payments_received(order_id,event_key,amount,method,reference) SELECT o.id,'manual:'||o.id,o.total,'Legacy owner confirmation','ISZ-'||o.id FROM orders o WHERE o.status IN ('Paid','Ready','Completed') AND NOT EXISTS(SELECT 1 FROM payments_received p WHERE p.order_id=o.id)")
            db().execute("INSERT INTO settings(key,value) VALUES('_eco_finance_backfill_v1','1')")
        db().commit()

    def throttled(key):
        row = db().execute('SELECT * FROM login_attempts WHERE ip=?',(key,)).fetchone()
        return bool(row and row['failures']>=5 and row['locked_until']>time.time())

    def failure(key):
        row = db().execute('SELECT * FROM login_attempts WHERE ip=?',(key,)).fetchone()
        count = row['failures']+1 if row and row['locked_until']>time.time() else 1
        db().execute('INSERT OR REPLACE INTO login_attempts(ip,failures,locked_until) VALUES(?,?,?)',(key,count,time.time()+900))
        db().commit()

    def agent_only(fn):
        @functools.wraps(fn)
        def wrapped(*args,**kwargs):
            agent = db().execute('SELECT * FROM agents WHERE id=? AND approved=1',(session.get('agent_id'),)).fetchone()
            if not agent or agent['auth_version'] != session.get('agent_version'):
                session.pop('agent_id',None)
                return redirect(url_for('eco.agent_login'))
            return fn(agent,*args,**kwargs)
        return wrapped

    @app.before_request
    def referral_query():
        if request.endpoint == 'shop' and 'ref' in request.args:
            agent = resolve_agent(request.args.get('ref',''))
            if agent:
                session['referral'],session['referral_at'] = agent['code'],time.time()

    @app.context_processor
    def connected_context():
        return dict(agent_code=current_referral(),gateway=payfast_config(),smtp_connected=smtp_ready(),customer=current_customer())

    @app.before_request
    def exclusive_customer_login():
        if session.get('admin') and request.endpoint in ('eco.customer_login','eco.customer_register','demo.account'):
            if request.method=='POST':
                abort(403,'Sign out of the owner account before signing in or registering as a customer.')
            flash('You are signed in as owner. Sign out before using a customer account, or use a separate browser profile.','error')
            return redirect(url_for('owner'))

    def current_customer():
        if session.get('admin'):
            return None
        customer=db().execute('SELECT * FROM customers WHERE id=? AND active=1',(session.get('customer_id'),)).fetchone()
        if not customer or customer['auth_version']!=session.get('customer_version'):
            return None
        return customer

    def customer_only(fn):
        @functools.wraps(fn)
        def wrapped(*args,**kwargs):
            customer=current_customer()
            if not customer:
                return redirect(url_for('eco.customer_login'))
            return fn(customer,*args,**kwargs)
        return wrapped

    def customer_session(customer):
        retained={key:session[key] for key in ('cart','coupon','referral','referral_at','after_auth_product','quick_product','after_auth_quick','after_auth_checkout') if key in session}
        session.clear();session.update(retained)
        session['customer_id']=customer['id'];session['customer_version']=customer['auth_version'];session.permanent=True

    def customer_destination():
        if session.pop('after_auth_checkout',False):
            session.pop('after_auth_quick',None)
            return url_for('checkout')
        quick=session.pop('after_auth_quick',None)
        if isinstance(quick,int):
            session['quick_product']=quick
            return url_for('checkout')
        product_id=session.pop('after_auth_product',None)
        return url_for('product',product_id=product_id) if isinstance(product_id,int) else url_for('eco.customer_account')

    @bp.route('/account/register',methods=['GET','POST'])
    def customer_register():
        if request.method=='POST' and 'pin' in request.form:
            return app.extensions['simple_checkout']['register_phone'](customer_session,customer_destination,throttled,failure)
        if request.method=='POST':
            key='register:'+(request.remote_addr or 'unknown')
            if throttled(key):
                abort(429)
            name=request.form.get('name','').strip();email=request.form.get('email','').strip().lower();password=request.form.get('password','');phone=request.form.get('phone','').strip()
            if not 2<=len(name)<=120 or len(email)>200 or not valid_email(email) or not 16<=len(password)<=256 or password!=request.form.get('confirm','') or not re.fullmatch(r'[+\d ()-]{7,25}',phone) or not request.form.get('consent'):
                flash('Enter your name, valid email/contact number, matching passwords of at least 16 characters and privacy consent.','error');failure(key)
            else:
                try:
                    customer_id=db().execute('INSERT INTO customers(name,email,phone,password_hash) VALUES(?,?,?,?)',(name,email,phone,generate_password_hash(password))).lastrowid
                    db().commit();failure(key)
                    customer_session(db().execute('SELECT * FROM customers WHERE id=?',(customer_id,)).fetchone())
                    return redirect(customer_destination())
                except sqlite3.IntegrityError:
                    db().rollback();failure(key);flash('Unable to create an account with those details. Try signing in or contact the team.','error')
        return render_template('customer_register.html',title='Create your account')

    @bp.route('/account/login',methods=['GET','POST'])
    def customer_login():
        if request.method=='POST' and 'pin' in request.form:
            return app.extensions['simple_checkout']['login_phone'](customer_session,customer_destination,throttled,failure)
        if request.method=='POST':
            key='customer:'+(request.remote_addr or 'unknown')
            if throttled(key):
                flash('Too many attempts. Please wait 15 minutes.','error')
                return render_template('customer_login.html',title='Customer sign in'),429
            customer=db().execute('SELECT * FROM customers WHERE email=? COLLATE NOCASE AND active=1',(request.form.get('email','').strip(),)).fetchone()
            if customer and check_password_hash(customer['password_hash'],request.form.get('password','')):
                db().execute('DELETE FROM login_attempts WHERE ip=?',(key,));db().commit();customer_session(customer)
                return redirect(customer_destination())
            failure(key);flash('Unable to sign in. Check your email and password.','error')
        return render_template('customer_login.html',title='Customer sign in')

    @bp.post('/account/logout')
    def customer_logout():
        session.clear();return redirect(url_for('home'))

    @bp.get('/account')
    @customer_only
    def customer_account(customer):
        orders=db().execute('SELECT o.*,e.delivery_status,e.payment_test FROM orders o JOIN order_extra e ON e.order_id=o.id WHERE e.customer_id=? ORDER BY o.id DESC',(customer['id'],)).fetchall()
        addresses=db().execute('SELECT * FROM customer_addresses WHERE customer_id=? ORDER BY id DESC',(customer['id'],)).fetchall()
        saved=db().execute('SELECT p.* FROM products p JOIN saved_products s ON s.product_id=p.id WHERE s.customer_id=? AND p.active=1 ORDER BY p.name',(customer['id'],)).fetchall()
        if app.config.get('DEMO_PAYMENTS_ENABLED') and not app.config.get('DEMO_MODE'):
            saved=[dict(p,stock=p['presentation_stock']) for p in map(dict,saved)]
        return render_template('customer_account.html',orders=orders,addresses=addresses,saved=saved,title='My account')

    @bp.post('/account/details')
    @customer_only
    def customer_details(customer):
        name=request.form.get('name','').strip();phone=request.form.get('phone','').strip()
        phone_account=app.extensions['simple_checkout']['account'](customer)
        if phone_account:
            phone=phone_account['phone']
        if not 2<=len(name)<=120 or not re.fullmatch(r'[+\d ()-]{7,25}',phone):
            flash('Enter a valid name and contact number.','error')
        else:
            db().execute('UPDATE customers SET name=?,phone=? WHERE id=?',(name,phone,customer['id']));db().commit();flash('Account details updated.','success')
        return redirect(url_for('eco.customer_account')+'#details')

    @bp.post('/account/password')
    @customer_only
    def customer_password(customer):
        password=request.form.get('password','')
        if not check_password_hash(customer['password_hash'],request.form.get('current_password','')) or not 16<=len(password)<=256 or password!=request.form.get('confirm',''):
            flash('Check your current password and use matching new passwords of at least 16 characters.','error')
        else:
            db().execute('UPDATE customers SET password_hash=?,auth_version=auth_version+1 WHERE id=?',(generate_password_hash(password),customer['id']));db().commit();session['customer_version']=customer['auth_version']+1;flash('Password changed. Other signed-in sessions have been invalidated.','success')
        return redirect(url_for('eco.customer_account')+'#password')

    @bp.post('/account/address')
    @customer_only
    def customer_address(customer):
        label=request.form.get('label','').strip();address=request.form.get('address','').strip()
        count=db().execute('SELECT COUNT(*) FROM customer_addresses WHERE customer_id=?',(customer['id'],)).fetchone()[0]
        if not 2<=len(label)<=80 or not 10<=len(address)<=600 or count>=10:
            flash('Use a label of 2–80 characters and a complete address. Up to ten addresses may be saved.','error')
        else:
            db().execute('INSERT INTO customer_addresses(customer_id,label,address) VALUES(?,?,?)',(customer['id'],label,address));db().commit();flash('Address saved.','success')
        return redirect(url_for('eco.customer_account')+'#addresses')

    @bp.post('/account/address/<int:address_id>/remove')
    @customer_only
    def customer_address_remove(customer,address_id):
        db().execute('DELETE FROM customer_addresses WHERE id=? AND customer_id=?',(address_id,customer['id']));db().commit()
        return redirect(url_for('eco.customer_account')+'#addresses')

    @bp.post('/account/saved/<int:product_id>')
    @customer_only
    def customer_saved(customer,product_id):
        if not db().execute('SELECT 1 FROM products WHERE id=? AND active=1',(product_id,)).fetchone():
            abort(404)
        if request.form.get('remove'):
            db().execute('DELETE FROM saved_products WHERE product_id=? AND customer_id=?',(product_id,customer['id']))
        else:
            db().execute('INSERT OR IGNORE INTO saved_products(customer_id,product_id) VALUES(?,?)',(customer['id'],product_id))
        db().commit();flash('Saved products updated.','success')
        return redirect(url_for('product',product_id=product_id))

    @bp.post('/account/orders/claim')
    @customer_only
    def customer_claim(customer):
        token=request.form.get('token','').strip()
        order=db().execute('SELECT o.id FROM orders o JOIN order_extra e ON e.order_id=o.id WHERE o.token=? AND lower(o.email)=lower(?) AND e.customer_id IS NULL',(token,customer['email'])).fetchone()
        if order:
            db().execute('UPDATE order_extra SET customer_id=? WHERE order_id=? AND customer_id IS NULL',(customer['id'],order['id']));db().commit();flash('Order added to your account.','success')
        else:
            flash('We could not match an unclaimed order receipt to your account.','error')
        return redirect(url_for('eco.customer_account'))

    def coupon_for_checkout(connection,subtotal):
        code=session.get('coupon','')
        if not code:
            return dict(coupon=None,discount=0)
        coupon=connection.execute('SELECT * FROM coupons WHERE code=? AND active=1',(code,)).fetchone()
        if not coupon or (coupon['expires'] and coupon['expires']<datetime.utcnow().strftime('%Y-%m-%d')) or subtotal<coupon['minimum']:
            raise ValueError('The promotion is unavailable or its minimum spend has not been met. Remove it from your cart or use another code.')
        uses=connection.execute("SELECT COUNT(*) FROM order_coupons c JOIN orders o ON o.id=c.order_id WHERE c.coupon_id=? AND o.status!='Cancelled'",(coupon['id'],)).fetchone()[0]
        if uses>=coupon['max_uses']:
            raise ValueError('This promotion has reached its usage limit. Remove it from your cart.')
        amount=subtotal*coupon['value']//10000 if coupon['kind']=='percent' else coupon['value']
        return dict(coupon=coupon,discount=min(subtotal,amount))

    def cart_promotion(subtotal):
        try:
            promo=coupon_for_checkout(db(),subtotal)
            return dict(discount=promo['discount'],coupon_code=session.get('coupon',''),coupon_error='')
        except ValueError as error:
            return dict(discount=0,coupon_code=session.get('coupon',''),coupon_error=str(error))

    @bp.post('/cart/coupon')
    def cart_coupon():
        if request.form.get('remove'):
            session.pop('coupon',None);return redirect(url_for('cart'))
        code=request.form.get('code','').strip().upper()
        if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{2,23}',code):
            flash('Enter a valid promotion code.','error');return redirect(url_for('cart'))
        subtotal=0
        for key,quantity in session.get('cart',{}).items():
            product=db().execute('SELECT price FROM products WHERE id=? AND active=1',(key,)).fetchone()
            if product:
                subtotal+=product['price']*quantity
        old=session.get('coupon');session['coupon']=code
        try:
            coupon_for_checkout(db(),subtotal);flash('Promotion applied.','success')
        except ValueError as error:
            if old:
                session['coupon']=old
            else:
                session.pop('coupon',None)
            flash(str(error),'error')
        return redirect(url_for('cart'))

    @bp.route('/owner/promotions',methods=['GET','POST'])
    @admin_only
    def owner_promotions():
        if request.method=='POST':
            try:
                code=request.form.get('code','').strip().upper();kind=request.form.get('kind','');value=gateway.cents(request.form.get('value',''));minimum=gateway.cents(request.form.get('minimum','0'));uses=int(request.form.get('max_uses','100'));expires=request.form.get('expires','').strip()
                if not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{2,23}',code) or kind not in ('fixed','percent') or value<=0 or (kind=='percent' and value>10000) or not 1<=uses<=100000:
                    raise ValueError('Check the code, discount amount/percentage and usage limit.')
                if expires:
                    datetime.strptime(expires,'%Y-%m-%d')
                db().execute('INSERT INTO coupons(code,kind,value,minimum,max_uses,expires,active) VALUES(?,?,?,?,?,?,?)',(code,kind,value,minimum,uses,expires,1 if request.form.get('active') else 0));db().commit();flash('Promotion created.','success')
                return redirect(url_for('eco.owner_promotions'))
            except (ValueError,sqlite3.IntegrityError) as error:
                db().rollback();flash(str(error) if isinstance(error,ValueError) else 'That code already exists.','error')
        coupons=db().execute("SELECT c.*,(SELECT COUNT(*) FROM order_coupons r JOIN orders o ON o.id=r.order_id WHERE r.coupon_id=c.id AND o.status!='Cancelled') AS uses FROM coupons c ORDER BY c.id DESC").fetchall()
        return render_template('owner_promotions.html',coupons=coupons,title='Promotions')

    @bp.post('/owner/promotions/<int:coupon_id>')
    @admin_only
    def owner_promotion_toggle(coupon_id):
        db().execute('UPDATE coupons SET active=? WHERE id=?',(1 if request.form.get('active') else 0,coupon_id));db().commit()
        return redirect(url_for('eco.owner_promotions'))

    def product_context(product_id):
        details=db().execute('SELECT * FROM product_details WHERE product_id=?',(product_id,)).fetchone()
        gallery=db().execute('SELECT * FROM product_gallery WHERE product_id=? ORDER BY id',(product_id,)).fetchall()
        reviews=db().execute('SELECT r.rating,r.comment,r.created_at,c.name FROM product_reviews r JOIN customers c ON c.id=r.customer_id WHERE r.product_id=? AND r.status=\'Published\' ORDER BY r.id DESC',(product_id,)).fetchall()
        customer=current_customer()
        saved=bool(customer and db().execute('SELECT 1 FROM saved_products WHERE customer_id=? AND product_id=?',(customer['id'],product_id)).fetchone())
        return dict(details=details or dict(benefits='',ingredients='',directions=''),gallery=gallery,reviews=reviews,rating=(sum(r['rating'] for r in reviews)/len(reviews)) if reviews else None,is_saved=saved)

    @bp.post('/product/<int:product_id>/review')
    @customer_only
    def product_review(customer,product_id):
        eligible=db().execute("SELECT 1 FROM orders o JOIN order_extra e ON e.order_id=o.id JOIN order_items i ON i.order_id=o.id WHERE e.customer_id=? AND e.payment_test=0 AND i.product_id=? AND o.status IN ('Paid','Ready','Completed') AND EXISTS(SELECT 1 FROM payments_received p WHERE p.order_id=o.id)",(customer['id'],product_id)).fetchone()
        try:
            rating=int(request.form.get('rating','0'));comment=request.form.get('comment','').strip()
            if not eligible or not 1<=rating<=5 or not 10<=len(comment)<=2000:
                raise ValueError('Reviews require a recorded purchase, a rating of 1–5 and 10–2,000 characters.')
            db().execute("INSERT INTO product_reviews(product_id,customer_id,rating,comment) VALUES(?,?,?,?) ON CONFLICT(product_id,customer_id) DO UPDATE SET rating=excluded.rating,comment=excluded.comment,status='Pending'",(product_id,customer['id'],rating,comment));db().commit();flash('Review submitted for moderation.','success')
        except ValueError as error:
            flash(str(error),'error')
        return redirect(url_for('product',product_id=product_id)+'#reviews')

    @bp.route('/owner/reviews',methods=['GET','POST'])
    @admin_only
    def owner_reviews():
        if request.method=='POST':
            status=request.form.get('status','')
            if status not in ('Pending','Published','Hidden'):
                abort(400)
            db().execute('UPDATE product_reviews SET status=? WHERE id=?',(status,request.form.get('review_id')));db().commit();flash('Review moderation saved.','success')
        reviews=db().execute('SELECT r.*,c.name,p.name AS product_name FROM product_reviews r JOIN customers c ON c.id=r.customer_id JOIN products p ON p.id=r.product_id ORDER BY r.id DESC LIMIT 200').fetchall()
        return render_template('owner_reviews.html',reviews=reviews,title='Product reviews')

    @bp.post('/owner/product/<int:product_id>/details')
    @admin_only
    def owner_product_details(product_id):
        if not db().execute('SELECT 1 FROM products WHERE id=?',(product_id,)).fetchone():
            abort(404)
        fields=[request.form.get(key,'').strip() for key in ('benefits','ingredients','directions')]
        if any(len(value)>5000 for value in fields):
            abort(400,'Each product detail field must be under 5,000 characters.')
        db().execute('INSERT INTO product_details(product_id,benefits,ingredients,directions) VALUES(?,?,?,?) ON CONFLICT(product_id) DO UPDATE SET benefits=excluded.benefits,ingredients=excluded.ingredients,directions=excluded.directions',(product_id,*fields));db().commit();flash('Product information saved.','success')
        return redirect(url_for('owner_product',product_id=product_id))

    @bp.post('/owner/product/<int:product_id>/gallery')
    @admin_only
    def owner_product_gallery(product_id):
        if not db().execute('SELECT 1 FROM products WHERE id=?',(product_id,)).fetchone():
            abort(404)
        from pathlib import Path
        from PIL import Image, UnidentifiedImageError
        uploads=request.files.getlist('images')
        existing=db().execute('SELECT COUNT(*) FROM product_gallery WHERE product_id=?',(product_id,)).fetchone()[0]
        paths=[]
        try:
            if not uploads or len(uploads)+existing>4:
                raise ValueError('Choose up to four supplementary product photographs in total.')
            for upload in uploads:
                if not upload.filename:
                    raise ValueError('Choose an image first.')
                upload.stream.seek(0,2)
                if upload.stream.tell()>10*1024*1024:
                    raise ValueError('Each photograph must be under 10 MB.')
                upload.stream.seek(0)
                with Image.open(upload.stream) as image:
                    if image.width*image.height>20000000:
                        raise ValueError('Use photographs under 20 megapixels.')
                    image=image.convert('RGB');image.thumbnail((2400,2400));name='upload-gallery-'+secrets.token_hex(16)+'.webp';path=Path(current_app.config['UPLOAD_DIR'])/name;paths.append(path);image.save(path,'WEBP',quality=92)
                db().execute('INSERT INTO product_gallery(product_id,filename) VALUES(?,?)',(product_id,name))
            db().commit();flash('Gallery photographs saved.','success')
        except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError) as error:
            db().rollback()
            for path in paths:
                path.unlink(missing_ok=True)
            flash(str(error) if isinstance(error,ValueError) else 'Upload valid JPG, PNG or WebP photographs.','error')
        return redirect(url_for('owner_product',product_id=product_id))

    @bp.post('/owner/product/<int:product_id>/gallery/<int:image_id>/remove')
    @admin_only
    def owner_gallery_remove(product_id,image_id):
        db().execute('DELETE FROM product_gallery WHERE id=? AND product_id=?',(image_id,product_id));db().commit()
        return redirect(url_for('owner_product',product_id=product_id))

    @bp.get('/r/<code>')
    def referral(code):
        agent = resolve_agent(code)
        if not agent:
            abort(404)
        session['referral'],session['referral_at'] = agent['code'],time.time()
        return redirect(url_for('shop'))

    @bp.route('/track',methods=['GET','POST'])
    def track():
        if request.method == 'POST':
            key='track:'+(request.remote_addr or 'unknown')
            if throttled(key):
                return render_template('track.html',title='Track your order',limited=True),429
            ref=request.form.get('reference','').strip().upper()
            match=re.fullmatch(r'(?:ISZ-)?(\d{1,10})',ref)
            order=db().execute('SELECT * FROM orders WHERE id=? AND lower(email)=lower(?)',(int(match.group(1)),request.form.get('email','').strip())).fetchone() if match else None
            last4=re.sub(r'\D','',request.form.get('phone_last4',''))
            if order and len(last4)==4 and re.sub(r'\D','',order['phone']).endswith(last4):
                db().execute('DELETE FROM login_attempts WHERE ip=?',(key,));db().commit()
                return redirect(url_for('confirmation',token=order['token']))
            failure(key)
            flash('We could not match those details. Check the reference, email and last four phone digits.','error')
        return render_template('track.html',title='Track your order',limited=False)

    @bp.route('/agent/login',methods=['GET','POST'])
    def agent_login():
        if request.method == 'POST':
            key='agent:'+(request.remote_addr or 'unknown')
            if throttled(key):
                flash('Too many attempts. Please wait 15 minutes.','error')
                return render_template('agent_login.html',title='Agent sign in'),429
            agent=db().execute('SELECT * FROM agents WHERE code=?',(request.form.get('code','').strip().upper(),)).fetchone()
            if agent and agent['approved'] and agent['password_hash'] and check_password_hash(agent['password_hash'],request.form.get('password','')):
                session.clear();session['agent_id']=agent['id'];session['agent_version']=agent['auth_version'];session.permanent=True
                db().execute('DELETE FROM login_attempts WHERE ip=?',(key,));db().commit()
                return redirect(url_for('eco.agent_portal'))
            failure(key);flash('Unable to sign in. Check your credentials and approval status.','error')
        return render_template('agent_login.html',title='Agent sign in')

    @bp.route('/agent/activate/<token>',methods=['GET','POST'])
    def agent_activate(token):
        agent=db().execute('SELECT * FROM agents WHERE invite_hash=? AND invite_expires>?',(hashlib.sha256(token.encode()).hexdigest(),time.time())).fetchone()
        if not agent:
            abort(404)
        if request.method=='POST':
            password=request.form.get('password','')
            if not 16<=len(password)<=256 or password!=request.form.get('confirm',''):
                flash('Use at least 16 characters and matching passwords.','error')
            else:
                # Single-use token update protects against simultaneous activation requests.
                updated=db().execute('UPDATE agents SET password_hash=?,invite_hash=NULL,invite_expires=NULL,auth_version=auth_version+1 WHERE id=? AND invite_hash=? AND invite_expires>?',(generate_password_hash(password),agent['id'],hashlib.sha256(token.encode()).hexdigest(),time.time()))
                if updated.rowcount!=1:
                    db().rollback();abort(400,'Invitation already used or expired.')
                audit(db(),'Agent activated',agent['id'],actor='agent:'+str(agent['id']));db().commit()
                session.clear();flash('Password saved. Sign in with your approved agent code.','success')
                return redirect(url_for('eco.agent_login'))
        return render_template('agent_activate.html',agent=agent,title='Activate agent access')

    @bp.post('/agent/logout')
    def agent_logout():
        session.clear();return redirect(url_for('eco.agent_login'))

    @bp.get('/agent')
    @agent_only
    def agent_portal(agent):
        # No customer contact details or receipt tokens are exposed to agents.
        sales=db().execute('SELECT o.id,o.created_at,o.subtotal,e.discount,o.status,COALESCE(c.target,0) AS commission FROM orders o JOIN order_extra e ON e.order_id=o.id LEFT JOIN commission_snapshots c ON c.order_id=o.id WHERE e.agent_id=? ORDER BY o.id DESC LIMIT 200',(agent['id'],)).fetchall()
        ledger=db().execute('SELECT * FROM commission_ledger WHERE agent_id=? ORDER BY id DESC LIMIT 200',(agent['id'],)).fetchall()
        totals=db().execute("SELECT COALESCE(SUM(CASE WHEN kind!='Payout' THEN amount ELSE 0 END),0) AS earned, COALESCE(-SUM(CASE WHEN kind='Payout' THEN amount ELSE 0 END),0) AS paid, COALESCE(SUM(amount),0) AS balance FROM commission_ledger WHERE agent_id=?",(agent['id'],)).fetchone()
        link=(public_base() or request.host_url.rstrip('/'))+url_for('eco.referral',code=agent['code'])
        return render_template('agent_portal.html',agent=agent,sales=sales,ledger=ledger,totals=totals,link=link,title='Agent portal')

    @bp.route('/owner/agents',methods=['GET','POST'])
    @admin_only
    def owner_agents():
        if request.method=='POST':
            try:
                name=request.form.get('name','').strip();email=request.form.get('email','').strip();code=request.form.get('code','').strip().upper()
                rate=gateway.cents(request.form.get('rate',''))
                if not 2<=len(name)<=120 or len(email)>200 or not valid_email(email) or not re.fullmatch(r'[A-Z0-9][A-Z0-9_-]{2,23}',code) or not 0<=rate<=10000:
                    raise ValueError('Enter a name, valid email, unique 3–24 character code and commission between 0% and 100%.')
                token=secrets.token_urlsafe(32)
                agent_id=db().execute('INSERT INTO agents(name,email,code,rate_bps,approved,invite_hash,invite_expires) VALUES(?,?,?,?,?,?,?)',(name,email,code,rate,1 if request.form.get('approved') else 0,hashlib.sha256(token.encode()).hexdigest(),time.time()+86400)).lastrowid
                audit(db(),'Agent created',agent_id);db().commit()
                invite=(public_base() or request.host_url.rstrip('/'))+url_for('eco.agent_activate',token=token)
                return render_template('agent_invite.html',invite=invite,code=code,title='Agent invitation')
            except (ValueError,sqlite3.IntegrityError) as error:
                db().rollback();flash(str(error) if isinstance(error,ValueError) else 'That agent code is already in use.','error')
        agents=db().execute('SELECT a.*,COALESCE((SELECT SUM(l.amount) FROM commission_ledger l WHERE l.agent_id=a.id),0) AS balance FROM agents a ORDER BY a.id DESC').fetchall()
        return render_template('owner_agents.html',agents=agents,title='Sales agents')

    @bp.post('/owner/agents/<int:agent_id>')
    @admin_only
    def owner_agent_update(agent_id):
        if not db().execute('SELECT 1 FROM agents WHERE id=?',(agent_id,)).fetchone():
            abort(404)
        try:
            rate=gateway.cents(request.form.get('rate',''))
            if rate>10000:
                raise ValueError('Commission must be between 0% and 100%.')
            db().execute('UPDATE agents SET approved=?,rate_bps=? WHERE id=?',(1 if request.form.get('approved') else 0,rate,agent_id))
            audit(db(),'Agent updated',agent_id);db().commit();flash('Agent updated. The rate applies to new orders only.','success')
        except ValueError as error:
            flash(str(error),'error')
        return redirect(url_for('eco.owner_agents'))

    @bp.post('/owner/agents/<int:agent_id>/invite')
    @admin_only
    def owner_agent_invite(agent_id):
        agent=db().execute('SELECT * FROM agents WHERE id=?',(agent_id,)).fetchone()
        if not agent:
            abort(404)
        token=secrets.token_urlsafe(32)
        db().execute('UPDATE agents SET invite_hash=?,invite_expires=? WHERE id=?',(hashlib.sha256(token.encode()).hexdigest(),time.time()+86400,agent_id));db().commit()
        invite=(public_base() or request.host_url.rstrip('/'))+url_for('eco.agent_activate',token=token)
        return render_template('agent_invite.html',invite=invite,code=agent['code'],title='Agent invitation')

    @bp.route('/owner/commissions',methods=['GET','POST'])
    @admin_only
    def owner_commissions():
        if request.method=='POST':
            connection=db()
            try:
                agent_id=int(request.form.get('agent_id','0'));amount=gateway.cents(request.form.get('amount',''));reference=request.form.get('reference','').strip()
                if amount<=0 or not 3<=len(reference)<=180:
                    raise ValueError('Enter a positive payout amount and the external payment reference.')
                connection.execute('BEGIN IMMEDIATE')
                balance=connection.execute('SELECT COALESCE(SUM(amount),0) FROM commission_ledger WHERE agent_id=?',(agent_id,)).fetchone()[0]
                if amount>balance:
                    raise ValueError('Payout exceeds the available commission balance.')
                event_key=request.form.get('event_key','')
                if not secrets.compare_digest(event_key,session.get('payout_key','')):
                    raise ValueError('This payout form expired. Reload and try again.')
                connection.execute('INSERT INTO commission_ledger(agent_id,amount,kind,reference,event_key) VALUES(?,?,?,?,?)',(agent_id,-amount,'Payout',reference,'payout:'+event_key))
                audit(connection,'Commission payout recorded',agent_id,reference);connection.commit();session.pop('payout_key',None);flash('Completed payout recorded. This app did not transfer money.','success')
                return redirect(url_for('eco.owner_commissions'))
            except (ValueError,sqlite3.IntegrityError) as error:
                connection.rollback();flash(str(error) if isinstance(error,ValueError) else 'This payout was already recorded.','error')
        session.setdefault('payout_key',secrets.token_hex(24))
        agents=db().execute("SELECT a.id,a.name,a.code,COALESCE(SUM(l.amount),0) AS balance FROM agents a LEFT JOIN commission_ledger l ON a.id=l.agent_id GROUP BY a.id ORDER BY a.name").fetchall()
        ledger=db().execute('SELECT l.*,a.code FROM commission_ledger l JOIN agents a ON a.id=l.agent_id ORDER BY l.id DESC LIMIT 300').fetchall()
        return render_template('owner_commissions.html',agents=agents,ledger=ledger,title='Commission ledger')

    @bp.route('/owner/customers',methods=['GET','POST'])
    @admin_only
    def owner_customers():
        if request.method=='POST':
            email=request.form.get('email','').strip().lower();notes=request.form.get('notes','').strip()
            if len(notes)>2000 or not db().execute('SELECT 1 FROM orders WHERE lower(email)=?',(email,)).fetchone():
                abort(400)
            db().execute('INSERT INTO customer_notes(email,notes) VALUES(?,?) ON CONFLICT(email) DO UPDATE SET notes=excluded.notes',(email,notes));audit(db(),'Customer note updated','customer');db().commit();flash('Customer note saved.','success')
        query=request.args.get('q','').strip()[:100]
        customers=db().execute('SELECT lower(o.email) AS email,MAX(o.name) AS name,MAX(o.phone) AS phone,COUNT(*) AS orders,MAX(o.created_at) AS last_order,COALESCE(n.notes,\'\') AS notes FROM orders o LEFT JOIN customer_notes n ON n.email=lower(o.email) WHERE o.email LIKE ? OR o.name LIKE ? GROUP BY lower(o.email) ORDER BY last_order DESC LIMIT 200',('%'+query+'%','%'+query+'%')).fetchall()
        return render_template('owner_customers.html',customers=customers,accounts=db().execute('SELECT id,name,email,phone,created_at FROM customers ORDER BY id DESC LIMIT 200').fetchall(),query=query,title='Customers')

    @bp.get('/owner/reports')
    @admin_only
    def owner_reports():
        start=request.args.get('start','');end=request.args.get('end','')
        for value in (start,end):
            if value:
                try:
                    datetime.strptime(value,'%Y-%m-%d')
                except ValueError:
                    abort(400,'Use YYYY-MM-DD dates.')
        if start and end and start>end:
            abort(400,'Start date must precede end date.')
        scope=request.args.get('scope','real')
        if scope not in ('real','test'):
            abort(400,'Choose real or test orders.')
        params=(1 if scope=='test' else 0,start,start,end,end)
        orders=db().execute("SELECT o.*,COALESCE((SELECT SUM(p.amount) FROM payments_received p WHERE p.order_id=o.id),0) AS received,COALESCE((SELECT SUM(r.goods+r.shipping+r.extra) FROM refunds r WHERE r.order_id=o.id),0) AS refunded FROM orders o WHERE o.id IN (SELECT order_id FROM order_extra WHERE payment_test=?) AND (?='' OR date(o.created_at)>=?) AND (?='' OR date(o.created_at)<=?) ORDER BY o.id DESC",params).fetchall()
        stats=dict(orders=len(orders),received=sum(o['received'] for o in orders),refunded=sum(o['refunded'] for o in orders),pending=sum(o['status']=='Awaiting confirmation' for o in orders))
        stats['net']=stats['received']-stats['refunded']
        monthly={}
        for order in orders:
            month=order['created_at'][:7];monthly[month]=monthly.get(month,0)+order['received']-order['refunded']
        stock_column='presentation_stock' if scope=='test' else 'stock'
        stock=db().execute(f'SELECT * FROM products WHERE active=1 AND {stock_column}<=5 ORDER BY {stock_column},name').fetchall()
        if scope=='test':
            stock=[dict(p,stock=p['presentation_stock']) for p in map(dict,stock)]
        statuses={}
        for order in orders:
            statuses[order['status']]=statuses.get(order['status'],0)+1
        if request.args.get('format')=='csv':
            output=io.StringIO(newline='');writer=csv.writer(output);writer.writerow(['Order','Created UTC','Status','Order ZAR','Received ZAR','Refunded ZAR','Net ZAR'])
            for o in orders:
                writer.writerow([f"ISZ-{o['id']:05d}",o['created_at'],o['status'],f"{o['total']/100:.2f}",f"{o['received']/100:.2f}",f"{o['refunded']/100:.2f}",f"{(o['received']-o['refunded'])/100:.2f}"])
            return Response(output.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=isazi-financial-report.csv'})
        return render_template('owner_reports.html',stats=stats,monthly=sorted(monthly.items()),statuses=statuses,stock=stock,start=start,end=end,scope=scope,title='Store reports')

    @bp.post('/owner/order/<int:order_id>/delivery')
    @admin_only
    def owner_delivery(order_id):
        if not extra_for(db(),order_id):
            abort(404)
        status=request.form.get('delivery_status','');courier=request.form.get('courier','').strip();reference=request.form.get('tracking_reference','').strip();link=request.form.get('tracking_url','').strip()
        try: parsed=urlsplit(link)
        except ValueError: abort(400, 'Use a valid HTTPS tracking URL.')
        if status not in DELIVERY_STATUSES or len(courier)>100 or len(reference)>180 or len(link)>1000 or (link and (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password)):
            flash('Choose a valid delivery status and use a valid HTTPS tracking URL.','error')
        else:
            db().execute('BEGIN IMMEDIATE')
            try:
                app.extensions['simple_checkout']['delivery_guard'](db(),order_id,status,reference)
            except ValueError as error:
                db().rollback()
                flash(str(error),'error')
                return redirect(url_for('owner_order',order_id=order_id))
            db().execute('UPDATE order_extra SET delivery_status=?,courier=?,tracking_reference=?,tracking_url=?,updated_at=datetime(\'now\') WHERE order_id=?',(status,courier,reference,link,order_id))
            queue_update(db(),order_id,'delivery:'+secrets.token_hex(16),'Delivery update: '+status+(('. Tracking reference: '+reference) if reference else ''))
            app.extensions['simple_checkout']['dispatch_sms'](db(),order_id,status,reference)
            audit(db(),'Delivery updated',order_id,status);db().commit();flash('Delivery details saved. Review the order message outbox for customer updates.','success')
        return redirect(url_for('owner_order',order_id=order_id))

    @bp.post('/owner/order/<int:order_id>/refund')
    @admin_only
    def owner_refund(order_id):
        connection=db()
        if not extra_for(connection,order_id):
            abort(404)
        try:
            goods=gateway.cents(request.form.get('goods','0'));shipping=gateway.cents(request.form.get('shipping','0'));extra=gateway.cents(request.form.get('extra','0'))
            reference=request.form.get('reference','').strip();reason=request.form.get('reason','').strip();key=request.form.get('refund_key','')
            if not 3<=len(reference)<=180 or not 3<=len(reason)<=500 or goods+shipping+extra<=0:
                raise ValueError('Enter refund amounts, the completed external refund reference and a reason.')
            if not secrets.compare_digest(key,session.get('refund_key_'+str(order_id),'')):
                raise ValueError('This refund form expired. Reload the order and try again.')
            connection.execute('BEGIN IMMEDIATE')
            order=connection.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone();info=financials(connection,order_id)
            if goods>order['subtotal']-extra_for(connection,order_id)['discount']-info['goods_refunded'] or shipping>order['shipping']-info['shipping_refunded'] or extra>info['overpaid']-info['extra_refunded'] or goods+shipping+extra>info['net']:
                raise ValueError('Refund exceeds recorded receipts or the remaining refundable amount.')
            connection.execute('INSERT INTO refunds(order_id,event_key,goods,shipping,extra,reference,reason) VALUES(?,?,?,?,?,?,?)',(order_id,'refund:'+key,goods,shipping,extra,reference,reason))
            sync_commission(connection,order_id);queue_update(connection,order_id,'refund:'+key,'A completed refund has been recorded by our team.');audit(connection,'Refund recorded',order_id,reference)
            connection.commit();session.pop('refund_key_'+str(order_id),None);flash('Completed refund recorded. No money was transferred by this action.','success')
        except (ValueError,sqlite3.IntegrityError) as error:
            connection.rollback();flash(str(error) if isinstance(error,ValueError) else 'This refund was already recorded.','error')
        return redirect(url_for('owner_order',order_id=order_id))

    @bp.get('/owner/notifications')
    @admin_only
    def owner_notifications():
        rows=db().execute('SELECT n.*,o.phone,o.status AS order_status FROM notifications n JOIN orders o ON o.id=n.order_id ORDER BY n.id DESC LIMIT 200').fetchall()
        return render_template('owner_notifications.html',notifications=rows,title='Order notifications')

    @bp.post('/owner/notifications/<int:notification_id>/send')
    @admin_only
    def owner_notification_send(notification_id):
        row=db().execute('SELECT * FROM notifications WHERE id=?',(notification_id,)).fetchone()
        if not row:
            abort(404)
        if not valid_email(row['recipient']):
            flash('This stored recipient address is not a valid single email address. Reconcile it before sending.', 'error')
            return redirect(url_for('eco.owner_notifications'))
        if not smtp_ready():
            flash('Configure the public HTTPS address and SMTP settings before sending email.','error')
            return redirect(url_for('eco.owner_notifications'))
        connection=db();connection.execute('BEGIN IMMEDIATE')
        changed=connection.execute("UPDATE notifications SET status='Sending' WHERE id=? AND status IN ('Queued','Failed')",(notification_id,))
        if changed.rowcount!=1:
            connection.rollback();flash('This message was already sent or is being processed.','error')
            return redirect(url_for('eco.owner_notifications'))
        connection.commit()
        message=EmailMessage();message['From']=option('SMTP_FROM');message['To']=row['recipient'];message['Subject']=row['subject'];message['Message-ID']=f"<isazi-update-{notification_id}@{option('SMTP_FROM').split('@')[-1]}>";message.set_content(row['body'])
        try:
            context=ssl.create_default_context();host=option('SMTP_HOST');port=int(option('SMTP_PORT','465' if option('SMTP_SECURITY','starttls')=='ssl' else '587'))
            client=smtplib.SMTP_SSL(host,port,timeout=12,context=context) if option('SMTP_SECURITY','starttls')=='ssl' else smtplib.SMTP(host,port,timeout=12)
            with client:
                if option('SMTP_SECURITY','starttls')!='ssl':
                    client.ehlo();client.starttls(context=context);client.ehlo()
                if option('SMTP_USER'):
                    client.login(option('SMTP_USER'),option('SMTP_PASSWORD'))
                client.send_message(message)
            connection.execute("UPDATE notifications SET status='Sent',sent_at=datetime('now'),last_error='' WHERE id=?",(notification_id,));audit(connection,'Order email sent',row['order_id']);connection.commit();flash('Email sent.','success')
        except (OSError,smtplib.SMTPException,ValueError):
            connection.execute("UPDATE notifications SET status='Failed',last_error='Delivery failed or was not confirmed. Check the mailbox/provider before retrying.' WHERE id=?",(notification_id,));connection.commit();flash('Email delivery was not confirmed. Check the provider before retrying.','error')
        return redirect(url_for('eco.owner_notifications'))

    @app.template_filter('whatsapp_phone')
    def whatsapp_phone(raw):
        number=re.sub(r'\D','',raw)
        return '27'+number[1:] if len(number)==10 and number.startswith('0') else number

    @app.template_filter('urlquote')
    def urlquote(raw):
        return quote(str(raw),safe='')

    @bp.get('/owner/integrations')
    @admin_only
    def owner_integrations():
        audit_rows=db().execute('SELECT * FROM audit_events ORDER BY id DESC LIMIT 100').fetchall()
        return render_template('owner_integrations.html',public_address=public_base(),audit_rows=audit_rows,title='Connected services')

    @bp.post('/pay/<token>')
    def pay(token):
        order=db().execute('SELECT * FROM orders WHERE token=?',(token,)).fetchone()
        if not order:
            abort(404)
        if order['fulfillment']=='pep':
            abort(409,'PEP transfer orders require owner confirmation.')
        if extra_for(db(),order['id'])['payment_test']:
            abort(409,'Test orders cannot be sent to a live payment provider.')
        config=payfast_config()
        if not config['ready']:
            flash('Online payment is not available yet. Contact our team to arrange payment.','error')
            return redirect(url_for('confirmation',token=token))
        if order['status']!='Awaiting confirmation' or financials(db(),order['id'])['received']>0 or order['total']<500:
            flash('This order is not eligible for another online payment. Contact the team if you need help.','error')
            return redirect(url_for('confirmation',token=token))
        connection=db();connection.execute('BEGIN IMMEDIATE')
        attempt=connection.execute('SELECT * FROM payment_attempts WHERE order_id=?',(order['id'],)).fetchone()
        if not attempt:
            payment_id=secrets.token_hex(24)
            connection.execute('INSERT INTO payment_attempts(id,order_id,amount) VALUES(?,?,?)',(payment_id,order['id'],order['total']))
        else:
            payment_id=attempt['id']
        connection.commit()
        names=order['name'].split(' ',1)
        fields={'merchant_id':str(option('PAYFAST_MERCHANT_ID')),'merchant_key':str(option('PAYFAST_MERCHANT_KEY')),'return_url':public_base()+url_for('confirmation',token=token)+'?payment=return','cancel_url':public_base()+url_for('confirmation',token=token)+'?payment=cancel','notify_url':public_base()+url_for('eco.payfast_itn'),'name_first':names[0][:100],'name_last':(names[1] if len(names)>1 else '')[:100],'email_address':order['email'][:100],'m_payment_id':payment_id,'amount':f"{order['total']/100:.2f}",'item_name':f"Isazi order ISZ-{order['id']:05d}"}
        if order['email'].endswith('@phone.invalid'):
            fields.pop('email_address',None)
        fields['signature']=gateway.signature(list(fields.items()),str(option('PAYFAST_PASSPHRASE')),outgoing=True)
        return render_template('payfast.html',order=order,fields=fields,host=config['host'],title='Secure payment')

    @bp.post('/payments/payfast/itn')
    def payfast_itn():
        config=payfast_config()
        if not config['ready']:
            abort(503)
        if request.content_length and request.content_length>65536:
            abort(400)
        pairs=list(request.form.items(multi=True))
        if not pairs or len(pairs)>80 or len({k for k,v in pairs})!=len(pairs) or any(len(k)>100 or len(v)>10000 for k,v in pairs):
            abort(400)
        data=dict(pairs)
        if not gateway.valid_signature(pairs,data.get('signature',''),str(option('PAYFAST_PASSPHRASE'))) or data.get('merchant_id')!=str(option('PAYFAST_MERCHANT_ID')):
            abort(400)
        networks=str(option('PAYFAST_ALLOWED_IPS',','.join(gateway.PAYFAST_NETWORKS))).split(',')
        proxies=str(option('TRUSTED_PROXY_CIDRS','')).split(',')
        ip=gateway.source_ip(request,proxies)
        if not gateway.network_contains(ip,networks):
            abort(400)
        attempt=db().execute('SELECT * FROM payment_attempts WHERE id=?',(data.get('m_payment_id',''),)).fetchone()
        try:
            amount=gateway.cents(data.get('amount_gross',''))
        except ValueError:
            abort(400)
        if not attempt or amount!=attempt['amount']:
            abort(400)
        if extra_for(db(),attempt['order_id'])['payment_test']:
            abort(409,'Test orders cannot receive a provider payment.')
        validator=current_app.config.get('PAYFAST_TEST_VALIDATOR') if current_app.testing else None
        valid=validator(gateway.parameter_string(pairs),config['mode']) if validator else gateway.server_validates(gateway.parameter_string(pairs),config['mode'])
        if not valid:
            abort(503)
        reference=data.get('pf_payment_id','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',reference):
            abort(400)
        connection=db();connection.execute('BEGIN IMMEDIATE')
        previous=connection.execute('SELECT * FROM payment_attempts WHERE id=?',(attempt['id'],)).fetchone()
        if previous['status']=='Paid':
            connection.rollback()
            if previous['provider_reference']!=reference:
                abort(409)
            return 'OK',200
        if data.get('payment_status')=='COMPLETE':
            try:
                connection.execute("UPDATE payment_attempts SET status='Paid',provider_reference=? WHERE id=?",(reference,attempt['id']))
                connection.execute('INSERT INTO payments_received(order_id,event_key,amount,method,reference) VALUES(?,?,?,?,?)',(attempt['order_id'],'payfast:'+reference,amount,'PayFast '+config['mode'],reference))
            except sqlite3.IntegrityError:
                connection.rollback();abort(409)
            order=connection.execute('SELECT * FROM orders WHERE id=?',(attempt['order_id'],)).fetchone()
            if order['status']=='Awaiting confirmation':
                connection.execute("UPDATE orders SET status='Paid' WHERE id=?",(order['id'],))
            sync_commission(connection,order['id'])
            queue_update(connection,order['id'],'payment:'+reference,'Payment was confirmed by the payment provider.' if order['status']!='Cancelled' else 'A late payment was received after cancellation. Please contact our team for review.')
            audit(connection,'Verified PayFast payment',order['id'],'Late payment after cancellation' if order['status']=='Cancelled' else reference,actor='payfast')
        else:
            connection.execute('UPDATE payment_attempts SET status=? WHERE id=?',(data.get('payment_status','Pending')[:40],attempt['id']))
        connection.commit()
        return 'OK',200

    def order_context(order_id):
        if session.get('admin'):
            key='refund_key_'+str(order_id)
            for old in list(session):
                if old.startswith('refund_key_') and old!=key:
                    session.pop(old,None)
            session.setdefault(key,secrets.token_hex(24))
        return dict(**app.extensions['simple_checkout']['order_info'](order_id),finance=financials(db(),order_id),delivery=extra_for(db(),order_id),delivery_statuses=DELIVERY_STATUSES,refunds=db().execute('SELECT * FROM refunds WHERE order_id=? ORDER BY id DESC',(order_id,)).fetchall(),receipts=db().execute('SELECT * FROM payments_received WHERE order_id=? ORDER BY id DESC',(order_id,)).fetchall())

    def checkout_addresses():
        customer=current_customer()
        return db().execute('SELECT * FROM customer_addresses WHERE customer_id=? ORDER BY id DESC',(customer['id'],)).fetchall() if customer else []

    app.register_blueprint(bp)
    return dict(initialize=initialize,capture_order=capture_order,order_changed=order_changed,resolve_agent=resolve_agent,current_referral=current_referral,order_context=order_context,cart_promotion=cart_promotion,coupon_for_checkout=coupon_for_checkout,product_context=product_context,current_customer=current_customer,checkout_addresses=checkout_addresses)
