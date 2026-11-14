"""Bounded discovery on allowlisted primary indexes, with per-food audit trails.

An index check is not a claim that an article or current crop information was
found. No paid search API, global web search, login or generated source URL.
"""
import datetime as dt
import hashlib
import io
import json
import os
import re
import time
import unicodedata
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin,urlparse
from bs4 import BeautifulSoup
from market_history import atomic_text
from update_data import BASE,USER_AGENT,now_iso

CATALOG=BASE/'data/topic_catalog.json'
STATE=BASE/'data/topic_monitor.json'
VERSION=1

def compact(value):
 return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(value))).strip()

def aliases_for(food):
 values=food['aliases'][:]
 # Kana variants are safe only within the configured food category.
 for alias in values[:]:
  if alias=='なし':continue
  values.append(''.join(chr(ord(c)+0x60) if 'ぁ'<=c<='ゖ' else c for c in alias))
  values.append(''.join(chr(ord(c)-0x60) if 'ァ'<=c<='ヶ' else c for c in alias))
 if food['name']=='なし':values=[s for s in values if s!='なし']
 return sorted(set(compact(s) for s in values if s),key=len,reverse=True)

def matching_foods(text,foods):
 text=compact(text);matches=[]
 for food in foods:
  for alias in aliases_for(food):
   for match in re.finditer(re.escape(alias),text):
    # Avoid サバ in an unrelated longer katakana word. Specific taxon
    # aliases are registered explicitly rather than guessed from price data.
    before=text[match.start()-1:match.start()] if match.start() else ''
    after=text[match.end():match.end()+1]
    if re.fullmatch(r'[ァ-ヶー]+',alias) and ((before and re.fullmatch(r'[ァ-ヶー]',before)) or (after and re.fullmatch(r'[ァ-ヶー]',after))):
     continue
    matches.append((match.start(),match.end(),food));break
   else:continue
   break
 out=[]
 for start,end,food in matches:
  if any(a<=start and b>=end and b-a>end-start for a,b,f in matches):continue
  if food not in out:out.append(food)
 return out

def trusted(url,source):
 parsed=urlparse(url)
 return parsed.scheme=='https' and parsed.hostname in source['hosts'] and not parsed.username and not parsed.password

def read_public(url,source,timeout=20,limit=3_000_000):
 if not trusted(url,source):raise ValueError('Non-allowlisted source')
 request=urllib.request.Request(url,headers={'User-Agent':USER_AGENT})
 with urllib.request.urlopen(request,timeout=timeout) as response:
  if not trusted(response.geturl(),source):raise ValueError('Non-allowlisted redirect')
  data=response.read(limit+1)
 if len(data)>limit:raise ValueError('Source too large')
 return data

def source_url(source,today):
 if source['id']=='fra-resources':
  return re.sub(r'/pr\d{4}/',f'/pr{today.year}/',source['url'])
 return source['url']

def discover_links(html,source,foods,today):
 soup=BeautifulSoup(html,'html.parser');found={}
 for a in soup.find_all('a',href=True):
  title=compact(a.get_text(' ',strip=True));url=urljoin(source_url(source,today),a['href']).split('#')[0]
  if not trusted(url,source) or source['include'] not in url or not title:continue
  candidates=matching_foods(title,foods)
  relevant=any(word in title for word in source['terms'])
  if not relevant:continue
  # Crop-wide reports can contain named food paragraphs even if no food is
  # named in the index. They enter the bounded queue, not automatic publication.
  if not candidates and not re.search('漁況情報|普及活動情勢|長期漁況|浮魚',title):continue
  if re.search('入札|採用|募集|研究報告|研究成果|レシピ|栽培方法',title):continue
  found[url]={'url':url,'title':title[:240],'foodIds':[f['foodId'] for f in candidates],
              'sourceId':source['id']}
 return list(found.values())[:160]

