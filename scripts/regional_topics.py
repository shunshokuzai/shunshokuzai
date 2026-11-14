"""Additional current crop reports; source-guarded factual paraphrases.

ALIC text is not mirrored. Only short quotations and attributed paraphrases
are published. Prepared summaries apply solely to the checked issue; changed
or future text cannot silently reuse them. No API requests are made here.
"""
import datetime as dt
import re
import unicodedata
from bs4 import BeautifulSoup
from urllib.parse import urljoin,urlparse
from update_data import fetch

ALIC_URL='https://vegetable.alic.go.jp/yasaijoho/jyukyu/2611_jyukyu1_2.html'
# name, paragraph prefix, required source claims, factual paraphrase, scope
ALIC_FACTS=[
 ('セロリ','セロリ（セルリー）は',['静岡産','11月中旬','12月初め','根腐れ'],
  '静岡の露地セロリは11月半ば、施設栽培は12月初めから出荷開始の見込み。定植後の育ちは良かった一方、その後の高温と長雨による根腐れが懸念されています。','静岡県の産地・首都圏向け需要'),
 ('カリフラワー','カリフラワーは',['福岡産','定植が遅れた','生育は順調','11月10日前後','前年を上回る'],
  '福岡では夏の少雨で植え付けが遅れましたが、その後の生育は良好。11月10日ごろの出荷開始と翌春までの継続が見込まれます。出荷量は、大雨の影響で少なかった前年より増える予想です。','福岡県の産地・首都圏向け需要'),
 ('かぼちゃ','かぼちゃは',['道北','10月初旬','干ばつ','平年には届かない'],
  '北海道北部では10月初めに収穫を終え、12月半ばまで出荷する見通しです。夏の少雨の影響に農家間の差があり、傷みを除く選別で数量が変わるため、出荷予測には不確かさがあります。前年超・平年未満の見込みです。','北海道道北の産地・首都圏向け需要'),
 ('さつまいも','かんしょは',['石川産','五郎島金時','令和8年産','数量的には十分','5月下旬'],
  '石川の「五郎島金時」は2026年産の数量を十分に確保しているとの報告です。8月後半から出荷し、翌年5月下旬まで計画的に供給する方針。中心となるサイズはMです。','石川県の五郎島金時・首都圏向け需要'),
 ('ごぼう','ごぼうは',['茨城産','芹沢のごぼう','11月','12月がピーク','ほぼ平年作'],
  '茨城の「芹沢のごぼう」は平年程度の作柄とされます。出荷は11月から増え、12月に最も多くなる見通し。Mサイズを中心とした供給が予定されています。','茨城県の芹沢のごぼう・首都圏向け需要'),
 ('れんこん','れんこんは',['茨城産','11月も平年並み','台風で葉が損傷','順調'],
  '茨城のれんこんは生育が良好で、台風による葉の損傷も報告されていません。11月の出荷は10月に続いて平年程度となる見込みです。','茨城県の産地・首都圏向け需要'),
 ('ミニトマト','ミニトマトは',['熊本産','9月22日','生育は順調','11月後半','和歌山産','着果が悪い','12月'],
  '熊本の冬春ミニトマトは育ちが良く、11月後半の出荷最盛期を見込んでいます。一方、和歌山では初期の果実が暑さで付きにくく、出荷が増える時期は12月以降とされます。産地で進み方が異なります。','熊本県・和歌山県の冬春作・首都圏向け需要'),
]

