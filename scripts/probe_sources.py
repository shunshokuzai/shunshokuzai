import urllib.request,re,io
from bs4 import BeautifulSoup
import xlrd,openpyxl
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Shunshokuzai/0.12 official-data-verification'}),timeout=30) as r:return r.read()
url='https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040515971&fileKind=0'
raw=get(url)
book=openpyxl.load_workbook(io.BytesIO(raw),data_only=True,read_only=True)
for sh in book.worksheets[:2]:
 print('SHEET',sh.title,sh.max_row,sh.max_column,flush=True)
 for i,row in enumerate(sh.iter_rows(values_only=True)):
  vals=list(row)
  if i<18: print('ROW',i,vals[:24],flush=True)
  if i<8 or any(re.search('まぐろ|キャベツ|りんご|1101|1401|にんじん|札幌|高知|松山',str(x)) for x in vals[:8]):print('SELECTROW',i,vals[:28],flush=True)
s=get('https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040515975&fileKind=1')
for enc in ('utf-8-sig','cp932'):
 try:print('SPEC CSV',s.decode(enc)[:5500],flush=True);break
 except UnicodeError:pass
soup=BeautifulSoup(get('https://www.e-stat.go.jp/stat-search/files?layout=datalist&toukei=00200571&tstat=000000680001&cycle=1'),'html.parser')
print('LATEST TEXT',soup.get_text(' ',strip=True)[-10000:-5000],flush=True)
for a in soup.select('a[href*="statInfId"]')[:4]:print('LATEST CARD',str(a.parent)[:4000],flush=True)
