import json,re
from bs4 import BeautifulSoup
from update_data import fetch
from regional_topics import ALIC_URL
BASE='https://www.e-stat.go.jp/stat-search/files?layout=dataset&page=1&limit=100&toukei=00500226&tclass1=000001032194&tclass2=000001046984'
def main():
 for name,extra in [('year','&year=20220&query=%E4%B8%BB%E8%A6%81%E5%8D%B8%E5%A3%B2%E5%B8%82%E5%A0%B4%E8%A8%88'),('yearclass','&tstat=000001015623&tclass3=000001163286'),('querymonth','&tstat=000001015623&tclass3=000001163286&tclass4=000001167486&query=%E4%B8%BB%E8%A6%81'),('queryannual','&tstat=000001015623&tclass3=000001163286&query=%E4%B8%BB%E8%A6%81')]:
  s=BeautifulSoup(fetch(BASE+extra,timeout=30),'html.parser')
  dl=[a.get('href') for a in s.find_all('a',href=True) if 'file-download' in a['href']]
  links=[{'text':a.get_text(' ',strip=True),'href':a.get('href')} for a in s.find_all('a',href=True) if 'stat_infid=' in a['href']]
  print('ESTAT PROBE',name,'csv',len(dl),'datasets',json.dumps(links[:2]+links[-2:],ensure_ascii=False),flush=True)
  if name=='yearclass':
   print('ESTAT MONTH MARKUP',[(str(t.parent)[:2500]) for t in s.find_all(['label','input','option','a']) if t.get_text(strip=True)=='1月'][:4],flush=True)
   print('ESTAT INPUTS',[(t.get('name'),t.get('value')) for t in s.find_all('input') if any(k in str(t.get('name')) for k in ('search','metadata','data','layout'))],flush=True)
 s=BeautifulSoup(fetch(ALIC_URL),'html.parser');text=s.get_text(' ',strip=True)
 print('ALIC DEBUG',s.original_encoding,len(text),'celery',text.find('セロリ'),text[text.find('セロリ')-30:text.find('セロリ')+400],flush=True)
 print('ALIC MATCHING',[(str(t)[:900]) for t in s.find_all(['p','td','div','span']) if 'セルリー' in t.get_text() and len(t.get_text())<1000][:5],flush=True)
if __name__=='__main__':main()
