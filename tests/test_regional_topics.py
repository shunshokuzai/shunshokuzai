import datetime as dt
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from regional_topics import ALIC_FACTS, alic_items, apple_items
from update_topics import merge_report

class RegionalTopicsTests(unittest.TestCase):
 def setUp(self):
  self.today=dt.date(2026,11,13)
  self.foods=[{'id':str(i),'name':r[0]} for i,r in enumerate(ALIC_FACTS)]
  self.html='<h1>野菜情報2026年11月号</h1>'+''.join('<p>'+prefix+'、'+ '、'.join(required)+'。</p>' for _,prefix,required,_,_ in ALIC_FACTS)
 def test_current_issue_guard_and_limited_public_quotes(self):
  items=alic_items(self.html,self.foods,self.today)
  self.assertEqual(len(items),7)
  for item in items:
   self.assertIsNone(item['publishedAt'])
   self.assertLessEqual(len(item['publicExcerpt']),25)
   self.assertTrue(item['isForecast'])
  self.assertEqual(alic_items(self.html,self.foods,dt.date(2026,12,1)),[])
  with self.assertRaises(ValueError):alic_items(self.html.replace('2026年11月号','2025年11月号'),self.foods,self.today)
 def test_changed_source_cannot_reuse_prepared_claims(self):
  with self.assertRaises(ValueError):alic_items(self.html.replace('生育は順調','生育は不良'),self.foods,self.today)
 def test_prepared_summary_does_not_consume_gemini_quota_or_mirror_source(self):
  item=alic_items(self.html,self.foods,self.today)[0]
  # Use real-like source and a numeric-free prepared paraphrase for this unit test.
  item['preparedSummary']='静岡の露地セロリの出荷見込みが示されています。高温と長雨による根腐れの懸念があります。'
  obj={'topics':[],'metadata':{}}
  result=merge_report(obj,[item],'unused-key','unused-model',6,on_attempt=lambda:self.fail('No API request expected'))
  self.assertEqual(result['aiAttempted'],0)
  row=obj['topics'][0]
  self.assertEqual(row['summaryProvider'],'ChatGPT')
  self.assertEqual(row['sourceExcerpt'],item['publicExcerpt'])
  self.assertFalse(row['verified'])
 def test_apple_maturity_not_production_forecast(self):
  html='<time>2026.11.06</time><h1>2026年りんご ふじ</h1><p>無袋：11月6日現在、糖度は高い。</p><p>有袋：11月6日現在、硬度は低い。</p>'
  row=apple_items(html,[{'id':'apple','name':'りんご'}],self.today)[0]
  self.assertFalse(row['isForecast'])
  self.assertEqual(row['publishedAt'],'2026-11-06')
  self.assertIn('調査樹',row['scope'])
  self.assertEqual(apple_items(html,[{'id':'apple','name':'りんご'}],dt.date(2027,2,1)),[])
