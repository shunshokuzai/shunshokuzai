import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from estat_history import daily_rows,aggregate_period,listing_entries,refresh_cached_baselines

HEADER='年,月,日,曜日,品目名,品目コード,産地名,産地コード,数量,価格\n'
class EstatHistoryTests(unittest.TestCase):
 def test_daily_aggregate_excludes_origins_and_imports(self):
  raw=(HEADER+'2022,7,26,火,ぶどう計,45000,,,200,1000\n2022,7,26,火,ぶどう計,45000,山梨,19,200,2000\n2022,7,26,火,ぶどう,50750,,,50,500\n').encode()
  self.assertEqual(daily_rows(raw,{'ぶどう'},'2022-07-26'),{'ぶどう':[200,1000]})
  with self.assertRaises(ValueError):daily_rows(raw,{'ぶどう'},'2022-07-25')
 def test_quantity_weighted_mean_and_incomplete_downloads(self):
  entries={'a':{},'b':{}}
  days={'a':{'values':{'だいこん':[100,100]}},'b':{'values':{'だいこん':[300,200]}}}
  self.assertEqual(aggregate_period(entries,days),{'だいこん':175})
  with self.assertRaises(ValueError):aggregate_period(entries,{'a':days['a']})
  days['b']['values']['だいこん']=None
  self.assertEqual(aggregate_period(entries,days),{})
 def test_manifest_requires_named_national_series_and_correct_year(self):
  html='<a href="/stat-search/files?stat_infid=000032228975">日別調査(令和4年7月26日) 果実 主要 卸売 市場 計</a><a href="/stat-search/files?stat_infid=000032228976">日別調査(令和4年7月26日) 果実 東京都</a>'
  self.assertEqual(len(listing_entries(html,2022)),1)
  with self.assertRaises(ValueError):listing_entries(html,2021)
