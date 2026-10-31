"""Adversarial requests against isolated temporary databases only."""
import unittest
from werkzeug.datastructures import MultiDict
import test_store
import payment_gateway

class ParameterSecurityTests(unittest.TestCase):
    setUp=test_store.StoreTests.setUp
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post

    def test_unicode_csrf_rejected_without_server_error(self):
        response=self.client.post('/owner/login',data={'csrf_token':'🔒','password':'invalid'})
        self.assertEqual(response.status_code,400)

    def test_unicode_checkout_key_rejected_without_server_error(self):
        self.post('/cart/add/1',{'quantity':'1'})
        self.client.get('/checkout')
        response=self.post('/checkout',{'checkout_key':'🔒'},follow=False)
        self.assertEqual(response.status_code,400)

    def test_unicode_payment_signature_fails_closed(self):
        self.assertFalse(payment_gateway.valid_signature([('amount','10.00')],'🔒','secret'))

    def test_duplicate_parameters_rejected_before_cart_mutation(self):
        response=self.client.post('/cart/add/1',data=MultiDict([('csrf_token',self.csrf()),('quantity','1'),('quantity','99')]))
        self.assertEqual(response.status_code,400)
        with self.client.session_transaction() as session:self.assertFalse(session.get('cart'))
        self.assertEqual(self.client.get('/shop?sort=name&sort=price-low').status_code,400)

    def test_resource_limits_on_public_requests(self):
        self.assertEqual(self.client.get('/shop?q='+'x'*9000).status_code,414)
        self.assertEqual(self.client.post('/owner/login',data={'csrf_token':self.csrf(),'password':'x'*70000}).status_code,413)
        self.assertEqual(self.client.post('/owner/login',data={'csrf_token':self.csrf(),'password':'x'*257}).status_code,400)

    def test_injection_sort_and_xss_cannot_escape_query_or_html(self):
        attack='\"><script>alert(1)</script>'
        response=self.client.get('/shop',query_string={'q':attack,'sort':'price; DROP TABLE products;--'})
        self.assertEqual(response.status_code,200)
        self.assertNotIn(b'<script>alert(1)</script>',response.data)
        self.assertEqual(self.client.get('/product/1').status_code,200)
        self.assertEqual(self.client.get('/owner?view=orders&scope=all').status_code,302)
        self.assertIn(self.client.get('/media/../app.py').status_code,(400,404))

    def test_owner_password_reset_revokes_existing_session(self):
        test_store.StoreTests.owner(self)
        self.assertEqual(self.client.get('/owner').status_code,200)
        result=self.app.test_cli_runner().invoke(args=['create-owner','--password','replacement-password-long'])
        self.assertEqual(result.exit_code,0)
        self.assertEqual(self.client.get('/owner').status_code,302)

    def test_owner_large_image_upload_survives_public_limit(self):
        import io, os
        from PIL import Image
        test_store.StoreTests.owner(self)
        data=io.BytesIO()
        Image.frombytes('RGB',(256,256),os.urandom(256*256*3)).save(data,'PNG')
        self.assertGreater(data.tell(),65536)
        data.seek(0)
        response=self.post('/owner/home-images/hero',{'image':(data,'image.png')},follow=False)
        self.assertEqual(response.status_code,302)
        with self.app.app_context():
            import sqlite3
            with sqlite3.connect(self.db_path) as db:
                name=db.execute("SELECT filename FROM home_images WHERE key='hero'").fetchone()[0]
        self.assertTrue(name.startswith('upload-'))

    def test_malformed_tracking_url_is_rejected(self):
        test_store.StoreTests.order(self)
        test_store.StoreTests.owner(self)
        response=self.post('/owner/order/1/delivery',{'delivery_status':'Booked','tracking_url':'https://[invalid'},follow=False)
        self.assertEqual(response.status_code,400)

    def test_malformed_public_base_disables_integration_without_crashing(self):
        self.app.config['PUBLIC_BASE_URL']='https://[invalid'
        self.assertEqual(self.client.get('/').status_code,200)
