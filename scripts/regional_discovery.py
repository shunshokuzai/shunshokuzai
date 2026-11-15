"""Dedicated region-aware parsers. Unrecognized dates and tables are held."""
import datetime as dt,hashlib,io,re,unicodedata
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urljoin,urlparse
from bs4 import BeautifulSoup
from cause_assessment import regional_cause,progress_text

def clean(v):return re.sub(r'\s+',' ',unicodedata.normalize('NFKC',str(v or ''))).strip()
def jpdate(text):
 text=clean(text)
 m=re.search(r'(20\d{2})年(\d{1,2})月(\d{1,2})日',text)
 if not m:
  m=re.search(r'令和(\d+)年(\d{1,2})月(\d{1,2})日',text)
  if not m:return None
  y,mo,d=map(int,m.groups());y+=2018
 else:y,mo,d=map(int,m.groups())
 try:return dt.date(y,mo,d)
 except ValueError:return None
def links(raw,source,foods,today,getter,matching):
 soup=BeautifulSoup(raw,'html.parser');root=source['url'];parser=source['parser'];out=[]
 if parser=='alic':
  children=[]
  fiscal=today.year-int(today.month<4)
  for a in soup.select('a[href]'):
   u=urljoin(root,a['href']);choices=matching(clean(a.get_text()),foods)
   if choices and re.search(r'/y'+str(fiscal)+r'/s\d+\.html$',urlparse(u).path):
    node=a;root_updated=None
    for _ in range(3):
     node=node.parent
     if node is None:break
     context=clean(node.get_text(' ',strip=True));dates=set(re.findall(r'20\d{2}年\d{1,2}月\d{1,2}日',context))
     if len(dates)==1:
      parsed=jpdate(next(iter(dates)));root_updated=parsed.isoformat() if parsed else None;break
    children.append((u,choices,root_updated))
  def child(pair):
   u,choices,root_updated=pair
   previous=[x for x in source.get('_previousLinks',[]) if x['url'].startswith(u.removesuffix('.html')+'/')]
   cached_updated=max((x.get('sourceUpdatedAt','') for x in previous),default='')
   same_day=source.get('_previousAt','')[:10]==today.isoformat()
   if previous and ((root_updated and cached_updated>=root_updated) or (not root_updated and same_day)):return previous
   page=BeautifulSoup(getter(u,source),'html.parser');result=[]
   for row in page.select('tr'):
    cells=[clean(c.get_text(' ',strip=True)) for c in row.find_all(['td','th'],recursive=False)]
    a=row.find('a',href=True)
    if len(cells)<3 or not a:continue
    when=jpdate(' '.join(cells));url=urljoin(u,a['href'])
    if not when or when>today or not re.search(r'/y\d{4}/s\d+/p\d+\.html$',urlparse(url).path):continue
    result.append({'url':url,'title':choices[0]['name']+'・'+cells[0]+'の生育調査','foodIds':[f['foodId'] for f in choices],'sourceId':source['id'],'region':re.sub('[都府県]$','',cells[0]),'sourceUpdatedAt':when.isoformat(),'fiscalYear':fiscal})
   return result
  errors=[]
  with ThreadPoolExecutor(max_workers=2) as pool:
   for f in as_completed([pool.submit(child,x) for x in children]):
    try:out.extend(f.result())
    except Exception as e:errors.append(type(e).__name__)
  source['_indexWarnings']=errors
  if not children or (errors and not out):raise ValueError('ALIC regional indexes unavailable')
  return sorted({x['url']:x for x in out}.values(),key=lambda x:x['sourceUpdatedAt'],reverse=True)
 if parser in ('wakayama','yamanashi'):
  return [{'url':root,'title':source['name'],'foodIds':[f['foodId'] for f in foods],'sourceId':source['id'],'region':source['region']}]
 if parser=='nagano':
  for a in soup.select('a[href]'):
   text=clean(a.get_text());u=urljoin(root,a['href'])
   if not urlparse(u).path.endswith('.pdf') or not any(x in text for x in ('巨峰','あかつき','ふじ')):continue
   parent=clean(a.parent.get_text(' ',strip=True));date=jpdate(parent)
   if date and date.year==today.year and date<=today:
    out.append({'url':u,'title':text,'foodIds':[f['foodId'] for f in matching(text,foods)],'sourceId':source['id'],'region':source['region'],'sourceUpdatedAt':date.isoformat()})
  return out
 return []
