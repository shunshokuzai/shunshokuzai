import datetime as dt,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from cause_assessment import regional_cause,assess,migrate_legacy
from regional_discovery import parse_alic
from update_topics import merge_report

class CauseTests(unittest.TestCase):
 def test_old_table_caption_migration_preserves_source_dates_without_inventing_causes(self):
  t={'summary':'2026年10月21日の渥美の調査。作況：豊作、生育進度：遅い、出荷進度：遅い、作付面積・前年比：前年並み。地域の調査値であり、全国の作柄を示すものではありません。','sourceFamily':'regional-alic-regions-x','retrievedAt':'2026-11-12','periodEnd':'2026-10-21'}
  self.assertEqual(migrate_legacy([t]),1);self.assertEqual(t['retrievedAt'],'2026-11-12');self.assertEqual(t['periodEnd'],'2026-10-21')
  self.assertEqual(t['causeAssessment']['status'],'unconfirmed');self.assertNotIn('作況：',t['summary']);self.assertIn('豊作',t['summary']);self.assertNotIn('雨',t['summary'])
  self.assertEqual(migrate_legacy([t]),0)
 def test_explicit_wet_damage_has_limited_scope(self):
  c=regional_cause({'生育状況':'9月期の雨の影響の湿害によって、活着不良や生育ムラのあるほ場が一部で見られる。'})
  self.assertEqual(c['status'],'documented');self.assertIn('一部',c['text']);self.assertNotIn('関東',c['text'])
 def test_recovery_must_not_be_described_as_continuing_deterioration(self):
  c=regional_cause({'生育状況':'9月中の長雨、日照不足による作柄不良、小玉傾向からは徐々に回復。'})
  self.assertEqual(c['status'],'documented');self.assertIn('回復',c['text'])
 def test_weather_alone_and_negation_do_not_establish_damage(self):
  for sections in ({'天候状況':'関東で豪雨。日照不足。','生育状況':'順調。'},{'生育状況':'雨の湿害による活着不良や生育ムラは見られない。'},{'生育状況':'雨の湿害による活着不良や生育ムラが懸念される。'}):
   self.assertEqual(regional_cause(sections)['status'],'unconfirmed')
 def test_sunshine_association_is_labelled_inference(self):
  c=regional_cause({'生育状況':'10月以降は日照時間も多くなり、活着も良く生育状況も良好。'})
  self.assertEqual(c['status'],'inference');self.assertIn('推測',c['text']);self.assertIn('確認できていません',c['text'])
 def test_latest_survey_narrative_does_not_include_older_survey_or_photo(self):
  html='<h2>令和8年度</h2><h4>第2回（調査日：10月21日）</h4><table><tr><th>調査産地</th><td>渥美</td></tr><tr><th>作況[平年比]</th><td>豊作</td><th>生育進度[平年比]</th><td>遅い</td></tr></table><h5>天候状況</h5><p>雨。</p><h5>生育状況</h5><p>9月期の雨の影響の湿害によって、活着不良や生育ムラのあるほ場が一部で見られる。</p><h5>写真の補足説明</h5><p>関東で豪雨。</p><h4>第1回（調査日：9月1日）</h4><h5>生育状況</h5><p>台風による壊滅。</p>'
  entry={'url':'https://vegetan.alic.go.jp/trend/y2026/s01/p23.html','region':'愛知','title':'キャベツ・愛知','fiscalYear':2026,'foodIds':['c']}
  items,_=parse_alic(html.encode(),entry,{'id':'alic','name':'ALIC','parser':'alic'},[{'foodId':'c','name':'キャベツ'}],dt.date(2026,11,15))
  item=items[0];self.assertEqual(item['causeAssessment']['status'],'documented')
  self.assertIn('根付き',item['summaryExcerpt']);self.assertNotIn('関東',item['summaryExcerpt']);self.assertNotIn('壊滅',item['summaryExcerpt'])
  self.assertLessEqual(len(item['publicExcerpt']),24)
  obj={'topics':[],'metadata':{}};merge_report(obj,items,'','test',0)
  self.assertEqual(obj['topics'][0]['summary'],item['summaryExcerpt']);self.assertEqual(obj['topics'][0]['causeAssessment'],item['causeAssessment'])
 def test_government_causal_explanation_preserves_forecast_uncertainty(self):
  item={'url':'https://www.maff.go.jp/j/press/example','evidenceSections':[{'label':'生育・出荷','text':'長雨の影響で出荷が減る見込み。'}]}
  self.assertIn('見込み',assess(item)['text']);self.assertEqual(assess(item)['status'],'documented')
 def test_protected_publisher_is_not_quoted_by_generic_cause_extractor(self):
  self.assertEqual(assess({'url':'https://vegetan.alic.go.jp/x','evidenceSections':[{'text':'長雨の影響で不良。'}]})['status'],'unconfirmed')
if __name__=='__main__':unittest.main()
