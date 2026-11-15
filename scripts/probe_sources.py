import urllib.request,io,re
from bs4 import BeautifulSoup
import openpyxl,xlrd
def get(url):
 with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Shunshokuzai/0.12 source verification'}),timeout=30) as r:return r.read()
for url in ['https://www.stat.go.jp/data/kouri/doukou/zuhyou/202609.xlsx','https://www.e-stat.go.jp/stat-search/files/data?sinfid=000040475795&ext=xls']:
 raw=get(url); print('WORKBOOK',url,flush=True)
 if raw[:2]==b'PK':
  b=openpyxl.load_workbook(io.BytesIO(raw),read_only=True,data_only=True)
  for sh in b.worksheets[:3]:
   print('SHEET',sh.title,sh.max_row,sh.max_column,flush=True)
   for i,row in enumerate(sh.iter_rows(values_only=True)):
    if i<18 or any(re.fullmatch(r'1101|1112|1401|1433|1533',str(v or '').strip()) for v in row):
     print('ROW',i,list(row)[:24],flush=True)
 else:
  b=xlrd.open_workbook(file_contents=raw)
  print('SHEETS',b.sheet_names(),flush=True)
  for sh in b.sheets()[:2]:
   for i in range(min(20,sh.nrows)):print('ROW',i,sh.row_values(i)[:24],flush=True)
soup=BeautifulSoup(get('https://www.e-stat.go.jp/stat-search/files?layout=dataset&toukei=00200571&tstat=000000680001&cycle=1&query=%E4%B8%BB%E8%A6%81%E5%93%81%E7%9B%AE%E3%81%AE%E9%83%BD%E5%B8%82%E5%88%A5%E5%B0%8F%E5%A3%B2%E4%BE%A1%E6%A0%BC&limit=20'),'html.parser')
for a in soup.select('a[href*="fileKind=0"]'):
 card=a.find_parent(class_=re.compile('stat-resource_list-item'))
 if card is None:card=a.parent.parent.parent
 text=card.get_text(' ',strip=True)
 if '1001' in text:print('RETAIL CANDIDATE',str(card)[:10000],flush=True)
