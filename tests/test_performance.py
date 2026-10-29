import gzip
import hashlib
import json
from pathlib import Path
import unittest
from PIL import Image
import test_store


class PerformanceTests(unittest.TestCase):
    setUp=test_store.StoreTests.setUp
    tearDown=test_store.StoreTests.tearDown

    def test_compression_and_static_cache_work_in_payment_test_mode(self):
        self.app.config['DEMO_PAYMENTS_ENABLED']=True
        root=Path(self.app.root_path)
        manifest=json.loads((root/'asset_manifest.json').read_text())
        path='/static/'+manifest['css']
        with self.client.get(path) as plain:
            original=plain.data
            self.assertIn('immutable',plain.headers['Cache-Control'])
        with self.client.get(path,headers={'Accept-Encoding':'gzip'}) as zipped:
            self.assertEqual(zipped.headers['Content-Encoding'],'gzip')
            self.assertEqual(gzip.decompress(zipped.data),original)
            self.assertLess(len(zipped.data),len(original)*.4)
            self.assertIn('Accept-Encoding',zipped.headers['Vary'])
            etag=zipped.headers['ETag']
        with self.client.get(path,headers={'If-None-Match':etag,'Accept-Encoding':'gzip'}) as unchanged:
            self.assertEqual(unchanged.status_code,304)
        with self.client.get(path,headers={'Accept-Encoding':'gzip;q=0, identity;q=1'}) as identity:
            self.assertNotIn('Content-Encoding',identity.headers)
            self.assertEqual(identity.data,original)
        page=self.client.get('/',headers={'Accept-Encoding':'gzip'})
        self.assertIn('no-store',page.headers['Cache-Control'])
        self.assertNotIn(b'class="demo-mode-bar"',gzip.decompress(page.data))

    def test_original_portrait_pixels_are_preserved_and_cards_are_smaller(self):
        root=Path(self.app.root_path);manifest=json.loads((root/'asset_manifest.json').read_text())
        for name in ['dr-ntuli-original.png','dr-ntuli-left-original-v2.png']:
            path=manifest['images'][name][-1]['path']
            with Image.open(root/'static/images'/name) as source,Image.open(root/'static'/path) as variant:
                self.assertEqual(source.size,variant.size)
                self.assertEqual(source.convert('RGBA').tobytes(),variant.convert('RGBA').tobytes())
        thumb=manifest['images']['demo-product-1.webp'][0]
        self.assertLess((root/'static'/thumb['path']).stat().st_size,(root/'static/images/demo-product-1.webp').stat().st_size*.3)
        page=self.client.get('/').get_data(as_text=True)
        self.assertEqual(page.count('rel="stylesheet"'),1)
        self.assertIn('srcset=',page)
        self.assertIn('loading="lazy" decoding="async"',page)

    def test_uploaded_thumbnails_cache_without_changing_source_or_video_ranges(self):
        root=Path(self.app.config['UPLOAD_DIR']);source=root/'upload-fixture.png'
        Image.new('RGB',(1800,1200),'green').save(source)
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        with self.client.get('/media/upload-fixture.png?w=320') as thumb:
            self.assertEqual(thumb.status_code,200)
            self.assertEqual(thumb.mimetype,'image/webp')
            self.assertIn('immutable',thumb.headers['Cache-Control'])
        cache=root/'_image_cache/320-upload-fixture.png.webp'
        with Image.open(cache) as im:self.assertLessEqual(im.width,320)
        stamp=cache.stat().st_mtime_ns
        with self.client.get('/media/upload-fixture.png?w=320') as again:self.assertEqual(again.status_code,200)
        self.assertEqual(cache.stat().st_mtime_ns,stamp)
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),digest)
        with self.client.get('/media/upload-fixture.png',headers={'Range':'bytes=0-15'}) as partial:
            self.assertEqual(partial.status_code,206);self.assertEqual(len(partial.data),16)
        invalid=self.client.get('/media/upload-fixture.png?w=100000')
        self.assertEqual(invalid.status_code,400);self.assertIn('no-store',invalid.headers['Cache-Control'])

    def test_private_account_pages_are_never_publicly_cached(self):
        response=self.client.get('/account/login',headers={'Accept-Encoding':'gzip'})
        self.assertIn('no-store',response.headers['Cache-Control'])
        self.assertNotIn('public',response.headers['Cache-Control'])
        self.assertIn(b'csrf_token',gzip.decompress(response.data))
