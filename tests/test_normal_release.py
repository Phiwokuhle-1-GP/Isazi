"""The normal storefront uses the current UI and real owner-managed inventory."""
import sqlite3
import unittest
import test_store


class NormalReleaseTests(unittest.TestCase):
    setUp=test_store.StoreTests.setUp
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post
    owner=test_store.StoreTests.owner
    fetch=test_store.StoreTests.fetch

    def test_normal_owner_stock_to_customer_cart_order_and_account(self):
        with sqlite3.connect(self.db_path) as db:db.execute('UPDATE products SET stock=0')
        self.owner()
        owner_page=self.client.get('/owner').data
        self.assertIn(b'Normal store',owner_page)
        self.assertIn(b'View storefront',owner_page)
        self.post('/owner/product/1',dict(name='Smolo Body Cured System',category='General Health',price='200.00',description='Approved test product information.',stock='7',active='on'))
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=1')[0][0],7)
        self.post('/owner/logout')
        self.client.get('/account/register')
        self.post('/account/register',dict(name='Normal Customer',email='normal@example.com',phone='0601234567',password='normal-customer-password',confirm='normal-customer-password',consent='on'))
        page=self.client.get('/product/1').data
        self.assertIn(b'Back to Shop',page);self.assertIn(b'Add to Cart',page)
        self.assertNotIn(b'Enquire about availability',page)
        result=self.post('/cart/add/1',dict(quantity='4'))
        self.assertIn(b'Your Shopping Cart',result.data)
        self.client.get('/checkout')
        with self.client.session_transaction() as s:key=s['checkout_key']
        result=self.post('/checkout',dict(checkout_key=key,name='Normal Customer',email='normal@example.com',phone='0601234567',fulfillment='randburg',address='123 Normal Street, Randburg',consent='on'))
        self.assertIn(b'ORDER RECEIVED',result.data);self.assertIn(b'View Payment Options',result.data)
        self.assertNotIn(b'DEMO ORDER',result.data)
        self.assertEqual(self.fetch('SELECT total,shipping,status FROM orders'),[(89900,9900,'Awaiting confirmation')])
        self.assertEqual(self.fetch('SELECT stock FROM products WHERE id=1')[0][0],3)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],0)
        self.assertIn(b'ISZ-00001',self.client.get('/account').data)
        token=self.fetch('SELECT token FROM orders')[0][0]
        for method in ['visa','mastercard','yoco','ozow','payfast','eft']:
            self.assertEqual(self.client.get('/payment-options/'+method).status_code,200)
            self.assertNotIn(b'Simulate Successful Payment',self.client.get('/payment-options/'+method).data)
            self.assertEqual(self.post('/demo/order/'+token+'/payment/'+method+'/complete',follow=False).status_code,404)
        self.assertFalse(self.client.get('/health').json['demo_mode'])

    def test_normal_home_has_latest_shared_visuals_and_owner_media_controls(self):
        page=self.client.get('/').data
        for item in [b'hero-natural-meadow.webp',b'dr-ntuli-original.png',b'hero-right-photo',b'Listen to testimonials',b'testimonials-title-tile',b'testimonials-grid',b'Courier delivery',b'Nationwide delivery',b'footer-socials',b'demo-product-1.webp']:
            self.assertIn(item,page)
        self.assertNotIn(b'CLIENT DEMO',page)
        with self.client.get('/static/css/ecosystem.css') as css:
            self.assertIn(b'var(--yellow)',css.data)
        self.owner()
        for route in ['/owner/home-images','/owner/media','/owner/settings','/owner/integrations']:
            response=self.client.get(route)
            self.assertEqual(response.status_code,200,route)
        self.assertIn(b'social_instagram',self.client.get('/owner/settings').data)
        self.assertIn(b'payment-options',self.client.get('/owner/integrations').data)
