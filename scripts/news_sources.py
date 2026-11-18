"""Bounded public-news discovery and auditable source use. No paid search API.

Article text lives in memory only. Publication, topic date, geography, source
attribution and publication-in-summary are separate facts in the public ledger.
"""
import datetime as dt,hashlib,json,re,time,unicodedata
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urljoin,urlparse,urlunparse,parse_qsl,urlencode
from bs4 import BeautifulSoup
from update_data import BASE,now_iso
from market_history import atomic_text
from topic_discovery import read_public,matching_foods

CONFIG=BASE/'data/news_sources.json'
STATE=BASE/'data/news_monitor.json'
VERSION=1
def clean(v):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(v or ''))).strip()
def canonical(url):
 p=urlparse(url)
 # Pagination and tracking do not create another article. Keep an article ID
 # query if a publisher uses one; never follow a different publisher's URL.
 query=[(k,v) for k,v in parse_qsl(p.query) if not (k.startswith('utm_') or k in ('page','display','fbclid','gclid'))]
 path=re.sub(r'/+$','',p.path)
 return urlunparse(('https',p.netloc.lower(),path,'',urlencode(sorted(query)),''))
def identity(url):return 'news-'+hashlib.sha256(canonical(url).encode()).hexdigest()[:16]
def load_state(path=STATE):
 try:return json.loads(path.read_text(encoding='utf-8'))
 except (FileNotFoundError,json.JSONDecodeError):return {'version':VERSION,'sources':{},'articles':{}}
def save_state(state,path=STATE):atomic_text(path,json.dumps(state,ensure_ascii=False,indent=2)+'\n')
def parse_date(value):
 try:
  stamp=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
  if stamp.tzinfo:return stamp.astimezone(dt.timezone(dt.timedelta(hours=9))).date()
 except ValueError:pass
 m=re.search(r'(20\d{2})[年/.-]\s*(\d{1,2})[月/.-]\s*(\d{1,2})',clean(value))
 if not m:return None
 try:return dt.date(*map(int,m.groups()))
 except ValueError:return None
def dated_metadata(soup):
 for attrs in ({'property':'article:published_time'},{'itemprop':'datePublished'},{'name':'pubdate'}):
  tag=soup.find('meta',attrs=attrs)
  if tag and parse_date(tag.get('content')):return parse_date(tag['content'])
 def search(value):
  if isinstance(value,dict):
   if value.get('datePublished'):return parse_date(value['datePublished'])
   for v in value.values():
    found=search(v)
    if found:return found
  if isinstance(value,list):
   for v in value:
    found=search(v)
    if found:return found
  return None
 for tag in soup.find_all('script',type='application/ld+json'):
  try:
   found=search(json.loads(tag.string or tag.get_text()))
   if found:return found
  except (ValueError,TypeError):pass
 for tag in soup.select('time[datetime]'):
  if parse_date(tag['datetime']):return parse_date(tag['datetime'])
 return None
def article_text(raw,foods):
 soup=BeautifulSoup(raw,'html.parser');published=dated_metadata(soup)
 # A login/menu is not a paywall. Reject an actual restricted article body.
 for tag in soup.find_all('script',type='application/ld+json'):
  if re.search(r'"isAccessibleForFree"\s*:\s*(?:false|"false")',tag.get_text(),re.I):raise ValueError('restricted_article')
 for tag in soup.select('script,style,nav,footer,aside'):tag.decompose()
 headings=[h for h in soup.find_all(['h1','h2','h3']) if matching_foods(clean(h.get_text()),foods)]
 if not headings:raise ValueError('food_heading_missing')
 heading=headings[0];title=clean(heading.get_text(' ',strip=True))
 root=soup.find('article') or soup.select_one('[itemprop="articleBody"],.article-body,.article_body,.article-content,.news-text,.newsTxt,.detail-body') or soup
 text=clean(root.get_text(' ',strip=True));position=text.find(title)
 if position<0:
  # Body-only containers may omit the headline; publication still needs
  # metadata or the neighborhood of that particular headline in the page.
  page=clean(soup.get_text(' ',strip=True));pos=page.find(title)
  near=page[max(0,pos-100):pos+len(title)+180]
 else:
  near=text[max(0,position-100):position+len(title)+180];text=text[position:]
 if not published:published=parse_date(near)
 for stop in ('この記事を読んで','アクセスランキング','関連記事','Related News','関連ニュース','最新ニュース一覧'):
  end=text.find(stop)
  if end>len(title)+40:text=text[:end]
 if len(text)>18000:raise ValueError('article_body_ambiguous')
 if re.search(r'続きを読むには.{0,30}(会員|登録|ログイン)|有料会員限定',text):raise ValueError('restricted_article')
 if len(text)<len(title)+50:raise ValueError('article_body_missing')
 return soup,title,published,text
