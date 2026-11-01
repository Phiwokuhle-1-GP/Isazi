"""Checkout routing and payment isolation against disposable databases."""
import json
import sqlite3
import unittest
from pathlib import Path
import test_store
from app import create_app


class CheckoutJourneyTests(unittest.TestCase):
    tearDown = test_store.StoreTests.tearDown
    csrf = test_store.StoreTests.csrf
    post = test_store.StoreTests.post
    fetch = test_store.StoreTests.fetch
    owner = test_store.StoreTests.owner

    def setUp(self):
        test_store.StoreTests.setUp(self)
        self.app = create_app({'TESTING': True, 'CUSTOMER_CHECKOUT_REQUIRED': True,
                               'DEMO_PAYMENTS_ENABLED': True, 'DATABASE': self.db_path,
                               'UPLOAD_DIR': self.app.config['UPLOAD_DIR']})
        self.client = self.app.test_client()
        self.client.get('/')
        self.post('/cart/add/1', {'quantity': '1'})
        self.branch = json.loads((Path(__file__).parents[1]/'data/paxi_branches.json').read_text())['branches'][0]['code']
        with sqlite3.connect(self.db_path) as db:
            db.execute("INSERT INTO simple_settings(key,value) VALUES('pep_fee','6000')")

    def register(self):
        return self.post('/account/register', {'phone':'0601234567', 'pin':'0456',
                         'confirm_pin':'0456', 'consent':'on'})

    def order(self, **values):
        self.client.get('/checkout')
        with self.client.session_transaction() as s:
            key = s['checkout_key']
        data = dict(checkout_key=key, name='Test Customer', fulfillment='collection', consent='on')
        data.update(values)
        return self.post('/checkout', data, follow=False)

    def test_choice_before_auth_then_branch_after_auth(self):
        choice = self.client.get('/checkout',follow_redirects=True).data
        for method in (b'card', b'paystack', b'ozow', b'pep'):
            self.assertIn(b'value="'+method+b'"', choice)
        self.assertNotIn(b'name="phone"', choice)
        self.assertNotIn(b'name="branch_code"', choice)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM customers')[0][0], 0)
        auth = self.post('/checkout/payment-choice', {'payment_method':'pep'}).data
        self.assertIn(b'name="phone"', auth)
        self.assertNotIn(b'name="branch_code"', auth)
        form = self.register().data
        self.assertIn(b'name="branch_code"', form)
        self.assertIn(b'Place order &amp; view bank details', form)
        self.assertNotIn(b'name="pin"', form)
        with self.client.session_transaction() as s:
            self.assertEqual(s['checkout_method'], 'pep')
            self.assertEqual(s['cart'], {'1':1})

    def test_card_resumes_and_only_simulates_in_test_mode(self):
        self.set_up_new_client('card')
        response = self.order()
        route = response.location
        self.assertTrue(route.endswith('/payment/visa'))
        self.assertIn(b'Simulate Successful Payment', self.client.get(route).data)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],0)
        paid = self.post(route+'/complete')
        self.assertIn(b'Test payment completed',paid.data)
        self.post(route+'/complete')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],1)

    def set_up_new_client(self, method):
        self.post('/checkout/payment-choice', {'payment_method':method})
        self.register()

    def test_paystack_preview_is_selected_without_second_method_choice(self):
        self.set_up_new_client('paystack')
        response=self.order()
        self.assertTrue(response.location.endswith('/payment/paystack'))
        self.assertEqual(self.fetch('SELECT method FROM checkout_payment_choice'),[('paystack',)])

    def test_ozow_preview_is_selected_without_second_method_choice(self):
        self.set_up_new_client('ozow')
        self.assertTrue(self.order().location.endswith('/payment/ozow'))

    def test_pep_requires_branch_and_owner_confirmation_before_dispatch(self):
        self.set_up_new_client('pep')
        response=self.order()
        self.assertEqual(response.status_code,200)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)
        # Forged collection selection is overridden by the server's PEP choice.
        response=self.order(branch_code=self.branch,fulfillment='collection',phone='0719999999')
        self.assertIn('/order/',response.location)
        row=self.fetch('SELECT fulfillment,phone,total FROM orders')[0]
        self.assertEqual(row,('pep','0601234567',25995))
        self.assertIn(b'Awaiting payment confirmation',self.client.get(response.location).data)
        self.assertEqual(self.post('/demo'+response.location+'/payment/visa/complete',follow=False).status_code,409)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM payments_received')[0][0],0)
        self.owner()
        self.post('/owner/order/1/delivery',{'delivery_status':'In transit','tracking_reference':'TEST-PAXI-1'})
        self.assertNotEqual(self.fetch('SELECT delivery_status FROM order_extra')[0][0],'In transit')

    def test_choice_validation_and_csrf_and_live_provider_block(self):
        self.assertEqual(self.client.post('/checkout/payment-choice',data={'payment_method':'pep'}).status_code,400)
        self.assertEqual(self.post('/checkout/payment-choice',{'payment_method':'https://evil.example'},follow=False).status_code,400)
        self.app.config['DEMO_PAYMENTS_ENABLED']=False
        for method in ('card','paystack','ozow'):
            self.assertEqual(self.post('/checkout/payment-choice',{'payment_method':method},follow=False).status_code,409)
        self.assertEqual(self.post('/checkout/payment-choice',{'payment_method':'pep'},follow=False).status_code,302)

    def test_signed_in_skips_auth_and_stale_choice_cannot_use_live_provider(self):
        self.set_up_new_client('card')
        response=self.post('/checkout/payment-choice',{'payment_method':'pep'})
        self.assertIn(b'name="branch_code"',response.data)
        self.assertNotIn(b'name="pin"',response.data)
        self.post('/checkout/payment-choice',{'payment_method':'paystack'})
        self.app.config['DEMO_PAYMENTS_ENABLED']=False
        self.assertIn(b'Choose payment option',self.client.get('/checkout',follow_redirects=True).data)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)

    def test_failed_signin_preserves_choice_and_uses_checkout_account_page(self):
        self.set_up_new_client('pep')
        self.post('/account/logout')
        self.post('/cart/add/1')
        self.post('/checkout/payment-choice',{'payment_method':'pep'})
        login=self.client.get('/account/login')
        self.assertIn(b'Your 4-digit PIN',login.data)
        self.assertNotIn(b'name="branch_code"',login.data)
        failed=self.post('/account/login',{'phone':'0601234567','pin':'9999'})
        self.assertEqual(failed.status_code,400)
        self.assertIn(b'Your 4-digit PIN',failed.data)
        resumed=self.post('/account/login',{'phone':'0601234567','pin':'0456'})
        self.assertIn(b'name="branch_code"',resumed.data)
        with self.client.session_transaction() as session:
            self.assertEqual(session['checkout_method'],'pep')

    def test_owner_cannot_choose_customer_payment(self):
        self.owner()
        self.assertEqual(self.post('/checkout/payment-choice',{'payment_method':'pep'},follow=False).status_code,403)

    def test_cart_payment_cards_continue_directly_to_auth(self):
        page=self.client.get('/cart').data
        self.assertIn(b'name="payment_method" value="card"',page)
        self.assertIn(b'action="/checkout/payment-choice"',page)
        auth=self.post('/checkout/payment-choice',{'payment_method':'card'})
        self.assertIn(b'Continue with your cellphone',auth.data)
        self.assertNotIn(b'data-payment-choice',auth.data)
        self.assertNotIn(b'name="branch_code"',auth.data)
        self.register()
        continued=self.post('/checkout/payment-choice',{'payment_method':'card'})
        self.assertIn(b'Delivery &amp; order details',continued.data)
        self.assertNotIn(b'name="pin"',continued.data)

    def test_courier_fixed_99_and_required_address(self):
        self.set_up_new_client('card')
        missing=self.order(fulfillment='courier')
        self.assertEqual(missing.status_code,200)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)
        response=self.order(fulfillment='courier',address='123 Test Street, Durban, 4001',shipping='0',total='1')
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.fetch('SELECT shipping,total,fulfillment FROM orders')[0],(9900,29900,'courier'))
        token=self.fetch('SELECT token FROM orders')[0][0]
        receipt=self.client.get('/order/'+token).data
        self.assertIn(b'Courier delivery',receipt)
        self.assertNotIn(b'Randburg delivery',receipt)

    def test_courier_99_even_above_600(self):
        self.set_up_new_client('card')
        self.post('/cart/update/1',{'quantity':'4'})
        response=self.order(fulfillment='courier',address='123 Test Street, Cape Town, 8001')
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.fetch('SELECT subtotal,shipping,total FROM orders')[0],(80000,9900,89900))

    def test_collection_stays_free_and_courier_text_is_consistent(self):
        self.set_up_new_client('card')
        for route in ('/cart','/checkout','/policies'):
            page=self.client.get(route).data
            self.assertIn(b'R99',page)
            self.assertNotIn(b'Randburg delivery',page)
            self.assertNotIn(b'Free delivery on orders over R600',page)
        self.order(fulfillment='collection')
        self.assertEqual(self.fetch('SELECT shipping,total FROM orders')[0],(0,20000))

    def test_pep_fixed_fee_display_does_not_need_owner_fee_configuration(self):
        with sqlite3.connect(self.db_path) as db:
            db.execute("DELETE FROM simple_settings WHERE key='pep_fee'")
        self.set_up_new_client('pep')
        page=self.client.get('/checkout').data
        self.assertIn(b'R59.95',page)
        self.assertIn('7–9 business days'.encode(),page)
        self.assertIn(b'role="combobox"',page)
        self.assertNotIn(b'Pricing for smaller orders is being configured',page)
        response=self.order(branch_code=self.branch)
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.fetch('SELECT shipping,total FROM orders')[0],(5995,25995))

    def test_duplicate_selection_page_redirects_to_cart_without_changing_choice(self):
        with self.client.session_transaction() as session:
            session['checkout_method']='pep'
        response=self.client.get('/checkout/payment-choice')
        self.assertEqual(response.status_code,302)
        self.assertEqual(response.location,'/cart#cart-payment-options')
        with self.client.session_transaction() as session:
            self.assertEqual(session['checkout_method'],'pep')
        page=self.client.get(response.location).data
        self.assertIn(b'Choose payment option',page)
        self.assertNotIn(b'Choose how to pay',page)

    def test_checkout_without_choice_returns_to_cart(self):
        response=self.client.get('/checkout')
        self.assertEqual(response.location,'/cart#cart-payment-options')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)

    def test_quick_purchase_without_choice_remains_available_in_cart(self):
        with self.client.session_transaction() as session:
            session['quick_product']=6
            session.pop('checkout_method',None)
        response=self.client.get('/checkout/payment-choice',follow_redirects=True)
        self.assertIn(b'Choose payment option',response.data)
        with self.client.session_transaction() as session:
            self.assertEqual(session['cart']['6'],1)
            self.assertNotIn('quick_product',session)
