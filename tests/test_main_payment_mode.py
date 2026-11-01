import sqlite3
import unittest
from app import create_app
import test_store


class MainPaymentModeTests(unittest.TestCase):
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post
    owner=test_store.StoreTests.owner
    fetch=test_store.StoreTests.fetch
    order=test_store.StoreTests.order

    def setUp(self):
        test_store.StoreTests.setUp(self)
        self.app=create_app({'TESTING':True,'DATABASE':self.db_path,'UPLOAD_DIR':self.app.config['UPLOAD_DIR'],'DEMO_PAYMENTS_ENABLED':True,'CUSTOMER_CHECKOUT_REQUIRED':False})
        self.client=self.app.test_client();self.client.get('/')

    def test_main_store_processes_six_simulations_without_sample_accounts_or_revenue(self):
        health=self.client.get('/health').json
        self.assertFalse(health['demo_mode']);self.assertTrue(health['demo_payments_enabled'])
        self.assertNotIn(b'class="demo-mode-bar"',self.client.get('/').data)
        self.assertNotIn(b'CLIENT DEMO',self.client.get('/').data)
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=1')[0][0],20)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM customers')[0][0],0)
        self.post('/account/register',dict(name='Main Customer',email='main@example.com',phone='0601234567',password='main-customer-password',confirm='main-customer-password',consent='on'))
        for method in ['visa','mastercard','yoco','ozow','payfast','eft']:
            self.order(quantity=1,email='main@example.com')
            token=self.fetch('SELECT token FROM orders ORDER BY id DESC')[0][0]
            preview=self.client.get('/demo/order/'+token+'/payment/'+method)
            self.assertIn(b'Simulate Successful Payment',preview.data)
            paid=self.post('/demo/order/'+token+'/payment/'+method+'/complete')
            self.assertIn(b'No money was charged',paid.data)
            self.assertIn(b'PAYMENT TEST ORDER',paid.data)
            self.post('/demo/order/'+token+'/payment/'+method+'/complete')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],6)
        self.assertEqual(self.fetch("SELECT COUNT(*) FROM orders WHERE status='Paid'")[0][0],6)
        self.assertEqual(self.fetch('SELECT SUM(payment_test) FROM order_extra')[0][0],6)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM notifications')[0][0],0)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payment_attempts')[0][0],0)
        self.assertIn(b'Test payment',self.client.get('/account').data)
        self.owner()
        report=self.client.get('/owner/reports?format=csv')
        self.assertNotIn(b'ISZ-00001',report.data)
        self.assertIn(b'Test payment',self.client.get('/owner?view=orders&scope=test').data)
        self.assertIn(b'Yes - simulated',self.client.get('/owner/orders.csv').data)

    def test_switch_off_and_existing_real_order_are_protected(self):
        self.post('/account/register',dict(name='Main Customer',email='main@example.com',phone='0601234567',password='main-customer-password',confirm='main-customer-password',consent='on'))
        self.app.config['DEMO_PAYMENTS_ENABLED']=False
        self.order(quantity=1)
        token=self.fetch('SELECT token FROM orders')[0][0]
        self.app.config['DEMO_PAYMENTS_ENABLED']=True
        self.assertEqual(self.post('/demo/order/'+token+'/payment/visa/complete',follow=False).status_code,409)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],0)
        self.order(quantity=1)
        token=self.fetch('SELECT token FROM orders ORDER BY id DESC')[0][0]
        self.assertEqual(self.post('/pay/'+token,follow=False).status_code,409)
        self.app.config['DEMO_PAYMENTS_ENABLED']=False
        self.assertEqual(self.post('/demo/order/'+token+'/payment/visa/complete',follow=False).status_code,404)

    def test_owner_cannot_log_in_or_register_as_customer_until_signing_out(self):
        self.owner()
        for route in ['/account/login','/account/register','/demo/account']:
            self.assertEqual(self.client.get(route).status_code,302)
            self.assertEqual(self.post(route,{'email':'any@example.com','password':'any-password-long'},follow=False).status_code,403)
        with self.client.session_transaction() as session:
            self.assertTrue(session['admin']);self.assertNotIn('customer_id',session)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM customers')[0][0],0)
        self.post('/owner/logout')
        self.post('/account/register',dict(name='Customer After Logout',email='after@example.com',phone='0601234567',password='customer-password-long',confirm='customer-password-long',consent='on'))
        self.assertEqual(self.client.get('/account').status_code,200)
        with self.client.session_transaction() as session:
            self.assertIn('customer_id',session);self.assertFalse(session.get('admin'))