def get_article(url,source,foods,getter=read_public):
 raw=getter(url,source);soup=BeautifulSoup(raw,'html.parser')
 # Follow only a publicly offered continuation of this exact article, once.
 more=next((urljoin(url,a['href']) for a in soup.select('a[href]') if clean(a.get_text()) in ('続きを読む','全文を読む') and canonical(urljoin(url,a['href']))==canonical(url)),None)
 if more and more!=url:raw=getter(more,source)
 return article_text(raw,foods)
def source_entries(raw,source,foods):
 soup=BeautifulSoup(raw,'html.parser');out={}
 for a in soup.select('a[href]'):
  url=urljoin(source['index'],a['href']);title=clean(a.get_text(' ',strip=True))
  if urlparse(url).scheme!='https' or urlparse(url).hostname not in source['hosts'] or source['include'] not in url:continue
  chosen=matching_foods(title,foods)
  if not chosen or not re.search('生育|出荷|収穫|不作|豊作|不漁|豊漁|水揚|漁|高温|少雨|長雨|日照|海水温|品質|小玉|大玉|肥大|果樹',title):continue
  url=canonical(url);out[url]={'url':url,'sourceId':source['id'],'title':title,'foodIds':[f['foodId'] for f in chosen]}
 return list(out.values())[:30]
def make_item(profile,food,text,published,title):
 name=food['name'];cause=profile.get('causeByFood',{}).get(name,profile.get('cause'))
 summary=profile.get('summaryByFood',{}).get(name,profile.get('summary'))
 url=canonical(profile['url']);ident=identity(url)
 return {'food':{'id':food['foodId'],'name':name},'url':url,'publishedAt':published.isoformat(),
  'reportKey':ident,'sourceFamily':ident,'sourceName':profile['publisher'],'sourceTitle':title,'title':name+'：'+profile['title'],
  'observedPeriod':profile['periodStart']+'～'+profile['periodEnd']+'の産地・海域情報（記事の取材時点）',
  'periodStart':profile['periodStart'],'periodEnd':profile['periodEnd'],'reportYear':int(profile['periodEnd'][:4]),'seasonalRecord':True,
  'scope':profile['scope'],'region':profile['region'],'geographicLevel':'regional','reportType':'報道機関の産地・海域取材',
  'sourceType':'news','newsArticleId':ident,'excerpt':text,'publicExcerpt':text[:24]+'…',
  'preparedSummary':summary,'summaryProvider':'ChatGPT','causeAssessment':cause,'causeIncludedInSummary':bool(cause and cause['text'] in summary),
  'evidenceSections':[{'label':'採用した事実（整理）','text':' '.join(profile['facts'])}],
  'newsReview':{'method':'source_text_review','reviewedAt':'2026-11-18','facts':profile['facts'],'checks':profile['reviewNotes'],
    'corroboration':profile.get('corroboration',[]),'verificationLevel':'reported'},
  'limitations':'記事が取材した産地・海域・時点に限った情報です。取材先の見解は全国的な因果関係の実証ではありません。'+(' 見解・推測は未確定として表示しています。' if cause and cause['status'] in ('inference','source_hypothesis') else '')}
def focus_text(text,food,foods):
 sentences=[s+'。' for s in text.split('。') if s]
 selected=[]
 for i,s in enumerate(sentences):
  if food not in matching_foods(s,foods):continue
  selected.append(s)
  if i+1<len(sentences):
   other=matching_foods(sentences[i+1],foods)
   if not other or other==[food]:selected.append(sentences[i+1])
 return ''.join(dict.fromkeys(selected))[:3200]
