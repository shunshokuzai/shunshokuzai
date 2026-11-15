import datetime as dt,io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import retail_prices as retail
import production_regions as prod
import regional_discovery as regional
import topic_discovery as discovery

def xlsx(rows,title='data'):
 b=openpyxl.Workbook();sh=b.active;sh.title=title
 for row in rows:sh.append(row)
 out=io.BytesIO();b.save(out);return out.getvalue()
class RetailTests(unittest.TestCase):
 def test_highlighted_dataset_title_and_publication_date_are_recognized(self):
  html='<div><h3><em>主要</em>品目の<em>都市</em>別<em>小売</em>価格「1001 米」～「2183 学校給食」</h3><p>2026-10-23</p><a href="/stat-search/file-download?statInfId=abc&fileKind=0">EXCEL</a></div>'
  self.assertEqual(retail.candidates(html.encode())[0]['publishedAt'],'2026-10-23')
 def test_basic_brand_excludes_table_control_metadata(self):
  raw=xlsx([[1101,'まぐろ','めばち又はきはだ、刺身用',None,None,'100g',None,'A',None,'●']])
  specs=retail.specifications(raw)
  self.assertIn('めばち',specs[1101]);self.assertNotIn('●',specs[1101]);self.assertNotIn('100g',specs[1101])
 def test_city_units_missing_values_and_local_brand_exceptions_remain_separate(self):
  codes=['01100','02201','03201','04100','05201','06201','07201','08201','09201','10201','11201','12100']
  names=['札幌市','青森市','盛岡市','仙台市','秋田市','山形市','福島市','水戸市','宇都宮市','前橋市','さいたま市','千葉市']
  rows=[['主要品目の都市別小売価格'],[None]*15+codes,[None]*7+['時間軸（月）コード','時間軸（月）','銘柄符号','品目','単位','銘柄改正年月','表章単位','地域']+names]
  for code in (1101,1401,1402,1403,1405,1406):
   rows.append([None]*7+[2026000909,'2026年9月',code,'調査品目','100g' if code==1101 else '1kg',None,'円',None]+[123]*12)
  rows[3][16]='-';specs={c:'調査規格' for c in (1101,1401,1402,1403,1405,1406)}
  records,regions=retail.parse_cities(xlsx(rows),{'url':'https://www.e-stat.go.jp/a','publishedAt':'2026-10-23'},specs,'https://www.stat.go.jp/spec',{(1101,'01100')},dt.date(2026,11,15))
  self.assertEqual(len(regions),12);self.assertEqual(len(records),70)
  self.assertFalse(any(r['itemCode']=='1101' and r['regionId'] in ('city-01100','city-02201') for r in records))
  self.assertEqual(next(r for r in records if r['itemCode']=='1101')['unit'],'100g')
  self.assertTrue(all(r['observationEnd']=='2026-09-30' for r in records))
 def test_source_failure_retains_the_last_valid_retail_data(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'retail.json';prior={'records':[{'foodId':'x','price':123,'sourceGroup':'city'}],'regions':[{'id':'city-x','name':'既存都市'}],'lastSuccessAt':'2026-11-01'}
   path.write_text(json.dumps(prior),encoding='utf-8');obj={'metadata':{}}
   def failed(url):raise OSError('offline')
   out=retail.refresh(obj,dt.date(2026,11,15),failed,path)
   self.assertEqual(out['records'],prior['records']);self.assertEqual(out['lastSuccessAt'],'2026-11-01');self.assertEqual(out['status'],'partial')
class RegionalTests(unittest.TestCase):
 def test_production_ranking_uses_harvest_tonnes_and_a_named_past_year(self):
  rows=[['令和7年産'],[None,'全国・都道府県','作付面積','10a当たり収量','収穫量','出荷量'],[None,'全国',100,100,1000,900],[None,'高知',1,50,50,45],[None,'北海道',80,300,600,500],[None,'千葉',10,200,200,180],[None,'青森',5,150,150,120]]
  out=prod.vegetable_profiles(xlsx(rows,'にんじん'),'https://www.e-stat.go.jp/source',[{'name':'にんじん'}])['にんじん']
  self.assertEqual(out['year'],2025);self.assertEqual([r['name'] for r in out['regions']],['北海道','千葉','青森']);self.assertEqual(out['regions'][0]['share'],60)
 def test_rotation_does_not_let_one_publisher_consume_the_whole_article_budget(self):
  rows=[{'sourceId':'kochi','url':'k'+str(i)} for i in range(5)]+[{'sourceId':'nagano','url':'n'},{'sourceId':'alic','url':'a'}]
  ordered=discovery.fair_queue(rows,lambda x:x['url'])
  self.assertEqual(len({x['sourceId'] for x in ordered[:3]}),3)
 def test_alic_latest_survey_is_kept_separate_from_previous_survey(self):
  html='<h2>令和8年度</h2><h4>第3回（調査日：11月6日）</h4><table><tr><th>調査産地</th><td>JAちばみどり管内</td></tr><tr><th>作況[平年比]</th><td>不良</td><th>生育進度[平年比]</th><td>遅い</td></tr></table><h4>第2回（調査日：9月14日）</h4><p>平年並み</p>'
  food={'foodId':'v-028','name':'長ねぎ'};entry={'url':'https://vegetan.alic.go.jp/trend/y2026/s09/p12.html','title':'長ねぎ・千葉','region':'千葉','foodIds':['v-028'],'fiscalYear':2026,'sourceUpdatedAt':'2026-11-12'};source={'id':'alic','name':'ALIC','parser':'alic','region':'千葉'}
  items,result=regional.parse_alic(html.encode(),entry,source,[food],dt.date(2026,11,15))
  self.assertEqual(result,'source_text_found');self.assertIn('不良',items[0]['shortSummary']);self.assertNotIn('9月14日',items[0]['shortSummary']);self.assertIsNone(items[0]['publishedAt']);self.assertEqual(items[0]['periodEnd'],'2026-11-06')
  self.assertEqual(regional.parse_alic(html.encode(),entry,source,[food],dt.date(2026,10,1))[1],'observation_date_outside_current_year')
 def test_yearly_trial_observations_cannot_be_reused_next_year(self):
  html='<h2>令和8年度 カンキツ生育概況</h2><h4>YN26</h4><table><tr><td>令和8年</td><td>4月1日</td><td>4月21日</td><td>4月24日</td><td>4月29日</td><td>5月2日</td></tr></table>'
  entry={'url':'https://www.pref.wakayama.lg.jp/x','title':'生育','region':'和歌山'};source={'id':'wakayama','name':'和歌山','parser':'wakayama','region':'和歌山'};food={'foodId':'f-055','name':'みかん'}
  items,_=regional.parse_inline(html.encode(),entry,source,[food],dt.date(2026,11,15));self.assertEqual(len(items),1);self.assertIn('4月29日',items[0]['shortSummary'])
  self.assertEqual(regional.parse_inline(html.encode(),entry,source,[food],dt.date(2027,1,1))[0],[])
if __name__=='__main__':unittest.main()