def make_item(food,entry,source,today,summary,observed,end,evidence):
 ident='regional-'+source['id']+'-'+hashlib.sha256(entry['url'].encode()).hexdigest()[:12]
 return {'food':{'id':food['foodId'],'name':food['name']},'url':entry['url'],'publishedAt':None,'sourceUpdatedAt':entry.get('sourceUpdatedAt'),'reportKey':ident,'sourceFamily':ident,'sourceName':source['name'],'sourceTitle':entry['title'],'title':food['name']+'：'+entry.get('region',source.get('region',''))+'の生育観測','observedPeriod':observed,'periodStart':end,'periodEnd':end,'seasonalRecord':True,'reportYear':int(end[:4]),'isForecast':False,'scope':entry.get('region',source.get('region',''))+'・資料の調査産地／試験樹','reportType':'主要産地の地域観測（全国の作柄ではありません）','geographicLevel':'regional','region':entry.get('region',source.get('region')),'excerpt':evidence,'publicExcerpt':evidence[:24] if source['parser']=='alic' else evidence,'evidenceSections':[{'label':'調査表から確認した項目','text':summary}],'shortSummary':summary,'requireAi':False,'nonAiTag':'公的調査表の項目を整理','nonAiChecks':['対象年・調査日・表見出しを照合'],'limitations':'資料の調査地点・品種の観測です。県全体や全国の収量・品質を代表するとは限りません。'}
def parse_alic(raw,entry,source,foods,today):
 soup=BeautifulSoup(raw,'html.parser');text=clean(soup.get_text(' ',strip=True))
 if '令和'+str(entry['fiscalYear']-2018)+'年度' not in text:return [],'report_year_unconfirmed'
 heading=next((h for h in soup.find_all(['h3','h4']) if '調査日' in clean(h.get_text())),None)
 if heading is None:return [],'observation_date_missing'
 m=re.search(r'調査日[:：]?\s*(\d+)月(\d+)日',clean(heading.get_text()))
 if not m:return [],'observation_date_missing'
 year=entry['fiscalYear']+int(int(m[1])<4);date=dt.date(year,int(m[1]),int(m[2]))
 if date>today or date.year!=today.year:return [],'observation_date_outside_current_year'
 table=heading.find_next('table')
 if table is None:return [],'structured_observation_table_missing'
 pairs={}
 for tr in table.select('tr'):
  cells=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)]
  for i in range(0,len(cells)-1,2):pairs[cells[i]]=cells[i+1]
 fields=[]
 for label,key in [('作況[平年比]','作況'),('生育進度[平年比]','生育進度'),('出荷進度[平年比]','出荷進度'),('作付面積[前年比]','作付面積・前年比')]:
  value=pairs.get(label)
  if value and value not in ('-','―','—','－') and len(value)<30:fields.append(key+'：'+value)
 if len(fields)<2:return [],'insufficient_structured_observations'
 place=pairs.get('調査産地',entry['region'])
 # Stop before the next survey. The page contains several dates and photo
 # captions; neither older surveys nor photo plots explain the latest area.
 sections={};label=None
 for node in heading.next_elements:
  if node is heading:continue
  if getattr(node,'name',None) in ('h3','h4'):break
  if getattr(node,'name',None)=='h5':
   label=clean(node.get_text());sections.setdefault(label,[])
  elif label and getattr(node,'name',None)=='p':
   value=clean(node.get_text(' ',strip=True))
   if value:sections[label].append(value)
 sections={k:' '.join(v) for k,v in sections.items()}
 cause=regional_cause(sections)
 summary=f'{date.year}年{date.month}月{date.day}日の{entry["region"]}・{place}の調査では、'+progress_text(pairs.get('生育進度[平年比]'),pairs.get('出荷進度[平年比]'))
 summary+=cause['text']
 if pairs.get('作況[平年比]'):summary+='調査表の作況評価は「'+pairs['作況[平年比]']+'」です。'
 out=[]
 for f in foods:
  if f['foodId'] not in entry['foodIds']:continue
  item=make_item(f,entry,source,today,summary,date.isoformat()+'の産地調査',date.isoformat(),summary)
  item.update({'summaryExcerpt':summary,'causeAssessment':cause,'evidenceSections':[{'label':'最新の調査表の項目（整理）','text':'、'.join(fields)},{'label':'原因の説明に使った箇所','text':cause['basis']}],'nonAiTag':'産地調査の表・原因説明を整理（AI未使用）','nonAiChecks':['対象年・最新調査日・産地を照合','因果表現の限定ルールで整理（認識できない原因は保留）']})
  out.append(item)
 return out,'source_text_found'
