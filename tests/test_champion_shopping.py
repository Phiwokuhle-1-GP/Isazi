"""One authenticated champion account can shop without customer registration."""
import json
import unittest
from pathlib import Path
from contextlib import closing
import sqlite3
import test_champion_rewards as helpers

class ChampionShoppingTests(unittest.TestCase):
    setUp=helpers.ChampionRewardsTests.setUp
    tearDown=helpers.ChampionRewardsTests.tearDown
    csrf=helpers.ChampionRewardsTests.csrf
    post=helpers.ChampionRewardsTests.post
    fetch=helpers.ChampionRewardsTests.fetch
    register=helpers.ChampionRewardsTests.register

    def setup_flow(self):
        self.app.config.update(DEMO_PAYMENTS_ENABLED=True,CUSTOMER_CHECKOUT_REQUIRED=True)
        code=self.register();self.client.get('/r/'+code)
        self.post('/cart/add/1',dict(quantity='3'))
        return code

    def checkout(self,method='card'):
        response=self.post('/checkout/payment-choice',dict(payment_method=method))
        self.assertIn(b'name="checkout_key"',response.data)
        self.assertNotIn(b'name="confirm_pin"',response.data)
        self.assertNotIn(b'name="email"',response.data)
        with self.client.session_transaction() as session:key=session['checkout_key']
        data=dict(checkout_key=key,name='Champion One',fulfillment='collection',consent='on',phone='0719999999',email='forged@example.com')
        if method=='pep':data['branch_code']=json.loads((Path(__file__).parents[1]/'data/paxi_branches.json').read_text())['branches'][0]['code']
        return self.post('/checkout',data)

    def test_registration_has_shop_cta_and_card_payment_without_second_signup(self):
        code=self.setup_flow();page=self.client.get('/agent').data
        self.assertIn(b'Shop now',page);self.assertIn(('/r/'+code).encode(),page)
        self.checkout()
        self.assertEqual(self.fetch('SELECT count(*) FROM customers'),[(1,)])
        self.assertEqual(self.fetch('SELECT phone,total FROM orders'),[('0601234567',57000)])
        self.assertIsNotNone(self.fetch('SELECT customer_id FROM order_extra')[0][0])
        token=self.fetch('SELECT token FROM orders')[0][0]
        self.post('/demo/order/'+token+'/payment/visa/complete')
        self.assertEqual(self.fetch('SELECT amount FROM champion_test_credits'),[(2850,)])
        self.assertIn(b'ISZ-00001',self.client.get('/account').data)

    def test_pep_checkout_uses_champion_phone_and_branch_without_signup(self):
        self.setup_flow();self.checkout('pep')
        self.assertEqual(self.fetch('SELECT fulfillment,phone,total FROM orders'),[('pep','0601234567',62995)])

    def test_returning_champion_login_reuses_profile_and_keeps_cart(self):
        self.setup_flow();self.post('/agent/logout');self.post('/cart/add/1',dict(quantity='1'))
        self.post('/agent/login',dict(phone='0601234567',pin='2749'))
        with self.client.session_transaction() as session:self.assertEqual(session['cart'],{'1':1})
        self.post('/checkout/payment-choice',dict(payment_method='card'))
        self.assertIn(b'name="checkout_key"',self.client.get('/checkout').data)
        self.assertEqual(self.fetch('SELECT count(*) FROM champion_customers'),[(1,)])
        self.assertEqual(self.fetch('SELECT count(*) FROM customers'),[(1,)])

    def test_existing_same_phone_customer_is_not_silently_linked(self):
        self.app.config['DEMO_PAYMENTS_ENABLED']=True
        self.post('/account/register',dict(phone='0601234567',pin='5678',confirm_pin='5678',preference='gateway',consent='on'))
        original=self.fetch('SELECT id FROM customers')[0][0]
        self.post('/account/logout');self.register()
        self.assertNotEqual(self.fetch('SELECT customer_id FROM champion_customers')[0][0],original)
        with self.client.session_transaction() as session:
            session['customer_id']=original;session['customer_version']=0
        page=self.client.get('/account').data
        self.assertEqual(self.fetch('SELECT count(*) FROM customers'),[(2,)])
        self.assertIn(b'Welcome, Champion One.',page)

    def test_registration_preserves_existing_cart_and_order_choice(self):
        self.app.config.update(DEMO_PAYMENTS_ENABLED=True,CUSTOMER_CHECKOUT_REQUIRED=True)
        self.post('/cart/add/1',dict(quantity='2'))
        self.post('/checkout/payment-choice',dict(payment_method='card'))
        self.register()
        with self.client.session_transaction() as session:
            self.assertEqual(session['cart'],{'1':2})
            self.assertEqual(session['checkout_method'],'card')
        self.assertIn(b'name="checkout_key"',self.client.get('/checkout').data)

    def test_paused_or_stale_champion_cannot_use_shopping_identity(self):
        self.setup_flow()
        with closing(sqlite3.connect(self.db_path)) as db,db:db.execute('UPDATE agents SET auth_version=auth_version+1')
        page=self.post('/checkout/payment-choice',dict(payment_method='card')).data
        self.assertNotIn(b'name="checkout_key"',page)
        self.assertEqual(self.client.get('/account').status_code,302)

if __name__=='__main__':unittest.main()
