"""Client demo never touches the normal store or external payment services."""
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app


class ClientDemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.normal_db=str(root/'normal.sqlite3')
        self.demo_db=str(root/'demo.sqlite3')
        self.config={'TESTING':True,'DEMO_MODE':True,'DATABASE':self.demo_db,'UPLOAD_DIR':str(root/'demo-uploads')}
        self.normal=create_app({'TESTING':True,'DATABASE':self.normal_db,'UPLOAD_DIR':str(root/'normal-uploads')})
        self.demo=create_app(self.config)
        self.client=self.demo.test_client();self.client.get('/')

    def tearDown(self):
        self.tmp.cleanup()

    def query(self,sql,args=(),normal=False):
        with sqlite3.connect(self.normal_db if normal else self.demo_db) as db:
            return db.execute(sql,args).fetchall()

    def post(self,route,data=None,client=None,follow=True):
        c=client or self.client;c.get('/account/login')
        with c.session_transaction() as session:token=session['csrf']
        return c.post(route,data={'csrf_token':token,**(data or {})},follow_redirects=follow)

    def order(self):
        self.post('/cart/add/1',{'quantity':'2'})
        self.client.get('/checkout')
        with self.client.session_transaction() as session:
            key=session['checkout_key'];customer_id=session['customer_id']
        email=self.query('SELECT email FROM customers WHERE id=?',(customer_id,))[0][0]
        result=self.post('/checkout',{'checkout_key':key,'name':'Demo Customer','email':email,'phone':'0600000000','fulfillment':'collection','consent':'on'},follow=False)
        self.assertEqual(result.status_code,302)
        token=self.query('SELECT token FROM orders ORDER BY id DESC LIMIT 1')[0][0]
        self.assertEqual(result.location,'/demo/order/'+token+'/payment')
        return token

    def test_isolated_stock_and_clear_demo_mode(self):
        self.assertEqual(self.query('SELECT stock FROM products',normal=True),[(0,)]*8)
        self.assertEqual(self.query('SELECT stock FROM products'),[(50,)]*8)
        self.assertEqual(self.client.get('/health').json['demo_mode'],True)
        self.assertNotIn(b'class="demo-mode-bar"',self.client.get('/').data)
        normal=self.normal.test_client()
        self.assertFalse(normal.get('/health').json['demo_mode'])
        self.assertNotIn(b'CLIENT DEMO',normal.get('/?demo=1').data)
        self.assertEqual(self.demo.config['SESSION_COOKIE_NAME'],'isazi_client_demo')
        page=self.client.get('/product/1').data
        self.assertIn(b'Back to Shop',page)
        self.assertIn(b'Add to Cart',page)
        self.assertNotIn(b'Enquire about availability',page)
        self.assertIn(b'Enquire about availability',normal.get('/product/1').data)

    def test_sample_accounts_are_private_and_keep_the_cart(self):
        with self.client.session_transaction() as session:session['cart']={'1':1}
        self.post('/demo/account')
        with self.client.session_transaction() as session:
            first=session['customer_id'];self.assertEqual(session['cart'],{'1':1});self.assertFalse(session.get('admin'))
        other=self.demo.test_client();self.post('/demo/account',client=other)
        with other.session_transaction() as session:second=session['customer_id']
        self.assertNotEqual(first,second)
        self.assertNotEqual(*[row[0] for row in self.query('SELECT email FROM customers ORDER BY id')])
        self.assertEqual(self.client.get('/owner').status_code,302)
        self.assertEqual(self.query('SELECT COUNT(*) FROM admins')[0][0],0)

    def test_full_shop_cart_checkout_payment_account_journey_and_replay(self):
        token=self.order()
        select=self.client.get('/demo/order/'+token+'/payment')
        self.assertEqual(select.status_code,200)
        for method in ['visa','mastercard','yoco','ozow','payfast','eft']:
            page=self.client.get('/demo/order/'+token+'/payment/'+method)
            self.assertEqual(page.status_code,200)
            self.assertIn(b'Simulate Successful Payment',page.data)
            self.assertIn(b'No money will be charged or transferred',page.data)
        self.assertEqual(self.query('SELECT COUNT(*) FROM payments_received')[0][0],0)
        with patch('payment_gateway.server_validates',side_effect=AssertionError('A demo must not contact PayFast')):
            result=self.post('/demo/order/'+token+'/payment/visa/complete')
        self.assertEqual(result.status_code,200)
        self.assertIn(b'No money was charged or transferred',result.data)
        self.assertEqual(self.query('SELECT status FROM orders')[0][0],'Paid')
        self.assertEqual(self.query('SELECT amount,method FROM payments_received'),[(40000,'CLIENT DEMO / Visa')])
        self.assertIn(b'ISZ-00001',self.client.get('/account').data)
        self.post('/demo/order/'+token+'/payment/payfast/complete')
        self.assertEqual(self.query('SELECT COUNT(*) FROM payments_received')[0][0],1)
        self.assertEqual(self.query('SELECT COUNT(*) FROM payment_attempts')[0][0],0)
        self.assertEqual(self.query('SELECT stock FROM products WHERE id=1')[0][0],48)
        create_app(self.config)
        self.assertEqual(self.query('SELECT stock FROM products WHERE id=1')[0][0],48)
        self.assertEqual(self.query('SELECT stock FROM products',normal=True),[(0,)]*8)
        self.assertEqual(self.query('SELECT COUNT(*) FROM orders',normal=True)[0][0],0)

    def test_demo_completion_is_unavailable_in_normal_mode(self):
        token=self.order();normal=self.normal.test_client()
        self.assertEqual(normal.get('/demo/account').status_code,404)
        self.assertEqual(normal.get('/demo/order/'+token+'/payment/visa').status_code,404)
        self.assertEqual(self.post('/demo/order/'+token+'/payment/visa/complete',client=normal,follow=False).status_code,404)
        for method in ['visa','mastercard','yoco','ozow','payfast','eft']:
            response=normal.get('/payment-options/'+method)
            self.assertEqual(response.status_code,200)
            self.assertNotIn(b'Simulate Successful Payment',response.data)
        self.assertEqual(self.query('SELECT COUNT(*) FROM payments_received',normal=True)[0][0],0)

    def test_cancelled_order_cannot_be_paid_and_payment_needs_csrf(self):
        token=self.order()
        self.assertEqual(self.client.post('/demo/order/'+token+'/payment/visa/complete').status_code,400)
        self.assertEqual(self.client.get('/demo/order/'+token+'/payment/unknown').status_code,404)
        self.assertEqual(self.client.get('/demo/order/not-a-token/payment/visa').status_code,404)
        with sqlite3.connect(self.demo_db) as db:
            db.execute("UPDATE orders SET status='Cancelled'")
            db.execute('UPDATE products SET stock=50 WHERE id=1')
        self.assertEqual(self.post('/demo/order/'+token+'/payment/visa/complete',follow=False).status_code,409)
        self.assertEqual(self.query('SELECT COUNT(*) FROM payments_received')[0][0],0)
        self.assertEqual(self.query('SELECT stock FROM products WHERE id=1')[0][0],50)

    def test_live_gateway_and_email_settings_are_disabled_in_demo(self):
        with patch.dict(os.environ,{'PAYFAST_ENABLED':'1','PAYFAST_MODE':'live','PUBLIC_BASE_URL':'https://example.com','SMTP_HOST':'real.example.com'}):
            app=create_app(self.config)
        self.assertEqual(app.config['PAYFAST_ENABLED'],'0')
        self.assertEqual(app.config['SMTP_HOST'],'')
        self.assertEqual(app.config['PUBLIC_BASE_URL'],'')
        self.assertFalse(app.config['SESSION_COOKIE_SECURE'])

    def test_demo_launcher_flag_forces_a_separate_data_folder(self):
        base=Path(self.tmp.name)/'launcher-root'
        with patch('app.ROOT',base),patch.dict(os.environ,{'ISAZI_CLIENT_DEMO':'1','DATA_DIR':str(Path(self.normal_db).parent)}):
            app=create_app()
        self.assertEqual(Path(app.config['DATABASE']),base/'instance-client-demo'/'shop.sqlite3')
        self.assertEqual(self.query('SELECT stock FROM products',normal=True),[(0,)]*8)
        self.assertEqual(app.config['SESSION_COOKIE_NAME'],'isazi_client_demo')

    def test_cart_quantity_back_links_and_sample_checkout_details(self):
        self.post('/cart/add/1')
        response=self.post('/cart/update/1',{'quantity':'3'})
        self.assertIn(b'Continue shopping',response.data)
        self.assertIn(b'/checkout/payment-choice',response.data)
        self.assertIn(b'name="payment_method" value="card"',response.data)
        checkout=self.client.get('/checkout')
        self.assertIn(b'value="Demo Customer"',checkout.data)
        self.assertIn(b'Confirm order',checkout.data)
        with self.client.session_transaction() as session:self.assertEqual(session['cart'],{'1':3})
