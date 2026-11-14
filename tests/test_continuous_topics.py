import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from topic_discovery import aliases_for,matching_foods,discover_links,article_items,collect,trusted
from regional_topics import alic_month_items
from update_topics import merge_report

class ContinuousTopicTests(unittest.TestCase):
 def setUp(self):
  self.today=dt.date(2026,11,14)
  self.source={'id':'kochi-fruit','name':'県試験場','url':'https://official.test/index','hosts':['official.test'],'categories':['fruit'],'scope':'県試験場の調査樹','include':'/article','terms':['生育調査']}
  self.food={'foodId':'chestnut','name':'くり','category':'fruit','aliases':['くり','クリ','栗'],'sourceIds':['kochi-fruit']}
  self.html='<html><h1>果樹試験場</h1><h1>2026年の生育調査(クリ)</h1><p>果樹試験場：2026/10/09</p><h2>コメント</h2><p>収穫始期は「ぽろたん」「筑波」ともに平年より早くなりました。収穫終期は品種によって異なりました。</p><h2>生態調査</h2><table><tr><td>過去年の表</td></tr></table></html>'
 def test_chestnut_commentary_is_not_the_logo_or_table(self):
  entry={'url':'https://official.test/article/1','title':'2026年の生育調査(クリ)'}
  items,result=article_items(self.html,entry,self.source,[self.food],self.today)
  self.assertEqual(result,'source_text_found');self.assertEqual(len(items),1)
  self.assertIn('収穫始期',items[0]['excerpt']);self.assertNotIn('過去年',items[0]['excerpt'])
  self.assertIsNone(items[0]['publishedAt'])
  self.assertEqual(items[0]['sourceUpdatedAt'],'2026-10-09')
  self.assertTrue(items[0]['seasonalRecord'])
  self.assertIn('調査樹',items[0]['scope'])
 def test_old_or_future_observation_is_not_published_as_current(self):
  entry={'url':'https://official.test/article/1','title':'クリ'}
  self.assertEqual(article_items(self.html.replace('2026/10/09','2027/10/09'),entry,self.source,[self.food],self.today)[0],[])
 def test_aliases_do_not_treat_negative_nashi_as_a_pear(self):
  pear={'foodId':'pear','name':'なし','category':'fruit','aliases':['なし','日本なし','梨'],'sourceIds':[]}
  self.assertEqual(matching_foods('被害なし。異常なし。',[pear]),[])
  self.assertEqual(matching_foods('日本なしの出荷が順調。',[pear]),[pear])
 def test_longer_named_food_does_not_leak_into_generic_food(self):
  foods=[{'foodId':'a','name':'エビ','aliases':['エビ'],'category':'fish'},
         {'foodId':'b','name':'甘エビ','aliases':['甘エビ'],'category':'fish'}]
  self.assertEqual([f['foodId'] for f in matching_foods('甘エビの水揚げ',foods)],['b'])
 def test_allowlist_and_source_index_discovery(self):
  html='<html><a href="/article/1">2026年の生育調査(クリ)</a><a href="https://evil.test/article/2">クリの生育調査</a></html>'
  links=discover_links(html,self.source,[self.food],self.today)
  self.assertEqual(len(links),1);self.assertEqual(links[0]['foodIds'],['chestnut'])
  self.assertFalse(trusted('http://official.test/article/1',self.source))
  self.assertFalse(trusted('https://official.test.evil.test/article/1',self.source))
 def test_index_check_and_article_check_are_distinct(self):
  catalog={'sources':[self.source],'foods':[self.food]}
  def getter(url,source):
   return ('<html><a href="/article/1">2026年の生育調査(クリ)</a></html>' if url.endswith('/index') else self.html).encode()
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'state.json';obj={'foods':[{'id':'chestnut','name':'くり'}],'topics':[],'metadata':{}}
   items,errors=collect(obj,self.today,limit=0,getter=getter,path=path,catalog=catalog)
   status=obj['metadata']['foodResearchStatus']['chestnut']
   self.assertTrue(status['lastIndexCheckedAt']);self.assertIsNone(status['lastArticleCheckedAt'])
   self.assertEqual(status['coverage'],'source_pending')
   items,errors=collect(obj,self.today,limit=1,getter=getter,path=path,catalog=catalog)
   self.assertEqual(len(items),1);self.assertFalse(errors)
   self.assertTrue(obj['metadata']['foodResearchStatus']['chestnut']['lastArticleCheckedAt'])
 def test_failed_index_preserves_previous_topic_and_does_not_claim_success(self):
  catalog={'sources':[self.source],'foods':[self.food]}
  with tempfile.TemporaryDirectory() as folder:
   obj={'foods':[{'id':'chestnut','name':'くり'}],'topics':[{'id':'old','foodId':'chestnut'}],'metadata':{}}
   def getter(url,source):raise OSError('unavailable')
   items,errors=collect(obj,self.today,getter=getter,path=Path(folder)/'state.json',catalog=catalog)
   self.assertEqual(items,[]);self.assertEqual(obj['topics'][0]['id'],'old')
   self.assertEqual(obj['metadata']['foodResearchStatus']['chestnut']['indexStatus'],'error')
   self.assertIsNone(obj['metadata']['foodResearchStatus']['chestnut']['lastIndexCheckedAt'])
 def test_copyrighted_source_is_not_published_without_a_summary(self):
  obj={'topics':[],'metadata':{}}
  item={'food':{'id':'x','name':'くり'},'url':'https://official.test/article','publishedAt':'2026-11-01','excerpt':'今年の栗の出荷が始まりました。品質がよく、産地で選別作業が続いています。','requireAi':True}
  result=merge_report(obj,[item],'','test',0)
  self.assertEqual(result['added'],0);self.assertEqual(obj['topics'],[])
 def test_next_month_does_not_reuse_november_prepared_summary(self):
  html='<h1>野菜情報2026年12月号</h1><p>セロリ（セルリー）は静岡産の出荷が増え、12月の生育は順調とされています。産地では天候に注意して出荷を進める予定です。</p><p>（執筆者：担当者）</p>'
  items=alic_month_items(html,[{'id':'celery','name':'セロリ','category':'vegetable'}],dt.date(2026,12,5))
  self.assertEqual(len(items),1);self.assertTrue(items[0]['requireAi'])
  self.assertNotIn('preparedSummary',items[0])
  self.assertIn('/2612_',items[0]['url'])
 def test_catalog_covers_every_registered_food(self):
  root=Path(__file__).resolve().parents[1]
  catalog=json.loads((root/'data/topic_catalog.json').read_text(encoding='utf-8'))
  seed=json.loads((root/'data/seed.json').read_text(encoding='utf-8'))
  self.assertEqual({f['foodId'] for f in catalog['foods']},{f['id'] for f in seed['foods']})
  self.assertTrue(all(f['sourceIds'] for f in catalog['foods']))

 def test_new_saury_pdf_must_match_publication_and_explicit_forecast_window(self):
  from topic_discovery import jafic_items
  from types import SimpleNamespace
  source={**self.source,'id':'jafic-forecasts'}
  entry={'url':'https://official.test/information/2026/11/19/report'}
  html='<h1>2026年度第8回サンマ中短期漁況予報（2026年11月19日公表）</h1><a href="/forecast.pdf">サンマ予報PDF</a>'
  text='2026年11月19日 来遊量 道東は断続的。三陸は低位。常磐は低位。問い合わせ先 予測期間:2026年11月下旬から12月下旬まで'
  class Pdf:
   def __enter__(self):return SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda:text)])
   def __exit__(self,*args):pass
  food={'foodId':'s','name':'サンマ','aliases':['サンマ'],'category':'fish','sourceIds':['jafic-forecasts']}
  with patch('pdfplumber.open',return_value=Pdf()):
   items,status=jafic_items(html,entry,source,[food],dt.date(2026,11,20),getter=lambda *a:b'%PDF')
  self.assertEqual(status,'source_text_found')
  self.assertEqual(items[0]['periodStart'],'2026-11-21')
  self.assertEqual(items[0]['periodEnd'],'2026-12-31')
  self.assertTrue(items[0]['requireAi'])
 def test_ja_h3_heading_and_article_date_are_supported(self):
  source={**self.source,'id':'ja-kumamoto'}
  html='<html><h3>栗の出荷が始まる</h3><p>2026.09.02</p><p>栗は夏の高温で早生が小ぶりですが、品質は例年並みと報告されています。</p></html>'
  items,status=article_items(html,{'url':'https://official.test/article/1','title':'栗の出荷が始まる'},source,[self.food],self.today)
  self.assertEqual(status,'source_text_found')
  self.assertEqual(items[0]['publishedAt'],'2026-09-02')
  self.assertTrue(items[0]['requireAi'])
  self.assertLessEqual(len(items[0]['publicExcerpt']),25)

 def test_chestnut_weight_table_keeps_year_and_variety_separate(self):
  from topic_discovery import chestnut_weights
  from bs4 import BeautifulSoup
  html='<table><tr><th>品種 年次 1果重(g) 比重</th></tr><tr><td>ぽろたん</td><td>2026</td><td>8/25</td><td>25.3</td><td>1.071</td></tr><tr><td>2025</td><td>9/3</td><td>31.7</td><td>1.049</td></tr><tr><td>平年</td><td>8/31</td><td>28.5</td><td>1.072</td></tr></table>'
  weights=chestnut_weights(BeautifulSoup(html,'html.parser'),2026)
  self.assertEqual(weights,['ぽろたんの1果重は25.3g（資料の平年値28.5g）'])
  self.assertNotIn('31.7',weights[0])

 def test_ai_budget_is_not_spent_twice_on_the_same_food_in_one_run(self):
  obj={'topics':[],'metadata':{}}
  base={'food':{'id':'chestnut','name':'くり'},'publishedAt':'2026-11-01','excerpt':'栗の出荷が始まり、品質は例年並みと報告されています。産地の出荷は今後も続く見通しです。','requireAi':True}
  items=[{**base,'url':'https://official.test/one','reportKey':'one'},{**base,'url':'https://official.test/two','reportKey':'two'}]
  with patch('update_topics.ai_summarize',return_value='栗の品質は例年並みと報告されており、産地では出荷が始まっています。今後も出荷が続く見通しです。') as mocked:
   result=merge_report(obj,items,'test','test',6)
  self.assertEqual(result['aiAttempted'],1)
  self.assertEqual(mocked.call_count,1)
  self.assertEqual(len(obj['topics']),1)

 def test_discovery_runs_without_user_action_on_a_non_ai_day(self):
  import run_refresh
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'seed.json'
   obj={'foods':[],'prices':[],'topics':[],'metadata':{}}
   path.write_text(json.dumps(obj),encoding='utf-8')
   calls=[]
   def step(script,env=None):
    calls.append((script,env))
    return 'ok'
   with patch.object(run_refresh,'DATA',path),patch.object(run_refresh,'run_step',side_effect=step),patch.object(run_refresh,'save'):
    result=run_refresh.run_pipeline(today=dt.datetime(2026,11,16,10,23),ai_key='test-key')
   self.assertEqual(result['topics'],'ok')
   self.assertEqual(result['gemini'],'not_scheduled')
   env=next(env for script,env in calls if script=='update_topics.py')
   self.assertEqual(env['SOURCES_ONLY'],'true')

 def test_monthly_leek_does_not_match_inside_onion(self):
  html='<h1>野菜情報2026年12月号</h1><p>たまねぎは北海道産の出荷が増え、12月の生育は順調とされています。産地では天候に注意して出荷を進める予定です。</p><p>（執筆者：担当者）</p>'
  foods=[{'id':'onion','name':'たまねぎ','category':'vegetable'},{'id':'leek','name':'長ねぎ','category':'vegetable'}]
  items=alic_month_items(html,foods,dt.date(2026,12,5))
  self.assertEqual([i['food']['id'] for i in items],['onion'])
