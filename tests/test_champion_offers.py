"""End-to-end 5% buyer discount and credit attribution using links or codes."""
import sqlite3
import unittest
import test_store
from champion_offers import parse_code

class ChampionOfferTests(unittest.TestCase):
    setUp=test_store.StoreTests.setUp
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post
    owner=test_store.StoreTests.owner
    fetch=test_store.StoreTests.fetch
    order=test_store.StoreTests.order

    def champion(self,phone='0601234567'):
        self.post('/agent/register',dict(name='Code Owner',phone=phone,pin='2749',confirm_pin='2749',consent='on'))
        code=self.fetch('SELECT code FROM agents ORDER BY id DESC')[0][0]
        self.post('/agent/logout')
        return code

    def submit(self, **extra):
        self.client.get('/checkout')
        with self.client.session_transaction() as s:key=s['checkout_key']
        data=dict(checkout_key=key,name='Buyer Two',email='buyer@example.com',phone='0821234567',fulfillment='collection',address='',consent='on')
        data.update(extra)
        return self.post('/checkout',data)

    def test_raw_code_applies_discount_and_credits_correct_owner_after_payment(self):
        code=self.champion();self.champion(phone='0711234567')
        self.post('/cart/add/1',dict(quantity='3'))
        r=self.post('/cart/coupon',dict(code=code.lower()))
        self.assertIn(b'Champion discount (5%)',r.data);self.assertIn(b'R570.00',r.data)
        self.submit(phone='0821234567')
        self.assertEqual(self.fetch('SELECT subtotal,total FROM orders')[0],(60000,57000))
        self.assertEqual(self.fetch('SELECT discount,agent_id,agent_code,rate_bps FROM order_extra')[0],(3000,1,code,500))
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)
        self.owner();self.post('/owner/order/1',dict(status='Paid'));self.post('/owner/order/1',dict(status='Paid'))
        self.assertEqual(self.fetch('SELECT agent_id,SUM(amount),COUNT(*) FROM commission_ledger GROUP BY agent_id'),[(1,2850,1)])

    def test_full_local_link_pasted_into_promotion_field(self):
        code=self.champion();self.post('/cart/add/1',dict(quantity='3'))
        r=self.post('/cart/coupon',dict(code='http://127.0.0.1:5000/r/'+code))
        self.assertNotIn(b'Enter a valid promotion',r.data);self.assertIn(b'R570.00',r.data)
        with self.client.session_transaction() as s:self.assertEqual(s['referral'],code)

    def test_click_referral_then_quantity_updates_and_checkout(self):
        code=self.champion();self.assertEqual(self.client.get('/r/'+code).status_code,302)
        self.post('/cart/add/1',dict(quantity='3'))
        self.assertIn(b'R570.00',self.client.get('/cart').data)
        self.post('/cart/update/1',dict(quantity='2'))
        self.assertIn(b'R380.00',self.client.get('/cart').data)
        self.submit(fulfillment='courier',address='10 Test Road, Johannesburg 2000')
        self.assertEqual(self.fetch('SELECT subtotal,shipping,total FROM orders')[0],(40000,9900,47900))
        self.owner();self.post('/owner/order/1',dict(status='Paid'))
        self.assertEqual(self.fetch('SELECT SUM(amount) FROM commission_ledger')[0][0],1900)

    def test_link_entered_directly_at_checkout(self):
        code=self.champion();self.order(quantity=3,agent_code='https://isazi.example/r/'+code)
        self.assertEqual(self.fetch('SELECT total FROM orders')[0][0],57000)
        self.assertEqual(self.fetch('SELECT agent_code FROM order_extra')[0][0],code)

    def test_promotion_does_not_stack_and_champion_can_replace_it(self):
        code=self.champion()
        with sqlite3.connect(self.db_path) as db:db.execute("INSERT INTO coupons(code,kind,value,max_uses) VALUES('SAVE10','percent',1000,100)")
        self.client.get('/r/'+code);self.post('/cart/add/1',dict(quantity='3'))
        self.post('/cart/coupon',dict(code='SAVE10'))
        self.assertIn(b'R540.00',self.client.get('/cart').data)
        self.post('/cart/coupon',dict(code=code));self.assertIn(b'R570.00',self.client.get('/cart').data)
        self.post('/cart/coupon',dict(remove='1'));self.assertIn(b'R600.00',self.client.get('/cart').data)
        with self.client.session_transaction() as s:self.assertNotIn('referral',s);self.assertNotIn('coupon',s)

    def test_paused_champion_has_no_discount_or_credit(self):
        code=self.champion();self.client.get('/r/'+code)
        with sqlite3.connect(self.db_path) as db:db.execute('UPDATE agents SET approved=0 WHERE id=1')
        self.assertEqual(self.client.get('/r/'+code).status_code,404)
        self.post('/cart/add/1',dict(quantity='3'))
        self.assertIn(b'unavailable',self.client.get('/cart').data)
        self.order(quantity=3,agent_code=code)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM orders')[0][0],0)

    def test_posted_discount_and_credit_amounts_are_ignored(self):
        code=self.champion();self.order(quantity=3,agent_code=code,discount='60000',credit='999999',rate_bps='10000',total='1')
        self.assertEqual(self.fetch('SELECT total FROM orders')[0][0],57000)
        self.assertEqual(self.fetch('SELECT discount,rate_bps FROM order_extra')[0],(3000,500))

    def test_referral_survives_customer_registration(self):
        code=self.champion();self.client.get('/r/'+code);self.post('/cart/add/1',dict(quantity='3'))
        self.post('/account/register',dict(name='Buyer Two',phone='0821234567',pin='5678',confirm_pin='5678',consent='on'))
        with self.client.session_transaction() as s:self.assertEqual(s['referral'],code)
        self.assertIn(b'R570.00',self.client.get('/cart').data)

    def test_test_order_discount_and_simulated_credit(self):
        code=self.champion();self.app.config['DEMO_PAYMENTS_ENABLED']=True
        self.order(quantity=3,agent_code=code);self.owner();self.post('/owner/order/1',dict(status='Paid'))
        self.assertEqual(self.fetch('SELECT total FROM orders')[0][0],57000)
        self.assertEqual(self.fetch('SELECT agent_id,amount FROM champion_test_credits')[0],(1,2850))
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM commission_ledger')[0][0],0)

    def test_query_referral_and_expiry(self):
        code=self.champion();self.client.get('/shop?ref='+code);self.post('/cart/add/1',dict(quantity='3'))
        self.assertIn(b'R570.00',self.client.get('/cart').data)
        with self.client.session_transaction() as s:s['referral_at']=0
        self.assertIn(b'R600.00',self.client.get('/cart').data)

    def test_invalid_input_preserves_existing_code(self):
        code=self.champion();self.client.get('/r/'+code);self.post('/cart/add/1',dict(quantity='3'))
        r=self.post('/cart/coupon',dict(code='javascript:alert(1)'))
        self.assertIn(b'R570.00',r.data)
        with self.client.session_transaction() as s:self.assertEqual(s['referral'],code)

class ReferralParserTests(unittest.TestCase):
    def test_code_links_and_untrusted_input(self):
        for value in ['isz-ABC123','http://127.0.0.1:5000/r/ISZ-ABC123','https://shop.example/r/isz-abc123/?utm_source=test','/r/ISZ-ABC123']:
            self.assertEqual(parse_code(value),'ISZ-ABC123')
        for value in ['javascript:ISZ-ABC123','https://user:secret@example.com/r/ISZ-ABC123','https://example.com/r/../../ISZ-ABC123','https://example.com/r/ISZ%2FABC123','x'*501,'https://example.com/r/ß123','abc\n123','//example.com/r/ISZ-ABC123']:
            self.assertEqual(parse_code(value),'',value)

if __name__=='__main__':unittest.main()
