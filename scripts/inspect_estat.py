"""Discover explicit e-Stat file lists without assuming IDs."""
import json,re
from bs4 import BeautifulSoup
from update_data import fetch
BASE='https://www.e-stat.go.jp/stat-search/files?layout=datalist&limit=100&toukei=00500226&tclass1=000001032194&tclass2=000001046984'
def main():
 for name,extra in [('all2022','&tclass3=000001163286&tclass4val=0&cycle=0'),('oct2023','&tclass3=000001201860&tclass4=000001212080&tclass5val=0&cycle=0'),('all2021','&tclass3=000001150226&tclass4val=0&cycle=0')]:
  s=BeautifulSoup(fetch(BASE+extra,timeout=40),'html.parser')
  dl=[a.get('href') for a in s.find_all('a',href=True) if 'file-download' in a['href']]
  links=[{'text':a.get_text(' ',strip=True),'href':a.get('href')} for a in s.find_all('a',href=True) if 'stat_infid=' in a['href'] or 'page=' in a['href']]
  print('ESTAT PROBE',name,'csv',len(dl),'first',dl[:2],'last',dl[-2:],flush=True)
  print('ESTAT LINKS',name,json.dumps(links[:3]+links[-8:],ensure_ascii=False),flush=True)
  print('ESTAT SELECT',name,str(s.find_all('select'))[:4500],flush=True)
  print('ESTAT TAIL',name,s.get_text(' ',strip=True)[-4000:],flush=True)
if __name__=='__main__':main()
