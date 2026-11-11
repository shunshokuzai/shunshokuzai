import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from update_data import page_csv_urls,parse_csv,apply_prices

class TestDataImport(unittest.TestCase):
 def test_csv_parser(self):
  csv_text='品目,卸売数量(t),卸売価格(円/kg),対前年同旬比(%),\nキャベツ,20,145,95,\nだいこん,12,180,101,\nはくさい,19,95,99,\nトマト,8,320,100,\nきゅうり,11,245,92,\nなす,8,290,109,\nさつまいも,6,195,98,\nみかん,7,342,105,\n'
  out=parse_csv(csv_text.encode('utf-8'),['キャベツ','だいこん','はくさい','トマト','きゅうり','なす','さつまいも','みかん'])
  self.assertEqual(out['キャベツ'],145.0);self.assertEqual(out['さつまいも'],195.0)
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
