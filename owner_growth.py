"""First-party owner analytics. Test records stay tagged; no destructive reset."""
import csv
import hashlib
import io
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from flask import Blueprint, Response, g, redirect, render_template, request, session, url_for
from itsdangerous import URLSafeTimedSerializer, BadSignature


def register_owner_growth(app, db, admin_only):
    bp = Blueprint('growth', __name__)
    signer = URLSafeTimedSerializer(app.secret_key, salt='owner-analytics-v1')
    public = {'home', 'shop', 'product', 'about', 'contact', 'tips', 'testimonials', 'cart'}

    def initialize():
        db().executescript('''
        CREATE TABLE IF NOT EXISTS growth_events (
          day TEXT NOT NULL, visitor TEXT NOT NULL, scope TEXT NOT NULL,
          event TEXT NOT NULL, page TEXT NOT NULL, device TEXT NOT NULL,
          browser TEXT NOT NULL, source TEXT NOT NULL, hits INTEGER NOT NULL DEFAULT 1,
          PRIMARY KEY(day,visitor,scope,event,page));
        CREATE INDEX IF NOT EXISTS idx_growth_day_scope ON growth_events(day,scope,event);
        CREATE TABLE IF NOT EXISTS growth_meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        INSERT OR IGNORE INTO growth_meta VALUES('started_at',datetime('now'));
        ''')
        db().commit()

    @app.before_request
    def remember_cart():
        if request.endpoint == 'cart_add':
            g.growth_cart = dict(session.get('cart', {}))

    @app.after_request
    def measure(response):
        endpoint = request.endpoint
        if session.get('admin') or request.headers.get('DNT') == '1':
            return response
        ua = request.user_agent.string.lower()
        if any(word in ua for word in ('bot', 'spider', 'crawler', 'lighthouse')):
            return response
        event = None
        if request.method == 'GET' and response.status_code == 200:
            if endpoint in public:
                event = 'product_view' if endpoint == 'product' else 'page_view'
            elif endpoint == 'checkout' and session.get('checkout_method'):
                event = 'checkout'
        elif endpoint == 'cart_add' and response.status_code in (302, 303):
            if session.get('cart', {}) != getattr(g, 'growth_cart', {}):
                event = 'add_to_cart'
        if not event:
            return response
        try:
            token = signer.loads(request.cookies.get('isazi_analytics', ''), max_age=180*86400)
            if not isinstance(token, str) or len(token) != 32:
                raise BadSignature('Invalid analytics token')
        except BadSignature:
            token = secrets.token_hex(16)
            response.set_cookie('isazi_analytics', signer.dumps(token), max_age=180*86400,
                                secure=app.config['SESSION_COOKIE_SECURE'], httponly=True, samesite='Lax')
        visitor = hashlib.sha256(token.encode()).hexdigest()
        scope = 'test' if app.config.get('DEMO_MODE') or app.config.get('DEMO_PAYMENTS_ENABLED') else 'real'
        device = 'Mobile' if any(x in ua for x in ('mobile', 'android', 'iphone', 'ipad')) else 'Desktop'
        browser = next((label for word, label in [('edg/', 'Edge'), ('firefox/', 'Firefox'),
                        ('chrome/', 'Chrome'), ('safari/', 'Safari')] if word in ua), 'Other')
        try:
            host = (urlsplit(request.referrer or '').hostname or '').lower()
            same = host == request.host.split(':')[0].lower()
            source = 'Direct' if not host or same else next((label for domain, label in
                     [('tiktok.com','TikTok'), ('google.com','Google'), ('google.co.za','Google'),
                      ('whatsapp.com','WhatsApp'), ('wa.me','WhatsApp'), ('facebook.com','Facebook'),
                      ('instagram.com','Instagram')] if host == domain or host.endswith('.'+domain)), 'Other referrals')
        except ValueError:
            source = 'Other referrals'
        # Store only route names and numeric product IDs, never URLs, query
        # strings, IPs, phone numbers, account details or raw user agents.
        page = str(endpoint)
        if endpoint == 'product':
            page += ':' + str(request.view_args['product_id'])
        day = datetime.now(timezone.utc).date().isoformat()
        try:
            connection = db()
            if connection.in_transaction:
                return response  # Never commit another handler's unfinished work.
            connection.execute('''INSERT INTO growth_events(day,visitor,scope,event,page,device,browser,source)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(day,visitor,scope,event,page)
                DO UPDATE SET hits=hits+1''', (day,visitor,scope,event,page,device,browser,source))
            connection.execute('DELETE FROM growth_events WHERE day < ?',
                               ((datetime.now(timezone.utc).date()-timedelta(days=180)).isoformat(),))
            connection.commit()
        except sqlite3.Error:
            db().rollback()
            app.logger.warning('Analytics write skipped; storefront response preserved')
        return response

    def summary():
        scope = request.args.get('scope', 'all')
        if scope not in ('all', 'test', 'real'):
            scope = 'all'
        period = request.args.get('days', '30')
        days = int(period) if period in ('7', '30', '90') else 30
        end = datetime.now(timezone.utc).date()
        start = end-timedelta(days=days-1)
        dates = (start.isoformat(), end.isoformat())
        condition = '' if scope == 'all' else ' AND e.payment_test=?'
        values = list(dates) + ([] if scope == 'all' else [int(scope == 'test')])
        # Aggregate receipts before joining order items to avoid multiplying sales.
        orders = db().execute('''SELECT o.*,e.payment_test,e.delivery_status,
            COALESCE(p.received,0) AS received,pep.confirmed_at AS pep_confirmed
            FROM orders o JOIN order_extra e ON e.order_id=o.id
            LEFT JOIN (SELECT order_id,SUM(amount) AS received FROM payments_received GROUP BY order_id) p ON p.order_id=o.id
            LEFT JOIN pep_orders pep ON pep.order_id=o.id
            WHERE date(o.created_at) BETWEEN ? AND ?''' + condition + ' ORDER BY o.id DESC', values).fetchall()
        confirmed = [o for o in orders if o['status'] in ('Paid','Ready','Completed') and o['received'] >= o['total']]
        confirmed_ids = {o['id'] for o in confirmed}
        sales = sum(o['total'] for o in confirmed)
        real_sales = sum(o['total'] for o in confirmed if not o['payment_test'])
        pending = [o for o in orders if o['status'] == 'Awaiting confirmation']
        pep_pending = [o for o in pending if o['fulfillment'] == 'pep' and not o['pep_confirmed']]
        dispatch = [o for o in confirmed if o['status'] != 'Completed' and o['delivery_status'] in ('Not arranged','Booked','Payment confirmed')]
        event_sql = 'SELECT * FROM growth_events WHERE day BETWEEN ? AND ?'
        event_values = list(dates)
        if scope != 'all':
            event_sql += ' AND scope=?'; event_values.append(scope)
        events = db().execute(event_sql, event_values).fetchall()
        traffic = [e for e in events if e['event'] in ('page_view','product_view')]
        visitors = {e['visitor'] for e in traffic}
        trends = []
        for i in range(days):
            day = (start+timedelta(days=i)).isoformat()
            trends.append((day, len({e['visitor'] for e in traffic if e['day']==day})))
        peak = max([v for _,v in trends]+[1])
        points = ' '.join(f'{20+i*660/max(1,days-1):.1f},{160-v/peak*135:.1f}' for i,(_,v) in enumerate(trends))
        def grouped(key):
            labels = sorted({e[key] for e in traffic})
            return sorted([(label,len({e['visitor'] for e in traffic if e[key]==label})) for label in labels],key=lambda x:-x[1])
        funnel = [(label,len({e['visitor'] for e in events if e['event'] in types})) for label,types in
                  [('Visitors',('page_view','product_view')),('Product viewers',('product_view',)),
                   ('Added to cart',('add_to_cart',)),('Reached checkout',('checkout',))]]
        top = []
        if confirmed_ids:
            # IDs are integers from our database; bind every value.
            top = db().execute('SELECT name,SUM(quantity) AS units,SUM(quantity*unit_price) AS goods FROM order_items WHERE order_id IN ('+
                               ','.join('?' for _ in confirmed_ids)+') GROUP BY name ORDER BY units DESC LIMIT 5',list(confirmed_ids)).fetchall()
        stocks = db().execute('SELECT id,name,stock,presentation_stock FROM products WHERE active=1 AND '+
                             ('stock<5' if scope=='real' else 'presentation_stock<5' if scope=='test' else '(stock<5 OR presentation_stock<5)')+' ORDER BY name').fetchall()
        return dict(scope=scope,days=days,start=dates[0],end=dates[1],orders=orders,confirmed=confirmed,
                    sales=sales,real_sales=real_sales,test_sales=sales-real_sales,pending=pending,pep_pending=pep_pending,
                    dispatch=dispatch,stocks=stocks,visitors=len(visitors),pageviews=sum(e['hits'] for e in traffic),
                    aov=sales//len(confirmed) if confirmed else 0,trends=trends,points=points,
                    devices=grouped('device'),sources=grouped('source'),browsers=grouped('browser'),
                    funnel=funnel,top=top,started=db().execute("SELECT value FROM growth_meta WHERE key='started_at'").fetchone()[0])

    @bp.get('/owner/growth')
    @admin_only
    def dashboard():
        return render_template('owner_growth.html', title='Traffic, Sales & Growth', growth=summary())

    @bp.get('/owner/growth/export.csv')
    @admin_only
    def export():
        data = summary(); stream = io.StringIO(); writer = csv.writer(stream)
        writer.writerow(['Scope',data['scope'],'From (UTC)',data['start'],'To (UTC)',data['end']])
        writer.writerow(['Metric','Value'])
        for label,key in [('Visitors','visitors'),('Page views','pageviews'),('Confirmed sales (cents; includes delivery, before refunds)','sales'),
                          ('Real confirmed sales (cents)','real_sales'),('Simulated confirmed sales (cents)','test_sales')]:
            writer.writerow([label,data[key]])
        writer.writerow(['Confirmed orders',len(data['confirmed'])])
        writer.writerow(['Awaiting payment',len(data['pending'])])
        writer.writerow(['Date (UTC)','Daily unique visitors'])
        writer.writerows(data['trends'])
        return Response(stream.getvalue(),mimetype='text/csv',headers={'Content-Disposition':'attachment; filename=isazi-growth.csv','Cache-Control':'no-store'})

    app.register_blueprint(bp)
    return dict(initialize=initialize,dashboard=dashboard)