def automatic_items(text,title,published,url,source,foods,today):
 """Unreviewed new articles need an attributed source and a free-budget AI pass."""
 if not re.search(r'によると|によりますと|研究員|教授|試験場|JA|ＪＡ|漁協|生産者|農家|園主',text):return [],'attribution_missing'
 out=[]
 # A publication date near the headline cannot establish the crop year.
 front=text[:len(title)+120].replace(title,'',1)
 front=re.sub(r'20\d{2}[年/.-]\s*\d{1,2}[月/.-]\s*\d{1,2}日?','',front)
 body=front+text[len(title)+120:]
 for food in matching_foods(title,foods):
  excerpt=focus_text(body,food,foods)
  if len(excerpt)<60 or not re.search('今年|ことし|今季|今シーズン|'+str(today.year),excerpt):continue
  # Old-year research in a newly published article is background, not this crop.
  if re.search(r'(?:202[0-5]|令和[1-7])年(?:度)?(?:の|に|産|夏|調査)',excerpt) and not re.search(str(today.year)+r'年|今年|ことし|今季|今シーズン',excerpt):continue
  ident=identity(url)
  out.append({'food':{'id':food['foodId'],'name':food['name']},'url':canonical(url),'publishedAt':published.isoformat(),
   'reportKey':ident,'sourceFamily':ident,'sourceName':source['name'],'sourceTitle':title,'title':food['name']+'：'+title,
   'observedPeriod':str(today.year)+'年の状況（記事が取材した時点）','periodStart':None,'periodEnd':published.isoformat(),
   'reportYear':today.year,'seasonalRecord':True,'scope':'記事に記載の産地・海域（原文参照）','geographicLevel':'regional',
   'sourceType':'news','newsArticleId':ident,'reportType':'報道機関の取材','excerpt':excerpt,'publicExcerpt':excerpt[:24]+'…','requireAi':True,
   'evidenceSections':[{'label':'原文冒頭（全文は記事へ）','text':excerpt[:24]+'…'}],
   'newsReview':{'method':'automatic_source_checks','checkedAt':now_iso(),'facts':[],
    'checks':['原文本文・公表日・今年への言及・取材先の記載を確認','要約の数値・見通し表現を自動照合。意味全体の独立検証は未実施'],
    'corroboration':[],'verificationLevel':'automatic_checks'},
   'limitations':'取材先の説明を整理した要約です。公表日と取材の対象期間は異なる場合があります。産地・魚種・時期の意味全体の独立検証は未実施です。'})
 return out,'awaiting_summary' if out else 'current_context_missing'
def collect(obj,today,limit=6,seconds=150,getter=read_public,path=STATE,config=None):
 config=config or json.loads(CONFIG.read_text(encoding='utf-8'));state=load_state(path);started=time.monotonic();items=[];errors=[];queue=[]
 sources={s['id']:{**s,'url':s['index']} for s in config['sources']};foods=json.loads((BASE/'data/topic_catalog.json').read_text(encoding='utf-8'))['foods']
 profiles={canonical(p['url']):p for p in config['reviewed'] if dt.date.fromisoformat(p['publishedAt'])<=today and (today-dt.date.fromisoformat(p['publishedAt'])).days<=120}
 # Known, source-reviewed examples precede general news; the same publisher
 # cannot occupy the whole discovery budget. One article can support two foods.
 for url,p in profiles.items():queue.append({'url':url,'sourceId':p['sourceId'],'title':p['title'],'reviewed':True})
 def index(source):
  return source,source_entries(getter(source['index'],source),source,foods)
 # Rotate five regional publisher indexes per run, instead of downloading
 # every portal repeatedly. Explicit source-reviewed articles remain queued.
 selected=sorted(sources.values(),key=lambda s:state['sources'].get(s['id'],{}).get('lastAttemptAt',''))[:5]
 with ThreadPoolExecutor(max_workers=2) as pool:
  futures={pool.submit(index,s):s for s in selected}
  for future in as_completed(futures):
   try:
    source,entries=future.result();queue.extend(entries);state['sources'][source['id']]={'checkedAt':now_iso(),'lastAttemptAt':now_iso(),'status':'ok','candidates':len(entries)}
   except Exception as error:
    source=futures[future];state['sources'][source['id']]={'lastAttemptAt':now_iso(),'status':'error','error':type(error).__name__};errors.append(source['id']+' index: '+type(error).__name__)
 # Stable reviewed-first ordering, then rotate least-recently checked articles.
 unique={}
 for e in queue:unique.setdefault(canonical(e['url']),e)
 queue=sorted(unique.values(),key=lambda e:(not e.get('reviewed'),state['articles'].get(identity(e['url']),{}).get('lastCheckedAt',''),e['url']))
 attempts=0;publisher_attempts={}
 for entry in queue:
  if attempts>=limit or time.monotonic()-started>seconds:break
  ident=identity(entry['url']);prior=state['articles'].setdefault(ident,{'id':ident,'url':canonical(entry['url']),'title':entry['title']})
  # Retain already generated/pending evidence for a later eligible AI run.
  if prior.get('retryAfter','')>today.isoformat():continue
  source=sources[entry['sourceId']]
  if publisher_attempts.get(source['id'],0)>=3:continue
  publisher_attempts[source['id']]=publisher_attempts.get(source['id'],0)+1;attempts+=1
  prior.update({'publisher':source['name'],'lastAttemptAt':now_iso()})
  try:
   _,title,published,text=get_article(entry['url'],source,foods,getter)
   if not published or published>today or (today-published).days>120:raise ValueError('publication_date_unconfirmed_or_old')
   fingerprint=hashlib.sha256(text.encode()).hexdigest();profile=profiles.get(canonical(entry['url']))
   if profile:
    if published.isoformat()!=profile['publishedAt'] or not all(clean(word).replace(' ','') in text.replace(' ','') for group in profile['required'] for word in group):raise ValueError('reviewed_source_claims_changed')
    if prior.get('reviewedFingerprint') and prior['reviewedFingerprint']!=fingerprint:
     found,status=automatic_items(text,title,published,entry['url'],source,foods,today)
     prior['reviewChanged']=True
    else:
     found=[make_item(profile,f,text,published,title) for f in foods if f['name'] in profile['foodNames']];status='source_reviewed'
     prior['reviewedFingerprint']=fingerprint
   else:found,status=automatic_items(text,title,published,entry['url'],source,foods,today)
   items.extend(found);prior.update({'title':title,'publishedAt':published.isoformat(),'fingerprint':fingerprint,'lastCheckedAt':now_iso(),'status':status,'foodIds':[i['food']['id'] for i in found],
    'retryAfter':(today+dt.timedelta(days=0 if any(i.get('requireAi') for i in found) else 3)).isoformat()})
  except Exception as error:
   # Public exceptions contain no request/credential body. Previous summaries
   # remain in the seed; an error is never labelled a source verification.
   prior.update({'lastCheckedAt':now_iso(),'status':'unavailable','error':str(error)[:100] if isinstance(error,ValueError) else type(error).__name__,'retryAfter':(today+dt.timedelta(days=1)).isoformat()})
   errors.append(source['id']+': '+prior['error'])
  save_state(state,path)
 state['lastRun']={'checkedAt':now_iso(),'articleAttempts':attempts,'sourceItems':len(items),'errors':errors}
 save_state(state,path);obj['metadata']['newsDiscoveryLastRun']=state['lastRun']
 print('NEWS DISCOVERY',json.dumps(state['lastRun'],ensure_ascii=False),flush=True)
 return items,errors
