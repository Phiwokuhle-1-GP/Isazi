"""Behavioural tests; only temporary databases are used."""
import io
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / 'test.sqlite3')
        self.app = create_app({'TESTING': True, 'CUSTOMER_CHECKOUT_REQUIRED':False, 'DATABASE': self.db_path, 'UPLOAD_DIR': str(Path(self.tmp.name) / 'uploads')})
        self.app.secret_key = 'test-only-key'
        self.client = self.app.test_client()
        with sqlite3.connect(self.db_path) as db:
            db.execute('UPDATE products SET stock=20')
        self.client.get('/')

    def tearDown(self):
        self.tmp.cleanup()

    def csrf(self):
        with self.client.session_transaction() as session:
            return session['csrf']

    def post(self, url, data=None, follow=True):
        return self.client.post(url, data={'csrf_token': self.csrf(), **(data or {})}, follow_redirects=follow)

    def owner(self):
        runner = self.app.test_cli_runner()
        result = runner.invoke(args=['create-owner', '--password', 'test-password-long-enough'])
        self.assertEqual(result.exit_code, 0, result.output)
        self.post('/owner/login', {'password': 'test-password-long-enough'})

    def order(self, product_id=1, quantity=1, **overrides):
        with self.client.session_transaction() as s:owner_signed_in=bool(s.get('admin'))
        if owner_signed_in:self.post('/owner/logout')
        self.post(f'/cart/add/{product_id}', {'quantity': str(quantity)})
        if self.app.config.get('CUSTOMER_CHECKOUT_REQUIRED') and not self.app.config.get('DEMO_MODE'):
            self.post('/checkout/payment-choice', {'payment_method':'card'})
        self.client.get('/checkout')
        with self.client.session_transaction() as session:
            key = session['checkout_key']
        data = dict(checkout_key=key, name='Test Customer', email='test@example.com', phone='060 123 4567', fulfillment='collection', address='', notes='', consent='on')
        data.update(overrides)
        return self.post('/checkout', data)

    def fetch(self, sql, args=()):
        with sqlite3.connect(self.db_path) as db:
            return db.execute(sql, args).fetchall()

    def test_social_profiles_validate_and_publish_without_invented_accounts(self):
        from app import DEFAULTS
        page=self.client.get('/').get_data(as_text=True)
        self.assertIn('https://wa.me/27605857817',page)
        self.assertIn('Facebook profile not linked yet',page)
        self.owner()
        values=dict(DEFAULTS, social_facebook='https://www.facebook.com/isazi-demo')
        self.post('/owner/settings',values)
        self.assertIn('https://www.facebook.com/isazi-demo',self.client.get('/').get_data(as_text=True))
        for bad in ['javascript:alert(1)','https://facebook.com.evil.example/a','https://user@facebook.com/a','https://facebook.com:bad/a']:
            self.post('/owner/settings',dict(values,social_facebook=bad))
            self.assertEqual(self.fetch("SELECT value FROM settings WHERE key='social_facebook'")[0][0],values['social_facebook'])
        self.assertIn('Nationwide delivery',self.client.get('/').get_data(as_text=True))
        self.assertIn('fixed R99',self.client.get('/policies').get_data(as_text=True))

    def test_owner_reset_replaces_password_and_preserves_products(self):
        self.owner()
        before=self.fetch('SELECT id,name,stock FROM products ORDER BY id')
        runner=self.app.test_cli_runner()
        result=runner.invoke(args=['create-owner','--password','new-test-owner-password-2026'])
        self.assertEqual(result.exit_code,0,result.output)
        other=self.app.test_client();other.get('/owner/login')
        with other.session_transaction() as s:csrf=s['csrf']
        bad=other.post('/owner/login',data={'csrf_token':csrf,'password':'test-password-long-enough'},follow_redirects=True)
        self.assertNotIn(b'Owner workspace',bad.data)
        other.post('/owner/login',data={'csrf_token':csrf,'password':'new-test-owner-password-2026'})
        self.assertEqual(other.get('/owner').status_code,200)
        self.assertEqual(before,self.fetch('SELECT id,name,stock FROM products ORDER BY id'))
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM admins')[0][0],1)

    def test_public_pages_and_asset_links(self):
        for url in ['/', '/shop', '/shop?category=Digestive+Health', '/product/1', '/about', '/health-tips', '/contact', '/policies', '/cart', '/owner/login', '/robots.txt', '/health']:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, url)
            for path in re.findall(r'(?:src|href)="(/static/[^"?]+)', response.get_data(as_text=True)):
                with self.client.get(path) as asset:
                    self.assertEqual(asset.status_code, 200, path)
        self.assertEqual(self.client.get('/product/999').status_code, 404)

    def test_search_category_and_sort(self):
        response = self.client.get('/shop?q=Mashamba')
        self.assertIn(b'Mashamba Mix', response.data)
        self.assertNotIn(b'Smolo Body Cured System', response.data)
        response = self.client.get('/shop?category=Immune+Support')
        self.assertIn(b'Isazi Immune Booster', response.data)
        self.assertNotIn(b'Mashamba Mix', response.data)
        response = self.client.get('/shop?sort=price-low')
        self.assertLess(response.data.index(b'Isazi Cleanse Mix'), response.data.index(b'Herbal Combo Pack'))

    def test_csrf_and_owner_access(self):
        self.assertEqual(self.client.post('/cart/add/1').status_code, 400)
        self.assertEqual(self.client.get('/owner').status_code, 302)
        self.assertEqual(self.client.get('/owner/orders.csv').status_code, 302)
        self.assertEqual(self.post('/owner/order/1', {'status': 'Paid'}, follow=False).status_code, 302)

    def test_cart_update_remove_and_stock_guard(self):
        self.post('/cart/add/1', {'quantity': '2'})
        self.assertIn(b'R400.00', self.client.get('/cart').data)
        self.post('/cart/update/1', {'quantity': '3'})
        with self.client.session_transaction() as session:
            self.assertEqual(session['cart']['1'], 3)
        self.post('/cart/add/1', {'quantity': '99'})
        with self.client.session_transaction() as session:
            self.assertEqual(session['cart']['1'], 3)
        self.post('/cart/remove/1')
        self.assertIn(b'Your cart is empty', self.client.get('/cart').data)
        self.assertEqual(self.post('/cart/add/1', {'quantity': '-1'}).status_code, 400)

    def test_collection_checkout_stores_snapshot_and_stock(self):
        response = self.order(quantity=2, total='1')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'ORDER RECEIVED', response.data)
        self.assertEqual(self.fetch('SELECT subtotal,shipping,total,status FROM orders'), [(40000,0,40000,'Awaiting confirmation')])
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=1')[0][0],18)
        self.assertEqual(self.fetch('SELECT name,quantity,unit_price FROM order_items')[0],('Smolo Body Cured System',2,20000))
        self.assertIn('noindex', response.headers['X-Robots-Tag'])
        self.assertEqual(self.client.get('/order/1').status_code,404)

    def test_courier_fixed_fee_at_all_order_values(self):
        self.order(fulfillment='randburg',address='123 Test Street, Randburg')
        self.assertEqual(self.fetch('SELECT shipping,total FROM orders'),[(9900,29900)])
        self.order(quantity=4,fulfillment='randburg',address='123 Test Street, Randburg')
        self.assertEqual(self.fetch('SELECT shipping,total FROM orders ORDER BY id DESC')[0],(9900,89900))

    def test_delivery_at_exact_threshold_is_not_free(self):
        self.order(product_id=5,quantity=6,fulfillment='randburg',address='123 Test Street, Randburg')
        self.assertEqual(self.fetch('SELECT shipping,total FROM orders'),[(9900,69900)])

    def test_checkout_validation_and_changed_stock(self):
        response = self.order(email='invalid')
        self.assertIn(b'Enter a valid email address',response.data)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)
        with sqlite3.connect(self.db_path) as db:
            db.execute('UPDATE products SET stock=0 WHERE id=1')
        response=self.order()
        self.assertIn(b'no longer available',response.data)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=1')[0][0],0)

    def test_atomic_rollback_when_one_item_sells_out(self):
        self.post('/cart/add/2')
        with sqlite3.connect(self.db_path) as db:
            db.execute('UPDATE products SET stock=0 WHERE id=2')
        self.order()
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=1')[0][0],20)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)

    def test_duplicate_submission_does_not_create_second_order(self):
        self.order()
        with sqlite3.connect(self.db_path) as db:
            key=db.execute('SELECT checkout_key FROM orders').fetchone()[0]
        self.post('/checkout',dict(checkout_key=key,name='Test',email='test@example.com',phone='0601234567',fulfillment='collection',consent='on'))
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],1)
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=1')[0][0],19)

    def test_admin_status_cancel_restores_stock_once(self):
        self.order(quantity=2)
        self.owner()
        self.assertEqual(self.client.get('/owner').status_code,200)
        self.assertEqual(self.client.get('/owner/order/1').status_code,200)
        self.post('/owner/order/1',{'status':'Paid'})
        self.assertEqual(self.fetch('SELECT status FROM orders')[0][0],'Paid')
        self.post('/owner/order/1',{'status':'Cancelled'})
        self.post('/owner/order/1',{'status':'Cancelled'})
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=1')[0][0],20)
        self.post('/owner/order/1',{'status':'Paid'})
        self.assertEqual(self.fetch('SELECT status FROM orders')[0][0],'Cancelled')
        self.assertEqual(self.client.get('/owner/orders.csv').status_code,200)

    def test_admin_edit_and_image_upload(self):
        self.owner()
        for path in ['/owner/product/1','/owner/product/new','/owner/settings']:
            self.assertEqual(self.client.get(path).status_code,200)
        image=io.BytesIO()
        Image.new('RGB',(50,50),'green').save(image,'PNG')
        image.seek(0)
        self.post('/owner/product/1',dict(name='Updated Product',category='General Health',price='249.99',stock='7',description='Verified product description.',active='on',image=(image,'photo.png')))
        row=self.fetch('SELECT name,price,stock,image FROM products WHERE id=1')[0]
        self.assertEqual(row[:3],('Updated Product',24999,7))
        with self.client.get('/media/'+row[3]) as response:
            self.assertEqual(response.status_code,200)
        self.post('/owner/product/new',dict(name='New Product',category='General Health',price='50.00',stock='4',description='New verified product.',active='on'))
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM products')[0][0],9)

    def test_contact_and_stored_html_is_escaped(self):
        self.post('/contact',dict(name='<script>alert(1)</script>',email='test@example.com',message='<script>alert(2)</script>',consent='on'))
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM enquiries')[0][0],1)
        self.owner()
        response=self.client.get('/owner?view=enquiries')
        self.assertIn(b'&lt;script&gt;alert(2)',response.data)
        self.assertNotIn(b'<script>alert(2)',response.data)

    def test_login_rate_limit(self):
        for _ in range(5):
            self.post('/owner/login',{'password':'wrong'})
        self.assertEqual(self.post('/owner/login',{'password':'wrong'}).status_code,429)

    def test_init_preserves_existing_data_and_no_default_owner(self):
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM admins')[0][0],0)
        create_app({'TESTING':True,'DATABASE':self.db_path,'UPLOAD_DIR':str(Path(self.tmp.name)/'uploads')})
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM products')[0][0],8)
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=1')[0][0],20)


if __name__=='__main__':
    unittest.main(verbosity=2)
