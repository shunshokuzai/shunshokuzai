"""Read-only discovery of e-Stat original daily files."""
import json,re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from update_data import fetch
BASE='https://www.e-stat.go.jp/stat-search/files?layout=datalist&limit=100&toukei=00500226&tclass1=000001032194&tclass2=000001046984&query=%E4%B8%BB%E8%A6%81%E5%8D%B8%E5%A3%B2%E5%B8%82%E5%A0%B4%E8%A8%88'
def main():
 for year,cls in [(2021,'000001150226'),(2022,'000001163286'),(2023,'000001201860')]:
  url=BASE+'&tclass3='+cls+'&cycle=0'
  s=BeautifulSoup(fetch(url,timeout=40),'html.parser')
  links=[{'text':a.get_text(' ',strip=True),'href':a.get('href')} for a in s.find_all('a',href=True) if any(k in a['href'] for k in ('page=','tclass4=','file-download'))]
  print('ESTAT DISCOVER',year,json.dumps(links[:8]+links[-14:],ensure_ascii=False),flush=True)
  print('ESTAT TEXT',year,s.get_text(' ',strip=True)[-8000:-3000],flush=True)
if __name__=='__main__':main()
