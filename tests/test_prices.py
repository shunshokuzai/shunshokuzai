import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_data import page_csv_urls,parse_csv,apply_prices

class TestDataImport(unittest.TestCase):
 def test_csv_parser(self):
  csv_text='品目,卸売数量(t),卸売価格(円/kg),対前年同旬比(%),\nキャベツ,20,145,95,\nだいこん,12,180,101,\nはくさい,19,95,99,\nトマト,8,320,100,\nきゅうり,11,245,92,\nなす,8,290,109,\nさつまいも,6,195,98,\nみかん,7,342,105,\n'
  out=parse_csv(csv_text.encode('utf-8'),['キャベツ','だいこん','はくさい','トマト','きゅうり','なす','さつまいも','みかん'])
  self.assertEqual(out['キャベツ'],145.0);self.assertEqual(out['さつまいも'],195.0)
 def test_official_multiline_table_numeric_invariant(self):
  # MAFF PDF: 卸売数量(t), 卸売価額(1,000円), 卸売価格(円/kg)
  raw='青果物卸売市場調査（旬別結果）主要卸売市場計,,,,,,,\n品目,主要卸売市場計,,,,対前年同旬比,,\n,卸売数量,卸売価額,卸売価格,卸売数量,卸売価格,,\nキャベツ,"9,508","741,273",78,143,25,93,86\nだいこん,"7,799","647,057",83,115,55,84,87\nトマト,"3,130","1,519,365",485,117,95,139,83\nりんご計,"2,104","974,592",463,93,88,68,97\n'
  result=parse_csv(raw.encode('utf-8'),['キャベツ','だいこん','トマト','りんご'])
  self.assertEqual(result, {'キャベツ':78.0,'だいこん':83.0,'トマト':485.0,'りんご':463.0})
 def test_rejects_numeric_table_without_verified_price(self):
  raw='キャベツ,100,2000,150,111,99\nトマト,100,1000,900,111,99\n'
  self.assertEqual(parse_csv(raw.encode('utf-8'),['キャベツ','トマト']),{})
 def test_pdf_links_ignored(self):
  html='<a href="csv/26101h_syuyo.csv">上旬</a><a href="pdf/26101h_syuyo.pdf">PDF</a>'
  urls=page_csv_urls(2026,html)
  self.assertEqual(len(urls),1)
  self.assertEqual(list(urls.keys())[0],(2026,10,1))
 def test_ratio_math(self):
  obj={'foods':[{'id':'v-001','name':'キャベツ'}],'prices':[],'metadata':{'priceStatus':'sample'}}
  changed=apply_prices(obj,{'キャベツ':80.0},{'キャベツ':[100.,100.,100.]},(2026,10,2),'https://www.maff.go.jp/sample.csv')
  self.assertEqual(changed,1);self.assertEqual(obj['prices'][0]['normalRatio'],80.0)
  self.assertFalse(obj['prices'][0]['sample'])
if __name__=='__main__':unittest.main()
