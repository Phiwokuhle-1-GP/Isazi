import io
from pathlib import Path
from unittest.mock import patch
import test_store

class StoryLibraryTests(test_store.StoreTests):
    def test_story_upload_library_and_visibility(self):
        self.assertEqual(self.post('/owner/media/stories', follow=False).status_code,302)
        self.owner()
        def convert(upload,directory):
            n=len(self.fetch("SELECT id FROM videos WHERE kind='story'"))
            names=(f'upload-video-story{n}-desktop.mp4',f'upload-video-story{n}-mobile.mp4')
            for name in names:(Path(directory)/name).write_bytes(b'encoded video')
            return names
        with patch('app.transcode_upload',side_effect=convert):
            for name in ['First story.mp4','Second story.mp4']:
                response=self.post('/owner/media/stories',{'video':(io.BytesIO(b'0000ftyp'+b'0'*30),name)},follow=False)
                self.assertEqual(response.status_code,201,response.data)
        page=self.client.get('/videos')
        self.assertEqual(page.status_code,200)
        self.assertIn(b'First story',page.data);self.assertIn(b'Second story',page.data)
        self.assertIn(b'data-video-mobile=',page.data)
        self.assertIn(b'href="/videos"',self.client.get('/').data)
        last=self.fetch("SELECT id FROM videos WHERE title='Second story'")[0][0]
        self.post('/owner/media/'+str(last),{'title':'Hidden story'})
        self.assertNotIn(b'Hidden story',self.client.get('/videos').data)

    def test_story_upload_failure_does_not_publish(self):
        self.owner();before=self.fetch('SELECT count(*) FROM videos')
        with patch('app.transcode_upload',side_effect=ValueError('Cannot process video')):
            res=self.post('/owner/media/stories',{'video':(io.BytesIO(b'0000ftyp'+b'0'*30),'bad.mp4')},follow=False)
            self.assertEqual(res.status_code,400)
        self.assertEqual(before,self.fetch('SELECT count(*) FROM videos'))
        res=self.post('/owner/media/stories',{'video':(io.BytesIO(b'not a valid video'),'bad.mp4')},follow=False)
        self.assertEqual(res.status_code,400)
