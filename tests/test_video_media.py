import io
import unittest
from PIL import Image
import test_store
from app import create_app


class MediaTests(unittest.TestCase):
    setUp = test_store.StoreTests.setUp
    tearDown = test_store.StoreTests.tearDown
    csrf = test_store.StoreTests.csrf
    post = test_store.StoreTests.post
    owner = test_store.StoreTests.owner
    fetch = test_store.StoreTests.fetch
    def test_home_has_continuous_sections_and_four_previews(self):
        response=self.client.get('/')
        for section in ['shop','story','testimonials','health-tips','best-sellers','contact']:
            self.assertIn(('id="'+section+'"').encode(),response.data)
        self.assertEqual(response.data.count(b'class="testimonial-card"'),4)
        self.assertIn(b'#testimonials">Testimonials</a>',response.data)
        self.assertEqual(response.headers['X-Isazi-Version'],'2.6.5')
        self.assertEqual(self.client.get('/health').json['version'],'2.6.5')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM videos')[0][0],5)
        self.assertEqual(self.client.get('/owner/media').status_code,302)
        self.assertEqual(self.post('/owner/media/2',{'title':'Unauthorised title'},follow=False).status_code,302)

    def test_owner_publishes_remote_video_and_safe_caption(self):
        self.owner()
        self.assertEqual(self.client.get('/owner/media').status_code,200)
        self.post('/owner/media/2',dict(title='Customer story',person='Verified Customer',caption='<script>alert(1)</script>',video_url='https://example.com/story.mp4',active='on'))
        self.assertEqual(self.fetch('SELECT video_source FROM videos WHERE id=2')[0][0],'https://example.com/story.mp4')
        response=self.client.get('/')
        self.assertIn(b'data-video-src="https://example.com/story.mp4"',response.data)
        self.assertIn(b'&lt;script&gt;alert(1)',response.data)
        self.assertNotIn(b'<script>alert(1)',response.data)
        self.assertIn(b'Play Customer story',response.data)

    def test_rejects_non_media_url_and_disguised_upload(self):
        self.owner()
        for value in ['javascript:alert(1)','http://example.com/a.mp4','https://youtube.com/watch?v=test','https://example.com/file.html']:
            response=self.post('/owner/media/2',dict(title='Testimonial',video_url=value,active='on'))
            self.assertEqual(self.fetch('SELECT video_source FROM videos WHERE id=2')[0][0],'')
        self.post('/owner/media/2',dict(title='Testimonial',active='on',video=(io.BytesIO(b'<html>not a video</html>'),'fake.mp4')))
        self.assertEqual(self.fetch('SELECT video_source FROM videos WHERE id=2')[0][0],'')

    def test_upload_storage_range_requests_and_cover_replacement(self):
        self.owner()
        # MP4 container-signature fixture tests upload transport, not media decoding.
        payload=b'\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2'+b'\x00'*64
        cover=io.BytesIO()
        Image.new('RGB',(160,100),'green').save(cover,'PNG')
        cover.seek(0)
        self.post('/owner/media/2',dict(title='Uploaded story',person='',caption='Test caption',active='on',video=(io.BytesIO(payload),'story.mp4'),poster=(cover,'cover.png')))
        source,poster=self.fetch('SELECT video_source,poster FROM videos WHERE id=2')[0]
        self.assertTrue(source.startswith('upload-video-'))
        self.assertTrue(poster.startswith('upload-poster-'))
        with self.client.get('/media/'+source,headers={'Range':'bytes=0-15'}) as response:
            self.assertEqual(response.status_code,206)
            self.assertEqual(response.data,payload[:16])
            self.assertIn('video/mp4',response.content_type)
        with self.client.get('/media/'+poster) as response:
            self.assertEqual(response.status_code,200)
        self.assertIn(source.encode(),self.client.get('/').data)

    def test_hide_clear_and_restart_preserve_media(self):
        self.owner()
        self.post('/owner/media/2',dict(title='Unique hidden story',video_url='https://example.com/story.webm',active='on'))
        create_app({'TESTING':True,'DATABASE':self.db_path,'UPLOAD_DIR':str(self.tmp.name+'/uploads')})
        self.assertEqual(self.fetch('SELECT title FROM videos WHERE id=2')[0][0],'Unique hidden story')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM videos')[0][0],5)
        self.post('/owner/media/2',dict(title='Unique hidden story',clear_video='on'))
        self.assertEqual(self.fetch('SELECT video_source,active FROM videos WHERE id=2')[0],('',0))
        self.assertNotIn(b'Unique hidden story',self.client.get('/').data)

