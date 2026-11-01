"""Cellphone accounts, verified PAXI directory, manual EFT and SMS outbox.
Live configured order events send SMS after commit; test events never send SMS.
"""
import base64
import hashlib
import io
import os
import json
import re
import secrets
import sqlite3
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for, send_file, g
from werkzeug.security import generate_password_hash, check_password_hash


def normalize_phone(value):
    value=re.sub(r'[ ()-]', '', value.strip())
    if value.startswith('+27'): value='0'+value[3:]
    elif value.startswith('27') and len(value)==11: value='0'+value[2:]
    return value if re.fullmatch(r'0[6-8][0-9]{8}',value) else ''


def register_simple(app, db, admin_only, eco):
    bp=Blueprint('simple',__name__)
    directory=json.loads((Path(__file__).parent/'data/paxi_branches.json').read_text())
    branches={row['code']:row for row in directory['branches']}

    def initialize():
        if 'is_bundle' not in {row[1] for row in db().execute('PRAGMA table_info(products)')}:
            db().execute('ALTER TABLE products ADD COLUMN is_bundle INTEGER NOT NULL DEFAULT 0')
            db().execute("UPDATE products SET is_bundle=1 WHERE name='Herbal Combo Pack'")
            db().commit()
        db().executescript('''
        CREATE TABLE IF NOT EXISTS checkout_payment_choice (
          order_id INTEGER PRIMARY KEY REFERENCES orders(id), method TEXT NOT NULL CHECK(method IN ('card','paystack','ozow','pep')));
        CREATE TABLE IF NOT EXISTS phone_accounts (
          customer_id INTEGER PRIMARY KEY REFERENCES customers(id), phone TEXT NOT NULL UNIQUE,
          pin_hash TEXT NOT NULL, preference TEXT NOT NULL DEFAULT 'pep', branch_code TEXT NOT NULL DEFAULT '',
          failures INTEGER NOT NULL DEFAULT 0, locked_until REAL NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS simple_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pep_orders (
          order_id INTEGER PRIMARY KEY REFERENCES orders(id), branch_code TEXT NOT NULL, branch_name TEXT NOT NULL,
          branch_address TEXT NOT NULL, payment_reference TEXT NOT NULL, bank_snapshot TEXT NOT NULL DEFAULT '',
          confirmed_at TEXT, confirmed_reference TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS sms_outbox (
          id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), event_key TEXT UNIQUE NOT NULL,
          recipient TEXT NOT NULL, body TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Queued',
          provider_id TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL DEFAULT (datetime('now')));
        ''')
        db().commit()

    def config():
        return dict(db().execute('SELECT key,value FROM simple_settings').fetchall())

    def public_config():
        values=config()
        result={key:values.get(key,'') for key in ('capitec_holder','capitec_number','capitec_type','capitec_branch')}
        result['pep_fee']='5995'
        return result

    def account(customer=None):
        customer=customer or eco['current_customer']()
        return db().execute('SELECT * FROM phone_accounts WHERE customer_id=?',(customer['id'],)).fetchone() if customer else None

    def qr_base():
        raw=str(app.config.get('PUBLIC_BASE_URL') or os.environ.get('PUBLIC_BASE_URL') or config().get('shop_url','')).rstrip('/')
        try: parsed=urlsplit(raw)
        except ValueError: return ''
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/'):
            return ''
        return raw

    @bp.get('/product/<int:product_id>/qr.png')
    def product_qr(product_id):
        product=db().execute('SELECT id FROM products WHERE id=? AND active=1 AND is_bundle=1',(product_id,)).fetchone()
        if not product: abort(404)
        base=qr_base()
        if not base: abort(503,'Set the public shop URL in owner Cellphone checkout settings before printing QR codes.')
        import qrcode
        qr=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,box_size=10,border=4)
        qr.add_data(base+url_for('quick_buy',product_id=product_id));qr.make(fit=True)
        out=io.BytesIO();qr.make_image(fill_color='black',back_color='white').save(out,format='PNG');out.seek(0)
        return send_file(out,mimetype='image/png',download_name=f'isazi-product-{product_id}-qr.png',as_attachment=request.args.get('download')=='1',max_age=300)

    def context():
        customer=eco['current_customer']()
        quick=db().execute('SELECT * FROM products WHERE id=? AND active=1',(session.get('quick_product'),)).fetchone()
        return dict(quick_product_card=quick,phone_account=account(customer),customer_code=('ISZ-C%07d'%customer['id']) if customer else '',
                    bundle_ids={row[0] for row in db().execute('SELECT id FROM products WHERE active=1 AND is_bundle=1')},qr_base=qr_base(),pep_branches=list(branches.values()),pep_directory_date=directory['updated'],pep_config=public_config())
    app.context_processor(context)

    def auth_page(tab='register',status=400):
        if session.get('after_auth_checkout') and session.get('checkout_method'):
            return render_template('checkout_account.html',title='Register or sign in',auth_tab=tab),status
        page='customer_login.html' if tab=='login' else 'customer_register.html'
        return render_template(page,title='Sign in' if tab=='login' else 'Create your account'),status

    def register_phone(customer_session, destination, throttled, failure):
        key='register:'+(request.remote_addr or 'unknown')
        if throttled(key): abort(429)
        phone=normalize_phone(request.form.get('phone',''));pin=request.form.get('pin','')
        checkout_auth=bool(session.get('after_auth_checkout') and session.get('checkout_method'))
        preference=('pep' if session.get('checkout_method')=='pep' else 'gateway') if checkout_auth else request.form.get('preference','pep')
        branch='' if checkout_auth else request.form.get('branch_code','')
        failure(key)
        if not phone or not re.fullmatch(r'[0-9]{4}',pin) or pin!=request.form.get('confirm_pin') or not request.form.get('consent') or preference not in ('pep','gateway') or (preference=='pep' and not checkout_auth and branch not in branches):
            flash('Enter a South African cellphone number, matching four-digit PINs and privacy consent.' if checkout_auth else 'Enter a South African cellphone number, matching four-digit PINs, your delivery choice and privacy consent. Select a PEP branch for pickup.','error')
            return auth_page()
        # Never silently link an existing account based on an unverified phone number.
        existing=any(normalize_phone(row['phone'])==phone for row in db().execute('SELECT phone FROM customers'))
        if existing:
            flash('Unable to register these details. Sign in to your existing account or contact the team.','error')
            return auth_page()
        try:
            db().execute('BEGIN IMMEDIATE')
            internal=secrets.token_hex(16)+'@phone.invalid'
            cid=db().execute('INSERT INTO customers(name,email,phone,password_hash) VALUES(?,?,?,?)',('Customer',internal,phone,generate_password_hash(secrets.token_urlsafe(40)))).lastrowid
            db().execute('INSERT INTO phone_accounts(customer_id,phone,pin_hash,preference,branch_code) VALUES(?,?,?,?,?)',(cid,phone,generate_password_hash(pin),preference,branch if preference=='pep' else ''))
            db().commit();customer_session(db().execute('SELECT * FROM customers WHERE id=?',(cid,)).fetchone())
            return redirect(destination())
        except sqlite3.IntegrityError:
            db().rollback();flash('Unable to register these details. Please sign in or contact the team.','error')
            return auth_page()

    def login_phone(customer_session, destination, throttled, failure):
        key='phone-login:'+(request.remote_addr or 'unknown');phone=normalize_phone(request.form.get('phone',''))
        row=db().execute('SELECT * FROM phone_accounts WHERE phone=?',(phone,)).fetchone()
        if throttled(key) or (row and row['locked_until']>time.time()):
            flash('Sign-in is temporarily locked. Please try later or contact the team.','error')
            return auth_page('login',429)
        pin=request.form.get('pin','')
        customer=db().execute('SELECT * FROM customers WHERE id=? AND active=1',(row['customer_id'],)).fetchone() if row else None
        if customer and re.fullmatch(r'[0-9]{4}',pin) and check_password_hash(row['pin_hash'],pin):
            db().execute('UPDATE phone_accounts SET failures=0,locked_until=0 WHERE customer_id=?',(customer['id'],));db().execute('DELETE FROM login_attempts WHERE ip=?',(key,));db().commit()
            customer_session(customer);return redirect(destination())
        if row:
            count=row['failures']+1
            db().execute('UPDATE phone_accounts SET failures=?,locked_until=? WHERE customer_id=?',(count,time.time()+(86400 if count>=10 else 900) if count>=5 else 0,row['customer_id']))
            db().commit()
        failure(key);flash('Unable to sign in. Check your cellphone number and PIN.','error')
        return auth_page('login',400)

    @bp.post('/account/pin')
    def change_pin():
        customer=eco['current_customer']();row=account(customer)
        if not row: abort(403)
        if row['locked_until']>time.time(): abort(429)
        if not check_password_hash(row['pin_hash'],request.form.get('current_pin','')):
            count=row['failures']+1
            db().execute('UPDATE phone_accounts SET failures=?,locked_until=? WHERE customer_id=?',(count,time.time()+86400 if count>=5 else 0,customer['id']));db().commit()
            flash('Current PIN is incorrect.','error')
        else:
            pin=request.form.get('pin','')
            if not re.fullmatch(r'[0-9]{4}',pin) or pin!=request.form.get('confirm_pin'):
                flash('Enter matching four-digit PINs.','error')
            else:
                db().execute('UPDATE phone_accounts SET pin_hash=?,failures=0,locked_until=0 WHERE customer_id=?',(generate_password_hash(pin),customer['id']))
                db().execute('UPDATE customers SET auth_version=auth_version+1 WHERE id=?',(customer['id'],));db().commit();session['customer_version']=customer['auth_version']+1
                flash('PIN updated. Other sessions have been signed out.','success')
        return redirect(url_for('eco.customer_account'))

    def validate_checkout(fields, subtotal):
        customer=eco['current_customer']();phone_account=account(customer)
        if phone_account:
            fields['phone']=phone_account['phone'];fields['email']=customer['email']
        if fields['fulfillment']!='pep': return None
        if not customer: raise ValueError('Sign in before choosing PEP pickup.')
        branch=branches.get(request.form.get('branch_code',''))
        if not branch: raise ValueError('Select a currently listed PEP pickup branch.')
        fields['phone']=normalize_phone(customer['phone'])
        if not fields['phone']: raise ValueError('Your account needs a valid South African cellphone number for PEP pickup.')
        fields['address']=branch['name']+' ('+branch['code']+')\n'+branch['address']
        return branch

    def shipping(total):
        # Fixed standard PEP bag fee, including orders above R600.
        return 5995

    def capture(connection,order_id,branch):
        if not branch: return
        order=connection.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
        values=public_config();snapshot=json.dumps(values)
        connection.execute('INSERT INTO pep_orders(order_id,branch_code,branch_name,branch_address,payment_reference,bank_snapshot) VALUES(?,?,?,?,?,?)',(order_id,branch['code'],branch['name'],branch['address'],order['phone'],snapshot))
        connection.execute("UPDATE order_extra SET courier='PAXI',delivery_status='Awaiting payment' WHERE order_id=?",(order_id,))
        # The test/store stock pool remains unchanged; manual EFT cannot be paid through demo endpoints.
        connection.execute('DELETE FROM notifications WHERE order_id=?',(order_id,))
        queue_sms(connection,order_id,'pending',f'Isazi order ISZ-{order_id:05d} received. Pending payment confirmation. We will notify you once your payment is received and confirmed.')

    def order_info(order_id):
        row=db().execute('SELECT * FROM pep_orders WHERE order_id=?',(order_id,)).fetchone()
        bank=json.loads(row['bank_snapshot']) if row else {}
        return dict(pep_order=row,pep_bank=bank,pep_bank_ready=all(bank.get(k) for k in ('capitec_holder','capitec_number','capitec_type')),sms_rows=db().execute('SELECT * FROM sms_outbox WHERE order_id=? ORDER BY id',(order_id,)).fetchall())

    @bp.route('/owner/phone-checkout',methods=['GET','POST'])
    @admin_only
    def settings():
        if request.method=='POST':
            values={key:request.form.get(key,'').strip() for key in ('capitec_holder','capitec_number','capitec_type','capitec_branch','pep_fee','sms_sid','sms_from','shop_url')}
            try:
                from payment_gateway import cents
                if values['pep_fee']:
                    fee=cents(values['pep_fee'])
                    if not 0<=fee<=100000: raise ValueError('Enter a PEP fee between R0 and R1,000.')
                    values['pep_fee']=str(fee)
                if any(len(v)>120 for v in values.values()): raise ValueError('Please shorten these settings.')
                if values['capitec_number'] and not re.fullmatch(r'[0-9]{6,20}',values['capitec_number']): raise ValueError('Use digits only for the bank account number.')
                if values['sms_sid'] and not re.fullmatch(r'AC[0-9a-fA-F]{32}',values['sms_sid']): raise ValueError('Enter a valid Twilio account SID.')
                if values['sms_from'] and not re.fullmatch(r'\+[1-9][0-9]{6,14}',values['sms_from']): raise ValueError('Use an international SMS sender number.')
                parsed=urlsplit(values['shop_url'])
                if values['shop_url'] and (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('','/')):
                    raise ValueError('Use your public HTTPS shop homepage URL, without a path or query.')
                token=request.form.get('sms_token','').strip()
                if token:
                    if not re.fullmatch(r'[0-9a-fA-F]{32}',token): raise ValueError('Enter a valid Twilio auth token.')
                    values['sms_token']=token
                values['pep_fee']='5995'
                values['sms_enabled']='1' if request.form.get('sms_enabled') else '0'
                for key,value in values.items(): db().execute('INSERT OR REPLACE INTO simple_settings(key,value) VALUES(?,?)',(key,value))
                db().execute("INSERT INTO audit_events(actor,event,reference,detail) VALUES('owner','Phone checkout settings','settings','Bank/delivery/SMS settings updated; secrets omitted')")
                db().commit();flash('Settings saved. No SMS was sent. Bank details are frozen on each new order.','success')
            except ValueError as error:
                db().rollback();flash(str(error),'error')
        values=config();values['pep_fee']='5995';values['sms_token_set']=bool(values.pop('sms_token',''))
        return render_template('owner_phone_checkout.html',values=values,title='Cellphone checkout & PEP')

    @bp.post('/owner/order/<int:order_id>/confirm-eft')
    @admin_only
    def confirm_eft(order_id):
        connection=db();connection.execute('BEGIN IMMEDIATE')
        order=connection.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
        row=connection.execute('SELECT * FROM pep_orders WHERE order_id=?',(order_id,)).fetchone()
        if not row or not order: connection.rollback();abort(404)
        if order['status']=='Cancelled': connection.rollback();abort(409)
        reference=request.form.get('bank_reference','').strip()
        if not request.form.get('verified') or not 3<=len(reference)<=180:
            connection.rollback();flash('Confirm the funds were received and enter the bank transaction reference.','error')
        elif row['confirmed_at']:
            connection.rollback();flash('Payment has already been confirmed.','success')
        else:
            test=connection.execute('SELECT payment_test FROM order_extra WHERE order_id=?',(order_id,)).fetchone()[0]
            connection.execute('INSERT INTO payments_received(order_id,event_key,amount,method,reference) VALUES(?,?,?,?,?)',(order_id,'pep-eft:'+str(order_id),order['total'],'TEST / Capitec EFT' if test else 'Capitec EFT',reference))
            connection.execute("UPDATE pep_orders SET confirmed_at=datetime('now'),confirmed_reference=? WHERE order_id=?",(reference,order_id))
            connection.execute("UPDATE orders SET status='Paid' WHERE id=?",(order_id,))
            connection.execute("UPDATE order_extra SET delivery_status='Payment confirmed' WHERE order_id=?",(order_id,))
            connection.execute("UPDATE sms_outbox SET status='Superseded' WHERE event_key=? AND status='Queued'",(f'pep:{order_id}:pending',))
            queue_sms(connection,order_id,'confirmed',f'Isazi order ISZ-{order_id:05d}: payment received and confirmed. Thank you! We are preparing your parcel for {row["branch_name"]}. We will notify you when it is dispatched.')
            eco['order_changed'](connection,order_id,order['status']);connection.commit();flash('Payment confirmed. The order can now be dispatched.','success')
        return redirect(url_for('owner_order',order_id=order_id))

    def delivery_guard(connection,order_id,status,reference):
        row=connection.execute('SELECT * FROM pep_orders WHERE order_id=?',(order_id,)).fetchone()
        if row:
            order=connection.execute('SELECT * FROM orders WHERE id=?',(order_id,)).fetchone()
            if order['status']=='Cancelled': raise ValueError('Cancelled orders cannot be dispatched.')
            if not row['confirmed_at']: raise ValueError('Confirm the Capitec payment before changing PEP delivery status.')
            if status in ('In transit','Ready for collection','Delivered','Collected') and not reference:
                raise ValueError('Enter the PAXI tracking number before dispatch or collection updates.')
        return row

    def queue_sms(connection,order_id,event,body):
        order=connection.execute('SELECT phone FROM orders WHERE id=?',(order_id,)).fetchone()
        test=connection.execute('SELECT payment_test FROM order_extra WHERE order_id=?',(order_id,)).fetchone()[0]
        key=f'pep:{order_id}:{event}'
        connection.execute('INSERT OR IGNORE INTO sms_outbox(order_id,event_key,recipient,body,status) VALUES(?,?,?,?,?)',(order_id,key,order['phone'],body,'Test - not sent' if test else 'Queued'))
        g.isazi_sms_events=getattr(g,'isazi_sms_events',[])+[key]

    def dispatch_sms(connection,order_id,status,reference):
        row=connection.execute('SELECT * FROM pep_orders WHERE order_id=?',(order_id,)).fetchone()
        if not row or status not in ('In transit','Ready for collection'): return
        phrase='has been dispatched to' if status=='In transit' else 'is ready for collection at'
        body=f"Isazi order ISZ-{order_id:05d} {phrase} {row['branch_name']} ({row['branch_code']}). PAXI tracking: {reference}. PAXI sends your collection PIN when the parcel is ready. Bring your ID and PAXI collection PIN, not your Isazi login PIN."
        queue_sms(connection,order_id,status+':'+reference,body)

    def deliver_sms(sms_id):
        values=config();connection=db();connection.execute('BEGIN IMMEDIATE')
        row=connection.execute('SELECT s.*,e.payment_test,o.status AS order_status FROM sms_outbox s JOIN order_extra e ON e.order_id=s.order_id JOIN orders o ON o.id=s.order_id WHERE s.id=?',(sms_id,)).fetchone()
        if not row: connection.rollback();return 'missing'
        if row['payment_test'] or row['order_status']=='Cancelled' or row['status']!='Queued': connection.rollback();return 'blocked'
        if values.get('sms_enabled')!='1' or not all(values.get(k) for k in ('sms_sid','sms_token','sms_from')):
            connection.rollback();return 'unconfigured'
        connection.execute("UPDATE sms_outbox SET status='Sending - reconcile before retry' WHERE id=?",(sms_id,));connection.commit()
        try:
            sid=values['sms_sid'];payload=urlencode({'To':'+27'+row['recipient'][1:],'From':values['sms_from'],'Body':row['body']}).encode()
            auth=base64.b64encode((sid+':'+values['sms_token']).encode()).decode()
            req=Request(f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',data=payload,headers={'Authorization':'Basic '+auth,'Content-Type':'application/x-www-form-urlencoded'})
            with urlopen(req,timeout=15) as response: result=json.load(response)
            if not re.fullmatch(r'S[MM][0-9a-fA-F]{32}',result.get('sid','')): raise ValueError('Unrecognised provider response')
            connection.execute('UPDATE sms_outbox SET status=?,provider_id=? WHERE id=?',('Provider accepted',result['sid'],sms_id));connection.commit()
            return 'accepted'
        except Exception:
            return 'uncertain'

    @app.after_request
    def send_committed_updates(response):
        # Only events created in this request, after the order transaction committed.
        # Rolled-back events are absent. Never replay the backlog or retry ambiguous sends.
        if response.status_code<400 and not db().in_transaction:
            for key in dict.fromkeys(getattr(g,'isazi_sms_events',[])):
                row=db().execute('SELECT id FROM sms_outbox WHERE event_key=?',(key,)).fetchone()
                if row: deliver_sms(row['id'])
        return response

    @bp.post('/owner/sms/<int:sms_id>/send')
    @admin_only
    def send_sms(sms_id):
        row=db().execute('SELECT order_id FROM sms_outbox WHERE id=?',(sms_id,)).fetchone()
        if not row: abort(404)
        result=deliver_sms(sms_id)
        if result=='blocked': abort(409,'This message cannot be sent.')
        messages={'unconfigured':'Configure and enable SMS in Cellphone checkout settings first.',
                  'accepted':'SMS accepted by provider. Handset delivery is not yet confirmed.',
                  'uncertain':'SMS outcome is uncertain. Check the provider dashboard before another send.'}
        flash(messages.get(result,'Message unavailable.'),'success' if result=='accepted' else 'error')
        return redirect(url_for('owner_order',order_id=row['order_id']))

    @bp.get('/owner/product-qr')
    @admin_only
    def qr_catalog():
        products=db().execute('SELECT * FROM products WHERE active=1 AND is_bundle=1 ORDER BY id').fetchall()
        return render_template('owner_product_qr.html',products=products,title='Product & combo QR codes')

    app.register_blueprint(bp)
    result=dict(initialize=initialize,account=account,register_phone=register_phone,login_phone=login_phone,validate_checkout=validate_checkout,shipping=shipping,capture=capture,order_info=order_info,delivery_guard=delivery_guard,dispatch_sms=dispatch_sms)
    app.extensions['simple_checkout']=result
    return result
