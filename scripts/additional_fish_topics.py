"""Additional seasonal fisheries reports, with explicit scope and time bounds."""
import calendar
import datetime as dt
import io
import re
import unicodedata
import urllib.request
from urllib.parse import urljoin,urlparse
from bs4 import BeautifulSoup
from update_data import fetch,USER_AGENT

def normalized(value):return re.sub(r'\s+','',unicodedata.normalize('NFKC',value))

KATSUO='https://www.fra.go.jp/home/kenkyushokai/press/pr2026/fri_20260629_katsuo.html'
SANMA='https://www.jafic.or.jp/information/2026/11/09/post-5/'
SALMON='https://www.fra.go.jp/shigen/salmon/sokuhou.html'

def katsuo_items(html,foods,today):
 if not dt.date(2026,6,29)<=today<=dt.date(2026,11,30):return []
 soup=BeautifulSoup(html,'html.parser');text=normalized(soup.get_text(' ',strip=True))
 match=re.search(r'検討の結果、令和8年6[~〜～]11月のカツオ来遊量は、.+?予測されました。',text)
 if not match or '令和8年6月29日' not in text:raise ValueError('Katsuo source date or outlook mismatch')
 food=next((f for f in foods if f['name']=='カツオ'),None)
 if not food:return []
 excerpt=match.group(0)
 return [{'food':food,'url':KATSUO,'publishedAt':'2026-06-29','reportKey':'fra-katsuo-2026-06-29',
  'sourceFamily':'fra-katsuo','sourceName':'水産研究・教育機構 水産資源研究所',
  'sourceTitle':'令和8年度常磐・三陸沖カツオ長期来遊資源動向予測（6～11月）',
  'title':'カツオ：常磐・三陸沖の来遊見通し（6月公表）',
  'observedPeriod':'2026年6月～11月の予測（6月29日公表時点）',
  'periodStart':'2026-06-01','periodEnd':'2026-11-30','isForecast':True,
  'excerpt':excerpt,'summaryExcerpt':excerpt,'scope':'常磐・三陸沖の近海カツオ一本釣り・まき網漁業',
  'reportType':'来遊資源の季節予測',
  'limitations':'6月に公表した漁期全体の予測です。現在の漁獲実績・全国の水揚げ量・価格を直接示すものではありません。'}]

def sanma_items(html,pdftext,foods,today):
 if not dt.date(2026,11,9)<=today<=dt.date(2026,12,31):return []
 soup=BeautifulSoup(html,'html.parser');title=soup.h1.get_text(' ',strip=True) if soup.h1 else ''
 text=normalized(pdftext)
 required=['2026年11月9日','11月中旬から12月下旬','道東海域','三陸海域','常磐海域','断続的な来遊','低位水準','さんま棒受網漁業']
 if '第7回サンマ' not in normalized(title) or not all(s in text for s in required):raise ValueError('Sanma forecast scope or dates changed')
 food=next((f for f in foods if f['name']=='サンマ'),None)
 if not food:return []
 # First-page overview has three separate sea-area claims.
 overview=re.search(r'来遊量(.+?)問い合わせ先',text)
 if not overview:raise ValueError('Sanma overview missing')
 excerpt='公表日:2026年11月9日。予測期間:2026年11月中旬から12月下旬。'+overview.group(1)
 summary='11月9日公表のサンマ予報では、道東は11月半ばに断続的な来遊となる見込み。三陸・常磐では11月半ばの来遊水準を低いと予測しています。対象は南下回遊群の棒受網漁で、全国の確定漁獲量ではありません。'
 return [{'food':food,'url':SANMA,'publishedAt':'2026-11-09','reportKey':'jafic-sanma-2026-11-09',
  'sourceFamily':'jafic-sanma','sourceName':'漁業情報サービスセンター（関係水産研究機関と検討）',
  'sourceTitle':title,'title':'サンマ：道東・三陸・常磐の中短期漁況予報',
  'observedPeriod':'2026年11月中旬～12月下旬の予測',
  'periodStart':'2026-11-11','periodEnd':'2026-12-31','isForecast':True,
  'excerpt':excerpt,'publicExcerpt':'道東海域では、11月中旬は断続的な来遊となる。',
  'preparedSummary':summary,'summaryProvider':'ChatGPT',
  'scope':'道東・三陸・常磐海域の南下回遊群・さんま棒受網漁業',
  'reportType':'海域別の来遊量予報',
  'evidenceSections':[{'label':'原文の一部（全文はPDF）','text':'道東海域では、11月中旬は断続的な来遊となる。'}],
  'limitations':'11月9日公表時点の予測です。12月までを対象とする資料ですが、この要約は原資料冒頭の11月中旬の海域別見通しを整理しています。詳しい旬別の見通しはPDF原文をご確認ください。'}]

