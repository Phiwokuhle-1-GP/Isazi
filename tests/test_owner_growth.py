"""Exercise real checkout handlers and owner views against disposable databases."""
from contextlib import closing
import sqlite3
import unittest
import test_checkout_journey


class OwnerGrowthTests(unittest.TestCase):
    def setUp(self):
        self.shop = test_checkout_journey.CheckoutJourneyTests()
        self.shop.setUp()
        self.app, self.client = self.shop.app, self.shop.client
        with closing(sqlite3.connect(self.shop.db_path)) as db, db:
            db.execute('DELETE FROM growth_events')

    def tearDown(self):
        self.shop.tearDown()

    def data(self, scope='all'):
        from flask import template_rendered
        captured = []
        def capture(sender, template, context, **kwargs):
            if template.name == 'owner_growth.html':
                captured.append(context['growth'])
        template_rendered.connect(capture, self.app)
        try:
            response = self.client.get('/owner/growth?scope='+scope)
        finally:
            template_rendered.disconnect(capture, self.app)
        self.assertEqual(response.status_code,200)
        return captured[0]

    def test_gateway_simulation_reaches_owner_sales_once(self):
        self.client.get('/product/1')
        self.shop.set_up_new_client('card')
        response = self.shop.order()
        self.shop.post(response.location+'/complete')
        self.shop.post(response.location+'/complete')
        self.shop.owner()
        data = self.data()
        self.assertEqual((data['sales'],data['test_sales'],data['real_sales']),(20000,20000,0))
        self.assertEqual(len(data['confirmed']),1)
        self.assertEqual(data['top'][0]['units'],1)
        self.assertEqual(self.data('real')['sales'],0)
        self.assertEqual(self.data('test')['sales'],20000)
        page=self.client.get('/owner').text
        self.assertIn('Testing phase',page)
        self.assertIn('TEST · simulated',page)
        self.assertIn('R200.00',page)

    def test_pep_pending_confirm_and_dispatch_use_test_records(self):
        self.shop.set_up_new_client('pep')
        self.shop.order(fulfillment='pep',branch_code=self.shop.branch)
        self.shop.owner()
        pending = self.data('test')
        self.assertEqual(len(pending['pep_pending']),1)
        self.assertEqual(pending['sales'],0)
        order_id=pending['pep_pending'][0]['id']
        self.shop.post(f'/owner/order/{order_id}/confirm-eft',{'bank_reference':'TEST-RECEIPT-1','verified':'on'})
        self.shop.post(f'/owner/order/{order_id}/confirm-eft',{'bank_reference':'TEST-RECEIPT-1','verified':'on'})
        data=self.data()
        self.assertEqual(len(data['pep_pending']),0)
        self.assertEqual(data['test_sales'],25995)
        self.assertEqual(len(data['dispatch']),1)
        self.assertEqual(self.shop.fetch('SELECT COUNT(*) FROM payments_received')[0][0],1)
        self.assertTrue(all(row[0]=='Test - not sent' for row in self.shop.fetch('SELECT status FROM sms_outbox')))
        self.assertEqual(self.shop.fetch('SELECT stock,presentation_stock FROM products WHERE id=1'),[(20,49)])
        for status in ('In transit','Collected'):
            self.shop.post(f'/owner/order/{order_id}/delivery',{'delivery_status':status,
                           'courier':'TEST PAXI','tracking_reference':'TEST-PAXI-123','tracking_url':''})
        self.assertEqual(len(self.data()['dispatch']),0)
        self.assertEqual(self.data()['test_sales'],25995)
        self.assertIn('Collected',self.client.get(f'/owner/order/{order_id}').text)
        self.assertTrue(all(row[0]=='Test - not sent' for row in self.shop.fetch('SELECT status FROM sms_outbox')))

    def test_traffic_uses_cookie_without_pii_and_honours_exclusions(self):
        self.client.get('/product/1?phone=0601234567',headers={'User-Agent':'Mozilla Chrome/120 Mobile','Referer':'https://www.tiktok.com/campaign?email=private@example.com'})
        self.client.get('/product/1')
        with closing(sqlite3.connect(self.shop.db_path)) as db, db:
            rows=db.execute('SELECT event,page,scope,hits FROM growth_events WHERE event="product_view"').fetchall()
            self.assertEqual(rows,[('product_view','product:1','test',2)])
            text=str(db.execute('SELECT * FROM growth_events').fetchall())
            self.assertNotIn('0601234567',text)
            self.assertNotIn('private@example.com',text)
            count=db.execute('SELECT SUM(hits) FROM growth_events').fetchone()[0]
        self.client.get('/',headers={'DNT':'1'})
        self.client.get('/',headers={'User-Agent':'Googlebot'})
        self.shop.owner()
        self.client.get('/')
        with closing(sqlite3.connect(self.shop.db_path)) as db, db:
            self.assertEqual(db.execute('SELECT SUM(hits) FROM growth_events').fetchone()[0],count)
        self.assertEqual(self.data('real')['visitors'],0)
        self.assertGreaterEqual(self.data('test')['visitors'],1)

    def test_filters_owner_access_and_csv_are_safe(self):
        self.assertEqual(self.client.get('/owner/growth').status_code,302)
        self.assertEqual(self.client.get('/owner/growth/export.csv').status_code,302)
        self.shop.owner()
        data=self.data("test' OR 1=1 --")
        self.assertEqual(data['scope'],'all')
        response=self.client.get('/owner/growth?days=999999&scope=test')
        self.assertEqual(response.status_code,200)
        self.assertIn('no-store',response.headers['Cache-Control'])
        response=self.client.get('/owner/growth/export.csv?scope=test')
        self.assertIn('Simulated confirmed sales',response.text)
        self.assertNotIn('0601234567',response.text)

    def test_stock_scope_and_cancelled_orders(self):
        with closing(sqlite3.connect(self.shop.db_path)) as db, db:
            db.execute('UPDATE products SET stock=20,presentation_stock=20')
            db.execute('UPDATE products SET presentation_stock=2 WHERE id=1')
            db.execute('UPDATE products SET stock=1 WHERE id=2')
        self.shop.set_up_new_client('card')
        response=self.shop.order()
        self.shop.post(response.location+'/complete')
        with closing(sqlite3.connect(self.shop.db_path)) as db, db:
            db.execute("UPDATE orders SET status='Cancelled'")
        self.shop.owner()
        self.assertEqual(self.data()['sales'],0)
        self.assertEqual([row['id'] for row in self.data('test')['stocks']],[1])
        self.assertEqual([row['id'] for row in self.data('real')['stocks']],[2])

    def test_checkout_stages_are_recorded_and_payment_counts_are_not_pageviews(self):
        self.client.get('/product/1')
        self.shop.post('/cart/add/1',{'quantity':'1'})
        self.shop.set_up_new_client('card')
        self.client.get('/checkout')
        self.shop.owner()
        counts=dict(self.data('test')['funnel'])
        self.assertEqual(counts['Product viewers'],1)
        self.assertEqual(counts['Added to cart'],1)
        self.assertEqual(counts['Reached checkout'],1)
