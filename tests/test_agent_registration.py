"""Agent application approval and access tests against disposable databases."""
import unittest
from werkzeug.security import check_password_hash
import test_store
from app import create_app

class AgentRegistrationTests(unittest.TestCase):
    setUp=test_store.StoreTests.setUp
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post
    owner=test_store.StoreTests.owner
    fetch=test_store.StoreTests.fetch

    def apply(self, **extra):
        data=dict(name='Agent Applicant',phone='0601234567',pin='2749',confirm_pin='2749',consent='on')
        data.update(extra)
        return self.post('/agent/register',data)

    def test_footer_and_registration_page(self):
        self.assertGreaterEqual(self.client.get('/').data.count(b'href="/agent/register"'),2)
        self.assertIn(b'Become a product champion',self.client.get('/agent/register').data)

    def test_immediate_activation_hashed_pin_cannot_choose_rate(self):
        response=self.apply(approved='on',code='HACKED',rate='100')
        self.assertIn(b'PRODUCT CHAMPION PORTAL',response.data)
        a=self.fetch('SELECT approved,rate_bps,code FROM agents')[0]
        self.assertEqual(a[:2],(1,500));self.assertTrue(a[2].startswith('ISZ-'))
        hashed=self.fetch('SELECT pin_hash FROM agent_phone_accounts')[0][0]
        self.assertNotEqual(hashed,'2749');self.assertTrue(check_password_hash(hashed,'2749'))
        self.assertIn(a[2].encode(),response.data)
        self.assertEqual(self.client.get('/agent').status_code,200)
        self.assertEqual(self.client.get('/owner/agents').status_code,302)

    def test_owner_rate_updates_preserve_code_and_portal(self):
        self.apply();applicant=self.app.test_client()
        with self.client.session_transaction() as s:saved=dict(s)
        with applicant.session_transaction() as s:s.update(saved)
        self.owner();self.post('/owner/agents/1',dict(approved='on',rate='10'))
        code=self.fetch('SELECT code FROM agents')[0][0]
        self.assertTrue(code.startswith('ISZ-'));self.assertEqual(len(code),20)
        self.assertIsNotNone(self.fetch('SELECT code_issued_at FROM agent_phone_accounts')[0][0])
        self.post('/owner/agents/1',dict(approved='on',rate='12'))
        self.assertEqual(code,self.fetch('SELECT code FROM agents')[0][0])
        portal=applicant.get('/agent',follow_redirects=True)
        self.assertIn(code.encode(),portal.data);self.assertIn(b'PRODUCT CHAMPION PORTAL',portal.data)
        self.assertNotIn(b'pin_hash',portal.data)
        self.assertEqual(applicant.get('/owner').status_code,302)

    def test_cellphone_login_needs_no_approval(self):
        self.apply();self.post('/agent/logout')
        self.assertIn(b'PRODUCT CHAMPION PORTAL',self.post('/agent/login',dict(phone='+27 60 123 4567',pin='2749')).data)
        self.owner();self.post('/owner/agents/1',dict(approved='on',rate='10'));self.post('/owner/logout')
        self.assertIn(b'PRODUCT CHAMPION PORTAL',self.post('/agent/login',dict(phone='0601234567',pin='2749')).data)

    def test_duplicate_normalized_phone_keeps_original_pin(self):
        self.apply();self.post('/agent/logout')
        self.assertEqual(self.apply(phone='+27 60 123 4567',pin='9999',confirm_pin='9999').status_code,400)
        self.assertEqual(self.fetch('SELECT count(*) FROM agents')[0][0],1)
        self.assertTrue(check_password_hash(self.fetch('SELECT pin_hash FROM agent_phone_accounts')[0][0],'2749'))

    def test_invalid_pin_phone_and_consent(self):
        for change in [dict(pin='abc1',confirm_pin='abc1'),dict(phone='xyz'),dict(pin='12345',confirm_pin='12345'),dict(confirm_pin='9999'),dict(consent='')]:
            self.assertEqual(self.apply(**change).status_code,400)
        self.assertEqual(self.fetch('SELECT count(*) FROM agents')[0][0],0)

    def test_csrf_and_owner_only_approval(self):
        self.assertEqual(self.client.post('/agent/register',data=dict(name='No CSRF')).status_code,400)
        self.apply()
        self.assertEqual(self.post('/owner/agents/1',dict(approved='on',rate='100'),follow=False).status_code,302)
        self.assertEqual(self.fetch('SELECT rate_bps FROM agents')[0][0],500)

    def test_pin_throttle_across_ips(self):
        self.apply();self.post('/agent/logout')
        for i in range(5):
            with self.client.session_transaction() as s:token=s['csrf']
            r=self.client.post('/agent/login',data=dict(csrf_token=token,phone='0601234567',pin='0000'),environ_overrides={'REMOTE_ADDR':f'10.0.0.{i+1}'})
            self.assertEqual(r.status_code,400)
        self.assertEqual(self.post('/agent/login',dict(phone='0601234567',pin='2749')).status_code,429)

    def test_pause_and_reapproval_revoke_old_session(self):
        self.apply();self.owner();self.post('/owner/agents/1',dict(approved='on',rate='10'));self.post('/owner/logout')
        self.post('/agent/login',dict(phone='0601234567',pin='2749'))
        with self.client.session_transaction() as s:old=dict(s)
        self.owner();self.post('/owner/agents/1',dict(rate='10'));self.post('/owner/agents/1',dict(approved='on',rate='10'))
        with self.client.session_transaction() as s:s.clear();s.update(old)
        self.assertEqual(self.client.get('/agent').status_code,302)

    def test_registration_rate_limit(self):
        for _ in range(5):self.apply(pin='bad')
        self.assertEqual(self.apply().status_code,429)

    def test_restart_preserves_application(self):
        self.apply()
        fresh=create_app(dict(TESTING=True,DATABASE=self.db_path,UPLOAD_DIR=self.app.config['UPLOAD_DIR']))
        self.assertIn(b'Product champion sign in',fresh.test_client().get('/agent/login').data)
        self.assertEqual(self.fetch('SELECT count(*) FROM agent_phone_accounts')[0][0],1)

if __name__=='__main__':unittest.main()
