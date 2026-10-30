"""Isazi Herbal Shop — Flask storefront with SQLite and manual order confirmation."""
import csv
import functools
import io
import os
import re
import secrets
import sqlite3
import time
from urllib.parse import urlsplit
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

import click
from flask import Flask, abort, flash, g, redirect, render_template, request, send_from_directory, session, url_for, Response
from werkzeug.security import check_password_hash, generate_password_hash
from PIL import Image, UnidentifiedImageError
from ecosystem import register_ecosystem, valid_email
from simple_checkout import register_simple
from client_demo import register_client_demo
from video_processing import transcode_upload
from performance import install_performance, upload_variant

APP_VERSION = '2.6.23'
ROOT = Path(__file__).resolve().parent
CATEGORIES = ['General Health', "Men’s Health", "Women’s Health", 'Digestive Health', 'Joint Health', 'Skin & Body Care', 'Immune Support', 'Energy & Vitality', 'Mind & Focus', 'Detox & Cleansing']
SEEDS = [
 ('Smolo Body Cured System', 'General Health', 20000, 'product-1.webp'),
 ('Ukhlanza Isibindi', 'Digestive Health', 35000, 'product-2.webp'),
 ('Mashamba Mix', 'General Health', 18000, 'product-3.webp'),
 ('Isazi Immune Booster', 'Immune Support', 18000, 'product-4.webp'),
 ('Isazi Cleanse Mix', 'Digestive Health', 10000, 'product-5.webp'),
 ('Herbal Combo Pack', 'General Health', 55000, 'combo.webp'),
]
VIDEO_SEEDS = [('story', 'Our Story', 'story-video-placeholder.png')] + [('testimonial', f'Customer testimony {n}', f'testimony-audio-cover-{n}.png') for n in range(1,5)]
HOME_IMAGE_SLOTS = {
 'shop_banner': ('Shop banner photograph', 'demo-botanicals.webp', 2400, 800, 'Text-free botanical landscape. Heading is live HTML.'),
 'contact_banner': ('Contact banner photograph', 'demo-article-2.webp', 2400, 800, 'Text-free botanical landscape.'),
 'hero': ('Desktop hero', 'hero-natural-meadow.webp', 2400, 800, 'Text-free landscape. Keep faces and important details inside the central 600 px vertically.'),
 'hero_mobile': ('Mobile hero (optional)', '', 1200, 1600, 'Portrait artwork. If unset, the desktop hero is used.'),
 'brand_mark': ('Brand crest (optional)', '', 512, 512, 'Square transparent PNG/WebP crest. The shop name remains sharp live text.'),
 'combo': ('Combo pack photograph', 'demo-combo.webp', 1500, 1000, 'Three-product photograph, no promotional text baked into the image.'),
 'promo_cleanse': ('Cleanse promotion photograph', 'demo-product-5.webp', 1500, 1000, 'Product photograph only. Banner copy and buttons remain live HTML.'),
 'promo_immune': ('Herbal collection promotion photograph', 'demo-product-4.webp', 1500, 1000, 'Product photograph only. Keep the whole bottle inside the frame.'),
 'article_1': ('Article 1 cover', 'demo-botanicals.webp', 1200, 800, 'Landscape botanical photograph.'),
 'article_2': ('Article 2 cover', 'demo-article-2.webp', 1200, 800, 'Landscape botanical photograph.'),
 'article_3': ('Article 3 cover', 'demo-article-3.webp', 1200, 800, 'Landscape botanical photograph.'),
 'article_4': ('Article 4 cover', 'demo-article-4.webp', 1200, 800, 'Landscape botanical photograph.'),
}
DEMO_REPLACEMENTS = {
 **{f'product-{n}.webp': f'demo-product-{n}.webp' for n in range(1, 6)},
 **{f'testimonial-{n}.webp': f'testimony-audio-cover-{n}.png' for n in range(1, 5)},
 **{f'demo-testimonial-{n}.webp': f'testimony-audio-cover-{n}.png' for n in range(1,5)},
 'combo.webp': 'demo-combo.webp', 'founder.webp': 'story-video-placeholder.png', 'story-scroll.webp': 'story-video-placeholder.png', 'demo-story.webp': 'story-video-placeholder.png', 'story-original-placeholder.svg': 'story-video-placeholder.png',
 **{f'article-{n}.webp': ('demo-botanicals.webp' if n == 1 else f'demo-article-{n}.webp') for n in range(1, 5)},
}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS home_images (
 key TEXT PRIMARY KEY, filename TEXT NOT NULL, width INTEGER NOT NULL DEFAULT 0, height INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS videos (
 id INTEGER PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL, person TEXT NOT NULL DEFAULT '',
 caption TEXT NOT NULL DEFAULT '', video_source TEXT NOT NULL DEFAULT '', audio_source TEXT NOT NULL DEFAULT '', poster TEXT NOT NULL,
 active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS products (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL, price INTEGER NOT NULL CHECK(price>=0),
 description TEXT NOT NULL, image TEXT NOT NULL, stock INTEGER NOT NULL DEFAULT 0 CHECK(stock>=0), active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS admins (id INTEGER PRIMARY KEY CHECK(id=1), password_hash TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS login_attempts (ip TEXT PRIMARY KEY, failures INTEGER NOT NULL, locked_until REAL NOT NULL);
CREATE TABLE IF NOT EXISTS orders (
 id INTEGER PRIMARY KEY, token TEXT UNIQUE NOT NULL, checkout_key TEXT UNIQUE NOT NULL, created_at TEXT NOT NULL DEFAULT (datetime('now')),
 name TEXT NOT NULL, email TEXT NOT NULL, phone TEXT NOT NULL, fulfillment TEXT NOT NULL, address TEXT NOT NULL,
 notes TEXT NOT NULL, subtotal INTEGER NOT NULL, shipping INTEGER NOT NULL, total INTEGER NOT NULL,
 status TEXT NOT NULL DEFAULT 'Awaiting confirmation');
CREATE TABLE IF NOT EXISTS order_items (
 id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), product_id INTEGER NOT NULL,
 name TEXT NOT NULL, quantity INTEGER NOT NULL CHECK(quantity>0), unit_price INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS enquiries (
 id INTEGER PRIMARY KEY, created_at TEXT NOT NULL DEFAULT (datetime('now')), name TEXT NOT NULL, email TEXT NOT NULL, message TEXT NOT NULL);
'''
DEFAULTS = {
 'social_facebook': '', 'social_instagram': '', 'social_tiktok': '', 'social_youtube': '',
 'email': '', 'business_hours': 'Mon–Fri: 08:00–17:00\nSat: 09:00–13:00',
 'phone': '060 585 7817', 'location': 'Randburg, Johannesburg',
 'about': 'Discover Isazi Herbal Shop and our range of traditional herbal products. Contact our team for product information, ingredients and directions before purchasing.',
 'story_video': '', 'payment_instructions': 'Your order is reserved for review. Our team will contact you to confirm availability, delivery and payment details. No online payment has been taken.',
 'delivery_note': 'Free local delivery in Randburg on orders over R600. A R50 local delivery fee applies to orders of R600 or less. Collection is free; the collection address is confirmed by our team.',
 'policy': 'Contact us promptly about an incorrect, damaged or unwanted order. Returns and refunds are handled in accordance with applicable consumer rights. Keep your order reference and proof of purchase.',
}

def create_app(test_config=None):
    app = Flask(__name__)
    demo_requested = os.environ.get('ISAZI_CLIENT_DEMO') == '1'
    data_dir = ROOT / 'instance-client-demo' if demo_requested else Path(os.environ.get('DATA_DIR', ROOT / 'instance'))
    data_dir.mkdir(parents=True, exist_ok=True)
    app.config.update(DATABASE=str(data_dir / 'shop.sqlite3'), UPLOAD_DIR=str(data_dir / 'uploads'),
                      MAX_CONTENT_LENGTH=312 * 1024 * 1024, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('COOKIE_SECURE') == '1',
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=2), TESTING=False, CUSTOMER_CHECKOUT_REQUIRED=True, DEMO_MODE=demo_requested, DEMO_PAYMENTS_ENABLED=os.environ.get('DEMO_PAYMENTS_ENABLED')=='1')
    if test_config:
        app.config.update(test_config)
    if app.config.get('DEMO_MODE'):
        if not demo_requested and not app.testing:
            raise RuntimeError('Start client-demo mode with START_DEMO_WINDOWS.ps1 so its data is isolated.')
        if Path(app.config['DATABASE']).resolve() == (ROOT/'instance'/'shop.sqlite3').resolve():
            raise RuntimeError('Demo mode cannot use the normal store database.')
        app.config.update(PAYFAST_ENABLED='0', SMTP_HOST='', PUBLIC_BASE_URL='', SESSION_COOKIE_NAME='isazi_client_demo', SESSION_COOKIE_SECURE=False)
    if app.config.get('DEMO_PAYMENTS_ENABLED'):
        app.config.update(PAYFAST_ENABLED='0', SMTP_HOST='')
    Path(app.config['UPLOAD_DIR']).mkdir(parents=True, exist_ok=True)
    secret = os.environ.get('SECRET_KEY')
    if not secret:
        key_path = data_dir / '.session-key'
        try:
            fd = os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(fd, 'w') as handle:
                handle.write(secrets.token_hex(32))
        except FileExistsError:
            pass
        secret = key_path.read_text().strip()
    app.secret_key = secret
    fast_assets=install_performance(app,ROOT)

    def db():
        if 'db' not in g:
            g.db = sqlite3.connect(app.config['DATABASE'], timeout=15)
            g.db.row_factory = sqlite3.Row
            g.db.execute('PRAGMA foreign_keys=ON')
        return g.db

    @app.teardown_appcontext
    def close_db(error):
        connection = g.pop('db', None)
        if connection:
            connection.close()

    def settings():
        return dict(db().execute('SELECT key,value FROM settings').fetchall())

    def csrf():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(32)
        return session['csrf']

    @app.before_request
    def protect():
        if request.method == 'POST' and request.endpoint != 'eco.payfast_itn':
            supplied = request.form.get('csrf_token', '')
            if not supplied or not secrets.compare_digest(supplied, session.get('csrf', '')):
                abort(400, 'The form expired. Reload the page and try again.')

    @app.after_request
    def headers(response):
        response.headers['X-Isazi-Version'] = APP_VERSION
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; media-src 'self' https:; frame-src 'none'; object-src 'none'; base-uri 'self'; form-action 'self' https://sandbox.payfast.co.za https://www.payfast.co.za"
        if request.endpoint and (request.endpoint.startswith(('owner','eco.')) or request.endpoint in ('cart', 'checkout', 'confirmation', 'login')):
            response.headers['Cache-Control'] = 'no-store'
            response.headers['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    def admin_only(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            if not session.get('admin'):
                return redirect(url_for('login'))
            return fn(*args, **kwargs)
        return wrapped

    def image_url(name, width=1280):
        name = DEMO_REPLACEMENTS.get(name, name)
        return url_for('uploaded',filename=name,w=min((320,640,1280),key=lambda x:abs(x-width))) if name.startswith('upload-') else fast_assets['image'](name,width)

    def image_srcset(name,widths=(320,640,1280)):
        return fast_assets['srcset'](DEMO_REPLACEMENTS.get(name,name),widths)

    @app.template_filter('money')
    def money(cents):
        return f'R{cents / 100:,.2f}'

    def video_url(source):
        return url_for('uploaded', filename=source) if source.startswith('upload-') else source

    @app.context_processor
    def context():
        return dict(app_version=APP_VERSION, home_images=dict(db().execute('SELECT key,filename FROM home_images').fetchall()), settings=settings(), categories=CATEGORIES, csrf_token=csrf, image_url=image_url,
                    video_url=video_url, image_srcset=image_srcset, cart_count=sum(session.get('cart', {}).values()))

    def presentation_inventory():
        return bool(app.config.get('DEMO_PAYMENTS_ENABLED') and not app.config.get('DEMO_MODE'))

    def customer_product(row):
        if row and presentation_inventory():
            row=dict(row);row['stock']=row['presentation_stock']
        return row

    @app.before_request
    def purchasing_role():
        purchase_endpoints={'cart_add','cart_update','cart_remove','checkout','quick_buy','demo.complete','eco.pay'}
        if session.get('admin') and request.endpoint in purchase_endpoints:
            abort(403,'Owners cannot purchase. Sign out and use a customer account, or open a separate browser profile.')
        if request.endpoint in {'cart_add','checkout'} and app.config.get('CUSTOMER_CHECKOUT_REQUIRED') and not app.config.get('DEMO_MODE') and not eco['current_customer']():
            if request.endpoint=='cart_add':
                session['after_auth_product']=request.view_args['product_id']
            flash('Create a customer account or sign in to continue shopping.','success')
            return redirect(url_for('eco.customer_register'))

    def get_product(product_id, active=True):
        row = db().execute('SELECT * FROM products WHERE id=?' + (' AND active=1' if active else ''), (product_id,)).fetchone()
        if not row:
            abort(404)
        return customer_product(row) if active else row

    def cart_lines():
        lines = []
        for key, qty in session.get('cart', {}).items():
            product = db().execute('SELECT * FROM products WHERE id=? AND active=1', (key,)).fetchone()
            if product:
                lines.append(dict(product=customer_product(product), quantity=qty, total=qty * product['price']))
        return lines

    def bounded_int(raw, low=1, high=99):
        try:
            value = int(raw)
            if not low <= value <= high:
                raise ValueError
            return value
        except (TypeError, ValueError):
            abort(400, 'Please enter a valid quantity.')

    @app.route('/')
    def home():
        products = db().execute('SELECT * FROM products WHERE active=1 ORDER BY id LIMIT 6').fetchall()
        story = db().execute("SELECT * FROM videos WHERE kind='story' AND active=1 ORDER BY id LIMIT 1").fetchone()
        testimonials = db().execute("SELECT * FROM videos WHERE kind='testimonial' AND active=1 ORDER BY id").fetchall()
        return render_template('home.html', products=[customer_product(p) for p in products], story=story, testimonials=testimonials, title='Traditional herbal wellness')

    @app.route('/shop')
    def shop():
        query = request.args.get('q', '').strip()[:100]
        category = request.args.get('category', '')
        sql, args = 'SELECT * FROM products WHERE active=1', []
        if query:
            sql += ' AND (name LIKE ? OR description LIKE ?)'
            args += ['%' + query + '%'] * 2
        if category:
            sql += ' AND category=?'
            args.append(category)
        sql += {'price-low': ' ORDER BY price,id', 'price-high': ' ORDER BY price DESC,id', 'name': ' ORDER BY name'}.get(request.args.get('sort'), ' ORDER BY id')
        category_counts={row['category']:row['count'] for row in db().execute('SELECT category,COUNT(*) AS count FROM products WHERE active=1 GROUP BY category')}
        ratings={row['product_id']:row for row in db().execute("SELECT product_id,COUNT(*) AS count,AVG(rating) AS average FROM product_reviews WHERE status='Published' GROUP BY product_id")}
        return render_template('shop.html', products=[customer_product(p) for p in db().execute(sql, args).fetchall()], query=query, category=category,category_counts=category_counts,all_count=sum(category_counts.values()),rating_summaries=ratings,title='Shop herbal products')

    @app.route('/product/<int:product_id>')
    def product(product_id):
        p = get_product(product_id)
        return render_template('product.html', product=p, title=p['name'],**eco['product_context'](p['id']))

    @app.post('/cart/add/<int:product_id>')
    def cart_add(product_id):
        session.pop('quick_product',None)
        p = get_product(product_id)
        qty = bounded_int(request.form.get('quantity', '1'))
        cart = dict(session.get('cart', {}))
        new_qty = cart.get(str(product_id), 0) + qty
        if new_qty > min(p['stock'], 99):
            flash('The requested quantity is not available.', 'error')
        else:
            if app.config.get('DEMO_MODE'):
                demo['ensure_customer']()
            cart[str(product_id)] = new_qty
            session['cart'] = cart
            flash(p['name'] + ' added to your cart.', 'success')
        return redirect(url_for('cart'))

    @app.post('/cart/remove/<int:product_id>')
    def cart_remove(product_id):
        cart = dict(session.get('cart', {}))
        cart.pop(str(product_id), None)
        session['cart'] = cart
        return redirect(url_for('cart'))

    @app.route('/cart')
    def cart():
        session.pop('quick_product',None)
        lines = cart_lines()
        subtotal=sum(x['total'] for x in lines)
        return render_template('cart.html', lines=lines, subtotal=subtotal, title='Your cart',**eco['cart_promotion'](subtotal))

    @app.post('/cart/update/<int:product_id>')
    def cart_update(product_id):
        qty = bounded_int(request.form.get('quantity'), 0)
        cart = dict(session.get('cart', {}))
        if qty == 0:
            cart.pop(str(product_id), None)
        else:
            p = get_product(product_id)
            if qty > p['stock']:
                flash('The requested quantity is not available.', 'error')
                return redirect(url_for('cart'))
            cart[str(product_id)] = qty
        session['cart'] = cart
        return redirect(url_for('cart'))

    @app.get('/buy/<int:product_id>')
    def quick_buy(product_id):
        p=get_product(product_id)
        if not p['is_bundle']: abort(404)
        if p['stock']<1:
            flash('This product is currently unavailable. Please choose another product.','error')
            return redirect(url_for('product',product_id=product_id))
        session['quick_product']=product_id
        session.pop('checkout_key',None)
        if not eco['current_customer']():
            session['after_auth_quick']=product_id
            return redirect(url_for('eco.customer_register'))
        return redirect(url_for('checkout'))

    @app.route('/checkout', methods=['GET', 'POST'])
    def checkout():
        quick_product=session.get('quick_product')
        if quick_product:
            quick=get_product(quick_product)
            if not quick['is_bundle']:
                session.pop('quick_product',None)
                return redirect(url_for('product',product_id=quick_product))
            lines=[dict(product=quick,quantity=1,total=quick['price'])]
        else:
            lines = cart_lines()
        if not lines:
            flash('Add a product before checking out.', 'error')
            return redirect(url_for('shop'))
        if app.config.get('DEMO_MODE'):
            demo['ensure_customer']()
        session.setdefault('checkout_key', secrets.token_hex(24))
        subtotal = sum(x['total'] for x in lines)
        if request.method == 'POST':
            key = request.form.get('checkout_key', '')
            if not secrets.compare_digest(key, session.get('checkout_key', '')):
                abort(400, 'This checkout has expired. Reload and try again.')
            previous = db().execute('SELECT token FROM orders WHERE checkout_key=?', (key,)).fetchone()
            if previous:
                return redirect(url_for('confirmation', token=previous['token']))
            fields = {k: request.form.get(k, '').strip() for k in ['name', 'email', 'phone', 'fulfillment', 'address', 'notes']}
            errors = []
            pep_branch = None
            try:
                pep_branch = simple['validate_checkout'](fields,subtotal)
            except ValueError as error:
                errors.append(str(error))
            code=request.form.get('agent_code',eco['current_referral']()).strip()
            if code and not eco['resolve_agent'](code):
                errors.append('Enter a valid approved agent code or leave it blank.')
            if not 2 <= len(fields['name']) <= 120:
                errors.append('Enter your full name (2–120 characters).')
            if not valid_email(fields['email']):
                errors.append('Enter a valid email address.')
            if not re.fullmatch(r'[+\d ()-]{7,25}', fields['phone']):
                errors.append('Enter a valid contact number.')
            if fields['fulfillment'] not in ['collection', 'randburg', 'pep']:
                errors.append('Choose PEP pickup, collection or delivery.')
            if fields['fulfillment'] == 'randburg' and not 10 <= len(fields['address']) <= 600:
                errors.append('Enter a full Randburg delivery address.')
            if len(fields['notes']) > 1000 or len(fields['address']) > 600:
                errors.append('Please shorten your address or order notes.')
            if not request.form.get('consent'):
                errors.append('Confirm that we may use your details to fulfil this order.')
            if errors:
                for error in errors:
                    flash(error, 'error')
            else:
                connection = db()
                try:
                    connection.execute('BEGIN IMMEDIATE')
                    # Atomic stock reservation and price calculation; never trust posted totals.
                    subtotal = 0
                    for line in lines:
                        p = get_product(line['product']['id'])
                        qty = line['quantity']
                        stock_column='presentation_stock' if presentation_inventory() else 'stock'
                        result = connection.execute(f'UPDATE products SET {stock_column}={stock_column}-? WHERE id=? AND {stock_column}>=? AND active=1', (qty, p['id'], qty))
                        if result.rowcount != 1:
                            raise ValueError(f"{p['name']} is no longer available in that quantity. Please update your cart.")
                        line['product'] = p
                        line['total']=p['price'] * qty
                        subtotal += line['total']
                    applied_coupon=eco['coupon_for_checkout'](connection,subtotal)
                    discount=applied_coupon['discount']
                    shipping = simple['shipping'](subtotal-discount) if fields['fulfillment']=='pep' else (0 if fields['fulfillment'] == 'collection' or subtotal-discount > 60000 else 5000)
                    token = secrets.token_urlsafe(32)
                    order_id = connection.execute('INSERT INTO orders(token,checkout_key,name,email,phone,fulfillment,address,notes,subtotal,shipping,total) VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                        (token, key, fields['name'], fields['email'], fields['phone'], fields['fulfillment'], fields['address'], fields['notes'], subtotal, shipping, subtotal-discount + shipping)).lastrowid
                    for line in lines:
                        p = line['product']
                        connection.execute('INSERT INTO order_items(order_id,product_id,name,quantity,unit_price) VALUES(?,?,?,?,?)', (order_id, p['id'], p['name'], line['quantity'], p['price']))
                    eco['capture_order'](connection,order_id,request.form,applied_coupon)
                    simple['capture'](connection,order_id,pep_branch)
                    connection.commit()
                    if not quick_product:
                        session['cart'] = {}
                    session.pop('quick_product',None)
                    session.pop('coupon',None)
                    session.pop('checkout_key', None)
                    session['recent_order'] = token
                    return redirect(url_for('demo.payment_select',token=token) if fields['fulfillment']!='pep' and (app.config.get('DEMO_MODE') or app.config.get('DEMO_PAYMENTS_ENABLED')) else url_for('confirmation', token=token))
                except ValueError as error:
                    connection.rollback()
                    flash(str(error), 'error')
                except sqlite3.IntegrityError:
                    connection.rollback()
                    existing = connection.execute('SELECT token FROM orders WHERE checkout_key=?', (key,)).fetchone()
                    if existing:
                        return redirect(url_for('confirmation', token=existing['token']))
                    raise
        return render_template('checkout.html', lines=lines, subtotal=subtotal, title='Checkout',addresses=eco['checkout_addresses'](),**eco['cart_promotion'](subtotal))

    @app.route('/order/<token>')
    def confirmation(token):
        # Opaque 256-bit link is the customer's order receipt; do not expose sequential IDs.
        order = db().execute('SELECT * FROM orders WHERE token=?', (token,)).fetchone()
        if not order:
            abort(404)
        items = db().execute('SELECT * FROM order_items WHERE order_id=?', (order['id'],)).fetchall()
        return render_template('confirmation.html', order=order, items=items, title='Order received',**eco['order_context'](order['id']))

    @app.route('/about')
    def about():
        return render_template('about.html', story=db().execute("SELECT * FROM videos WHERE kind='story' AND active=1 ORDER BY id LIMIT 1").fetchone(), title='About Dr Ntuli')

    @app.route('/health-tips')
    def tips():
        return render_template('tips.html', title='Health tips & product guidance')

    @app.route('/contact', methods=['GET', 'POST'])
    def contact():
        if request.method == 'POST':
            name, email, message = (request.form.get(k, '').strip() for k in ['name', 'email', 'message'])
            if not 2 <= len(name) <= 120 or not valid_email(email) or not 10 <= len(message) <= 3000:
                flash('Enter your name, valid email and a message of 10–3,000 characters.', 'error')
            elif request.form.get('website'):
                abort(400)
            elif not request.form.get('consent'):
                flash('Please agree to be contacted about your enquiry.', 'error')
            elif time.time() - session.get('enquiry_at', 0) < 60:
                flash('Your message was already received. Please wait a minute before sending another.', 'error')
            else:
                subject=request.form.get('subject','General enquiry')
                if subject not in ('General enquiry','Product information','Existing order','Delivery','Returns'):
                    abort(400)
                db().execute('INSERT INTO enquiries(name,email,message) VALUES(?,?,?)', (name, email, 'Subject: '+subject+'\n\n'+message))
                db().commit()
                session['enquiry_at'] = time.time()
                flash('Your enquiry has been saved for our team.', 'success')
                return redirect(url_for('contact'))
        return render_template('contact.html', title='Contact Isazi')

    @app.route('/policies')
    def policies():
        return render_template('policies.html', title='Delivery, returns & privacy')

    @app.route('/media/<filename>')
    def uploaded(filename):
        if request.args.get('w') and filename.lower().endswith(('.webp','.png','.jpg','.jpeg')):
            try:width=int(request.args['w'])
            except ValueError:abort(400)
            directory,variant_name=upload_variant(app,filename,width)
            return send_from_directory(directory,variant_name,conditional=True)
        return send_from_directory(app.config['UPLOAD_DIR'], filename)

    @app.route('/owner/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            ip = request.remote_addr or 'unknown'
            row = db().execute('SELECT * FROM login_attempts WHERE ip=?', (ip,)).fetchone()
            if row and row['locked_until'] > time.time():
                flash('Too many attempts. Please wait 15 minutes.', 'error')
                return render_template('login.html', title='Owner sign in'), 429
            admin = db().execute('SELECT * FROM admins WHERE id=1').fetchone()
            if admin and check_password_hash(admin['password_hash'], request.form.get('password', '')):
                session.clear()
                session['admin'] = True
                session.permanent = True
                db().execute('DELETE FROM login_attempts WHERE ip=?', (ip,))
                db().commit()
                return redirect(url_for('owner'))
            failures = (row['failures'] if row and time.time() - row['locked_until'] < 900 else 0) + 1
            db().execute('INSERT OR REPLACE INTO login_attempts(ip,failures,locked_until) VALUES(?,?,?)', (ip, failures, time.time() + 900 if failures >= 5 else time.time()))
            db().commit()
            flash('Unable to sign in. Check your password. First run? Use the create-owner command in the README.', 'error')
        return render_template('login.html', title='Owner sign in')

    @app.post('/owner/logout')
    @admin_only
    def owner_logout():
        session.clear()
        return redirect(url_for('home'))

    @app.route('/owner')
    @admin_only
    def owner():
        orders = db().execute('SELECT o.*,e.payment_test FROM orders o JOIN order_extra e ON e.order_id=o.id ORDER BY o.id DESC LIMIT 200').fetchall()
        counts = db().execute("SELECT COUNT(*) AS orders, COALESCE(SUM(CASE WHEN status IN ('Paid','Ready','Completed') THEN total ELSE 0 END),0) AS confirmed, SUM(CASE WHEN status='Awaiting confirmation' THEN 1 ELSE 0 END) AS pending FROM orders WHERE id NOT IN (SELECT order_id FROM order_extra WHERE payment_test=1)").fetchone()
        test_counts=db().execute("SELECT COUNT(*) AS orders,COALESCE((SELECT SUM(p.amount) FROM payments_received p JOIN order_extra x ON x.order_id=p.order_id WHERE x.payment_test=1),0) AS received FROM order_extra WHERE payment_test=1").fetchone()
        products = db().execute('SELECT * FROM products ORDER BY id').fetchall()
        enquiries = db().execute('SELECT * FROM enquiries ORDER BY id DESC LIMIT 100').fetchall()
        return render_template('owner.html', orders=orders, counts=counts, test_counts=test_counts, products=products, enquiries=enquiries, title='Owner dashboard')

    @app.route('/owner/product/new', methods=['GET', 'POST'])
    @app.route('/owner/product/<int:product_id>', methods=['GET', 'POST'])
    @admin_only
    def owner_product(product_id=None):
        p = get_product(product_id, False) if product_id else None
        if request.method == 'POST':
            try:
                name, category = request.form.get('name', '').strip(), request.form.get('category', '')
                description = request.form.get('description', '').strip()
                if not 2 <= len(name) <= 120 or category not in CATEGORIES or not 10 <= len(description) <= 5000:
                    raise ValueError('Enter a name, category and description (10–5,000 characters).')
                value = Decimal(request.form.get('price', ''))
                if not value.is_finite() or value < 0 or value > 100000 or value != value.quantize(Decimal('.01')):
                    raise ValueError('Enter a price between R0 and R100,000 with no more than two decimals.')
                price = int(value * 100)
                stock = int(request.form.get('stock', ''))
                if not 0 <= stock <= 100000:
                    raise ValueError('Enter stock between 0 and 100,000.')
                image_name = p['image'] if p else 'product-1.webp'
                upload = request.files.get('image')
                if upload and upload.filename:
                    try:
                        upload.stream.seek(0, os.SEEK_END)
                        if upload.stream.tell() > 10 * 1024 * 1024:
                            raise ValueError('Product images must be under 10 MB.')
                        upload.stream.seek(0)
                        with Image.open(upload.stream) as im:
                            if im.width * im.height > 20000000:
                                raise ValueError('Image is too large. Use an image under 20 megapixels.')
                            im = im.convert('RGB')
                            im.thumbnail((2400, 2400))
                            image_name = 'upload-' + secrets.token_hex(16) + '.webp'
                            im.save(Path(app.config['UPLOAD_DIR']) / image_name, 'WEBP', quality=88)
                    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
                        raise ValueError('Upload a valid JPG, PNG or WebP image.')
                presentation_stock=int(request.form.get('presentation_stock',p['presentation_stock'] if p else 50))
                if not 0<=presentation_stock<=100000:
                    raise ValueError('Enter test stock between 0 and 100,000.')
                active = 1 if request.form.get('active') else 0
                values = (name, category, price, description, image_name, stock, active)
                if p:
                    db().execute('UPDATE products SET name=?,category=?,price=?,description=?,image=?,stock=?,active=? WHERE id=?', values + (p['id'],))
                    db().execute('UPDATE products SET presentation_stock=? WHERE id=?',(presentation_stock,p['id']))
                else:
                    inserted=db().execute('INSERT INTO products(name,category,price,description,image,stock,active) VALUES(?,?,?,?,?,?,?)', values)
                    db().execute('UPDATE products SET presentation_stock=? WHERE id=?',(presentation_stock,inserted.lastrowid))
                db().execute('UPDATE products SET is_bundle=? WHERE id=?',(1 if request.form.get('is_bundle') else 0,p['id'] if p else inserted.lastrowid))
                db().commit()
                flash('Product saved.', 'success')
                return redirect(url_for('owner'))
            except (ValueError, InvalidOperation) as error:
                flash(str(error) if isinstance(error, ValueError) else 'Enter a valid price.', 'error')
        return render_template('owner_product.html', product=p, title='Edit product' if p else 'Add product',**(eco['product_context'](p['id']) if p else {}))

    @app.route('/owner/order/<int:order_id>', methods=['GET', 'POST'])
    @admin_only
    def owner_order(order_id):
        connection = db()
        order = connection.execute('SELECT * FROM orders WHERE id=?', (order_id,)).fetchone()
        if not order:
            abort(404)
        items = connection.execute('SELECT * FROM order_items WHERE order_id=?', (order_id,)).fetchall()
        if request.method == 'POST':
            status = request.form.get('status')
            if status not in ['Awaiting confirmation', 'Paid', 'Ready', 'Completed', 'Cancelled']:
                abort(400)
            pep = connection.execute('SELECT * FROM pep_orders WHERE order_id=?',(order_id,)).fetchone()
            if pep and status in ('Paid','Ready','Completed') and not pep['confirmed_at']:
                flash('Use Confirm Capitec payment before preparing or completing a PEP order.','error')
                return redirect(url_for('owner_order',order_id=order_id))
            connection.execute('BEGIN IMMEDIATE')
            current = connection.execute('SELECT status FROM orders WHERE id=?', (order_id,)).fetchone()['status']
            if current == 'Cancelled' and status != 'Cancelled':
                connection.rollback()
                flash('Cancelled orders cannot be reopened. Create a new order to reserve stock again.', 'error')
            elif status=='Awaiting confirmation' and eco['order_context'](order_id)['finance']['received']>0:
                connection.rollback()
                flash('Recorded payment cannot be undone by changing status. Use the refund workflow for money already returned.', 'error')
            else:
                if status == 'Cancelled' and current != 'Cancelled':
                    for item in items:
                        stock_pool=connection.execute('SELECT stock_pool FROM order_extra WHERE order_id=?',(order_id,)).fetchone()['stock_pool']
                        stock_column='presentation_stock' if stock_pool=='presentation' else 'stock'
                        connection.execute(f'UPDATE products SET {stock_column}={stock_column}+? WHERE id=?', (item['quantity'], item['product_id']))
                connection.execute('UPDATE orders SET status=? WHERE id=?', (status, order_id))
                eco['order_changed'](connection,order_id,current)
                connection.commit()
                flash('Order updated.', 'success')
            return redirect(url_for('owner_order', order_id=order_id))
        return render_template('owner_order.html', order=order, items=items, title=f'Order ISZ-{order_id:05d}',**eco['order_context'](order_id))

    @app.route('/owner/home-images')
    @admin_only
    def owner_home_images():
        saved = {row['key']: dict(row) for row in db().execute('SELECT * FROM home_images')}
        return render_template('owner_home_images.html', slots=HOME_IMAGE_SLOTS, saved=saved, title='Home images & sizes')

    @app.post('/owner/home-images/<key>')
    @admin_only
    def owner_home_image_save(key):
        if key not in HOME_IMAGE_SLOTS:
            abort(404)
        label, default, recommended_width, recommended_height, hint = HOME_IMAGE_SLOTS[key]
        if request.form.get('reset'):
            db().execute('UPDATE home_images SET filename=?,width=0,height=0 WHERE key=?', (default, key))
            db().commit()
            flash(label + ' reset to the default artwork.', 'success')
            return redirect(url_for('owner_home_images'))
        upload = request.files.get('image')
        if not upload or not upload.filename:
            flash('Choose an image first.', 'error')
            return redirect(url_for('owner_home_images'))
        target = None
        try:
            upload.stream.seek(0, os.SEEK_END)
            if upload.stream.tell() > 10 * 1024 * 1024:
                raise ValueError('Use an image under 10 MB.')
            upload.stream.seek(0)
            with Image.open(upload.stream) as image:
                if image.width * image.height > 20000000:
                    raise ValueError('Use an image under 20 megapixels.')
                image = image.convert('RGBA' if image.mode in ('RGBA', 'LA') or 'transparency' in image.info else 'RGB')
                image.thumbnail((3200, 3200))
                width, height = image.size
                filename = 'upload-home-' + secrets.token_hex(16) + '.webp'
                target = Path(app.config['UPLOAD_DIR']) / filename
                image.save(target, 'WEBP', quality=92)
            db().execute('UPDATE home_images SET filename=?,width=?,height=? WHERE key=?', (filename, width, height, key))
            db().commit()
            flash(label + ' saved.', 'success')
            if width < recommended_width * .7 or height < recommended_height * .7:
                flash(f'This image is {width} × {height} px. For sharper display, use approximately {recommended_width} × {recommended_height} px.', 'error')
        except (ValueError, UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
            if target:
                target.unlink(missing_ok=True)
            flash(str(error) if isinstance(error, ValueError) else 'Upload a valid JPG, PNG or WebP image.', 'error')
        return redirect(url_for('owner_home_images'))

    @app.get('/videos')
    def story_library():
        videos = [dict(v) for v in db().execute("SELECT * FROM videos WHERE kind='story' AND active=1 ORDER BY id DESC").fetchall()]
        # Preserve the legacy settings-only story source.
        for video in videos:
            if not video['video_source'] and video['id'] == 1:
                video['video_source'] = settings().get('story_video', '')
        return render_template('story_library.html', videos=[v for v in videos if v['video_source']], title='Our video library')

    @app.post('/owner/media/stories')
    @admin_only
    def owner_story_upload():
        created = []
        try:
            upload = request.files.get('video')
            if not upload or not upload.filename:
                raise ValueError('Choose an MP4 or WebM video.')
            upload.stream.seek(0, os.SEEK_END)
            size = upload.stream.tell()
            upload.stream.seek(0)
            header = upload.stream.read(32)
            upload.stream.seek(0)
            ext = Path(upload.filename).suffix.lower()
            if not 12 <= size <= 250 * 1024 * 1024:
                raise ValueError('Each video must be under 250 MB.')
            if not ((ext == '.mp4' and header[4:8] == b'ftyp') or (ext == '.webm' and header[:4] == b'\x1aE\xdf\xa3')):
                raise ValueError('Choose a valid MP4 or WebM video.')
            title = Path(upload.filename.replace('\\', '/')).stem.replace('_', ' ').strip()[:100] or 'Our story'
            source, mobile = transcode_upload(upload, app.config['UPLOAD_DIR'])
            created = [Path(app.config['UPLOAD_DIR']) / n for n in (source, mobile)]
            row = db().execute("INSERT INTO videos(kind,title,poster,video_source,mobile_video_source,active) VALUES('story',?,?,?,?,1)",
                               (title, 'story-dr-ntuli-poster-v2622.png', source, mobile))
            db().commit()
            return {'id': row.lastrowid, 'title': title, 'status': 'published'}, 201
        except (ValueError, OSError) as error:
            db().rollback()
            for path in created:
                path.unlink(missing_ok=True)
            return {'error': str(error)}, 400
        except Exception:
            db().rollback()
            for path in created:
                path.unlink(missing_ok=True)
            raise

    @app.route('/owner/media')
    @admin_only
    def owner_media():
        return render_template('owner_media.html', videos=db().execute('SELECT * FROM videos ORDER BY id').fetchall(), title='Videos & testimonials')

    @app.post('/owner/media/<int:video_id>')
    @admin_only
    def owner_media_save(video_id):
        video = db().execute('SELECT * FROM videos WHERE id=?', (video_id,)).fetchone()
        if not video:
            abort(404)
        created_files = []
        try:
            title = request.form.get('title', '').strip()
            person = request.form.get('person', '').strip()
            caption = request.form.get('caption', '').strip()
            if not 2 <= len(title) <= 100 or len(person) > 100 or len(caption) > 500:
                raise ValueError('Use a title of 2–100 characters, a name under 100 characters and a caption under 500 characters.')
            source = video['video_source']
            mobile_source = video['mobile_video_source']
            remote = request.form.get('video_url', '').strip()
            if remote:
                parsed = urlsplit(remote)
                if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or len(remote) > 1500:
                    raise ValueError('Use a direct HTTPS MP4 or WebM video URL.')
                if not parsed.path.lower().endswith(('.mp4', '.webm')):
                    raise ValueError('Use a direct .mp4 or .webm file URL, not a YouTube or social media page.')
                source = remote
                mobile_source = ''
            upload = request.files.get('video')
            if upload and upload.filename:
                upload.stream.seek(0, os.SEEK_END)
                size = upload.stream.tell()
                upload.stream.seek(0)
                if not 12 <= size <= 250 * 1024 * 1024:
                    raise ValueError('Upload an MP4 or WebM video up to 250 MB.')
                header = upload.stream.read(32)
                upload.stream.seek(0)
                ext = Path(upload.filename).suffix.lower()
                if not ((ext == '.mp4' and header[4:8] == b'ftyp') or (ext == '.webm' and header[:4] == b'\x1aE\xdf\xa3')):
                    raise ValueError('The file must be a valid MP4 or WebM video.')
                source, mobile_source = transcode_upload(upload, app.config['UPLOAD_DIR'])
                created_files.extend(Path(app.config['UPLOAD_DIR']) / name for name in (source, mobile_source))
            if request.form.get('clear_video'):
                source = ''
                mobile_source = ''
            audio_source = video['audio_source']
            audio_remote = request.form.get('audio_url', '').strip()
            audio_upload = request.files.get('audio')
            if video['kind'] != 'testimonial' and (audio_remote or (audio_upload and audio_upload.filename)):
                raise ValueError('Audio uploads belong to testimonial slots. Use the video field for Our Story.')
            if audio_remote:
                parsed = urlsplit(audio_remote)
                if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or len(audio_remote)>1500 or not parsed.path.lower().endswith(('.mp3','.m4a','.ogg','.wav')):
                    raise ValueError('Use a direct HTTPS MP3, M4A, OGG or WAV audio file URL.')
                audio_source = audio_remote
            if audio_upload and audio_upload.filename:
                audio_upload.stream.seek(0, os.SEEK_END)
                size = audio_upload.stream.tell()
                audio_upload.stream.seek(0)
                if not 12 <= size <= 50*1024*1024:
                    raise ValueError('Upload an MP3, M4A, OGG or WAV recording under 50 MB.')
                header = audio_upload.stream.read(32)
                audio_upload.stream.seek(0)
                ext = Path(audio_upload.filename).suffix.lower()
                valid = ((ext=='.mp3' and (header[:3]==b'ID3' or (header[0]==255 and header[1]&224==224)))
                         or (ext=='.m4a' and header[4:8]==b'ftyp')
                         or (ext=='.ogg' and header[:4]==b'OggS')
                         or (ext=='.wav' and header[:4]==b'RIFF' and header[8:12]==b'WAVE'))
                if not valid:
                    raise ValueError('The recording must be a valid MP3, M4A, OGG or WAV audio file.')
                audio_source='upload-audio-'+secrets.token_hex(16)+ext
                target=Path(app.config['UPLOAD_DIR'])/audio_source
                created_files.append(target)
                audio_upload.save(target)
            if request.form.get('clear_audio'):
                audio_source=''
            poster = video['poster']
            cover = request.files.get('poster')
            if cover and cover.filename:
                cover.stream.seek(0, os.SEEK_END)
                if cover.stream.tell() > 10 * 1024 * 1024:
                    raise ValueError('Cover images must be under 10 MB.')
                cover.stream.seek(0)
                try:
                    with Image.open(cover.stream) as img:
                        if img.width * img.height > 20000000:
                            raise ValueError('Use a cover image under 20 megapixels.')
                        img = img.convert('RGB')
                        img.thumbnail((2048, 2048))
                        poster = 'upload-poster-' + secrets.token_hex(16) + '.webp'
                        target = Path(app.config['UPLOAD_DIR']) / poster
                        created_files.append(target)
                        img.save(target, 'WEBP', quality=90)
                except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
                    raise ValueError('Use a valid JPG, PNG or WebP cover image.')
            active = 1 if request.form.get('active') else 0
            db().execute('UPDATE videos SET title=?,person=?,caption=?,video_source=?,mobile_video_source=?,audio_source=?,poster=?,active=? WHERE id=?', (title, person, caption, source, mobile_source, audio_source, poster, active, video_id))
            db().commit()
            flash('Media and testimonial details saved.', 'success')
        except (ValueError, OSError) as error:
            for target in created_files:
                target.unlink(missing_ok=True)
            flash(str(error), 'error')
        return redirect(url_for('owner_media'))

    @app.route('/owner/settings', methods=['GET', 'POST'])
    @admin_only
    def owner_settings():
        if request.method == 'POST':
            for key in DEFAULTS:
                value = request.form.get(key, '').strip()
                if key.startswith('social_') and value:
                    allowed = {'social_facebook': {'facebook.com','www.facebook.com','m.facebook.com'}, 'social_instagram': {'instagram.com','www.instagram.com'}, 'social_tiktok': {'tiktok.com','www.tiktok.com'}, 'social_youtube': {'youtube.com','www.youtube.com','youtu.be'}}
                    try:
                        parsed = urlsplit(value)
                        valid = parsed.scheme == 'https' and parsed.hostname in allowed[key] and not parsed.username and not parsed.password and parsed.port in (None,443) and not any(ord(c)<33 for c in value)
                    except ValueError:
                        valid = False
                    if not valid:
                        flash('Use the full HTTPS profile link for the matching social platform.', 'error')
                        return render_template('owner_settings.html', title='Store settings')
                if len(value) > 5000 or (key == 'story_video' and value and (not value.startswith('https://') or len(value) > 1000)):
                    flash('Use a direct HTTPS video URL and keep each field under 5,000 characters.', 'error')
                    return render_template('owner_settings.html', title='Store settings')
            for key in DEFAULTS:
                db().execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)', (key, request.form.get(key, '').strip()))
            db().commit()
            flash('Settings saved.', 'success')
            return redirect(url_for('owner_settings'))
        return render_template('owner_settings.html', title='Store settings')

    @app.route('/owner/orders.csv')
    @admin_only
    def owner_export():
        output = io.StringIO(newline='')
        writer = csv.writer(output)
        writer.writerow(['Order', 'Created (UTC)', 'Customer', 'Email', 'Phone', 'Fulfillment', 'Total (ZAR)', 'Status', 'Payment test'])
        def safe(value):
            value = str(value)
            return "'" + value if value[:1] in ('=', '+', '-', '@', '\t', '\r', '\n') else value
        for o in db().execute('SELECT o.*,e.payment_test FROM orders o JOIN order_extra e ON e.order_id=o.id ORDER BY o.id DESC'):
            writer.writerow([f"ISZ-{o['id']:05d}", o['created_at'], safe(o['name']), safe(o['email']), safe(o['phone']), o['fulfillment'], f"{o['total']/100:.2f}", o['status'], 'Yes - simulated' if o['payment_test'] else 'No'])
        return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=isazi-orders.csv'})

    @app.get('/robots.txt')
    def robots():
        # Private transactional and owner pages should never be indexed.
        return Response('User-agent: *\nDisallow: /owner\nDisallow: /cart\nDisallow: /checkout\nDisallow: /order/\nDisallow: /account\nDisallow: /agent\nDisallow: /track\nDisallow: /pay/\n', mimetype='text/plain')

    @app.get('/health')
    def health():
        db().execute('SELECT 1')
        return {'status': 'ok', 'version': APP_VERSION, 'demo_mode':bool(app.config.get('DEMO_MODE')), 'demo_payments_enabled':bool(app.config.get('DEMO_MODE') or app.config.get('DEMO_PAYMENTS_ENABLED'))}

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(error):
        return render_template('error.html', error=error, title='Please try again'), error.code

    @app.cli.command('create-owner')
    @click.password_option(confirmation_prompt=True)
    def create_owner(password):
        """Create or reset the single store owner password (never shipped in the code)."""
        if len(password) < 16:
            raise click.ClickException('Use at least 16 characters.')
        db().execute('INSERT OR REPLACE INTO admins(id,password_hash) VALUES(1,?)', (generate_password_hash(password),))
        db().execute('DELETE FROM login_attempts')
        db().commit()
        click.echo('Owner password saved. Sign in at /owner/login.')

    @app.cli.command('init-db')
    def init_db_command():
        """Ensure the database exists; preserve existing records."""
        initialize()
        click.echo('Database ready. Existing data preserved.')

    def initialize():
        db().executescript(SCHEMA)
        if 'presentation_stock' not in {row[1] for row in db().execute('PRAGMA table_info(products)')}:
            db().execute('ALTER TABLE products ADD COLUMN presentation_stock INTEGER NOT NULL DEFAULT 50')
        if 'audio_source' not in {row[1] for row in db().execute('PRAGMA table_info(videos)')}:
            db().execute("ALTER TABLE videos ADD COLUMN audio_source TEXT NOT NULL DEFAULT ''")
        if 'mobile_video_source' not in {row[1] for row in db().execute('PRAGMA table_info(videos)')}:
            db().execute("ALTER TABLE videos ADD COLUMN mobile_video_source TEXT NOT NULL DEFAULT ''")
        for key, slot in HOME_IMAGE_SLOTS.items():
            db().execute('INSERT OR IGNORE INTO home_images(key,filename) VALUES(?,?)', (key, slot[1]))
        # Upgrade only the built-in backdrop; preserve custom owner-uploaded heroes.
        db().execute("UPDATE home_images SET filename='hero-natural-meadow.webp',width=0,height=0 WHERE key='hero' AND filename IN ('demo-hero.webp','hero-landscape-composite.webp')")
        for index, (kind, title, poster) in enumerate(VIDEO_SEEDS, 1):
            db().execute('INSERT OR IGNORE INTO videos(id,kind,title,poster) VALUES(?,?,?,?)', (index, kind, title, poster))
        for n, old_title in enumerate(['My Health Journey','Digestive Health','Men’s Health','Immune Support'],1):
            db().execute("UPDATE videos SET title=? WHERE id=? AND kind='testimonial' AND title=? AND person='' AND caption=''", (f'Customer testimony {n}',n+1,old_title))
        for key, value in DEFAULTS.items():
            db().execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)', (key, value))
        # Apply the requested delivery threshold without resetting other store text.
        db().execute("UPDATE settings SET value=replace(value,'R300','R600') WHERE key='delivery_note'")
        if not db().execute('SELECT 1 FROM products LIMIT 1').fetchone():
            for name, category, price, image_name in SEEDS:
                db().execute('INSERT INTO products(name,category,price,description,image,stock) VALUES(?,?,?,?,?,?)',
                             (name, category, price, 'Traditional herbal product from Isazi Herbal Shop. Ingredients, pack size and directions must be confirmed with our team before use. Product information is being finalised.', image_name, 0))
        db().commit()

    eco=register_ecosystem(app,db,admin_only)
    simple=register_simple(app,db,admin_only,eco)
    demo=register_client_demo(app,db,eco)
    with app.app_context():
        initialize()
        eco['initialize']()
        simple['initialize']()
        demo['initialize']()
    return app


app = create_app()
if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)), debug=False)
