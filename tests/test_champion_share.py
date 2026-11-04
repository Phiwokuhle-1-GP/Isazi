"""Owner registration sharing keeps recruitment separate from buyer referrals."""
import unittest
import test_store

class ChampionShareTests(unittest.TestCase):
    setUp=test_store.StoreTests.setUp
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post
    owner=test_store.StoreTests.owner
    fetch=test_store.StoreTests.fetch

    def test_owner_sees_champions_navigation_and_public_tiktok_link(self):
        self.owner();page=self.client.get('/owner/agents').data
        self.assertIn(b'>Champions</a>',page);self.assertNotIn(b'>Sales agents</a>',page)
        self.assertIn(b'https://isazi-herbal-shop-client-portal.onrender.com/agent/register?utm_source=tiktok',page)
        self.assertIn(b'Copy link',page);self.assertIn(b'Create registration link',page)
        self.assertIn(b'/static/champion-share.js',page)
        self.assertNotIn(b'http://localhost/agent/register',page)

    def test_configured_public_domain_used(self):
        self.app.config['PUBLIC_BASE_URL']='https://shop.isazi.example'
        self.owner();page=self.client.get('/owner/agents').data
        self.assertIn(b'https://shop.isazi.example/agent/register?utm_source=tiktok',page)

    def test_anonymous_cannot_open_owner_sharing_tools(self):
        self.assertEqual(self.client.get('/owner/agents').status_code,302)
        page=self.client.get('/agent/register?utm_source=tiktok&utm_medium=social&utm_campaign=november').data
        self.assertIn(b'name="phone"',page);self.assertIn(b'name="pin"',page)
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM agents')[0][0],0)

    def test_visitor_registers_through_campaign_link_and_gets_code(self):
        self.client.get('/agent/register?utm_source=tiktok&utm_medium=social&utm_campaign=november')
        page=self.post('/agent/register',dict(name='TikTok Champion',phone='0711234567',pin='2749',confirm_pin='2749',consent='on')).data
        self.assertIn(b'PRODUCT CHAMPION PORTAL',page)
        row=self.fetch('SELECT code,approved,rate_bps FROM agents')[0]
        self.assertTrue(row[0].startswith('ISZ-'));self.assertEqual(row[1:],(1,500))

if __name__=='__main__':unittest.main()