def alic_items(html,foods,today):
 if today.year!=2026 or today.month!=11:return []
 soup=BeautifulSoup(html,'html.parser')
 text=unicodedata.normalize('NFKC',soup.get_text(' ',strip=True))
 if '2026年11月号' not in text:raise ValueError('ALIC issue mismatch')
 byname={f['name']:f for f in foods}
 out=[]
 for name,prefix,required,summary,scope in ALIC_FACTS:
  if name not in byname:continue
  prefix=unicodedata.normalize('NFKC',prefix)
  # Paragraphs may include spans/ruby; normalize whitespace only, not meaning.
  paragraphs=[unicodedata.normalize('NFKC',p.get_text('',strip=True)).strip() for p in soup.find_all('p')]
  paragraph=next((p for p in paragraphs if p.startswith(prefix)),None)
  if not paragraph:
   body=unicodedata.normalize('NFKC',soup.get_text('',strip=True))
   start=body.find(prefix)
   if start>=0:
    markers=['だいこんは','にんじんは','キャベツは','はくさいは','ほうれんそうは','ねぎは','ブロッコリーは','レタスは','きゅうりは','なすは','トマトは','ミニトマトは','ピーマンは','ばれいしょは','たまねぎは','さといもは','セロリ(セルリー)は','カリフラワーは','かぼちゃは','かんしょは','ごぼうは','れんこんは','(執筆者']
    ends=[body.find(mark,start+len(prefix)) for mark in markers]
    paragraph=body[start:min([end for end in ends if end>=0] or [len(body)])]
  if not paragraph or not all(word in paragraph for word in required):
   raise ValueError('ALIC source claims changed: '+name)
  quote=paragraph[:24]+'…'
  out.append({'food':byname[name],'url':ALIC_URL,'publishedAt':None,
   'reportKey':'alic-2026-11','sourceFamily':'alic-monthly-vegetable',
   'sourceName':'農畜産業振興機構（執筆：加藤宏一）',
   'sourceTitle':'野菜情報2026年11月号「首都圏の需要を中心とした11月の見通し」',
   'observedPeriod':'2026年11月の見通し（刊行時点の産地情報）',
   'periodStart':'2026-11-01','periodEnd':'2026-11-30','isForecast':True,
   'excerpt':'野菜情報2026年11月号\n'+paragraph,'publicExcerpt':quote,'preparedSummary':summary,
   'summaryProvider':'ChatGPT','scope':scope,'reportType':'産地の作柄・出荷の見通し',
   'evidenceSections':[{'label':'原文の冒頭（全文は出典リンク）','text':quote}],
   'limitations':'11月号に掲載された刊行時点の見通しです。11月現在の実績を確認したものではありません。記載の産地・品種に限った情報で、全国の生産量ではありません。正確な公表日は未確認です。'})
 return out

AOMORI_URL='https://www.nounavi-aomori.jp/farmer/archives/18185'
def apple_items(html,foods,today,url=AOMORI_URL):
 soup=BeautifulSoup(html,'html.parser')
 text=unicodedata.normalize('NFKC',soup.get_text(' ',strip=True))
 title=unicodedata.normalize('NFKC',soup.h1.get_text(' ',strip=True) if soup.h1 else '')
 year=re.search(r'(20\d{2})年りんご',title)
 observed=re.search(r'(\d{1,2})月\s*(\d{1,2})日現在',text)
 if not year or not observed:return []
 date=dt.date(int(year[1]),int(observed[1]),int(observed[2]))
 if date.year!=today.year:return []
 if today<date or (today-date).days>65:return []
 food=next((f for f in foods if f['name']=='りんご'),None)
 if not food:return []
 claims=[]
 for label in ('無袋','有袋'):
  m=re.search(label+r'[:：]\s*'+str(date.month)+r'月\s*'+str(date.day)+r'日現在[^。]*。',text)
  if not m:raise ValueError('Aomori maturity overview missing')
  claims.append(m.group(0))
 excerpt='\n'.join(claims)
 return [{'food':food,'url':url,'publishedAt':next((m.group(0).replace('.','-') for m in re.finditer(r'20\d{2}\.\d{2}\.\d{2}',text)),None),
  'reportKey':'aomori-fuji-'+date.isoformat(),'sourceFamily':'aomori-apple-maturity',
  'sourceName':'青森県・農なび青森（りんご研究所）',
  'sourceTitle':title,
  'observedPeriod':f'{date.year}年{date.month}月{date.day}日の熟度調査',
  'periodStart':date.isoformat(),'periodEnd':date.isoformat(),'isForecast':False,
  'excerpt':excerpt,'scope':'青森県りんご研究所の調査樹・ふじ（無袋と有袋）',
  'reportType':'糖度・着色などの品質調査',
  'evidenceSections':[{'label':'熟度調査の概要','text':excerpt}],
  'limitations':'研究所の調査樹の結果であり、青森県全域の品質や出荷量を示すものではありません。資料の平年値は主に20か年平均で、価格の参考平年比とは異なります。'}]