def build_ledger(obj,state=None):
 """Used means linked to an actually published summary, never just fetched."""
 state=state or load_state();articles={}
 for t in obj['topics']:
  if t.get('sourceType')!='news' or not t.get('newsArticleId'):continue
  s=t['sources'][0];ident=t['newsArticleId'];review=t.get('newsReview') or {}
  row=articles.setdefault(ident,{'id':ident,'url':s['url'],'publisher':s.get('name'),'title':s.get('title'),
   'publishedAt':t.get('publishedAt'),'status':'used','foodIds':[],'uses':[],'facts':review.get('facts',[]),
   'checks':review.get('checks',[]),'verificationLevel':review.get('verificationLevel'),'corroboration':review.get('corroboration',[])})
  if t['foodId'] not in row['foodIds']:row['foodIds'].append(t['foodId'])
  row['uses'].append({'topicId':t['id'],'foodId':t['foodId'],'scope':t.get('scope'),'observedPeriod':t.get('observedPeriod'),'causeStatus':t.get('causeAssessment',{}).get('status','unconfirmed')})
 for ident,p in state.get('articles',{}).items():
  if ident in articles:
   articles[ident]['lastCheckedAt']=p.get('lastCheckedAt');articles[ident]['latestSourceStatus']=p.get('status');articles[ident]['sourceChanged']=p.get('reviewChanged',False);continue
  articles[ident]={k:p[k] for k in ('id','url','title','publisher','publishedAt','lastCheckedAt','foodIds') if k in p}
  articles[ident]['status']='pending' if p.get('status') in ('source_reviewed','awaiting_summary') else 'unavailable' if p.get('status')=='unavailable' else 'held'
  articles[ident]['uses']=[];articles[ident]['reason']=p.get('error') or p.get('status')
 rows=sorted(articles.values(),key=lambda r:r.get('publishedAt',''),reverse=True)
 obj['news']={'articles':rows,'lastCheckedAt':state.get('lastRun',{}).get('checkedAt'),'sourceErrors':state.get('lastRun',{}).get('errors',[])}
 return obj['news']