def publication_date(soup,title):
 # Publication metadata is distinguished from a visible "updated" date.
 for attrs in ({'property':'article:published_time'},{'itemprop':'datePublished'}):
  tag=soup.find('meta',attrs=attrs)
  if tag and tag.get('content'):
   value=tag['content'][:10]
   try:return dt.date.fromisoformat(value)
   except ValueError:pass
 for tag in soup.find_all('time',datetime=True):
  try:return dt.date.fromisoformat(tag['datetime'][:10])
  except ValueError:pass
 # Body dates near the article header only. Do not mistake footer dates or
 # dates embedded in an archive URL for a publication date.
 node=next((h for h in soup.find_all(['h1','h2']) if compact(h.get_text())==title),None)
 if not node:return None
 text=compact(' '.join(str(x.get_text(' ',strip=True) if hasattr(x,'get_text') else x) for x in list(node.next_siblings)[:8]))[:1100]
 for pattern in (r'(20\d{2})[年/.-]\s*(\d{1,2})[月/.-]\s*(\d{1,2})日?',r'令和\s*(\d+)年\s*(\d+)月\s*(\d+)日'):
  match=re.search(pattern,text)
  if match:
   year,month,day=map(int,match.groups())
   if pattern.startswith('令和'):year+=2018
   try:return dt.date(year,month,day)
   except ValueError:return None
 return None

def article_items(raw,entry,source,foods,today):
 if raw.startswith(b'%PDF'):
  # General PDF tables require a dedicated parser; never turn table cells
  # into supply news. PDF links are retained in the source queue for maintenance.
  return [],'dedicated_pdf_parser_needed'
 soup=BeautifulSoup(raw,'html.parser')
 for tag in soup.find_all(['script','style','nav','footer','aside']):tag.decompose()
 headings=[h for h in soup.find_all('h1') if len(compact(h.get_text()))>4]
 title_node=next((h for h in headings if matching_foods(h.get_text(),foods) or any(w in h.get_text() for w in source['terms'])),headings[-1] if headings else None)
 if not title_node:return [],'article_heading_missing'
 title=compact(title_node.get_text(' ',strip=True))
 text=compact(soup.get_text(' ',strip=True))
 candidates=matching_foods(title,foods)
 kochi=source['id']=='kochi-fruit' and re.search(str(today.year)+r'年の生育調査',title)
 if kochi:
  date_match=re.search(r'(20\d{2})/(\d{1,2})/(\d{1,2})',text)
  date=dt.date(*map(int,date_match.groups())) if date_match else None
  if not date or date>today or date.year!=today.year:return [],'observation_update_date_unconfirmed'
  block=text.split('コメント',1)[1].split('生態調査',1)[0].strip() if 'コメント' in text else ''
  if not block or not candidates:return [],'crop_commentary_missing'
  published=None;updated=date.isoformat()
 else:
  date=publication_date(soup,title)
  if not date or date.year!=today.year or date>today:return [],'current_publication_date_unconfirmed'
  published=date.isoformat();updated=None
  if not candidates:candidates=matching_foods(text,foods)
  block=None
 root=soup.find('article') or soup.select_one('.entry-content,.post-content,.article-body') or soup
 paragraphs=[compact(p.get_text(' ',strip=True)) for p in root.find_all(['p','li'])]
 if not paragraphs:paragraphs=[compact(line) for line in root.get_text('\n',strip=True).splitlines()]
 items=[]
 for food in candidates:
  if block:excerpt=block
  else:
   chosen=[]
   for paragraph in paragraphs:
    if 24<=len(paragraph)<=1600 and food in matching_foods(paragraph,foods) and re.search(r'生育|出荷|収穫|作柄|肥大|着色|水揚|漁獲|来遊|回帰|漁況|へい死',paragraph):
     if re.search('レシピ|お問い合わせ|関連リンク',paragraph):continue
     chosen.append(paragraph)
   excerpt='\n'.join(dict.fromkeys(chosen))[:1200]
  if len(excerpt)<24:continue
  # A paragraph explicitly discussing only a past year must not acquire the
  # current year merely from the page date.
  years=re.findall(r'20\d{2}',excerpt)
  if years and str(today.year) not in years and any(int(y)<today.year for y in years):continue
  digest=hashlib.sha256(entry['url'].encode()).hexdigest()[:12]
  short='。'.join(excerpt.split('。')[:3]).strip('。')+'。'
  if len(short)>330:short=short[:short.rfind('。',0,330)+1] or short[:160]+'…'
  items.append({'food':{'id':food['foodId'],'name':food['name']},'url':entry['url'],
   'publishedAt':published,'sourceUpdatedAt':updated,
   'reportKey':'discovery-'+source['id']+'-'+digest,'sourceFamily':'discovery-'+source['id'],
   'sourceName':source['name'],'sourceTitle':title,
   'title':food['name']+'：'+title,
   'observedPeriod':f'{today.year}年の生育調査（資料の記載品種）' if kochi else f'{date.year}年{date.month}月{date.day}日公表の資料（詳細な対象期間は原文参照）',
   'periodStart':None,'periodEnd':None,'seasonalRecord':bool(kochi),'reportYear':today.year,
   'isForecast':False,'scope':source['scope'],'reportType':'試験場の生育観測' if kochi else '産地・海域の生育、出荷または漁況に関する記述',
   'excerpt':excerpt,'summaryExcerpt':short,'requireAi':source['id'].startswith('ja-'),
   'publicExcerpt':excerpt[:24]+'…' if source['id'].startswith('ja-') else excerpt,
   'evidenceSections':[{'label':'原文の該当箇所' if kochi else '出典の記述（対象条件は原文参照）','text':excerpt if not source['id'].startswith('ja-') else excerpt[:24]+'…'}],
   'limitations':'記載の産地・品種・調査樹・海域に限った情報です。全国の収穫量・漁獲量を示すものではありません。'+('更新日は確認しましたが初回公表日は未確認です。' if kochi else '公表日と情報の対象期間は一致するとは限りません。')})
 return items,'source_text_found' if items else 'food_specific_evidence_missing'

