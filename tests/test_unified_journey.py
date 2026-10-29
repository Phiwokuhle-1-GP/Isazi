import sqlite3
import unittest
import test_store
from app import create_app


class UnifiedJourneyTests(unittest.TestCase):
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post
    owner=test_store.StoreTests.owner
    fetch=test_store.StoreTests.fetch
    order=test_store.StoreTests.order

    def setUp(self):
        test_store.StoreTests.setUp(self)
        with sqlite3.connect(self.db_path) as db:db.execute('UPDATE products SET stock=0')
        self.config={'TESTING':True,'DATABASE':self.db_path,'UPLOAD_DIR':self.app.config['UPLOAD_DIR'],'DEMO_PAYMENTS_ENABLED':True}
        self.app=create_app(self.config);self.client=self.app.test_client();self.client.get('/')

    def register(self):
        return self.post('/account/register',dict(name='Dry Run Customer',email='dryrun@example.com',phone='0601234567',password='dry-run-password-2026',confirm='dry-run-password-2026',consent='on'))

    def test_zero_real_stock_has_add_to_cart_and_registration_returns_to_product(self):
        for route in ['/','/shop','/product/1']:
            page=self.client.get(route).data
            self.assertIn(b'Add to Cart',page)
            self.assertNotIn(b'Enquire about availability',page)
        self.assertEqual(self.fetch('SELECT stock,presentation_stock FROM products WHERE id=1'),[(0,50)])
        result=self.post('/cart/add/1',follow=False)
        self.assertEqual(result.location,'/account/register')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)
        registered=self.register()
        self.assertIn(b'Smolo Body Cured System',registered.data)
        self.assertIn(b'Back to Shop',registered.data)
        self.order(quantity=2,email='dryrun@example.com')
        token=self.fetch('SELECT token FROM orders')[0][0]
        self.post('/demo/order/'+token+'/payment/visa/complete')
        self.assertEqual(self.fetch('SELECT stock,presentation_stock FROM products WHERE id=1'),[(0,48)])
        self.assertEqual(self.fetch('SELECT payment_test,stock_pool FROM order_extra'),[(1,'presentation')])
        self.assertIn(b'ISZ-00001',self.client.get('/account').data)

    def test_saved_orders_visible_to_owner_reports_restart_and_fulfilment(self):
        self.register();self.order(email='dryrun@example.com')
        token=self.fetch('SELECT token FROM orders')[0][0]
        self.post('/demo/order/'+token+'/payment/ozow/complete')
        self.owner()
        self.assertIn(b'ISZ-00001',self.client.get('/owner').data)
        self.assertIn(b'Saved test orders',self.client.get('/owner').data)
        self.assertIn(b'ISZ-00001',self.client.get('/owner/reports?scope=test&format=csv').data)
        self.assertNotIn(b'ISZ-00001',self.client.get('/owner/reports?scope=real&format=csv').data)
        for status in ['Ready','Completed']:
            self.post('/owner/order/1',dict(status=status))
            self.assertEqual(self.fetch('SELECT status FROM orders')[0][0],status)
        restarted=create_app(self.config)
        self.assertEqual(restarted.test_client().get('/order/'+token).status_code,200)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],1)
        # Cancellation restores the original inventory pool even after switching modes.
        self.app.config['DEMO_PAYMENTS_ENABLED']=False
        self.post('/owner/order/1',dict(status='Cancelled'))
        self.post('/owner/order/1',dict(status='Cancelled'))
        self.assertEqual(self.fetch('SELECT stock,presentation_stock FROM products WHERE id=1'),[(0,50)])
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],1)

    def test_owner_cannot_purchase_and_can_manage_test_inventory(self):
        self.owner()
        page=self.client.get('/product/1').data
        self.assertIn(b'Owner view',page);self.assertNotIn(b'Add to Cart',page)
        for route in ['/cart/add/1','/cart/update/1','/checkout']:
            self.assertEqual(self.post(route,{'quantity':'1'},follow=False).status_code,403)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)
        self.post('/owner/product/1',dict(name='Smolo Body Cured System',category='General Health',price='200.00',description='Approved test description.',stock='0',presentation_stock='25',active='on'))
        self.assertEqual(self.fetch('SELECT stock,presentation_stock FROM products WHERE id=1'),[(0,25)])
        self.post('/owner/logout');self.register()
        self.assertEqual(self.client.get('/account').status_code,200)
        self.assertEqual(self.client.get('/owner').status_code,302)

    def test_checkout_requires_account_and_live_mode_uses_real_stock(self):
        with self.client.session_transaction() as session:session['cart']={'1':1}
        self.assertEqual(self.client.get('/checkout').location,'/account/register')
        self.app.config['DEMO_PAYMENTS_ENABLED']=False
        self.assertNotIn(b'Add to Cart',self.client.get('/product/1').data)
        self.assertEqual(self.fetch('SELECT stock,presentation_stock FROM products WHERE id=1'),[(0,50)])