def salmon_items(html,foods,today):
 soup=BeautifulSoup(html,'html.parser')
 title=normalized(soup.h1.get_text() if soup.h1 else '')
 year=re.search(r'さけます来遊速報\(令和(\d+)年度\)',title)
 if not year:raise ValueError('Salmon bulletin year missing')
 year=int(year[1])+2018
 heading=next((h for h in soup.find_all(['h2','h3']) if re.search(r'サケ道県別来遊数.*現在.*更新',normalized(h.get_text()))),None)
 if not heading:raise ValueError('Dated salmon section missing')
 dates=re.search(r'\((\d+)月(\d+)日現在\)(\d+)月(\d+)日更新',normalized(heading.get_text()))
 if not dates:raise ValueError('Salmon observation/publication dates missing')
 mon,day,pmon,pday=map(int,dates.groups())
 observed=dt.date(year+(mon<7),mon,day);published=dt.date(year+(pmon<7),pmon,pday)
 if published>today or (today-observed).days>65:return []
 table=heading.find_next('table')
 if not table:raise ValueError('Salmon numeric table missing')
 row=next((tr for tr in table.find_all('tr') if normalized(tr.get_text()).startswith('合計')),None)
 cells=[normalized(td.get_text()) for td in row.find_all(['td','th'])] if row else []
 if len(cells)!=13:raise ValueError('Salmon table layout changed')
 num=lambda s:int(s.replace(',','').replace('%',''))
 river,prior_river=num(cells[1]),num(cells[2]);catch,prior_catch=num(cells[7]),num(cells[8]);total,prior_total,ratio=map(num,cells[10:13])
 if total!=river+catch or prior_total!=prior_river+prior_catch or abs(100*total/prior_total-ratio)>.51:raise ValueError('Salmon arithmetic mismatch')
 food=next((f for f in foods if f['name']=='サケ'),None)
 if not food:return []
 summary=f'{observed.month}月{observed.day}日までの11道県のサケ総来遊数は{total:,}尾、前年同期の{ratio}%です。内訳は沿岸の漁獲{catch:,}尾と河川等の捕獲{river:,}尾。期間途中の速報で、年間の確定値ではありません。'
 return [{'food':food,'url':SALMON,'publishedAt':published.isoformat(),'reportKey':'fra-salmon-'+observed.isoformat(),
  'sourceFamily':'fra-salmon','sourceName':'水産研究・教育機構（関係11道県の速報を集計）',
  'sourceTitle':f'さけます来遊速報 令和{year-2018}年度・サケ道県別来遊数',
  'title':f'サケ：11道県の来遊速報（{observed.month}月{observed.day}日現在）',
  'observedPeriod':f'{observed.year}年7月以降～{observed.month}月{observed.day}日の累計（漁獲は8月以降）',
  'periodStart':f'{year}-07-01','periodEnd':observed.isoformat(),'isForecast':False,
  'excerpt':summary,'summaryExcerpt':summary,'kind':'official_data_digest','nonAiTag':'公的統計の数値を整理（AI未使用）','nonAiChecks':['合計内訳・前年比の算術照合'],'scope':'北海道・青森・岩手・宮城・福島・茨城・秋田・山形・新潟・富山・石川の11道県',
  'reportType':'内水面捕獲数＋沿岸漁獲数の累計速報',
  'evidenceSections':[{'label':'合計行から整理した数値','text':f'捕獲数 {river:,}尾／漁獲数 {catch:,}尾／総来遊数 {total:,}尾／総来遊数前年比 {ratio}%'}],
  'limitations':'総来遊数は河川などの捕獲数と沿岸漁獲数の合計で、海面漁獲量だけを示す数値ではありません。11道県の期間途中の速報で、追録・修正されることがあります。'}]

def additional_items(foods,today):
 items=[];errors=[]
 for name,url,parser in [('Katsuo',KATSUO,katsuo_items),('Salmon',SALMON,salmon_items)]:
  try:items.extend(parser(fetch(url,timeout=25),foods,today))
  except Exception as error:errors.append(name+': '+type(error).__name__+': '+str(error)[:80])
 try:
  if dt.date(2026,11,9)<=today<=dt.date(2026,12,31):
   html=fetch(SANMA,timeout=25);soup=BeautifulSoup(html,'html.parser')
   link=next((urljoin(SANMA,a['href']) for a in soup.find_all('a',href=True) if 'sanma20261109.pdf' in a['href']),None)
   if not link or urlparse(link).hostname!='www.jafic.or.jp':raise ValueError('Official sanma PDF missing')
   req=urllib.request.Request(link,headers={'User-Agent':USER_AGENT})
   with urllib.request.urlopen(req,timeout=30) as response:raw=response.read(4_000_001)
   if len(raw)>4_000_000 or not raw.startswith(b'%PDF'):raise ValueError('Sanma PDF invalid')
   import pdfplumber
   with pdfplumber.open(io.BytesIO(raw)) as pdf:text='\n'.join(p.extract_text() or '' for p in pdf.pages[:2])
   rows=sanma_items(html,text,foods,today)
   for row in rows:row['extraSources']=[{'name':'中短期予報のPDF原文','url':link,'publishedAt':'2026-11-09'}]
   items.extend(rows)
 except Exception as error:errors.append('Sanma: '+type(error).__name__+': '+str(error)[:80])
 print('ADDITIONAL FISH TOPICS',len(items),errors,flush=True)
 return items,errors
