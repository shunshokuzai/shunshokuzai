import urllib.request,re,io
from bs4 import BeautifulSoup
import xlrd,openpyxl
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Shunshokuzai/0.12 official-data-verification'}),timeout=30) as r:return r.read()
url='https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040515971&fileKind=0'
raw=get(url)
book=xlrd.open_workbook(file_contents=raw) if raw[:2]!=b'PK' else None
if book:
 for sh in book.sheets()[:2]:
  print('SHEET',sh.name,sh.nrows,sh.ncols,flush=True)
  for i in range(min(20,sh.nrows)):print('ROW',i,sh.row_values(i)[:23],flush=True)
  for i in range(sh.nrows):
   vals=sh.row_values(i)
   if any(re.search('まぐろ|キャベツ|りんご|1101|1401|にんじん|魚介|生鮮果物|札幌|高知|松山',str(x)) for x in vals[:8]):print('FOODROW',i,vals[:18],flush=True)
  for i in range(min(18,sh.nrows)):
   print('HEADERALL',i,sh.row_values(i),flush=True)
else:print('XLSX format',flush=True)
s=get('https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040515975&fileKind=1')
for enc in ('utf-8-sig','cp932'):
 try:print('SPEC CSV',s.decode(enc)[:5500],flush=True);break
 except UnicodeError:pass
soup=BeautifulSoup(get('https://www.e-stat.go.jp/stat-search/files?layout=datalist&toukei=00200571&tstat=000000680001&cycle=1'),'html.parser')
for a in soup.select('a.js-data')[:10]:print('LATEST CARD',str(a.parent.parent)[:3000],flush=True)
