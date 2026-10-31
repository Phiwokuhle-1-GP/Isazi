"""Build reusable web assets without replacing original images. Run after asset edits."""
import hashlib
import json
import io
from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parent
STYLES=['style.css','layout.css','scroll.css','demo.css','ecosystem.css','mobile.css','storefront.css','quick-purchase.css','visual-audit.css']


def build():
    image_root=ROOT/'static/images'
    images=sorted(p for p in image_root.iterdir() if p.suffix.lower() in {'.png','.webp','.jpg','.jpeg'})
    sources=[ROOT/'static/css'/name for name in STYLES]+images+[Path(__file__)]
    fingerprint=hashlib.sha256(b''.join(p.read_bytes() for p in sources)).hexdigest()
    manifest_path=ROOT/'asset_manifest.json'
    if manifest_path.exists():
        previous=json.loads(manifest_path.read_text())
        paths=[previous.get('css','')]+[v['path'] for rows in previous.get('images',{}).values() for v in rows]
        if previous.get('fingerprint')==fingerprint and all((ROOT/'static'/p).is_file() and (ROOT/'static'/p).stat().st_size>0 for p in paths):
            print('Optimized assets are current.');return previous
    css=b'\n'.join((ROOT/'static/css'/name).read_bytes() for name in STYLES)
    css_path='optimized/store-'+hashlib.sha256(css).hexdigest()[:16]+'.css'
    (ROOT/'static/optimized').mkdir(exist_ok=True)
    (ROOT/'static'/css_path).write_bytes(css)
    manifest={'fingerprint':fingerprint,'css':css_path,'images':{}}
    original_bytes=optimized_bytes=0
    for source in images:
        digest=hashlib.sha256(source.read_bytes()+Path(__file__).read_bytes()).hexdigest()[:16]
        variants=[]
        with Image.open(source) as im:
            im.load()
            # Portraits retain exact decoded pixel data; only their encoding changes.
            original_portrait=source.name.startswith('dr-ntuli-')
            sizes=[im.width] if original_portrait else sorted(set(min(w,im.width) for w in ([640,1280,2172] if 'hero' in source.name else [320,640,1280])))
            for width in sizes:
                copy=im.copy()
                if copy.mode not in ('RGB','RGBA'):copy=copy.convert('RGBA' if 'transparency' in copy.info else 'RGB')
                if width<copy.width:copy=copy.resize((width,round(copy.height*width/copy.width)),Image.Resampling.LANCZOS)
                relative=f'optimized/{source.name}/{copy.width}-{digest}.webp'
                target=ROOT/'static'/relative;target.parent.mkdir(parents=True,exist_ok=True)
                buffer=io.BytesIO()
                copy.save(buffer,'WEBP',lossless=original_portrait,quality=88 if 'testimony' in source.name else 84,method=6)
                payload=buffer.getvalue()
                if not payload:raise RuntimeError(f'Empty image encoding: {source.name} at {width}')
                with Image.open(io.BytesIO(payload)) as check:check.verify()
                target.write_bytes(payload)
                # Do not replace an already smaller native source with a larger encoding.
                if copy.size==im.size and target.stat().st_size>=source.stat().st_size:
                    target.unlink();relative='images/'+source.name
                variants.append({'width':copy.width,'height':copy.height,'path':relative})
        manifest['images'][source.name]=variants
        original_bytes+=source.stat().st_size
        optimized_bytes+=(ROOT/'static'/variants[-1]['path']).stat().st_size
    manifest_path.write_text(json.dumps(manifest,sort_keys=True,indent=2)+'\n')
    print(f'Built {len(images)} responsive image sets and one stylesheet; native sources {original_bytes:,} bytes, largest served variants {optimized_bytes:,} bytes.')
    return manifest

if __name__=='__main__':build()
