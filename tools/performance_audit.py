"""Repeatable local payload audit; not a browser/Lighthouse timing score."""
import sys, json, statistics, time
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from test_store import StoreTests
class Assets(HTMLParser):
    def __init__(self): super().__init__(); self.images=[]; self.scripts=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='img': self.images.append(a)
        if tag=='image': self.images.append({'src':a.get('href','')})
        if tag=='script' and a.get('src'): self.scripts.append(a['src'])
def measure():
    case=StoreTests();case.setUp()
    try:
        results={}
        for route in ['/','/shop','/product/1']:
            samples=[]
            for _ in range(25):
                start=time.perf_counter();response=case.client.get(route,headers={'Accept-Encoding':'gzip'});samples.append((time.perf_counter()-start)*1000)
            plain=case.client.get(route);parser=Assets();parser.feed(plain.get_data(as_text=True))
            def size(url):
                path=urlsplit(url).path
                p=Path(case.app.root_path)/unquote(path.lstrip('/'))
                return p.stat().st_size if path.startswith('/static/') and p.is_file() else 0
            all_urls={a.get('src','') for a in parser.images}
            eager={a.get('src','') for a in parser.images if a.get('loading')!='lazy'}
            results[route]={'status':plain.status_code,'median_local_ms':round(statistics.median(samples),2),'html_gzip_bytes':len(response.data),'default_image_bytes':sum(map(size,all_urls)),'eager_default_image_bytes':sum(map(size,eager)),'script_bytes':sum(map(size,set(parser.scripts))),'responsive_img_count':sum(bool(a.get('srcset')) for a in parser.images)}
        return results
    finally:case.tearDown()
if __name__=='__main__':print(json.dumps(measure(),indent=2))
