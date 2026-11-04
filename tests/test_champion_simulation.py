"""Simulated payments credit the champion end to end without real funds."""
import json
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch
from app import create_app
import test_champion_rewards as helpers

class ChampionSimulationTests(unittest.TestCase):
    setUp=helpers.ChampionRewardsTests.setUp
    tearDown=helpers.ChampionRewardsTests.tearDown
    csrf=helpers.ChampionRewardsTests.csrf
    post=helpers.ChampionRewardsTests.post
    owner=helpers.ChampionRewardsTests.owner
    fetch=helpers.ChampionRewardsTests.fetch
    order=helpers.ChampionRewardsTests.order
    register=helpers.ChampionRewardsTests.register

    def prepare(self):
        self.code=self.register();self.post('/agent/logout')
        self.app.config['DEMO_PAYMENTS_ENABLED']=True
        self.order(quantity=3,agent_code=self.code,fulfillment='courier',address='10 Test Road, Johannesburg')
        self.token=self.fetch('SELECT token FROM orders')[0][0]
        self.route='/demo/order/'+self.token+'/payment/visa/complete'
        self.assertEqual(self.fetch('SELECT subtotal,shipping,total FROM orders')[0],(60000,9900,66900))

    def test_simulated_gateway_payment_and_replay_credit_only_link_owner(self):
        self.prepare()
        self.assertEqual(self.fetch('SELECT count(*) FROM champion_test_credits')[0][0],0)
        with patch('payment_gateway.server_validates',side_effect=AssertionError('No gateway calls')):
            self.assertEqual(self.post(self.route).status_code,200)
            self.assertEqual(self.post(self.route).status_code,200)
        self.assertEqual(self.fetch('SELECT agent_id,amount FROM champion_test_credits'),[(1,2850)])
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)
        self.assertEqual(self.fetch('SELECT count(*) FROM payments_received')[0][0],1)
        page=self.post('/agent/login',dict(phone='0601234567',pin='2749')).data
        self.assertIn(b'Credit balance \xe2\x80\x94 TEST',page)
        self.assertIn(b'Real credit: R0.00',page);self.assertIn(b'Simulated credit: R28.50',page)
        self.assertIn(b'Credit ledger',page);self.assertIn(b'Simulated purchase credit',page)
        self.assertIn(b'light\">TEST</strong>',page);self.assertIn(b'ISZ-00001',page)
        self.post('/agent/logout');self.register(phone='0711234567')
        self.assertNotIn(b'R28.50',self.client.get('/agent').data)

    def test_cancelled_simulation_reverses_test_credit(self):
        self.prepare();self.post(self.route);self.owner()
        self.post('/owner/order/1',dict(status='Cancelled'))
        self.assertEqual(self.fetch('SELECT amount FROM champion_test_credits'),[(0,)])
        self.post('/owner/logout')
        self.assertEqual(self.post(self.route,follow=False).status_code,409)

    def test_simulated_refund_recalculates_credit(self):
        self.prepare();self.post(self.route);self.owner();self.client.get('/owner/order/1')
        with self.client.session_transaction() as s:key=s['refund_key_1']
        self.post('/owner/order/1/refund',dict(refund_key=key,goods='100',shipping='0',extra='0',reference='SIM-REFUND',reason='Test return'))
        self.assertEqual(self.fetch('SELECT amount FROM champion_test_credits'),[(2350,)])
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)

    def test_existing_paid_test_order_recovered_once_on_restart(self):
        self.prepare();self.post(self.route)
        with sqlite3.connect(self.db_path) as db:
            db.execute('DELETE FROM champion_test_credits')
            db.execute("DELETE FROM settings WHERE key='_champion_test_credit_backfill_v1'")
        cfg=dict(TESTING=True,DATABASE=self.db_path,UPLOAD_DIR=self.app.config['UPLOAD_DIR'],DEMO_PAYMENTS_ENABLED=True)
        create_app(cfg);create_app(cfg)
        self.assertEqual(self.fetch('SELECT agent_id,amount FROM champion_test_credits'),[(1,2850)])
        self.assertEqual(self.fetch('SELECT count(*) FROM payments_received')[0][0],1)
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)

    def test_pep_test_order_credits_only_after_owner_confirms_payment(self):
        code=self.register();self.post('/agent/logout')
        self.app.config.update(DEMO_PAYMENTS_ENABLED=True,CUSTOMER_CHECKOUT_REQUIRED=True)
        self.client.get('/r/'+code);self.post('/cart/add/1',dict(quantity='3'))
        self.post('/checkout/payment-choice',dict(payment_method='pep'))
        self.post('/account/register',dict(phone='0821234567',pin='5678',confirm_pin='5678',consent='on'))
        self.client.get('/checkout')
        with self.client.session_transaction() as session:key=session['checkout_key']
        branch=json.loads((Path(__file__).parents[1]/'data/paxi_branches.json').read_text())['branches'][0]['code']
        self.post('/checkout',dict(checkout_key=key,name='PEP Buyer',branch_code=branch,consent='on'))
        self.assertEqual(self.fetch('SELECT fulfillment,total FROM orders'),[('pep',62995)])
        self.assertEqual(self.fetch('SELECT count(*) FROM champion_test_credits')[0][0],0)
        self.owner();self.post('/owner/order/1/confirm-eft',dict(bank_reference='SIM-PEP-1',verified='on'));self.post('/owner/order/1/confirm-eft',dict(bank_reference='SIM-PEP-1',verified='on'))
        self.assertEqual(self.fetch('SELECT amount FROM champion_test_credits'),[(2850,)])
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)

    def test_disabling_test_mode_keeps_simulation_out_of_main_balance(self):
        self.prepare();self.post(self.route);self.app.config['DEMO_PAYMENTS_ENABLED']=False
        page=self.post('/agent/login',dict(phone='0601234567',pin='2749')).data
        self.assertNotIn(b'Credit balance \xe2\x80\x94 TEST',page)
        self.assertIn(b'Simulated purchase credits',page)
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)

if __name__=='__main__':unittest.main()
