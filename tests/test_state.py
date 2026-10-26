"""Run: python -m unittest discover -s tests -v (Flask not needed for these checks)."""
import tempfile
import unittest
from pathlib import Path

from state import CHOICES, SCHEMA, ConflictError, Store, ValidationError, completion


class ProjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Store(Path(self.tmp.name) / 'workspace.sqlite3')
        self.db.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_seed_and_idempotent_init(self):
        v, data = self.db.current()
        self.assertEqual(v, 1)
        self.assertEqual(len(data['sprints']), 6)
        self.assertGreaterEqual(len(data['stories']), 14)
        self.db.initialize()
        self.assertEqual(self.db.current()[0], 1)
        self.assertEqual(completion(data)['done'], 0)

    def test_edit_creates_snapshot_and_old_version_unchanged(self):
        version, data = self.db.current()
        old = data['overview']['vision']
        new = self.db.save(version, 'ecs', 'Updated business direction', {'action':'overview','values':{'vision':'Test agreed direction'}})
        self.assertEqual(new, 2)
        self.assertEqual(self.db.current()[1]['overview']['vision'], 'Test agreed direction')
        self.assertEqual(self.db.revision(1)['state']['overview']['vision'], old)
        self.assertEqual(self.db.revision(2)['actor'], 'ecs')

    def test_conflicting_older_edit_rejected_without_changes(self):
        self.db.save(1,'ecs','First edit',{'action':'overview','values':{'vision':'new'}})
        with self.assertRaises(ConflictError):
            self.db.save(1,'client','Stale edit',{'action':'overview','values':{'vision':'stale'}})
        self.assertEqual(self.db.current()[1]['overview']['vision'],'new')
        self.assertEqual(len(self.db.versions()),2)

    def test_restore_creates_a_new_revision(self):
        self.db.save(1,'ecs','Changed vision',{'action':'overview','values':{'vision':'updated'}})
        self.db.save(2,'client','Restoring original',{'action':'restore','restore_version':1})
        self.assertEqual(self.db.current()[0],3)
        self.assertEqual(self.db.current()[1]['overview']['vision'],self.db.revision(1)['state']['overview']['vision'])
        self.assertEqual(self.db.revision(2)['state']['overview']['vision'],'updated')

    def test_crud_story_status_and_priority(self):
        version, data=self.db.current()
        raw={k:'' for k,_,_ in SCHEMA['stories'][1]}
        raw.update(title='New user story',persona='Sales agent',want='View referrals',benefit='Understand sales',priority='High',status='Ready',sprint='Sprint 4',points='5')
        self.db.save(version,'ecs','Added backlog item',{'action':'create','collection':'stories','values':raw})
        v2, state=self.db.current()
        created=state['stories'][-1]
        self.assertEqual(created['title'],'New user story')
        raw.update(title='Changed story',status='Done')
        self.db.save(v2,'ecs','Moved feature to done',{'action':'update','collection':'stories','id':created['id'],'values':raw})
        self.assertEqual(self.db.current()[1]['stories'][-1]['status'],'Done')
        self.db.save(3,'ecs','Deleted new story',{'action':'delete','collection':'stories','id':created['id']})
        self.assertEqual(len(self.db.current()[1]['stories']),len(data['stories']))
        self.assertEqual(self.db.revision(3)['state']['stories'][-1]['title'],'Changed story')

    def test_invalid_items_do_not_write_revisions(self):
        with self.assertRaises(ValidationError):
            self.db.save(1,'ecs','Bad status',{'action':'create','collection':'stories','values':{'title':'Hi','priority':'Urgent'}})
        self.assertEqual(self.db.current()[0],1)
        with self.assertRaises(ValidationError):
            self.db.save(1,'ecs','Too large',{'action':'overview','values':{'vision':'x'*6001}})
        self.assertEqual(self.db.current()[0],1)

    def test_checkpoint_and_metadata(self):
        self.db.save(1,'client','Sign-off meeting checkpoint',{'action':'checkpoint'})
        self.assertEqual(self.db.current()[0],2)
        self.assertEqual(self.db.revision(2)['message'],'Sign-off meeting checkpoint')
        self.assertEqual(self.db.revision(2)['state'],self.db.revision(1)['state'])

    def test_all_seeded_collections_have_valid_item_fields(self):
        _, plan=self.db.current()
        for col, (_,fields) in SCHEMA.items():
            self.assertIn(col,plan)
            field_names={x[0] for x in fields}
            for item in plan[col]:
                self.assertTrue(field_names.issubset(item.keys()),(col,item))
                for field, _, kind in fields:
                    if kind in CHOICES:
                        self.assertIn(item[field],CHOICES[kind],(col,field,item[field]))


if __name__=='__main__':
    unittest.main()
