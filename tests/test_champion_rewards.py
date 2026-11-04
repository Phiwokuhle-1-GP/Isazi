"""Champion credits and SMS transport tests; no live messages are sent."""
from contextlib import closing
import sqlite3
import unittest
from unittest.mock import Mock
from werkzeug.security import generate_password_hash
import test_store
from app import create_app

class ChampionRewardsTests(unittest.TestCase):
    setUp=test_store.StoreTests.setUp
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post
    owner=test_store.StoreTests.owner
    fetch=test_store.StoreTests.fetch
    order=test_store.StoreTests.order

    def register(self,phone='0601234567'):
        r=self.post('/agent/register',dict(name='Champion One',phone=phone,pin='2749',confirm_pin='2749',consent='on'))
        self.assertEqual(r.status_code,200)
        return self.fetch('SELECT code FROM agents ORDER BY id DESC')[0][0]

    def paid(self,test=False,**extra):
        code=self.register();self.post('/agent/logout');self.app.config['DEMO_PAYMENTS_ENABLED']=test
        self.order(agent_code=code,**extra);self.owner();self.post('/owner/order/1',dict(status='Paid'))
        return code

    def sms(self,enabled=True,fail=False):
        self.app.testing=False;self.app.config.update(DEMO_PAYMENTS_ENABLED=False,DEMO_MODE=False)
        cfg=dict(sms_enabled='1' if enabled else '0',sms_sid='AC'+'b'*32,sms_token='c'*32,sms_from='+27123456789')
        sender=Mock(side_effect=TimeoutError()) if fail else Mock(return_value='SM'+'a'*32)
        self.app.extensions['simple_checkout']['sms_config']=lambda:cfg
        self.app.extensions['simple_checkout']['send_text']=sender
        return sender,cfg

    def test_immediate_code_five_percent_confirmation_no_pin_or_test_send(self):
        sender=Mock();self.app.extensions['simple_checkout']['send_text']=sender
        code=self.register();row=self.fetch('SELECT recipient,body,status FROM champion_sms')[0]
        self.assertIn(code,row[1]);self.assertIn('5%',row[1]);self.assertNotIn('2749',row[1].replace(code,''))
        self.assertEqual(row[2],'Test - not sent');sender.assert_not_called()
        self.assertEqual(self.fetch('SELECT approved,rate_bps FROM agents')[0],(1,500))

    def test_five_percent_excludes_delivery_and_posts_once(self):
        code=self.register();self.post('/agent/logout');self.order(agent_code=code,fulfillment='courier',address='10 Test Road, Johannesburg')
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)
        subtotal,shipping=self.fetch('SELECT subtotal,shipping FROM orders')[0];self.assertEqual(shipping,9900)
        self.owner();self.post('/owner/order/1',dict(status='Paid'));self.post('/owner/order/1',dict(status='Paid'))
        self.assertEqual(self.fetch('SELECT SUM(amount),count(*) FROM commission_ledger')[0],(subtotal*9500//10000*500//10000,1))
        self.assertEqual(self.fetch('SELECT count(*) FROM champion_test_credits')[0][0],0)
        self.post('/owner/logout');page=self.post('/agent/login',dict(phone='0601234567',pin='2749'))
        self.assertIn(b'R9.50',page.data)

    def test_existing_order_rate_snapshot_and_future_rate(self):
        code=self.register();self.post('/agent/logout');self.order(agent_code=code)
        self.owner();self.post('/owner/agents/1',dict(approved='on',rate='7.5'));self.post('/owner/order/1',dict(status='Paid'))
        self.assertEqual(self.fetch('SELECT rate_bps FROM order_extra')[0][0],500)
        subtotal=self.fetch('SELECT subtotal FROM orders')[0][0]
        self.assertEqual(self.fetch('SELECT SUM(amount) FROM commission_ledger')[0][0],subtotal*9500//10000*500//10000)
        self.post('/owner/logout');self.order(agent_code=code)
        self.assertEqual(self.fetch('SELECT rate_bps FROM order_extra ORDER BY order_id DESC')[0][0],750)

    def test_owner_adjustable_default_new_accounts_only(self):
        self.register();self.post('/agent/logout')
        self.assertEqual(self.post('/owner/champions/settings',dict(rate='95'),follow=False).status_code,302)
        self.owner();self.post('/owner/champions/settings',dict(rate='6.5'));self.post('/owner/logout');self.register(phone='0711234567')
        self.assertEqual(self.fetch('SELECT rate_bps FROM agents ORDER BY id'),[(500,),(650,)])
        self.owner();self.post('/owner/champions/settings',dict(rate='101'))
        self.assertEqual(self.fetch("SELECT value FROM settings WHERE key='champion_default_bps'")[0][0],'650')

    def test_cancellation_reverses_credit(self):
        self.paid();self.post('/owner/order/1',dict(status='Cancelled'))
        self.assertEqual(self.fetch('SELECT SUM(amount) FROM commission_ledger')[0][0],0)

    def test_partial_refund_reduces_credit(self):
        self.paid();self.client.get('/owner/order/1')
        with self.client.session_transaction() as s:key=s['refund_key_1']
        self.post('/owner/order/1/refund',dict(refund_key=key,goods='100',shipping='0',extra='0',reference='CREDIT-REFUND-1',reason='Partial goods returned'))
        subtotal=self.fetch('SELECT subtotal FROM orders')[0][0]
        self.assertEqual(self.fetch('SELECT SUM(amount) FROM commission_ledger')[0][0],(subtotal*9500//10000-10000)*5//100)

    def test_simulated_credit_separate_from_real_ledger(self):
        self.paid(test=True);subtotal=self.fetch('SELECT subtotal FROM orders')[0][0]
        self.assertEqual(self.fetch('SELECT amount FROM champion_test_credits')[0][0],subtotal*9500//10000*500//10000)
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)
        self.post('/owner/logout');r=self.post('/agent/login',dict(phone='0601234567',pin='2749'))
        self.assertIn(b'Simulated purchase credits',r.data);self.assertIn(b'cannot be spent or withdrawn',r.data)

    def test_live_sms_provider_acceptance_no_replay(self):
        sender,cfg=self.sms();self.register();self.assertEqual(sender.call_count,1)
        self.assertEqual(self.fetch('SELECT status FROM champion_sms')[0][0],'Provider accepted')
        self.client.get('/agent');self.owner();self.assertEqual(self.post('/owner/champions/1/sms').status_code,409)
        self.assertEqual(sender.call_count,1)

    def test_unconfigured_sms_keeps_code_and_manual_send_when_ready(self):
        sender,cfg=self.sms(enabled=False);self.register();sender.assert_not_called()
        self.assertEqual(self.fetch('SELECT status FROM champion_sms')[0][0],'Queued')
        cfg['sms_enabled']='1';self.owner();self.post('/owner/champions/1/sms');self.assertEqual(sender.call_count,1)

    def test_uncertain_sms_no_retry(self):
        sender,cfg=self.sms(fail=True);self.register();self.client.get('/agent')
        self.assertEqual(self.fetch('SELECT status FROM champion_sms')[0][0],'Sending - reconcile before retry')
        self.assertEqual(sender.call_count,1)

    def test_migration_pending_only_and_no_startup_sms(self):
        code=self.register()
        with closing(sqlite3.connect(self.db_path)) as db, db:
            db.execute('UPDATE agents SET approved=0 WHERE id=1')
            aid=db.execute("INSERT INTO agents(name,email,code,rate_bps,approved) VALUES('Pending','','PENDING-OLD',0,0)").lastrowid
            db.execute('INSERT INTO agent_phone_accounts(agent_id,phone,pin_hash) VALUES(?,?,?)',(aid,'0711234567',generate_password_hash('1111')))
        create_app(dict(TESTING=True,DATABASE=self.db_path,UPLOAD_DIR=self.app.config['UPLOAD_DIR']))
        rows=self.fetch('SELECT approved,rate_bps,code FROM agents ORDER BY id')
        self.assertEqual(rows[0],(0,500,code));self.assertEqual(rows[1][:2],(1,500));self.assertTrue(rows[1][2].startswith('ISZ-'))

if __name__=='__main__':unittest.main()
