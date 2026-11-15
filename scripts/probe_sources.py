import urllib.request,io
import openpyxl
with urllib.request.urlopen('https://www.e-stat.go.jp/stat-search/files/data?sinfid=000040475795&ext=xls',timeout=30) as r:raw=r.read()
b=openpyxl.load_workbook(io.BytesIO(raw),data_only=True,read_only=True)
print('SHEETS',b.sheetnames,flush=True)
for sh in b.worksheets[2:4]:
 print('SHEET',sh.title,flush=True)
 for i,row in enumerate(sh.iter_rows(values_only=True)):
  if i<20:print('R',i,list(row),flush=True)
