"""Owner and champion simulated commission balances agree; payouts remain real-only."""
import unittest
import test_champion_simulation as simulation

class OwnerChampionTestLedgerTests(unittest.TestCase):
    setUp=simulation.ChampionSimulationTests.setUp
    tearDown=simulation.ChampionSimulationTests.tearDown
    csrf=simulation.ChampionSimulationTests.csrf
    post=simulation.ChampionSimulationTests.post
    owner=simulation.ChampionSimulationTests.owner
    fetch=simulation.ChampionSimulationTests.fetch
    order=simulation.ChampionSimulationTests.order
    register=simulation.ChampionSimulationTests.register
    prepare=simulation.ChampionSimulationTests.prepare

    def paid(self):
        self.prepare();self.post(self.route);self.owner()

    def test_owner_sees_matching_test_balance_and_entry_once(self):
        self.paid();self.post('/owner/logout');self.post(self.route);self.owner()
        page=self.client.get('/owner/commissions').data
        self.assertIn(self.code.encode(),page);self.assertIn(b'R28.50',page)
        self.assertIn(b'Total balance',page);self.assertIn(b'TEST',page)
        self.assertEqual(page.count(b'Simulated purchase credit'),1)
        self.assertIn(b'R0.00 real credit available',page)
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)

    def test_simulated_credit_cannot_fund_recorded_real_payout(self):
        self.paid();self.client.get('/owner/commissions')
        with self.client.session_transaction() as session:key=session['payout_key']
        page=self.post('/owner/commissions',dict(agent_id='1',amount='10',reference='TEST-BLOCK',event_key=key)).data
        self.assertIn(b'Payout exceeds',page)
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)
        self.assertEqual(self.fetch('SELECT amount FROM champion_test_credits'),[(2850,)])

    def test_refund_and_cancellation_update_owner_view(self):
        self.paid();self.client.get('/owner/order/1')
        with self.client.session_transaction() as session:key=session['refund_key_1']
        self.post('/owner/order/1/refund',dict(refund_key=key,goods='100',shipping='0',extra='0',reference='TEST-REFUND',reason='Testing reversal'))
        self.assertIn(b'R23.50',self.client.get('/owner/commissions').data)
        self.post('/owner/order/1',dict(status='Cancelled'))
        page=self.client.get('/owner/commissions').data
        self.assertNotIn(b'R23.50',page);self.assertNotIn(b'Simulated purchase credit',page)
        self.assertEqual(self.fetch('SELECT amount FROM champion_test_credits'),[(0,)])

    def test_live_view_keeps_historical_test_credit_labelled_and_excludes_total(self):
        self.paid();self.app.config['DEMO_PAYMENTS_ENABLED']=False
        page=self.client.get('/owner/commissions').data
        self.assertNotIn(b'Total balance',page)
        self.assertIn(b'R28.50',page);self.assertIn(b'Simulated balance',page)
        self.assertIn(b'R0.00 real credit available',page)

if __name__=='__main__':unittest.main()
