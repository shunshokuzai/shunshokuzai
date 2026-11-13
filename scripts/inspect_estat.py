"""Inspect public e-Stat download metadata and one CSV without API credentials."""
import json,re
from bs4 import BeautifulSoup
from update_data import fetch,decode_csv

URL='https://www.e-stat.go.jp/stat-search/files?layout=datalist&stat_infid=000032228975&toukei=00500226'
LIST='https://www.e-stat.go.jp/stat-search/files?layout=dataset&page=1&limit=100&toukei=00500226&tclass1=000001032194&tclass2=000001046984&year=20220&query=%E4%B8%BB%E8%A6%81%E5%8D%B8%E5%A3%B2%E5%B8%82%E5%A0%B4%E8%A8%88'
def main():
 for name,url in [('dataset',URL),('listing',LIST)]:
  try:
   raw=fetch(url,timeout=35);soup=BeautifulSoup(raw,'html.parser')
   print('ESTAT',name,'bytes',len(raw),'title',soup.title.get_text() if soup.title else None,flush=True)
   tags=[{'tag':t.name,'attrs':t.attrs,'text':t.get_text(' ',strip=True)[:160]} for t in soup.find_all(['a','button','div','input']) if re.search('download|fileKind|stat_infid|statInfId',json.dumps(t.attrs),re.I)]
   print('ESTAT DOWNLOAD TAGS',name,json.dumps(tags[:12],ensure_ascii=False),flush=True)
   print('ESTAT PAGINATION',name,json.dumps([{'text':a.get_text(' ',strip=True),'href':a.get('href')} for a in soup.find_all('a',href=True) if 'page=' in a['href']][-8:],ensure_ascii=False),flush=True)
   if name=='dataset':
    for a in soup.find_all('a',href=True):
     if 'file-download' in a['href']:
      from urllib.parse import urljoin
      link=urljoin(url,a['href'])
      print('ESTAT CSV LINK',link,flush=True)
      data=fetch(link,timeout=35)
      print('ESTAT CSV SAMPLE',repr(decode_csv(data)[:3200]),flush=True)
      break
  except Exception as e:print('ESTAT ERROR',name,type(e).__name__,str(e)[:150],flush=True)
if __name__=='__main__':main()