def load_state(path=STATE):
 if not path.exists():return {'version':VERSION,'sources':{},'articles':{},'foods':{}}
 state=json.loads(path.read_text(encoding='utf-8'))
 if state.get('version')!=VERSION:raise ValueError('Unknown topic-monitor format')
 return state

def save_state(state,path=STATE):
 atomic_text(path,json.dumps(state,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def collect(obj,today,limit=8,seconds=210,getter=read_public,path=STATE,catalog=None):
 catalog=catalog or json.loads(CATALOG.read_text(encoding='utf-8'))
 state=load_state(path);started=time.monotonic();items=[];errors=[];checked=[];queue=[]
 sources={s['id']:s for s in catalog['sources']};foods=catalog['foods'];date=today.isoformat()
 def index(source):
  url=source_url(source,today)
  try:
   raw=getter(url,source)
   if not raw or b'<html' not in raw[:2000].lower():raise ValueError('Index HTML missing')
   choices=[f for f in foods if source['id'] in f['sourceIds']]
   links=discover_links(raw,source,choices,today)
   return source,{'checkedAt':now_iso(),'status':'ok','url':url,'candidateCount':len(links),'links':links},None
  except Exception as error:return source,None,type(error).__name__
 with ThreadPoolExecutor(max_workers=2) as pool:
  for future in as_completed([pool.submit(index,s) for s in sources.values()]):
   source,result,error=future.result();sid=source['id']
   if error:
    prior=state['sources'].setdefault(sid,{})
    prior.update({'lastAttemptAt':now_iso(),'status':'error','error':error})
    errors.append(sid+': '+error)
   else:
    state['sources'][sid]=result;checked.append(sid);queue.extend(result['links'])
 # Fair rotation: source checks are recorded for every food, while body checks
 # have separate timestamps. No source match is not labelled successful coverage.
 for food in foods:
  row=state['foods'].setdefault(food['foodId'],{'foodId':food['foodId'],'name':food['name']})
  relevant=[sid for sid in checked if sid in food['sourceIds']]
  row['lastAttemptAt']=now_iso();row['sourceIds']=food['sourceIds']
  if relevant:
   row['lastIndexCheckedAt']=now_iso();row['checkedSourceIds']=relevant
   row['candidateCount']=sum(food['foodId'] in x['foodIds'] for x in queue)
  row['indexStatus']='ok' if len(relevant)==len(food['sourceIds']) else 'partial' if relevant else 'error'
  row['coverage']='source_pending' if row.get('candidateCount') else 'no_matching_link' if relevant else 'source_unavailable'
 articles=state['articles']
 queue=list({q['url']:q for q in queue}.values())
 def priority(entry):
  ids=entry['foodIds'];missing=sum(not any(t.get('foodId')==f and t.get('yearSpecific') for t in obj['topics']) for f in ids)
  prior=articles.get(entry['url'],{})
  return (0 if any(f.get('name')=='くり' and f['foodId'] in ids for f in foods) else 1,
          -missing,prior.get('lastCheckedAt',''),entry['url'])
 pending=[q for q in queue if articles.get(q['url'],{}).get('retryAfter','')<=date]
 pending.sort(key=priority);attempts=0
 for entry in pending:
  if attempts>=limit or time.monotonic()-started>=seconds:break
  source=sources[entry['sourceId']];choices=[f for f in foods if source['id'] in f['sourceIds']]
  attempts+=1;prior=articles.setdefault(entry['url'],{})
  try:
   raw=getter(entry['url'],source)
   found,result=article_items(raw,entry,source,choices,today)
   items.extend(found)
   prior.update({'lastCheckedAt':now_iso(),'status':result,'fingerprint':hashlib.sha256(raw).hexdigest(),
    'foodIds':list(set(entry['foodIds']+[i['food']['id'] for i in found])),
    'retryAfter':(today+dt.timedelta(days=3 if found else 7)).isoformat()})
   for fid in prior['foodIds']:
    row=state['foods'][fid];row['lastArticleCheckedAt']=now_iso();row['lastArticleResult']=result
    if found and any(x['food']['id']==fid for x in found):row['lastEvidenceFoundAt']=now_iso();row['coverage']='evidence_found'
  except Exception as error:
   prior.update({'lastCheckedAt':now_iso(),'status':'error','error':type(error).__name__,
    'retryAfter':(today+dt.timedelta(days=3)).isoformat()});errors.append(source['id']+' article: '+type(error).__name__)
  save_state(state,path)
 obj['metadata']['topicDiscoverySources']=[{'id':s['id'],'name':s['name'],'url':source_url(s,today)} for s in sources.values()]
 state['lastRun']={'checkedAt':now_iso(),'registeredFoods':len(foods),'checkedIndexes':len(checked),
  'totalIndexes':len(sources),'articleAttempts':attempts,'sourceItems':len(items),'errors':errors}
 save_state(state,path);obj['metadata']['topicDiscoveryLastRun']=state['lastRun']
 publish_monitor(obj,state,today)
 print('CONTINUOUS TOPIC DISCOVERY',json.dumps(state['lastRun'],ensure_ascii=False),flush=True)
 return items,errors

def publish_monitor(obj,state,today):
 rows={}
 for food in obj['foods']:
  source=state.get('foods',{}).get(food['id'],{})
  latest=[t for t in obj['topics'] if t.get('foodId')==food['id'] and t.get('yearSpecific') and t.get('sources')]
  latest.sort(key=lambda t:t.get('publishedAt') or t.get('sourceUpdatedAt') or '',reverse=True)
  rows[food['id']]={k:source.get(k) for k in ('lastAttemptAt','lastIndexCheckedAt','lastArticleCheckedAt','lastArticleResult','lastEvidenceFoundAt','indexStatus','coverage','candidateCount','checkedSourceIds')}
  rows[food['id']]['hasCollectedYearSpecificSource']=bool(latest)
  rows[food['id']]['lastSourcePublicationAt']=latest[0].get('publishedAt') if latest else None
 obj['metadata']['foodResearchStatus']=rows