def parse_inline(raw,entry,source,foods,today):
 soup=BeautifulSoup(raw,'html.parser');text=clean(soup.get_text(' ',strip=True))
 if not re.search(r'令和'+str(today.year-2018)+r'年|'+str(today.year)+r'年',text):return [],'report_year_unconfirmed'
 out=[]
 for food in foods:
  records=[]
  for h in soup.find_all(['h3','h4']):
   title=clean(h.get_text())
   if source['parser']=='wakayama':
    if food['name']!='みかん' or title not in ('YN26','日南1号','ゆら早生','田口早生','宮川早生','興津早生','向山温州','林温州','丹生系温州'):continue
   else:
    aliases={'もも':['モモ','桃'],'すもも':['スモモ'],'さくらんぼ':['オウトウ'],'ぶどう':['ブドウ'],'巨峰':['巨峰'],'シャインマスカット':['シャインマスカット']}.get(food['name'],[food['name']])
    if not any(x in title for x in aliases):continue
   table=h.find_next('table')
   if not table:continue
   vals=[]
   for tr in table.select('tr'):
    cells=[clean(c.get_text(' ',strip=True)) for c in tr.find_all(['td','th'],recursive=False)]
    if cells and cells[0] in ('令和'+str(today.year-2018)+'年',str(today.year)+'年'):
     vals=cells[1:];break
   if not vals:continue
   if source['parser']=='wakayama' and len(vals)==5:
    desc=title+'の開花盛期は'+vals[3]+'、開花終期は'+vals[4]
    dates=vals
   elif source['parser']=='yamanashi' and len(vals)>=6:
    desc=title+'の収穫始期は'+vals[-2]+'、収穫終期は'+vals[-1];dates=vals
   else:continue
   actual=[]
   for v in dates:
    m=re.fullmatch(r'(\d+)月(\d+)日',v)
    if m:
     d=dt.date(today.year,int(m[1]),int(m[2]))
     if d<=today:actual.append(d)
   if not actual:continue
   records.append((desc,max(actual)))
  if records:
   summary='。'.join(x[0] for x in records[:3])+'。試験場の調査樹における今年の記録で、全国の作柄ではありません。'
   end=max(x[1] for x in records).isoformat();out.append(make_item(food,entry,source,today,summary,str(today.year)+'年の試験場観測（記載品種）',end,summary))
 return out,'source_text_found' if out else 'structured_observation_missing'
def parse_nagano(raw,entry,source,foods,today):
 import pdfplumber
 out=[]
 with pdfplumber.open(io.BytesIO(raw)) as pdf:
  for page in pdf.pages[:6]:
   text=clean(page.extract_text() or '')
   if '令和'+str(today.year-2018)+'年' not in text:continue
   if '糖度' not in text or '平年' not in text:continue
   match=re.search(r'品種[:：]\s*([^\s]+)',text)
   if not match:continue
   variety=match[1];block=text.split('糖度',1)[1].split('酸含量',1)[0]
   rows=re.findall(r'(\d{1,2})/(\d{1,2})\s+(\d+\.\d+)\s+(\d+\.\d+)\s+(\d+\.\d+)',block)
   valid=[r for r in rows if dt.date(today.year,int(r[0]),int(r[1]))<=today]
   if not valid:continue
   row=valid[-1];date=dt.date(today.year,int(row[0]),int(row[1]))
   name='シャインマスカット' if 'シャイン' in variety else '巨峰' if '巨峰' in variety else 'ぶどう'
   choices=[f for f in foods if f['name']==name]
   for f in choices:
    summary=f'{date.month}月{date.day}日の「{variety}」の糖度はBrix {row[2]}%（前年{row[3]}%、資料の平年値{row[4]}%）。長野県果樹試験場の調査樹の果実品質であり、県全体や全国の品質・収量ではありません。'
    item=make_item(f,entry,source,today,summary,date.isoformat()+'の果実品質調査',date.isoformat(),summary);out.append(item)
 return out,'source_text_found' if out else 'dedicated_pdf_parser_needed'
def parse(raw,entry,source,foods,today):
 parser=source['parser']
 if parser=='alic':return parse_alic(raw,entry,source,foods,today)
 if parser in ('wakayama','yamanashi'):return parse_inline(raw,entry,source,foods,today)
 if parser=='nagano':return parse_nagano(raw,entry,source,foods,today)
 return [],'dedicated_pdf_parser_needed'
