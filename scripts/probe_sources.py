import urllib.request,re,io,json
from bs4 import BeautifulSoup
import xlrd,openpyxl
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Shunshokuzai/0.12 official-data-verification'}),timeout=30) as r:return r.read()
urls=['https://www.e-stat.go.jp/stat-search/files?layout=datalist&toukei=00200571&tstat=000000680001&cycle=1&year=20260&month=23070909',
'https://www.stat.go.jp/data/kouri/doukou/3.html',
'https://www.maff.go.jp/j/press/nousan/engei/261030.html',
'https://www.maff.go.jp/j/tokei/kouhyou/sakumotu/sakkyou_yasai/']
for url in urls:
 try:
  raw=get(url);soup=BeautifulSoup(raw,'html.parser');print('URL',url,flush=True)
  if 'e-stat' in url:
   for tag in soup.find_all(['a','button','div']):
    if any('statInfId' in str(v) or 'stat_infid' in str(v) or 'file-download' in str(v) for v in tag.attrs.values()):
     print('ESTAT LINK',str(tag)[:1100],flush=True)
  else:
   for a in soup.find_all('a',href=True):
    if re.search('e-stat|syukaku|26|csv|xls',a['href']):print('LINK',a.get_text(' ',strip=True)[:80],a['href'],flush=True)
  if '/261030' in url:
   for tr in soup.select('table tr')[:22]: print('ORIGIN',tr.get_text(' | ',strip=True),flush=True)
 except Exception as e:print('PROBE ERROR',type(e).__name__,str(e),flush=True)
