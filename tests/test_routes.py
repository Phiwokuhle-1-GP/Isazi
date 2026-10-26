"""Flask integration tests. Requires dependencies from requirements.txt."""
import importlib.util
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(importlib.util.find_spec('flask') is not None, 'Flask not installed here; install requirements and rerun.')
class RouteTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        from werkzeug.security import generate_password_hash
        self.tmp = tempfile.TemporaryDirectory()
        self.app = create_app({'TESTING': True, 'DATABASE': str(Path(self.tmp.name)/'test.sqlite3'), 'SECRET_KEY':'test-key'})
        self.client = self.app.test_client()
        with self.app.extensions['isazi_store'].connect() as conn:
            conn.execute("INSERT INTO users(username,password_hash,role,enabled,created_at) VALUES (?,?,?,?,?)",
                         ('admin',generate_password_hash('strong-test-password'),'admin',1,'2026-01-01'))
            conn.execute("INSERT INTO users(username,password_hash,role,enabled,created_at) VALUES (?,?,?,?,?)",
                         ('viewer',generate_password_hash('viewer-test-password'),'viewer',1,'2026-01-01'))

    def tearDown(self):
        self.tmp.cleanup()

    def sign_in(self, name, password):
        self.client.get('/login')
        with self.client.session_transaction() as sess:
            token=sess['csrf']
        return self.client.post('/login',data={'csrf_token':token,'username':name,'password':password},follow_redirects=True)

    def token(self):
        with self.client.session_transaction() as sess:
            return sess['csrf']

    def test_full_edit_history_restore_flow(self):
        page=self.sign_in('admin','strong-test-password')
        self.assertEqual(page.status_code,200)
        for n in range(1,5):
            response=self.client.get(f'/page/{n}')
            self.assertEqual(response.status_code,200)
        editor=self.client.get('/edit/overview')
        self.assertIn(b'Edit project overview',editor.data)
        data={k:'New text for '+k for k in ['project_name','client','delivery_partner','summary','agile_intro','agile_cycle','vision','assumptions']}
        data.update(csrf_token=self.token(),version='1',message='Client workshop edits')
        response=self.client.post('/save/overview',data=data,follow_redirects=True)
        self.assertEqual(response.status_code,200)
        self.assertIn(b'version 2',response.data)
        self.assertEqual(self.client.get('/history').status_code,200)
        self.assertEqual(self.client.get('/history/compare?from=1&to=2').status_code,200)
        restored=self.client.post('/history/1/restore',data={'csrf_token':self.token(),'version':'2'},follow_redirects=True)
        self.assertIn(b'version 3',restored.data)
        self.assertEqual(self.client.get('/export/revision/2.json').status_code,200)
        self.assertEqual(self.client.get('/export/stories.csv').status_code,200)

    def test_viewer_cannot_edit_and_csrf_guard(self):
        self.sign_in('viewer','viewer-test-password')
        self.assertEqual(self.client.get('/page/4').status_code,200)
        self.assertEqual(self.client.get('/edit/stories').status_code,403)
        self.assertEqual(self.client.get('/users').status_code,403)
        self.assertEqual(self.client.post('/checkpoint',data={'version':'1','message':'bad'}).status_code,403)

    def test_client_tracker_and_design_review_permissions(self):
        self.sign_in('viewer','viewer-test-password')
        progress=self.client.get('/client/progress')
        self.assertEqual(progress.status_code,200)
        self.assertIn(b'Domain registration',progress.data)
        listing=self.client.get('/client/designs')
        self.assertEqual(listing.status_code,200)
        self.assertIn(b'Botanical Classic',listing.data)
        _, plan=self.app.extensions['isazi_store'].current()
        design=plan['designs'][0]
        response=self.client.get('/client/designs/'+design['id'])
        self.assertEqual(response.status_code,200)
        self.assertIn(b'View product',response.data)
        response=self.client.post('/client/feedback/design/'+design['id'],data={
          'csrf_token':self.token(),'feedback_type':'Request changes',
          'comment':'Use bigger typography and more space between product cards.'},follow_redirects=True)
        self.assertIn(b'Use bigger typography',response.data)
        self.assertEqual(self.client.get('/edit/designs').status_code,403)
        self.assertEqual(self.client.post('/client/designs/'+design['id']+'/status',
          data={'csrf_token':self.token(),'status':'Approved','version':'1'}).status_code,403)
        export=self.client.get('/export/client-feedback.csv')
        self.assertEqual(export.status_code,200)
        self.assertIn(b'Request changes',export.data)

    def test_admin_can_update_progress_and_design_with_version_control(self):
        self.sign_in('admin','strong-test-password')
        store=self.app.extensions['isazi_store']
        version,data=store.current()
        step=data['client_steps'][0]
        response=self.client.post('/client/progress/'+step['id']+'/status',data={
          'csrf_token':self.token(),'version':str(version),'status':'In progress'},follow_redirects=True)
        self.assertEqual(response.status_code,200)
        self.assertEqual(store.current()[0],version+1)
        self.assertEqual(store.current()[1]['client_steps'][0]['status'],'In progress')
        design=data['designs'][0]
        response=self.client.post('/client/designs/'+design['id']+'/status',data={
          'csrf_token':self.token(),'version':str(version+1),'status':'Selected'},follow_redirects=True)
        self.assertEqual(response.status_code,200)
        self.assertEqual(store.current()[1]['designs'][0]['status'],'Selected')
        self.assertIn(b'client_feedback',self.client.get('/export/json').data)

    def test_csrf_editor(self):
        self.sign_in('admin','strong-test-password')
        response=self.client.post('/checkpoint',data={'version':'1','message':'test'})
        self.assertEqual(response.status_code,403)

    def test_public_construction_and_owner_auth(self):
        public=self.client.get('/')
        self.assertEqual(public.status_code,200)
        self.assertIn(b'Website in development',public.data)
        self.assertEqual(self.client.get('/owner').status_code,302)
        self.sign_in('viewer','viewer-test-password')
        self.assertEqual(self.client.get('/owner').status_code,403)
        self.client.post('/logout', data={'csrf_token':self.token()})
        self.sign_in('admin','strong-test-password')
        owner=self.client.get('/owner')
        self.assertEqual(owner.status_code,200)
        self.assertIn(b'Owner control centre',owner.data)
        self.assertIn(b'Not yet built',owner.data)

    def test_owner_can_change_own_password(self):
        self.sign_in('admin','strong-test-password')
        bad=self.client.post('/account/password', data={'csrf_token':self.token(),
            'current_password':'wrong','new_password':'replacement-strong-pass',
            'confirm_password':'replacement-strong-pass'}, follow_redirects=True)
        self.assertIn(b'Current password is incorrect',bad.data)
        updated=self.client.post('/account/password', data={'csrf_token':self.token(),
            'current_password':'strong-test-password','new_password':'replacement-strong-pass',
            'confirm_password':'replacement-strong-pass'},follow_redirects=True)
        self.assertIn(b'Password changed',updated.data)
        self.assertEqual(self.client.get('/owner').status_code,302)
        self.sign_in('admin','replacement-strong-pass')
        self.assertEqual(self.client.get('/owner').status_code,200)

if __name__=='__main__':
    unittest.main()
