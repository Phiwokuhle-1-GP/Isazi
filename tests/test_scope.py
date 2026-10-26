"""Commercial scope behaviour - no invoices are created in this application."""
import tempfile
import unittest
from pathlib import Path
from state import Store, ValidationError
from status_report import build_status_pdf

class CommercialScopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / 'project.db')
        self.store.initialize()
    def tearDown(self):
        self.tmp.cleanup()
    def test_scope_and_separate_services(self):
        _, state = self.store.current()
        scope = state['commercial_scope']
        self.assertNotIn('price_zar', scope)
        self.assertIn('separately charged',scope['change_control'])
        self.assertIn('separate written quotation',scope['change_control'])
        self.assertNotIn('R5,999',str(scope))
        self.assertIn('Domain name registration',scope['third_party'])
        self.assertEqual(scope['scope_status'],'Draft for confirmation')
    def test_scope_edit_creates_a_revision(self):
        version,_ = self.store.current()
        new = self.store.save(version,'owner','Clarified exclusions',{'action':'commercial_scope','values':{'excluded':'Extra design rounds - separately quoted'}})
        self.assertEqual(new, version+1)
        self.assertIn('Extra design', self.store.current()[1]['commercial_scope']['excluded'])
        self.assertNotIn('Extra design', self.store.revision(version)['state']['commercial_scope']['excluded'])
        self.assertNotIn('price_zar',self.store.current()[1]['commercial_scope'])
    def test_scope_approval_requires_written_signoff(self):
        version,_ = self.store.current()
        with self.assertRaises(ValidationError):
            self.store.save(version,'owner','Approval',{'action':'commercial_scope','values':{'scope_status':'Approved in writing'}})
        self.assertEqual(self.store.current()[0],version)
    def test_removes_legacy_amount_on_upgrade_preserving_history(self):
        import json
        version,state=self.store.current()
        scope=state['commercial_scope']
        scope['price_zar']=5999
        scope['change_control']='Any work outside R5,999 must be quoted.'
        scope['tax_note']='The project costs R5,999.'
        with self.store.connect() as conn:
            conn.execute('UPDATE current_state SET state_json=? WHERE id=1', (json.dumps(state),))
        self.store.initialize()
        new_version,new_state=self.store.current()
        self.assertEqual(new_version,version+1)
        self.assertNotIn('price_zar',new_state['commercial_scope'])
        self.assertNotIn('5,999',str(new_state['commercial_scope']))
        self.assertIn('separately charged',new_state['commercial_scope']['change_control'])
        self.assertEqual(self.store.revision(version)['version'],version)
        self.store.initialize()
        self.assertEqual(self.store.current()[0],new_version)

    def test_old_scope_restore_removes_amount(self):
        import json
        version,state=self.store.current()
        state['commercial_scope']['price_zar']=5999
        state['commercial_scope']['tax_note']='Once-off R5,999.'
        with self.store.connect() as conn:
            conn.execute('UPDATE revisions SET snapshot_json=? WHERE version=?',(json.dumps(state),version))
        new=self.store.save(version,'owner','restore snapshot', {'action':'restore','restore_version':version})
        self.assertEqual(new,version+1)
        self.assertNotIn('price_zar',self.store.current()[1]['commercial_scope'])
        self.assertNotIn('5,999',str(self.store.current()[1]['commercial_scope']))

    def test_scope_is_in_pdf(self):
        version,state = self.store.current()
        pdf = build_status_pdf(state,version,[])
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertGreater(len(pdf),6000)

if __name__ == '__main__': unittest.main()
