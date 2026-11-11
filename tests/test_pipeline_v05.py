import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from update_data import parse_csv,apply_prices
from update_fish import compute_ratio,parse_rows,url_index,apply_fish,parse_piece_size
from update_topics import grounded_result

class FakeResponse:
    def __init__(self,x):self.x=x
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return self.x

class PipelineTests(unittest.TestCase):
    def test_schema_and_records(self):
        data=json.loads((ROOT/'data/seed.json').read_text(encoding='utf-8'))
        self.assertTrue(len(data['foods'])>=100)
        self.assertTrue(len(data['prices'])>=40)
        self.assertTrue(len(data['topics'])>=9)
        self.assertTrue(all('price' in p and p['price']>0 and 'sourceUrl' in p for p in data['prices']))
    def test_fish_table_extracts_first_middle_price_only(self):
        rows=[['サ バ','16.5','74','↓','99','↓','宮城','－','1404','799','540','121','123','7-10入/5kg'],
              ['サ ン マ','6.4','44','↓','14','↓','北海道','生','4320','1863','1080','99','205','130g'],
              ['',None,None,None,None,None,'各地','解凍','1080','-','648',None,None,None],
              ['ア ジ','43.8','88','↓','127','↑','鳥取','中','3240','670','540','113','91','200g']]
        res=parse_rows([rows]);self.assertEqual(res['サンマ']['price'],1863)
        self.assertEqual(res['サバ']['price'],799)
        self.assertAlmostEqual(res['サバ']['pieceWeightKg'],5/8.5)
        self.assertAlmostEqual(res['サンマ']['pieceWeightKg'],.13)
        self.assertEqual(res['サンマ']['yearAgoRatio'],205)
    def test_fish_piece_weight(self):
        self.assertAlmostEqual(parse_piece_size('130–140g/尾','サンマ'),.135)
        self.assertAlmostEqual(parse_piece_size('7-10入/5kg','サバ'),5/8.5)
        self.assertAlmostEqual(parse_piece_size('200g','アジ'),.2)
        self.assertAlmostEqual(parse_piece_size('0.5-1.5kg/尾','キンメダイ'),1.)
        self.assertIsNone(parse_piece_size('-','マグロ'))
        self.assertIsNone(parse_piece_size('0.1kg','カキ'))
    def test_fish_index_headings(self):
        s='<h2>2026年</h2><h3>10月</h3><a href="/documents/d/shijou/2026104-1-pdf">第4週</a><h2>2025年</h2><h3>10月</h3><a href="/documents/d/shijou/2025104-pdf">第4週</a>'
        links=url_index(s);self.assertEqual(len(links),2)
        self.assertIn((2026,10,4),links)
    def test_benchmark_no_prior_year_leakage(self):
        self.assertEqual(compute_ratio(80,[100,100,100]),(100,80))
        self.assertEqual(compute_ratio(80,[100,100]),(None,None))
        obj={'foods':[{'name':'サバ','id':'f-097','category':'fish'}],'prices':[], 'metadata':{}}
        apply_fish(obj,{'サバ':{'price':99,'yearAgoRatio':111}}, {'サバ':{2025:100}},(2026,11,1),
                   'https://www.shijou.metro.tokyo.lg.jp/test.pdf', {2025:'https://www.shijou.metro.tokyo.lg.jp/past.pdf'}, {1:{'サバ':{'price':99}}})
        self.assertIsNone(obj['prices'][0]['normalRatio'])
        self.assertEqual(obj['prices'][0]['history'],[99])
    def test_new_csv_replace_only_available_food_and_mark_rest_stale(self):
        obj={'foods':[{'id':'v-001','name':'キャベツ','category':'vegetable'}, {'id':'v-002','name':'トマト','category':'vegetable'}],
          'prices':[{'foodId':'v-002','price':300,'normalRatio':101}], 'metadata':{}}
        apply_prices(obj,{'キャベツ':250},{'キャベツ':[200,200,200]},(2026,11,1),'https://www.maff.go.jp/csv')
        by={p['foodId']:p for p in obj['prices']}
        self.assertEqual(by['v-001']['normalRatio'],125)
        self.assertTrue(by['v-002']['stale']);self.assertIsNone(by['v-002']['normalRatio'])
    def test_gemini_rejects_unsupported_summary(self):
        payload={'candidates':[{'content':{'parts':[{'text':'2026年の状況について、詳細な情報が発表されている。'}]},
          'groundingMetadata':{'groundingChunks':[]}}]}
        with patch('urllib.request.urlopen',return_value=FakeResponse(json.dumps(payload).encode())):
            self.assertIsNone(grounded_result('キャベツ','key','gemini-2.5-flash-lite',2026))
        payload['candidates'][0]['groundingMetadata']['groundingChunks']=[{'web':{'uri':'https://www.maff.go.jp/test','title':'農林水産省'}}]
        with patch('urllib.request.urlopen',return_value=FakeResponse(json.dumps(payload).encode())):
            self.assertIsNotNone(grounded_result('キャベツ','key','gemini-2.5-flash-lite',2026))

if __name__=='__main__':unittest.main()
