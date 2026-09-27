from flask import Flask, request, jsonify, render_template, send_file
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import io, zipfile, re, os, requests
app=Flask(__name__,static_folder='static',template_folder='templates')
UA='Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36'
def clean(s): return re.sub(r'[ \t\r\f\v]+',' ',s or '').strip()
def extract(url):
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        c=b.new_context(user_agent=UA,locale='fr-FR',viewport={'width':1280,'height':900}); page=c.new_page()
        page.goto(url,wait_until='domcontentloaded',timeout=45000)
        try: page.wait_for_load_state('networkidle',timeout=12000)
        except Exception: pass
        page.wait_for_timeout(1500)
        for _ in range(4): page.mouse.wheel(0,1400); page.wait_for_timeout(400)
        final=page.url; title=page.title(); html=page.content(); b.close()
    s=BeautifulSoup(html,'html.parser')
    for x in s(['script','style','noscript','svg','nav','footer','header','form','aside']): x.decompose()
    og=s.find('meta',property='og:title'); h1=s.find('h1')
    if og and og.get('content'): title=clean(og['content'])
    if h1: title=clean(h1.get_text(' ',strip=True)) or title
    cs=s.find_all(['article','main','section','div'])
    def score(n):
        mark=(' '.join(n.get('class',[]))+' '+(n.get('id') or '')).lower(); q=min(len(n.get_text(' ',strip=True))/100,25)+4*len(n.find_all('p'))
        q+=10*sum(k in mark for k in ('article','content','post','story','entry','main'))-10*sum(k in mark for k in ('comment','footer','sidebar','menu','nav','related')); return q
    box=max(cs,key=score) if cs else s.body; parts=[]
    for e in box.find_all(['h1','h2','h3','p','li','blockquote']):
        t=clean(e.get_text(' ',strip=True))
        if len(t)>=20 and t not in parts: parts.append(t)
    imgs=[]; ogi=s.find('meta',property='og:image')
    if ogi and ogi.get('content'): imgs.append({'url':urljoin(final,ogi['content']),'alt':'Image principale'})
    for im in s.find_all('img'):
        src=im.get('src') or im.get('data-src') or im.get('data-lazy-src') or im.get('data-original')
        if not src and im.get('srcset'): src=im['srcset'].split(',')[-1].strip().split(' ')[0]
        if not src: continue
        u=urljoin(final,src); low=(u+' '+clean(im.get('alt'))).lower()
        if u.startswith(('http://','https://')) and not any(x['url']==u for x in imgs) and not any(k in low for k in ('favicon','sprite','tracking','avatar')): imgs.append({'url':u,'alt':clean(im.get('alt'))})
    return {'title':clean(title) or 'Article sans titre','text':'\n\n'.join(parts),'images':imgs,'final_url':final}
@app.get('/')
def home(): return render_template('index.html')
@app.get('/health')
def health(): return jsonify(ok=True)
@app.post('/api/extract')
def api():
    u=(request.get_json(silent=True) or {}).get('url','').strip()
    if not u.startswith(('http://','https://')): return jsonify(error='URL invalide.'),400
    try: return jsonify(extract(u))
    except Exception as e: return jsonify(error='Extraction impossible: '+str(e)),502
@app.post('/api/download-images')
def dl():
    urls=(request.get_json(silent=True) or {}).get('urls',[]); mem=io.BytesIO()
    with zipfile.ZipFile(mem,'w',zipfile.ZIP_DEFLATED) as z:
        for i,u in enumerate(urls,1):
            try:
                r=requests.get(u,headers={'User-Agent':UA},timeout=20); r.raise_for_status(); ct=r.headers.get('content-type',''); ext='.jpg'
                if 'png' in ct: ext='.png'
                elif 'webp' in ct: ext='.webp'
                elif 'gif' in ct: ext='.gif'
                z.writestr(f'image_{i}{ext}',r.content)
            except Exception: pass
    mem.seek(0); return send_file(mem,as_attachment=True,download_name='images_article.zip',mimetype='application/zip')
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT','5000')))
