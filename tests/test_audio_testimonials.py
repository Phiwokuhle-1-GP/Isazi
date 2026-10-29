import io
import sqlite3
import unittest
import wave
from pathlib import Path

import test_store
from app import create_app


class AudioTestimonialTests(unittest.TestCase):
    setUp = test_store.StoreTests.setUp
    tearDown = test_store.StoreTests.tearDown
    csrf = test_store.StoreTests.csrf
    post = test_store.StoreTests.post
    owner = test_store.StoreTests.owner
    fetch = test_store.StoreTests.fetch

    @staticmethod
    def recording():
        # A real short silent WAV tests transport only; it is never seeded as a testimony.
        result = io.BytesIO()
        with wave.open(result, 'wb') as out:
            out.setnchannels(1)
            out.setsampwidth(2)
            out.setframerate(8000)
            out.writeframes(b'\0\0' * 80)
        return result.getvalue()

    def test_four_supplied_covers_without_coming_soon_labels(self):
        page = self.client.get('/').get_data(as_text=True)
        section = page.split('<section class="testimonials-section"')[1].split('</section>')[0]
        self.assertIn('Listen to testimonials', section)
        self.assertNotIn('class="audio-label"', section)
        self.assertEqual(section.count('class="testimonial-card"'), 4)
        for n in range(1, 5):
            self.assertIn(f'testimony-audio-cover-{n}.png', section)
        self.assertNotIn('Coming soon', section)
        self.assertNotIn('coming soon', section)
        self.assertNotIn('<audio', section)
        self.assertEqual(self.client.get('/owner/media').status_code, 302)
        self.assertEqual(self.post('/owner/media/2', {'title':'Unauthorized','audio_url':'https://example.com/a.mp3'}, follow=False).status_code,302)

    def test_reject_invalid_audio_urls_files_and_missing_csrf(self):
        self.owner()
        self.assertEqual(self.client.post('/owner/media/2', data={'title':'Audio','audio_url':'https://example.com/a.mp3'}).status_code,400)
        for url in ['javascript:alert(1)','http://example.com/a.mp3','https://example.com/a.html','https://user:pass@example.com/a.mp3']:
            self.post('/owner/media/2', {'title':'Audio testimony','audio_url':url,'active':'on'})
            self.assertEqual(self.fetch('SELECT audio_source FROM videos WHERE id=2')[0][0],'')
        self.post('/owner/media/2', {'title':'Audio testimony','active':'on','audio':(io.BytesIO(b'<html>not audio</html>'),'fake.mp3')})
        self.assertEqual(self.fetch('SELECT audio_source FROM videos WHERE id=2')[0][0],'')

    def test_real_wav_upload_range_and_restart_persistence(self):
        self.owner()
        data = self.recording()
        self.post('/owner/media/2', {'title':'Customer recording','active':'on','audio_url':'https://example.com/remote.mp3','audio':(io.BytesIO(data),'recording.wav')})
        source = self.fetch('SELECT audio_source FROM videos WHERE id=2')[0][0]
        self.assertTrue(source.startswith('upload-audio-'))
        with self.client.get('/media/'+source, headers={'Range':'bytes=0-15'}) as response:
            self.assertEqual(response.status_code,206)
            self.assertEqual(response.data,data[:16])
            self.assertIn('audio/',response.content_type)
        self.assertIn(source.encode(),self.client.get('/').data)
        self.assertIn(b'class="testimonial-audio" controls',self.client.get('/').data)
        create_app({'TESTING':True,'DATABASE':self.db_path,'UPLOAD_DIR':self.tmp.name+'/uploads'})
        self.assertEqual(self.fetch('SELECT audio_source FROM videos WHERE id=2')[0][0],source)

    def test_audio_priority_and_clear_preserve_existing_video_and_cover(self):
        self.owner()
        self.post('/owner/media/2', {'title':'Customer testimony','active':'on','audio_url':'https://example.com/customer.mp3','video_url':'https://example.com/legacy.mp4'})
        poster = self.fetch('SELECT poster FROM videos WHERE id=2')[0][0]
        page = self.client.get('/').data
        self.assertIn(b'https://example.com/customer.mp3',page)
        self.assertNotIn(b'data-video-src="https://example.com/legacy.mp4"',page)
        self.post('/owner/media/2', {'title':'Customer testimony','active':'on','clear_audio':'on'})
        self.assertEqual(self.fetch('SELECT audio_source,video_source,poster FROM videos WHERE id=2')[0],('', 'https://example.com/legacy.mp4',poster))

    def test_additive_migration_preserves_custom_legacy_media(self):
        old_db = Path(self.tmp.name)/'legacy.sqlite3'
        with sqlite3.connect(old_db) as db:
            db.execute("CREATE TABLE videos(id INTEGER PRIMARY KEY,kind TEXT NOT NULL,title TEXT NOT NULL,person TEXT NOT NULL DEFAULT '',caption TEXT NOT NULL DEFAULT '',video_source TEXT NOT NULL DEFAULT '',poster TEXT NOT NULL,active INTEGER NOT NULL DEFAULT 1)")
            db.execute("INSERT INTO videos(id,kind,title,video_source,poster) VALUES(2,'testimonial','Existing custom title','https://example.com/old.mp4','upload-existing.webp')")
        create_app({'TESTING':True,'DATABASE':str(old_db),'UPLOAD_DIR':self.tmp.name+'/uploads'})
        with sqlite3.connect(old_db) as db:
            row = db.execute('SELECT title,video_source,poster,audio_source FROM videos WHERE id=2').fetchone()
        self.assertEqual(row,('Existing custom title','https://example.com/old.mp4','upload-existing.webp',''))

    def test_story_slot_keeps_video_only_and_failed_audio_keeps_existing_recording(self):
        self.owner()
        self.post('/owner/media/1', {'title':'Our Story','active':'on','audio_url':'https://example.com/invalid-story.mp3'})
        self.assertEqual(self.fetch('SELECT audio_source FROM videos WHERE id=1')[0][0],'')
        self.post('/owner/media/2', {'title':'Audio testimony','active':'on','audio_url':'https://example.com/current.ogg'})
        self.post('/owner/media/2', {'title':'Audio testimony','active':'on','audio':(io.BytesIO(b'not a valid audio file'),'bad.wav')})
        self.assertEqual(self.fetch('SELECT audio_source FROM videos WHERE id=2')[0][0],'https://example.com/current.ogg')
