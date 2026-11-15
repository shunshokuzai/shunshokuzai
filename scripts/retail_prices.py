#!/usr/bin/env python3
"""Official retail observations, preserving regions, specifications and missingness."""
import calendar,csv,datetime as dt,io,json,re,unicodedata,urllib.parse,urllib.request
from bs4 import BeautifulSoup
import openpyxl
from update_data import BASE,DATA,now_iso,save
from market_history import atomic_text

STATE=BASE/'data/retail_prices.json'
INDEX='https://www.e-stat.go.jp/stat-search/files?'+urllib.parse.urlencode({'layout':'dataset','toukei':'00200571','tstat':'000000680001','cycle':1,'query':'主要品目の都市別小売価格','limit':20})
SPEC_INDEX='https://www.stat.go.jp/data/kouri/doukou/3.html'
NATIONAL='https://www.maff.go.jp/j/zyukyu/anpo/kouri/k_yasai/h22index.html'
ITEMS={1101:'f-102',1102:'f-098',1103:'f-099',1116:'f-095',1106:'f-100',1107:'f-097',1108:'f-094',1110:'f-103',1111:'f-101',1112:'f-132',1113:'f-135',1114:'f-141',1401:'v-001',1402:'v-005',1403:'v-002',1405:'v-028',1406:'v-009',1409:'v-007',1410:'v-032',1411:'v-020',1412:'v-021',1413:'v-022',1414:'v-003',1415:'v-004',1416:'v-025',1417:'v-027',1419:'v-024',1420:'v-023',1421:'v-030',1430:'v-037',1432:'v-051',1433:'v-019',1434:'v-012',1435:'v-013',1436:'v-010',1437:'v-014',1438:'v-040',1442:'v-043',1443:'v-042',1501:'f-054',1502:'f-054',1511:'f-055',1521:'f-067',1531:'f-064',1532:'f-066',1533:'f-065',1541:'f-063',1551:'f-073',1561:'f-079',1563:'f-080',1571:'f-072',1572:'f-075',1582:'f-071',1584:'f-084'}
def norm(x):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(x or ''))).strip()
def get(url):
 p=urllib.parse.urlparse(url)
 if p.scheme!='https' or p.hostname not in ('www.e-stat.go.jp','www.stat.go.jp','www.maff.go.jp'):raise ValueError('Untrusted retail URL')
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Shunshokuzai/0.12 official retail reference'}),timeout=25) as r:
  if urllib.parse.urlparse(r.geturl()).hostname not in ('www.e-stat.go.jp','www.stat.go.jp','www.maff.go.jp'):raise ValueError('Untrusted redirect')
  raw=r.read(6_000_001)
 if len(raw)>6_000_000:raise ValueError('Retail source too large')
 return raw
def workbook(raw):
 if raw[:2]!=b'PK':raise ValueError('Expected official xlsx file')
 return openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
def candidates(html):
 soup=BeautifulSoup(html,'html.parser');out={}
 for a in soup.select('a[href*="fileKind=0"]'):
  node=a
  for _ in range(8):
   node=node.parent
   if node is None:break
   text=norm(node.get_text(' ',strip=True))
   if '主要品目の都市別小売価格' in re.sub(r'\s+','',text) and '1001' in text and '2183' in text:
    dates=re.findall(r'20\d{2}-\d{2}-\d{2}',text)
    url=urllib.parse.urljoin(INDEX,a['href'])
    out[url]={'url':url,'publishedAt':dates[-1] if dates else None,'text':text}
    break
 return sorted(out.values(),key=lambda x:x['publishedAt'] or '',reverse=True)
def specifications(raw):
 out={}
 for sh in workbook(raw).worksheets:
  for row in sh.iter_rows(values_only=True):
   for k,value in enumerate(row[:5]):
    s=norm(value);m=re.fullmatch(r'(\d{4})(?:\.\d+)?',s)
    if not m:continue
    code=int(m[1])
    if code in ITEMS:
     desc='／'.join(norm(v) for v in row[1:5] if norm(v))
     if not norm(row[2] if len(row)>2 else None):desc+='／サイズ・産地の個別指定は基本銘柄に記載なし'
     if len(desc)>=4:out[code]=desc
 return out
def local_brands(raw):
 for enc in ('utf-8-sig','cp932'):
  try:text=raw.decode(enc);break
  except UnicodeError:continue
 else:raise ValueError('Unknown CSV encoding')
 out=set()
 for row in csv.reader(io.StringIO(text)):
  if len(row)>=5 and re.fullmatch(r'\d{4}',row[1].strip()) and re.fullmatch(r'\d{5}',row[3].strip()):out.add((int(row[1]),row[3].strip()))
 return out
