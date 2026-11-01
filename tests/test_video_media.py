import io
import unittest
import subprocess
import tempfile
import json
from pathlib import Path
from unittest.mock import patch
from video_processing import ffmpeg_executable
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
        self.assertEqual(response.headers['X-Isazi-Version'],'2.6.40')
        self.assertEqual(self.client.get('/health').json['version'],'2.6.40')
        self.assertEqual(self.fetch('SELECT COUNT(*) FROM videos')[0][0],5)
        self.assertEqual(self.client.get('/owner/media').status_code,302)
        self.assertEqual(self.post('/owner/media/2',{'title':'Unauthorised title'},follow=False).status_code,302)

    def test_owner_publishes_remote_video_and_safe_caption(self):
        self.owner()
        self.assertEqual(self.client.get('/owner/media').status_code,200)
        self.post('/owner/media/2',dict(title='Customer story',person='Verified Customer',caption='<script>alert(1)</script>',video_url='https://example.com/story.mp4',active='on'))
        self.assertEqual(self.fetch('SELECT video_source FROM videos WHERE id=2')[0][0],'https://example.com/story.mp4')
        response=self.client.get('/')
        self.assertIn(b'<source src="https://example.com/story.mp4"',response.data)
        self.assertIn(b'&lt;script&gt;alert(1)',response.data)
        self.assertNotIn(b'<script>alert(1)',response.data)
        self.assertIn(b'Listen to Customer story',response.data)

    def test_rejects_non_media_url_and_disguised_upload(self):
        self.owner()
        for value in ['javascript:alert(1)','http://example.com/a.mp4','https://youtube.com/watch?v=test','https://example.com/file.html']:
            response=self.post('/owner/media/2',dict(title='Testimonial',video_url=value,active='on'))
            self.assertEqual(self.fetch('SELECT video_source FROM videos WHERE id=2')[0][0],'')
        self.post('/owner/media/2',dict(title='Testimonial',active='on',video=(io.BytesIO(b'<html>not a video</html>'),'fake.mp4')))
        self.assertEqual(self.fetch('SELECT video_source FROM videos WHERE id=2')[0][0],'')

    def test_upload_storage_range_requests_and_cover_replacement(self):
        self.owner()
        payload=self.make_video()
        cover=io.BytesIO()
        Image.new('RGB',(160,100),'green').save(cover,'PNG')
        cover.seek(0)
        self.post('/owner/media/1',dict(title='Uploaded story',person='',caption='Test caption',active='on',video=(io.BytesIO(payload),'story.mp4'),poster=(cover,'cover.png')))
        source,poster,mobile=self.fetch('SELECT video_source,poster,mobile_video_source FROM videos WHERE id=1')[0]
        self.assertTrue(mobile.endswith('-mobile.mp4'))
        desktop=(Path(self.tmp.name)/'uploads'/source).read_bytes()
        self.assertLess(len(desktop),len(payload))
        self.assertLess((Path(self.tmp.name)/'uploads'/mobile).stat().st_size,len(payload))
        self.assertLess(desktop.index(b'moov'),desktop.index(b'mdat'))
        for name in (source,mobile):
            subprocess.run([ffmpeg_executable(),'-v','error','-i',str(Path(self.tmp.name)/'uploads'/name),'-f','null','-'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        self.assertTrue(source.startswith('upload-video-'))
        self.assertTrue(poster.startswith('upload-poster-'))
        with self.client.get('/media/'+source,headers={'Range':'bytes=0-15'}) as response:
            self.assertEqual(response.status_code,206)
            self.assertEqual(response.data,desktop[:16])
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


    @staticmethod
    def make_video(portrait=False):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'source.mp4'
            size='480x960' if portrait else '960x540'
            subprocess.run([ffmpeg_executable(),'-nostdin','-v','error','-f','lavfi','-i',f'testsrc2=size={size}:rate=30',
                            '-f','lavfi','-i','sine=frequency=440:sample_rate=44100','-t','0.5',
                            '-c:v','libx264','-qp','0','-threads','1','-c:a','aac',str(path)],check=True)
            return path.read_bytes()

    def test_corrupt_video_keeps_existing_and_no_partial_files(self):
        self.owner()
        self.post('/owner/media/1',dict(title='Original story',video_url='https://example.com/old.mp4',active='on'))
        payload=b'\x00\x00\x00\x18ftypisom'+b'\x00'*64
        response=self.post('/owner/media/1',dict(title='New story',video=(io.BytesIO(payload),'broken.mp4'),active='on'))
        self.assertIn(b'could not be processed',response.data)
        self.assertEqual(self.fetch('SELECT title,video_source FROM videos WHERE id=1')[0],('Original story','https://example.com/old.mp4'))
        self.assertEqual(list((Path(self.tmp.name)/'uploads').glob('upload-video-*')),[])

    def test_second_encode_timeout_keeps_previous_video(self):
        self.owner()
        self.post('/owner/media/1',dict(title='Original story',video_url='https://example.com/old.mp4',active='on'))
        import video_processing
        real_run=video_processing.subprocess.run
        calls=[]
        def run(command,**kwargs):
            calls.append(command)
            if len(calls)==2:
                raise subprocess.TimeoutExpired(command,240)
            return real_run(command,**kwargs)
        payload=self.make_video()
        with patch('video_processing.subprocess.run',side_effect=run):
            response=self.post('/owner/media/1',dict(title='New story',video=(io.BytesIO(payload),'story.mp4'),active='on'))
        self.assertIn(b'took too long',response.data)
        self.assertEqual(self.fetch('SELECT video_source,mobile_video_source FROM videos WHERE id=1')[0],('https://example.com/old.mp4',''))
        self.assertEqual(list((Path(self.tmp.name)/'uploads').glob('upload-video-*')),[])

    def test_portrait_variants_playback_clear_and_restart(self):
        self.owner()
        self.post('/owner/media/1',dict(title='Portrait story',video=(io.BytesIO(self.make_video(True)),'story.mp4'),active='on'))
        source,mobile=self.fetch('SELECT video_source,mobile_video_source FROM videos WHERE id=1')[0]
        for name,expected in [(source,(360,720)),(mobile,(240,480))]:
            # FFmpeg itself decodes both, and exposes the expected portrait dimensions.
            result=subprocess.run([ffmpeg_executable(),'-hide_banner','-i',str(Path(self.tmp.name)/'uploads'/name),'-f','null','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            self.assertEqual(result.returncode,0)
            self.assertIn(f'{expected[0]}x{expected[1]}'.encode(),result.stderr)
            self.assertIn(b'h264',result.stderr)
            self.assertIn(b'aac',result.stderr)
        for url in ['/','/about','/owner/media']:
            self.assertIn(mobile.encode(),self.client.get(url).data)
        create_app({'TESTING':True,'DATABASE':self.db_path,'UPLOAD_DIR':str(self.tmp.name+'/uploads')})
        self.assertEqual(self.fetch('SELECT mobile_video_source FROM videos WHERE id=1')[0][0],mobile)
        self.post('/owner/media/1',dict(title='Portrait story',clear_video='on',active='on'))
        self.assertEqual(self.fetch('SELECT video_source,mobile_video_source FROM videos WHERE id=1')[0],('',''))

    def test_111mb_video_is_accepted_and_compressed_before_publishing(self):
        self.owner()
        # Valid MP4 with a large free box, not a mocked converter or fake signature.
        import struct
        payload=self.make_video()
        size=111*1024*1024
        with tempfile.TemporaryFile() as video:
            video.write(payload)
            video.write(struct.pack('>I4s',size-len(payload),b'free'))
            video.truncate(size)
            video.seek(0)
            response=self.post('/owner/media/1',dict(title='Large uploaded story',video=(video,'large.mp4'),active='on'))
        self.assertIn(b'Media and testimonial details saved.',response.data)
        sources=self.fetch('SELECT video_source,mobile_video_source FROM videos WHERE id=1')[0]
        for source in sources:
            self.assertTrue(source.startswith('upload-video-'))
            self.assertLess((Path(self.tmp.name)/'uploads'/source).stat().st_size,size)
