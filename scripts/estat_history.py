"""Public e-Stat daily originals as a documented, approximate ten-day fallback.

The original rounded daily yen/kg prices cannot recover exact transaction
amounts. Quantity-weighted daily prices are labelled estimates, never passed
off as official ten-day quotations. Missing downloads block the whole period.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup
from market_history import atomic_text
from update_data import DATA, fetch, decode_csv, normalize, IMPORTED_FRUIT

CACHE=DATA.parent/'estat_daily.json'
YEAR_CLASS={2021:'000001150226',2022:'000001163286',2023:'000001201860'}
BASE='https://www.e-stat.go.jp/stat-search/files'
METHOD='estat_daily_weighted_v1'

def listing_url(year,page=1):
 return BASE+'?'+urlencode({'layout':'dataset','page':page,'limit':100,'toukei':'00500226',
  'tstat':'000001015623','tclass1':'000001032194','tclass2':'000001046984',
  'tclass3':YEAR_CLASS[year],'query':'主要'})

def listing_entries(html,year):
 soup=BeautifulSoup(html,'html.parser');entries={}
 for a in soup.find_all('a',href=True):
  href=a['href']
  if 'stat_infid=' not in href:continue
  label=re.sub(r'\s+','',a.get_text(' ',strip=True))
  m=re.search(r'日別調査\(令和(\d+)年(\d+)月(\d+)日\)(野菜|果実)主要卸売市場計',label)
  if not m:continue
  y,month,day,category=m.groups();date=dt.date(int(y)+2018,int(month),int(day))
  if date.year!=year:raise ValueError('e-Stat dataset year mismatch')
  ident=parse_qs(urlparse(href).query).get('stat_infid',[''])[0]
  if not re.fullmatch(r'\d{12}',ident):raise ValueError('Invalid public dataset ID')
  key=date.isoformat()+':'+category
  item={'date':date.isoformat(),'category':category,'url':'https://www.e-stat.go.jp/stat-search/file-download?'+urlencode({'statInfId':ident,'fileKind':1})}
  if key in entries and entries[key]!=item:raise ValueError('Conflicting daily datasets')
  entries[key]=item
 return entries

def daily_rows(blob,names,date):
 rows=csv.DictReader(io.StringIO(decode_csv(blob)))
 required={'年','月','日','品目名','品目コード','産地名','産地コード','数量','価格'}
 if not required.issubset(rows.fieldnames or []):raise ValueError('Daily CSV layout mismatch')
 out={};seen=False
 for row in rows:
  actual=dt.date(int(row['年']),int(row['月']),int(row['日'])).isoformat()
  if actual!=date:raise ValueError('Daily CSV observation date mismatch')
  seen=True
  if row['産地名'].strip() or row['産地コード'].strip():continue
  name=normalize(row['品目名']);code=int(row['品目コード'])
  if name not in names:continue
  if (name in IMPORTED_FRUIT)!=(50000<=code<60000):continue
  if name=='メロン' and code!=47000:continue
  try:q=float(row['数量'].replace(',',''));p=float(row['価格'].replace(',',''))
  except ValueError:
   # An unknown price with positive quantity makes this food unusable.
   try:q=float(row['数量'].replace(',',''))
   except ValueError:q=0
   if q>0:out[name]=None
   continue
  if not math.isfinite(q) or q<0 or not math.isfinite(p) or not 0<p<150000:raise ValueError('Invalid daily observation')
  if q==0:continue
  if name in out and out[name]!=[q,p]:raise ValueError('Conflicting daily commodity aggregates')
  out[name]=[q,p]
 if not seen:raise ValueError('Empty daily CSV')
 return out

def aggregate_period(entries,days):
 totals=defaultdict(lambda:[0,0]);invalid=set()
 for key in entries:
  if key not in days:raise ValueError('Incomplete period: daily download missing')
  for name,datum in days[key]['values'].items():
   if datum is None:invalid.add(name);continue
   q,p=datum;totals[name][0]+=q;totals[name][1]+=q*p
 return {name:round(amount/q,1) for name,(q,amount) in totals.items() if q>0 and name not in invalid}

def cache_load(path=CACHE):
 if not path.exists():return {'version':1,'manifests':{},'days':{}}
 value=json.loads(path.read_text(encoding='utf-8'))
 if value.get('version')!=1:raise ValueError('Unrecognized daily cache')
 return value

def cache_save(cache,path=CACHE):
 atomic_text(path,json.dumps(cache,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def manifest(year,cache):
 existing=cache['manifests'].get(str(year))
 if existing and existing.get('complete'):return existing['entries']
 allrows={}
 for page in range(1,41):
  found=listing_entries(fetch(listing_url(year,page),timeout=30),year)
  fresh={k:v for k,v in found.items() if k not in allrows}
  if not fresh:
   if page==1:raise ValueError('No national daily datasets in explicit year listing')
   break
  allrows.update(fresh)
  print('ESTAT MANIFEST',year,page,len(allrows),flush=True)
 else:raise ValueError('Daily manifest page budget exceeded')
 dates={k.split(':')[0] for k in allrows}
 if len(dates)<220 or {d[5:7] for d in dates}!={f'{m:02}' for m in range(1,13)}:
  raise ValueError('Incomplete annual daily manifest')
 for date in dates:
  if any(date+':'+c not in allrows for c in ('野菜','果実')):raise ValueError('Daily category pair missing')
 cache['manifests'][str(year)]={'complete':True,'entries':allrows}
 cache_save(cache)
 return allrows

def retrieve(entries,cache,names,limit,deadline):
 tasks=[(k,v) for k,v in entries.items() if k not in cache['days']][:limit]
 def get(task):
  key,item=task
  if time.monotonic()>deadline:return key,None,'time_budget'
  try:
   raw=fetch(item['url'],timeout=25)
   values=daily_rows(raw,names,item['date'])
   return key,{'sourceUrl':item['url'],'sha256':hashlib.sha256(raw).hexdigest(),'values':values},None
  except Exception as error:return key,None,type(error).__name__
 result={'attempted':0,'succeeded':0,'failed':0}
 with ThreadPoolExecutor(max_workers=2) as pool:
  for future in as_completed([pool.submit(get,t) for t in tasks]):
   key,value,error=future.result()
   if error=='time_budget':continue
   result['attempted']+=1
   if error:result['failed']+=1;print('ESTAT DAILY FAILED',key,error,flush=True)
   else:cache['days'][key]=value;result['succeeded']+=1
   if result['attempted']%10==0:cache_save(cache)
 cache_save(cache)
 return result

def grouped(entries):
 result=defaultdict(dict)
 for key,item in entries.items():
  date=dt.date.fromisoformat(item['date']);stamp=(date.year,date.month,min(3,(date.day-1)//10+1))
  result[stamp][key]=item
 return result

def verify_reconstruction(cache,archive):
 # A current, obtainable ten-day publication independently checks the method,
 # commodity selections, units and completeness before historical estimates.
 entries=cache['manifests'].get('2023',{}).get('entries',{})
 samples={s:v for s,v in grouped(entries).items() if s[1]==10}
 if len(samples)!=3:raise ValueError('Three October validation periods required')
 details=[]
 for stamp,parts in samples.items():
  estimate=aggregate_period(parts,cache['days'])
  official=archive.get('produce',stamp)
  if not official:raise ValueError('Official validation period missing')
  errors={name:round(abs(price-official['values'][name]),3) for name,price in estimate.items() if name in official['values']}
  if len(errors)<35 or max(errors.values())>1.1:
   raise ValueError('Daily reconstruction differs from official period: '+str(stamp)+' '+str(sorted(errors.items(),key=lambda x:-x[1])[:8]))
  details.append({'stamp':list(stamp),'foods':len(errors),'maxDifferenceYenKg':max(errors.values()),'sourceUrl':official['sourceUrl']})
 return details

def backfill_daily(obj,archive,limit=80,seconds=360):
 cache=cache_load();names={f['name'] for f in obj['foods'] if f['category']!='fish'}
 started=time.monotonic();deadline=started+seconds
 # Validate on full October 2023, not on a few favorable food observations.
 m=manifest(2023,cache);october={k:v for k,v in m.items() if v['date'][5:7]=='10'}
 result=retrieve(october,cache,names,limit,deadline)
 try:checks=verify_reconstruction(cache,archive)
 except ValueError as error:
  obj['metadata']['estatHistoryLastRun']={**result,'state':'validation_pending','detail':str(error)[:260]}
  print('ESTAT VALIDATION PENDING',str(error)[:260],flush=True);return result
 cache['validation']={'method':METHOD,'periods':checks};cache_save(cache)
 print('ESTAT VALIDATED',json.dumps(checks,ensure_ascii=False),flush=True)
 remaining=max(0,limit-result['attempted']);added=0
 # Current comparison month first, then all remaining months.
 for year in (2022,2021):
  entries=manifest(year,cache)
  ordered=dict(sorted(entries.items(),key=lambda kv:(kv[1]['date'][5:7]!='10',kv[1]['date'])))
  part=retrieve(ordered,cache,names,remaining,deadline)
  remaining-=part['attempted']
  for k in result:result[k]+=part[k]
  for stamp,pieces in grouped(entries).items():
   if any(k not in cache['days'] for k in pieces):continue
   if archive.get('produce',stamp):continue
   values=aggregate_period(pieces,cache['days'])
   if len(values)<8:continue
   from update_data import cache_produce
   cache_produce(archive,stamp,listing_url(year),values)
   record=archive.get('produce',stamp)
   record.update({'method':METHOD,'estimate':True,'roundingUncertaintyYenKg':0.55,
    'dailySources':[v['url'] for v in pieces.values()],
    'dailyObservationDates':sorted({v['date'] for v in pieces.values()}),
    'methodNote':'公表日別単価（円/kg）を数量（kg）で加重平均した旬別参考推計。丸め前の取引価額は未取得であり、農林水産省の旬別公表値ではありません。'})
   archive.data.get('backfillFailures',{}).pop('produce:'+ '-'.join(map(str,stamp)),None);added+=1
  archive.save()
  if remaining<=0 or time.monotonic()>deadline:break
 obj['metadata']['estatHistoryLastRun']={**result,'state':'validated','addedPeriods':added,'validation':checks}
 print('ESTAT HISTORICAL FALLBACK',json.dumps(obj['metadata']['estatHistoryLastRun'],ensure_ascii=False),flush=True)
 return result


def refresh_cached_baselines(obj,archive):
 """Recompute same-period comparisons after a historical cache is extended."""
 records=archive.records('produce')
 if not records:return
 stamp=records[-1]['stamp'];names={f['id']:f['name'] for f in obj['foods'] if f['category']!='fish'}
 for row in obj['prices']:
  name=names.get(row['foodId'])
  if not name or row.get('stale'):continue
  pairs=[]
  for year in range(stamp[0]-5,stamp[0]):
   rec=archive.get('produce',(year,stamp[1],stamp[2]))
   if rec and rec.get('schemaVersion')==2 and name in rec['values']:pairs.append((year,rec))
  row['historicalYears']=[y for y,r in pairs]
  row['historicalPrices']=[r['values'][name] for y,r in pairs]
  row['historicalSources']=[r['sourceUrl'] for y,r in pairs]
  row['historicalEstimates']=[bool(r.get('estimate')) for y,r in pairs]
  row['historicalSampleCount']=len(pairs)
  row['normalRatioRange']=None;row['classificationUncertain']=False
  mean=round(sum(row['historicalPrices'])/len(pairs),1) if len(pairs)>=3 else None
  row['normalPrice']=mean;row['normalRatio']=round(100*row['price']/mean,1) if mean else None
  row['normalRatioBasis']=f'過去{len(pairs)}年の同月・同旬の単純平均' if mean else '比較年数不足'
  if mean and any(row['historicalEstimates']):
   error=sum(r.get('roundingUncertaintyYenKg',0) for y,r in pairs)/len(pairs)+0.05
   lo=100*row['price']/(mean+error);hi=100*row['price']/(mean-error)
   row['normalRatioRange']=[math.floor(lo*10)/10,math.ceil(hi*10)/10]
   row['classificationUncertain']=(lo<85<=hi or lo<=115<hi)
   row['normalRatioBasis']+='（日別数量加重平均の参考推計を含む）'
   base=row.get('note','').split('【日別再集計】')[0]
   row['note']=base+'【日別再集計】2021〜2022年はe-Statの主要卸売市場計の日別数量・整数単価を加重平均した参考推計を含みます。旬別公表値とは異なり、丸め誤差があります。推計誤差で判定境界をまたぐ場合は色を付けません。'
  elif row.get('note'):row['note']=row['note'].split('【日別再集計】')[0]
 obj['metadata']['produceReferenceRatioCount']=sum(p.get('normalRatio') is not None and not p.get('stale') for p in obj['prices'] if p['foodId'] in names)

if __name__=='__main__':
 from market_history import MarketHistory
 from update_data import save
 from backfill_history import attach_long_history
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--limit',type=int,default=80);args=p.parse_args()
 obj=json.loads(DATA.read_text(encoding='utf-8'));archive=MarketHistory()
 backfill_daily(obj,archive,limit=min(1200,max(0,args.limit)),seconds=650)
 refresh_cached_baselines(obj,archive);attach_long_history(obj,archive);save(obj)
