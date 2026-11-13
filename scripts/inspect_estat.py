"""Inspect official historical file lists and paragraph markup."""
import json,re
from bs4 import BeautifulSoup
from update_data import fetch
from regional_topics import ALIC_URL
URLS=[
('june2022','https://www.e-stat.go.jp/stat-search/files?layout=dataset&page=1&tclass1=000001032194&tclass2=000001046984&tclass3=000001163286&tclass4=000001167486&toukei=00500226&tstat=000001015623'),
('oct2023','https://www.e-stat.go.jp/stat-search/files?layout=dataset&page=1&tclass1=000001032194&tclass2=000001046984&tclass3=000001201860&tclass4=000001212080&toukei=00500226&tstat=000001015623'),
('all2022','https://www.e-stat.go.jp/stat-search/files?layout=dataset&page=1&limit=100&tclass1=000001032194&tclass2=000001046984&tclass3=000001163286&tclass4val=0&toukei=00500226&tstat=000001015623&query=%E4%B8%BB%E8%A6%81%E5%8D%B8%E5%A3%B2%E5%B8%82%E5%A0%B4%E8%A8%88')]
def main():
 for name,url in URLS:
  s=BeautifulSoup(fetch(url,timeout=30),'html.parser')
  dl=[a.get('href') for a in s.find_all('a',href=True) if 'file-download' in a['href']]
  links=[{'text':a.get_text(' ',strip=True),'href':a.get('href')} for a in s.find_all('a',href=True) if 'stat_infid=' in a['href'] or 'page=' in a['href']]
  print('ESTAT PROBE',name,'csv',len(dl),flush=True)
  print('ESTAT LINKS',name,json.dumps(links[:3]+links[-8:],ensure_ascii=False),flush=True)
  # Structural metadata for a complete dataset row.
  a=next((a for a in s.find_all('a',href=True) if 'file-download' in a['href']),None)
  if a:print('ESTAT ROW',name,str(a.parent.parent)[:5000],flush=True)
 s=BeautifulSoup(fetch(ALIC_URL),'html.parser')
 print('ALIC HTML',[(str(p)[:1600]) for p in s.find_all(['p','div']) if 'セロリ' in p.get_text() and len(p.get_text())<800],flush=True)
if __name__=='__main__':main()