def parse_cities(raw,source,specs,spec_url,locals_set,today):
 records=[];regions={};count=0
 for sh in workbook(raw).worksheets:
  rows=list(sh.iter_rows(values_only=True))
  title=' '.join(norm(v) for row in rows[:10] for v in row if v is not None)
  if '主要品目の都市別小売価格' not in title:continue
  header=next((i for i,r in enumerate(rows[:25]) if '銘柄符号' in [norm(x) for x in r] and '時間軸(月)' in [norm(x) for x in r]),None)
  if header is None:
   header=next((i for i,r in enumerate(rows[:25]) if '銘柄符号' in [norm(x) for x in r] and '品目' in [norm(x) for x in r]),None)
  if header is None:continue
  labels=[norm(x) for x in rows[header]];codes=rows[header-1]
  ic=labels.index('銘柄符号');iname=labels.index('品目');iu=labels.index('単位')
  it=next(i for i,n in enumerate(labels) if n in ('時間軸(月)','時間軸（月）'))
  for row in rows[header+1:]:
   try:code=int(row[ic])
   except (ValueError,TypeError):continue
   if code not in ITEMS:continue
   period=norm(row[it]);m=re.fullmatch(r'(20\d{2})年(\d{1,2})月',period)
   if not m:continue
   y,mo=map(int,m.groups());end=dt.date(y,mo,calendar.monthrange(y,mo)[1])
   if end>today:continue
   spec=specs.get(code)
   if not spec:continue
   # Do not silently map generic squid/tai to a particular species.
   if code==1112 and (not re.search('するめ|スルメ',spec) or re.search('やり|ヤリ|又は',spec)):continue
   if code==1110 and (not re.search('まだい|マダイ|真鯛',spec) or re.search('きだい|キダイ|又は',spec)):continue
   for j,(area,label) in enumerate(zip(codes,labels)):
    area=norm(area)
    if not re.fullmatch(r'\d{5}',area) or not label:continue
    price=row[j]
    if isinstance(price,bool) or not isinstance(price,(float,int)) or not 0<price<1_000_000:continue
    if (code,area) in locals_set:continue
    count+=1;region='city-'+area;regions[region]=label
    records.append({'foodId':ITEMS[code],'itemCode':str(code),'statisticalItem':norm(row[iname]),'price':price,'unit':norm(row[iu]),'regionId':region,'regionName':label,'period':period,'observationEnd':end.isoformat(),'publishedAt':source['publishedAt'],'sourceUrl':source['url'],'sourceName':'総務省統計局・小売物価統計調査','specification':spec,'specificationUrl':spec_url,'taxIncluded':True,'sourceGroup':'city'})
 if len(records)<50 or len(regions)<10:raise ValueError('Insufficient validated city retail observations')
 return records,[{'id':k,'name':v} for k,v in regions.items()]
def collect_cities(today,getter=get):
 options=candidates(getter(INDEX))
 if not options:raise ValueError('Official city retail workbook not found')
 source=next((x for x in options if not x['publishedAt'] or x['publishedAt']<=today.isoformat()),None)
 if not source:raise ValueError('Only future retail sources found')
 raw=getter(source['url'])
 book=workbook(raw);alltext=' '.join(norm(v) for sh in book.worksheets for row in list(sh.iter_rows(values_only=True))[:15] for v in row if v is not None)
 dates=re.findall(r'(20\d{2})年(\d{1,2})月',alltext)
 if not dates:raise ValueError('Retail observation month unconfirmed')
 year,month=map(int,dates[-1]);sp=BeautifulSoup(getter(SPEC_INDEX),'html.parser');choices=[]
 for a in sp.select('a[href]'):
  mm=re.search(r'/(\d{4})(\d{2})\.xlsx$',a['href'])
  if mm and int(mm[1])==year and int(mm[2])>=month:choices.append((int(mm[2]),urllib.parse.urljoin(SPEC_INDEX,a['href'])))
 if not choices:raise ValueError('Matching monthly basic specifications not found')
 spec_url=min(choices)[1];specs=specifications(getter(spec_url))
 # The paired file identifies cities using a different local brand.
 month_url='https://www.e-stat.go.jp/stat-search/files?'+urllib.parse.urlencode({'layout':'datalist','toukei':'00200571','tstat':'000000680001','cycle':1,'year':str(year)+'0','month':'2307'+f'{month:02}{month:02}'})
 page=BeautifulSoup(getter(month_url),'html.parser');local_link=page.select_one('a[data-file_type="CSV"]')
 if local_link is None:raise ValueError('Local-brand exceptions file not found')
 locals_set=local_brands(getter(urllib.parse.urljoin(month_url,local_link['href'])))
 return parse_cities(raw,source,specs,spec_url,locals_set,today)
