import io
import unittest
from PIL import Image
import test_store
from app import create_app


class HomeImageTests(unittest.TestCase):
    setUp=test_store.StoreTests.setUp
    tearDown=test_store.StoreTests.tearDown
    csrf=test_store.StoreTests.csrf
    post=test_store.StoreTests.post
    owner=test_store.StoreTests.owner
    fetch=test_store.StoreTests.fetch

    def picture(self, mode='RGB', size=(2000,800)):
        buffer=io.BytesIO()
        Image.new(mode,size,(0,100,50,120) if mode=='RGBA' else (0,100,50)).save(buffer,'PNG')
        buffer.seek(0)
        return buffer

    def test_image_editor_requires_owner_and_csrf(self):
        self.assertEqual(self.client.get('/owner/home-images').status_code,302)
        self.assertEqual(self.post('/owner/home-images/hero',follow=False).status_code,302)
        self.owner()
        self.assertEqual(self.client.get('/owner/home-images').status_code,200)
        self.assertEqual(self.client.post('/owner/home-images/hero').status_code,400)
        self.assertEqual(self.post('/owner/home-images/unknown').status_code,404)

    def test_upload_persists_and_replaces_only_selected_banner(self):
        self.owner()
        original=self.fetch("SELECT filename FROM home_images WHERE key='promo_cleanse'")[0][0]
        self.post('/owner/home-images/hero',{'image':(self.picture(),'hero.png')})
        filename,width,height=self.fetch("SELECT filename,width,height FROM home_images WHERE key='hero'")[0]
        self.assertTrue(filename.startswith('upload-home-'))
        self.assertEqual((width,height),(2000,800))
        self.assertIn(filename.encode(),self.client.get('/').data)
        self.assertEqual(self.fetch("SELECT filename FROM home_images WHERE key='promo_cleanse'")[0][0],original)
        create_app({'TESTING':True,'DATABASE':self.db_path,'UPLOAD_DIR':str(self.tmp.name+'/uploads')})
        self.assertEqual(self.fetch("SELECT filename FROM home_images WHERE key='hero'")[0][0],filename)
        with self.client.get('/media/'+filename) as response:
            self.assertEqual(response.status_code,200)
        self.post('/owner/home-images/hero',{'reset':'1'})
        self.assertEqual(self.fetch("SELECT filename FROM home_images WHERE key='hero'")[0][0],'hero-natural-meadow.webp')

    def test_invalid_image_keeps_existing_banner_and_transparent_crest_survives(self):
        self.owner()
        before=self.fetch("SELECT filename FROM home_images WHERE key='hero'")[0][0]
        self.post('/owner/home-images/hero',{'image':(io.BytesIO(b'<html>bad</html>'),'picture.png')})
        self.assertEqual(self.fetch("SELECT filename FROM home_images WHERE key='hero'")[0][0],before)
        self.post('/owner/home-images/brand_mark',{'image':(self.picture('RGBA',(512,512)),'crest.png')})
        filename=self.fetch("SELECT filename FROM home_images WHERE key='brand_mark'")[0][0]
        with self.client.get('/media/'+filename) as response:
            with Image.open(io.BytesIO(response.data)) as image:
                self.assertEqual(image.mode,'RGBA')
                self.assertEqual(image.size,(512,512))

    def test_original_navigation_and_sharp_demo_assets_are_wired(self):
        response=self.client.get('/')
        self.assertNotIn(b'css/sage.css',response.data)
        self.assertIn(b'hero-natural-meadow.webp',response.data)
        self.assertIn(b'demo-product-1.webp',response.data)
        self.assertIn(b'testimony-audio-cover-1.png',response.data)
        self.assertIn(b'<h1>IYENQABA INKUNZI',response.data)
        self.assertEqual(response.data.count(b'class="testimonial-card"'),4)
