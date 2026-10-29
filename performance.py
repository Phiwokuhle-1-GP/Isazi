"""Asset caching, responsive image selection and negotiated text compression."""
import gzip
import io
import secrets
import json
from pathlib import Path
from flask import abort, request, url_for
from PIL import Image

WIDTHS=(320,640,1280)


def install_performance(app,root):
    manifest_file=Path(root)/'asset_manifest.json'
    assets=json.loads(manifest_file.read_text()) if manifest_file.exists() else {}

    def variant(name,width=1280):
        rows=assets.get('images',{}).get(name,[])
        return next((row for row in rows if row['width']>=width),rows[-1] if rows else None)

    def static_image(name,width=1280):
        row=variant(name,width)
        return url_for('static',filename=row['path']) if row else url_for('static',filename='images/'+name)

    def srcset(name,widths=(320,640,1280)):
        if name.startswith('upload-'):
            return ', '.join(url_for('uploaded',filename=name,w=w)+f' {w}w' for w in WIDTHS if w in widths)
        chosen={}
        for width in widths:
            row=variant(name,width)
            if row:chosen[row['width']]=row['path']
        return ', '.join(url_for('static',filename=path)+f' {width}w' for width,path in sorted(chosen.items()))

    @app.context_processor
    def asset_context():
        return {'stylesheet_url':url_for('static',filename=assets['css']) if assets.get('css') else None}

    @app.after_request
    def faster_responses(response):
        static=request.endpoint=='static'
        upload=request.endpoint=='uploaded'
        if (static or upload) and response.status_code in (200,206,304):
            immutable=(static and request.view_args.get('filename','').startswith('optimized/')) or (upload and request.view_args.get('filename','').startswith('upload-'))
            response.headers['Cache-Control']='public, max-age=31536000, immutable' if immutable else 'public, max-age=86400'
        elif response.mimetype=='text/html':
            # HTML includes sessions/CSRF tokens. Never put it in a shared/public cache.
            response.headers['Cache-Control']='private, no-store'
        text_type=response.mimetype in {'text/html','text/css','application/javascript','text/javascript','application/json','image/svg+xml'}
        if text_type:
            response.vary.add('Accept-Encoding')
        if (request.method=='GET' and response.status_code==200 and text_type and not response.headers.get('Content-Encoding') and not request.headers.get('Range') and request.accept_encodings['gzip']>0):
            response.direct_passthrough=False
            data=response.get_data()
            if len(data)>=1024:
                compressed=gzip.compress(data,compresslevel=5,mtime=0)
                if len(compressed)<len(data):
                    response.set_data(compressed)
                    response.headers['Content-Encoding']='gzip'
                    response.headers['Content-Length']=str(len(compressed))
                    etag,_=response.get_etag()
                    if etag:response.set_etag(etag,weak=True)
        return response

    return {'image':static_image,'srcset':srcset}


def upload_variant(app,filename,width):
    """Cache only three bounded sizes; preserve original uploads and video range handling."""
    if width not in WIDTHS:abort(400,'Choose a supported image size.')
    root=Path(app.config['UPLOAD_DIR']).resolve();source=root/filename
    if source.parent!=root or not source.is_file():abort(404)
    directory=root/'_image_cache';target=directory/f'{width}-{filename}.webp'
    if not target.exists():
        directory.mkdir(exist_ok=True)
        with Image.open(source) as im:
            if im.width*im.height>20000000:abort(400,'Image is too large.')
            im=im.convert('RGBA' if im.mode=='RGBA' else 'RGB')
            im.thumbnail((width,width*4),Image.Resampling.LANCZOS)
            # Atomic rename permits concurrent requests to the same new thumbnail.
            data_name=secrets.token_hex(16)
            temporary=directory/(data_name+'.webp')
            try:
                buffer=io.BytesIO();im.save(buffer,'WEBP',quality=85,method=4)
                payload=buffer.getvalue()
                if not payload:raise ValueError('Image encoding failed.')
                temporary.write_bytes(payload)
                temporary.replace(target)
            finally:temporary.unlink(missing_ok=True)
    return directory,target.name