def collect_national(today,getter=get):
 import pdfplumber
 soup=BeautifulSoup(getter(NATIONAL),'html.parser');options=[]
 for a in soup.select('a[href]'):
  if '.pdf' in a['href'] and '週' in a.get_text():
   options.append((norm(a.get_text()),urllib.parse.urljoin(NATIONAL,a['href'])))
 if not options:raise ValueError('National weekly retail release not found')
 title,url=options[0]
 with pdfplumber.open(io.BytesIO(getter(url))) as pdf:
  text=unicodedata.normalize('NFKC',pdf.pages[0].extract_text() or '')
 lines=[norm(l) for l in text.splitlines()]
 header=next((l for l in lines if 'キャベツ' in l and 'にんじん' in l),None)
 if not header:raise ValueError('National retail header not recognized')
 names=header.replace('品目','').split()
 prices=next((re.findall(r'\d[\d,]*(?:\.\d+)?',l.split('価格',1)[1]) for l in lines if re.search(r'(?:^|\s)価格\s+\d',l)),None)
 m=re.search(r'(?:令和(\d+)年|(20\d{2})年)\s*(\d+)月\s*(\d+)日の週',text)
 if not m or not prices or len(prices)!=len(names):raise ValueError('National retail row or observation date mismatch')
 year=int(m[2]) if m[2] else 2018+int(m[1]);date=dt.date(year,int(m[3]),int(m[4]))
 if date>today:raise ValueError('Future national observation')
 byname={'キャベツ':'v-001','ねぎ':'v-028','レタス':'v-009','たまねぎ':'v-027','トマト':'v-010','にんじん':'v-004','はくさい':'v-002','だいこん':'v-003','ばれいしょ':'v-021','きゅうり':'v-012'}
 out=[]
 for name,value in zip(names,prices):
  if name not in byname:raise ValueError('Unknown national retail commodity')
  price=float(value.replace(',',''))
  if price<=0:raise ValueError('Invalid retail price')
  out.append({'foodId':byname[name],'statisticalItem':name,'price':price,'unit':'kg','regionId':'national','regionName':'全国平均','period':f'{year}年{date.month}月{date.day}日の週（原表の調査日を参照）','observationEnd':date.isoformat(),'publishedAt':None,'sourceUrl':url,'sourceName':'農林水産省・食品価格動向調査','specification':'全国の調査店舗の単純平均。特売等を除く税込価格。サイズ・産地別の値ではありません。','specificationUrl':NATIONAL,'taxIncluded':True,'sourceGroup':'national'})
 return out
def refresh(obj,today,getter=get,path=STATE):
 previous=json.loads(path.read_text(encoding='utf-8')) if path.exists() else obj.get('retail',{})
 records=list(previous.get('records',[]));regions=list(previous.get('regions',[]));errors=[];counts={}
 for group,collector in [('city',collect_cities),('national',collect_national)]:
  try:
   result=collector(today,getter)
   if group=='city':fresh,regions=result
   else:fresh=result
   records=[r for r in records if r.get('sourceGroup')!=group]+fresh;counts[group]=len(fresh)
  except Exception as e:errors.append(group+': '+type(e).__name__+': '+str(e)[:160])
 payload={'version':1,'lastAttemptAt':now_iso(),'lastSuccessAt':now_iso() if not errors else previous.get('lastSuccessAt'),'status':'partial' if errors and records else 'error' if errors else 'ok','records':records,'regions':regions,'errors':errors,'counts':counts}
 obj['retail']=payload
 obj['recipes']=json.loads((BASE/'data/recipes.json').read_text(encoding='utf-8'))
 obj['metadata']['retailLastRun']={k:v for k,v in payload.items() if k not in ('records','regions')}
 atomic_text(path,json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
 print('OFFICIAL RETAIL',json.dumps({'records':len(records),'foods':len({r['foodId'] for r in records}),'regions':len(regions),'counts':counts,'errors':errors},ensure_ascii=False),flush=True)
 return payload
def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');p.add_argument('--require-cities',action='store_true');args=p.parse_args()
 if not args.live:return
 obj=json.loads(DATA.read_text(encoding='utf-8'));result=refresh(obj,dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date());save(obj)
 if args.require_cities and (len(result['regions'])<10 or not any(r.get('sourceGroup')=='city' for r in result['records'])):raise RuntimeError('City retail verification required')
 if result['status']=='error':raise RuntimeError('All retail sources unavailable; old data retained')
if __name__=='__main__':main()
