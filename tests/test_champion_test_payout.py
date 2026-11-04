"""Owner can simulate payouts without changing the real commission ledger."""
import unittest
import test_owner_champion_test_ledger as owner_tests

class ChampionTestPayoutTests(unittest.TestCase):
    setUp=owner_tests.OwnerChampionTestLedgerTests.setUp
    tearDown=owner_tests.OwnerChampionTestLedgerTests.tearDown
    csrf=owner_tests.OwnerChampionTestLedgerTests.csrf
    post=owner_tests.OwnerChampionTestLedgerTests.post
    owner=owner_tests.OwnerChampionTestLedgerTests.owner
    fetch=owner_tests.OwnerChampionTestLedgerTests.fetch
    order=owner_tests.OwnerChampionTestLedgerTests.order
    register=owner_tests.OwnerChampionTestLedgerTests.register
    prepare=owner_tests.OwnerChampionTestLedgerTests.prepare
    paid=owner_tests.OwnerChampionTestLedgerTests.paid

    def payout(self,amount='20',reference='TEST-PAYOUT-1',**overrides):
        self.client.get('/owner/commissions')
        with self.client.session_transaction() as session:key=session['payout_key']
        data=dict(agent_id='1',amount=amount,reference=reference,event_key=key,payout_mode='test');data.update(overrides)
        return self.post('/owner/commissions',data),data

    def test_test_payout_updates_owner_and_champion_and_cannot_replay(self):
        self.paid();page=self.client.get('/owner/commissions').data
        self.assertIn(b'R28.50 TEST credit available',page)
        result,data=self.payout();self.assertIn(b'TEST payout recorded',result.data)
        self.assertIn(b'R8.50 TEST credit available',result.data)
        self.post('/owner/commissions',data)
        self.payout(reference='TEST-PAYOUT-1')
        self.assertEqual(self.fetch('SELECT amount,reference FROM champion_test_payouts'),[(2000,'TEST-PAYOUT-1')])
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)
        self.post('/owner/logout');page=self.post('/agent/login',dict(phone='0601234567',pin='2749')).data
        self.assertIn(b'Simulated credit: R8.50',page)
        self.assertIn(b'TEST payouts recorded: R20.00',page)
        self.assertIn(b'TEST credit earned: R28.50',page)
        self.assertIn(b'Simulated payout',page);self.assertIn(b'TEST-PAYOUT-1',page)
        self.assertIn(b'R-20.00',page)

    def test_overdraw_and_invalid_modes_rejected(self):
        self.paid()
        for values in [dict(amount='28.51'),dict(amount='0'),dict(amount='-1'),dict(payout_mode='other'),dict(agent_id='999'),dict(event_key='')]:
            self.payout(**values)
        self.assertEqual(self.fetch('SELECT count(*) FROM champion_test_payouts')[0][0],0)
        self.payout(amount='28.50');self.payout(amount='0.01',reference='TEST-PAYOUT-2')
        self.assertEqual(self.fetch('SELECT sum(amount) FROM champion_test_payouts')[0][0],2850)

    def test_test_mode_off_and_missing_csrf_rejected(self):
        self.paid()
        self.assertEqual(self.client.post('/owner/commissions',data=dict(payout_mode='test',agent_id='1',amount='20',reference='TEST')).status_code,400)
        self.app.config['DEMO_PAYMENTS_ENABLED']=False
        result,_=self.payout();self.assertIn(b'require payment test mode',result.data)
        self.assertEqual(self.fetch('SELECT count(*) FROM champion_test_payouts')[0][0],0)

    def test_reversal_after_test_payout_keeps_negative_test_balance(self):
        self.paid();self.payout();self.post('/owner/order/1',dict(status='Cancelled'))
        page=self.client.get('/owner/commissions').data
        self.assertIn(b'R-20.00 TEST credit available',page)
        self.assertIn(b'Simulated payout',page)
        self.payout(amount='1',reference='TEST-PAYOUT-2')
        self.assertEqual(self.fetch('SELECT count(*) FROM champion_test_payouts')[0][0],1)
        self.assertEqual(self.fetch('SELECT count(*) FROM commission_ledger')[0][0],0)

if __name__=='__main__':unittest.main()