def latest_apple_items(foods,today):
 index='https://www.nounavi-aomori.jp/farmer/tag/%E3%82%8A%E3%82%93%E3%81%94'
 soup=BeautifulSoup(fetch(index,timeout=25),'html.parser')
 links=[]
 for a in soup.find_all('a',href=True):
  title=unicodedata.normalize('NFKC',a.get_text(' ',strip=True))
  url=urljoin(index,a['href'])
  if str(today.year)+'年' in title and 'ふじ' in title and '熟度調査結果' in title and urlparse(url).hostname=='www.nounavi-aomori.jp' and '/farmer/archives/' in url:
   if url not in links:links.append(url)
 for url in links[:2]:
  items=apple_items(fetch(url,timeout=25),foods,today,url)
  if items:return items
 return []


def alic_month_items(html,foods,today):
 """Roll the monthly source forward; public summaries require AI or prepared facts.

 Future issues never reuse November's prepared prose. Copyrighted full
 paragraphs stay in memory only; no full article is persisted or republished.
 """
 if today.year==2026 and today.month==11:return alic_items(html,foods,today)
 soup=BeautifulSoup(html,'html.parser')
 text=unicodedata.normalize('NFKC',soup.get_text('',strip=True))
 issue=f'{today.year}年{today.month}月号'
 if issue not in text:raise ValueError('Current ALIC issue not confirmed')
 byname={f['name']:f for f in foods if f['category']=='vegetable'}
 labels={'セロリ':'セロリ(セルリー)','さつまいも':'かんしょ','じゃがいも':'ばれいしょ','長ねぎ':'ねぎ'}
 prefixes={name:labels.get(name,name)+'は' for name in byname}
 # Include the footer as an explicit stop; never collect unrelated site text.
 positions=[]
 for name,prefix in prefixes.items():
  match=re.search(r'(?<![ぁ-ゖァ-ヺ一-龥])'+re.escape(prefix),text)
  if match:positions.append((match.start(),name,prefix))
 positions.sort()
 out=[]
 url=f'https://vegetable.alic.go.jp/yasaijoho/jyukyu/{today:%y%m}_jyukyu1_2.html'
 for index,(start,name,prefix) in enumerate(positions):
  end=positions[index+1][0] if index+1<len(positions) else text.find('(執筆者',start)
  if end<0:continue
  block=text[start:end]
  if not 40<=len(block)<=4000 or not re.search('生育|出荷|収穫|作柄',block):continue
  out.append({'food':byname[name],'url':url,'publishedAt':None,
   'reportKey':'alic-'+today.strftime('%Y-%m'),'sourceFamily':'alic-monthly-vegetable',
   'sourceName':'農畜産業振興機構','sourceTitle':'野菜情報'+issue+'・首都圏の需要を中心とした見通し',
   'observedPeriod':f'{today.year}年{today.month}月の見通し（刊行時点）',
   'periodStart':today.replace(day=1).isoformat(),
   'periodEnd':f'{today.year}-{today.month:02}-{__import__("calendar").monthrange(today.year,today.month)[1]}',
   'isForecast':True,'scope':'資料に記載された主産地・首都圏向け需要',
   'reportType':'産地の作柄・出荷見通し','excerpt':issue+'\n'+block,
   'requireAi':True,'publicExcerpt':block[:24]+'…',
   'evidenceSections':[{'label':'原文冒頭（全文は出典へ）','text':block[:24]+'…'}],
   'limitations':'刊行時点の見通しで、現在の確定実績ではありません。対象産地を全国へ一般化できません。公表日の詳細は未確認です。'})
 return out


def regional_items(foods,today):
 items=[];errors=[]
 for name,url,parser in [('ALIC',f'https://vegetable.alic.go.jp/yasaijoho/jyukyu/{today:%y%m}_jyukyu1_2.html',alic_month_items)]:
  try:items.extend(parser(fetch(url,timeout=25),foods,today))
  except Exception as error:errors.append(name+': '+type(error).__name__+': '+str(error)[:100])
 try:items.extend(latest_apple_items(foods,today))
 except Exception as error:errors.append('Aomori: '+type(error).__name__)
 print('REGIONAL CROP REPORTS',len(items),errors,flush=True)
 return items,errors
