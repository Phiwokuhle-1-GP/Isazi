"""Test v3 client status & feedback persistence; no Flask dependency."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from state import Store, ValidationError, ConflictError, add_feedback, feedback_list

class ClientModulesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.db=Path(self.tmp.name)/'plan.sqlite3'
        self.store=Store(self.db)
        self.store.initialize()
    def tearDown(self):
        self.tmp.cleanup()

    def test_three_designs_and_nine_steps(self):
        ver,plan=self.store.current()
        self.assertEqual(len(plan['designs']),3)
        self.assertEqual(len(plan['client_steps']),9)
        self.assertEqual(plan['client_steps'][0]['title'],'Domain registration')
        self.assertEqual(plan['client_steps'][0]['status'],'Not started')
        self.assertTrue(all(d['status']=='Proposed' for d in plan['designs']))

    def test_status_updates_have_immutable_snapshots_and_conflicts(self):
        ver,plan=self.store.current()
        step=plan['client_steps'][0].copy()
        step['status']='In progress'
        updated=self.store.save(ver,'ecs','Domain registration underway',{'action':'update','collection':'client_steps','id':step['id'],'values':{k:v for k,v in step.items() if k!='id'}})
        self.assertEqual(updated,ver+1)
        self.assertEqual(self.store.current()[1]['client_steps'][0]['status'],'In progress')
        self.assertEqual(self.store.revision(ver)['state']['client_steps'][0]['status'],'Not started')
        with self.assertRaises(ConflictError):
            self.store.save(ver,'ecs','Stale edit',{'action':'update','collection':'client_steps','id':step['id'],'values':{k:v for k,v in step.items() if k!='id'}})

    def test_feedback_is_append_only_with_authorship_and_timestamp(self):
        _,plan=self.store.current()
        ident=plan['designs'][0]['id']
        add_feedback(self.store,'design',ident,'isazi-client','Prefer this design','The botanical direction fits our brand, but enlarge the search bar.')
        add_feedback(self.store,'design',ident,'ecs-editor','Comment','Will update search placement in the next review.')
        notes=feedback_list(self.store,'design',ident)
        self.assertEqual(len(notes),2)
        self.assertEqual(notes[0]['author'],'ecs-editor')
        self.assertEqual(notes[1]['feedback_type'],'Prefer this design')
        self.assertIn('T',notes[0]['created_at'])
        self.assertEqual(self.store.current()[0],1) # Notes do not overwrite approved plan revisions.

    def test_feedback_rejects_invalid_subjects_and_empty_notes(self):
        _,plan=self.store.current()
        ident=plan['client_steps'][0]['id']
        for subject,kind,msg in [('step','Prefer this design','yes'),('step','Comment',''),('design','Comment','not here')]:
            with self.assertRaises(ValidationError):
                add_feedback(self.store,subject,ident,'client',kind,msg)
        self.assertEqual(feedback_list(self.store,'step',ident),[])

    def test_existing_db_migrates_without_losing_older_story_revisions(self):
        with self.store.connect() as conn:
            row=conn.execute('SELECT version,state_json FROM current_state WHERE id=1').fetchone()
            plan=json.loads(row['state_json'])
            oldstory=plan['stories'][0]['title']
            del plan['designs']; del plan['client_steps']
            conn.execute('UPDATE current_state SET state_json=? WHERE id=1',(json.dumps(plan),))
        self.store.initialize()
        v,migrated=self.store.current()
        self.assertEqual(v,2)
        self.assertEqual(migrated['stories'][0]['title'],oldstory)
        self.assertEqual(len(migrated['designs']),3)
        self.assertEqual(self.store.revision(1)['state']['stories'][0]['title'],oldstory)
        self.store.initialize()
        self.assertEqual(self.store.current()[0],2)

    def test_restore_legacy_snapshot_preserves_new_modules(self):
        with self.store.connect() as conn:
            old=json.loads(conn.execute('SELECT snapshot_json FROM revisions WHERE version=1').fetchone()[0])
            old.pop('client_steps'); old.pop('designs')
            conn.execute('UPDATE revisions SET snapshot_json=? WHERE version=1',(json.dumps(old),))
        version,_=self.store.current()
        self.store.save(version,'owner','Restore old','{"hello":"bad"}' if False else {'action':'restore','restore_version':1})
        _,plan=self.store.current()
        self.assertEqual(len(plan['client_steps']),9)
        self.assertEqual(len(plan['designs']),3)

if __name__=='__main__': unittest.main()
