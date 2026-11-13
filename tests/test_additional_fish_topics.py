import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from additional_fish_topics import salmon_items,katsuo_items,sanma_items
from update_topics import validate_summary

class AdditionalFishTests(unittest.TestCase):
 def test_salmon_total_keeps_coastal_catch_and_river_capture_distinct(self):
  html='<h1 class="logo"></h1><h1>さけます来遊速報(令和8年度)</h1><h3>サケ道県別来遊数（9月30日現在）10月16日更新</h3><table><tr>'+''.join('<td>'+str(x)+'</td>' for x in ['合計',20,40,'50%',0,0,'0%',80,160,'50%',100,200,'50%'])+'</tr></table>'
  row=salmon_items(html,[{'id':'salmon','name':'サケ'}],dt.date(2026,11,13))[0]
  self.assertFalse(row['isForecast'])
  self.assertIn('沿岸の漁獲80尾',row['summaryExcerpt'])
  self.assertIn('捕獲20尾',row['summaryExcerpt'])
  self.assertEqual(row['periodEnd'],'2026-09-30')
  with self.assertRaises(ValueError):salmon_items(html.replace('<td>100</td>','<td>101</td>'),[{'id':'s','name':'サケ'}],dt.date(2026,11,13))
 def test_katsuo_forecast_expires_and_is_sea_area_specific(self):
  html='<p>令和8年6月29日。検討の結果、令和8年6～11月のカツオ来遊量は、昨年を上回ると予測されました。</p>'
  foods=[{'id':'k','name':'カツオ'}]
  row=katsuo_items(html,foods,dt.date(2026,11,13))[0]
  self.assertEqual(row['periodEnd'],'2026-11-30')
  self.assertIn('常磐',row['scope'])
  self.assertEqual(katsuo_items(html,foods,dt.date(2026,12,1)),[])
 def test_sanma_publication_and_regional_claims_are_required(self):
  html='<h1>2026年度第7回サンマ中短期漁況予報</h1>'
  text='2026年11月9日。11月中旬から12月下旬。さんま棒受網漁業。南下回遊群。来遊量・道東海域では、11月中旬は断続的な来遊となる。・三陸海域では、11月中旬は低位水準。・常磐海域では、11月中旬は低位水準。問い合わせ先'
  foods=[{'id':'s','name':'サンマ'}]
  row=sanma_items(html,text,foods,dt.date(2026,11,13))[0]
  validate_summary(row['preparedSummary'],row['excerpt'])
  self.assertEqual(row['periodStart'],'2026-11-11')
  with self.assertRaises(ValueError):sanma_items(html,text.replace('常磐海域',''),foods,dt.date(2026,11,13))
