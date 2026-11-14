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
