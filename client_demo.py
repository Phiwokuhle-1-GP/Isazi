"""Isolated client-demo journeys. Never submits a payment or sends a notification."""
import secrets
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

METHODS = (
    ('visa','Visa','Card payment'),
    ('mastercard','Mastercard','Card payment'),
    ('yoco','Yoco','Card checkout'),
    ('ozow','Ozow','Instant EFT'),
    ('payfast','PayFast','Hosted checkout'),
    ('eft','EFT','Bank transfer'),
)


def register_client_demo(app, db, eco):
    bp = Blueprint('demo', __name__)

    def required():
        if not current_app.config.get('DEMO_MODE'):
            abort(404)

    def initialize():
        if not app.config.get('DEMO_MODE'):
            return
        connection=db()
        try:
            connection.execute('BEGIN IMMEDIATE')
            if not connection.execute("SELECT 1 FROM settings WHERE key='_client_demo_seed_v1'").fetchone():
                connection.execute('UPDATE products SET stock=50 WHERE active=1')
                connection.execute("INSERT INTO settings(key,value) VALUES('_client_demo_seed_v1','1')")
            connection.commit()
        except Exception:
            connection.rollback()
            raise

    @app.after_request
    def demo_cache_control(response):
        if current_app.config.get('DEMO_MODE') or current_app.config.get('DEMO_PAYMENTS_ENABLED') or (request.endpoint and request.endpoint.startswith('demo.')):
            response.headers['Cache-Control']='no-store'
            response.headers['X-Robots-Tag']='noindex, nofollow'
        return response

    def ensure_customer():
        required()
        if session.get('admin'):
            abort(403,'Sign out of the owner account before using a sample customer account.')
        customer = eco['current_customer']()
        if customer:
            return customer
        email = 'demo-'+secrets.token_hex(8)+'@example.com'
        customer_id = db().execute('INSERT INTO customers(name,email,phone,password_hash) VALUES(?,?,?,?)',
            ('Demo Customer',email,'0600000000',generate_password_hash(secrets.token_hex(32)))).lastrowid
        db().execute('INSERT INTO customer_addresses(customer_id,label,address) VALUES(?,?,?)',
            (customer_id,'Demo delivery address','Demo address, Randburg, Johannesburg'))
        db().commit()
        retained = {key:session[key] for key in ('cart','coupon','referral','referral_at','csrf','recent_order') if key in session}
        session.clear();session.update(retained)
        session['customer_id']=customer_id;session['customer_version']=0;session.permanent=True
        return eco['current_customer']()

    def payments_required():
        if not (current_app.config.get('DEMO_MODE') or current_app.config.get('DEMO_PAYMENTS_ENABLED')):
            abort(404)

    def order_by_token(token):
        payments_required()
        order = db().execute('SELECT * FROM orders WHERE token=?',(token,)).fetchone()
        if not order:
            abort(404)
        extra=db().execute('SELECT payment_test FROM order_extra WHERE order_id=?',(order['id'],)).fetchone()
        if not extra or not extra['payment_test']:
            abort(409,'Only an order placed in payment test mode can use simulated payments.')
        return order

    def method_info(method):
        result = next((row for row in METHODS if row[0]==method),None)
        if not result:
            abort(404)
        return result

    def context():
        return dict(demo_mode=bool(current_app.config.get('DEMO_MODE')),payment_methods=METHODS,demo_payments_enabled=bool(current_app.config.get('DEMO_MODE') or current_app.config.get('DEMO_PAYMENTS_ENABLED')))

    # App-wide because storefront templates are rendered by other blueprints.
    app.context_processor(context)

    @bp.route('/demo/account',methods=['GET','POST'])
    def account():
        required()
        if request.method=='POST':
            ensure_customer()
            return redirect(url_for('eco.customer_account'))
        if eco['current_customer']():
            return redirect(url_for('eco.customer_account'))
        return render_template('demo_account.html',title='Try My Account')

    @bp.get('/payment-options')
    def payment_options():
        return render_template('payment_options.html',title='Payment options',selected=None,order=None)

    @bp.get('/payment-options/<method>')
    def provider_preview(method):
        selected=method_info(method)
        return render_template('payment_options.html',title=selected[1]+' payment preview',selected=selected,order=None)

    @bp.get('/demo/order/<token>/payment')
    def payment_select(token):
        order=order_by_token(token)
        return render_template('payment_options.html',title='Choose a demo payment',selected=None,order=order)

    @bp.get('/demo/order/<token>/payment/<method>')
    def payment_preview(token,method):
        order=order_by_token(token);selected=method_info(method)
        return render_template('demo_payment.html',order=order,selected=selected,title=selected[1]+' demo checkout',**eco['order_context'](order['id']))

    @bp.post('/demo/order/<token>/payment/<method>/complete')
    def complete(token,method):
        payments_required();selected=method_info(method)
        connection=db()
        try:
            connection.execute('BEGIN IMMEDIATE')
            order=order_by_token(token)
            if order['status']=='Cancelled':
                abort(409,'This demo order was cancelled.')
            received=connection.execute('SELECT COALESCE(SUM(amount),0) FROM payments_received WHERE order_id=?',(order['id'],)).fetchone()[0]
            outstanding=max(0,order['total']-received)
            if outstanding:
                connection.execute('INSERT INTO payments_received(order_id,event_key,amount,method,reference) VALUES(?,?,?,?,?)',
                    (order['id'],'client-demo:'+str(order['id']),outstanding,'CLIENT DEMO / '+selected[1],'DEMO-'+str(order['id'])))
            previous=order['status']
            if previous=='Awaiting confirmation':
                connection.execute("UPDATE orders SET status='Paid' WHERE id=?",(order['id'],))
                if order['total']>0:
                    eco['order_changed'](connection,order['id'],previous)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        flash('Demo payment completed. No money was charged or transferred.','success')
        return redirect(url_for('confirmation',token=token))

    app.register_blueprint(bp)
    return dict(initialize=initialize,ensure_customer=ensure_customer)
