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

    def test_preview_plays_published_story_when_first_slot_empty(self):
        self.owner()
        with self.app.app_context():
            import sqlite3
            with sqlite3.connect(self.db_path) as con:
                con.execute("INSERT INTO videos(kind,title,poster,video_source,mobile_video_source,active) VALUES('story','Published story','story-dr-ntuli-poster-v2622.png','https://example.com/desktop.mp4','https://example.com/mobile.mp4',1)")
        for route in ['/', '/about']:
            page=self.client.get(route).get_data(as_text=True)
            self.assertIn('class="story-preview-trigger" data-video-src="https://example.com/desktop.mp4"',page)
            self.assertIn('data-video-mobile="https://example.com/mobile.mp4"',page)
            self.assertIn('aria-label="Play Published story"',page)
            self.assertIn('id="video-dialog"',page)
            self.assertIn('Watch Our Stories',page)
        with sqlite3.connect(self.db_path) as con:
            con.execute("UPDATE videos SET active=0 WHERE title='Published story'")
        page=self.client.get('/').get_data(as_text=True)
        self.assertNotIn('https://example.com/desktop.mp4',page)
        self.assertIn('aria-label="Open our video library"',page)
