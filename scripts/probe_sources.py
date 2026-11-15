import urllib.request,re,io
from bs4 import BeautifulSoup
import openpyxl,xlrd
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Shunshokuzai/0.12 official-data-verification'}),timeout=30) as r:return r.read()
raw=get('https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040515971&fileKind=0')
ws=openpyxl.load_workbook(io.BytesIO(raw),data_only=True,read_only=True).worksheets[0]
for i,row in enumerate(ws.iter_rows(values_only=True)):
 if i>=18 and i<150: print('FOOD',list(row)[7:16],flush=True)
soup=BeautifulSoup(get('https://www.stat.go.jp/data/kouri/doukou/3.html'),'html.parser')
for a in soup.select('a[href]'):
 if '.xls' in a['href'] and ('26' in a['href'] or '25' in a['href']):print('SPEC LINK',a.text,a['href'],flush=True)
urls=['https://www.e-stat.go.jp/stat-search/files?layout=dataset&toukei=00200571&tstat=000000680001&cycle=1&query=%E4%B8%BB%E8%A6%81%E5%93%81%E7%9B%AE%E3%81%AE%E9%83%BD%E5%B8%82%E5%88%A5%E5%B0%8F%E5%A3%B2%E4%BE%A1%E6%A0%BC&limit=20',
'https://www.e-stat.go.jp/stat-search/files?layout=datalist&toukei=00200571&tstat=000000680001&cycle=1&year=20260']
for url in urls:
 soup=BeautifulSoup(get(url),'html.parser');aa=soup.select('a[href*="file-download"]')
 print('INDEX',url,'LINKS',len(aa),flush=True)
 for a in aa[:3]:print('CARD',str(a.parent.parent)[:6500],flush=True)
