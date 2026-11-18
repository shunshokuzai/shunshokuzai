import datetime as dt,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from news_sources import canonical,identity,article_text,automatic_items,build_ledger,parse_date,make_item
from cause_assessment import assess
from update_topics import merge_report

FOOD={'foodId':'f','name':'みかん','aliases':['みかん','ミカン'],'category':'fruit'}
class NewsTests(unittest.TestCase):
 def test_tracking_and_pagination_are_one_article(self):
  self.assertEqual(identity('https://example.com/a?utm_source=x&page=2'),identity('https://example.com/a?display=1'))
 def test_publication_date_is_the_article_date_not_the_current_navigation_date(self):
  raw='<nav>2026年11月18日</nav><article><header><h1>みかんの収穫</h1><time datetime="2026-11-04T18:30:00+09:00">11月4日</time></header><p>今年のみかんについて産地の生産者に取材しました。少雨の影響で小玉となり、水やりを続けて収穫を迎えています。</p></article>'
  _,title,date,text=article_text(raw.encode(),[FOOD]);self.assertEqual(date,dt.date(2026,11,4));self.assertIn('少雨',text)
  self.assertEqual(parse_date('2026-11-03T16:00:00Z'),dt.date(2026,11,4))
 def test_restricted_articles_are_not_used(self):
  html='<script type="application/ld+json">{"isAccessibleForFree":false}</script><h1>みかん</h1>'
  with self.assertRaisesRegex(ValueError,'restricted'):article_text(html.encode(),[FOOD])
 def test_source_attribution_and_current_season_are_required_for_automatic_publication(self):
  args=('みかんの収穫',dt.date(2026,11,4),'https://example.com/a',{'name':'ニュース'},[FOOD],dt.date(2026,11,18))
  self.assertEqual(automatic_items('今年は少雨の影響で小玉です。'*6,*args)[1],'attribution_missing')
  out,status=automatic_items('今年のみかんは少雨の影響で小玉傾向となり、生産者によると水やりを続けながら収穫しているということです。適期の出荷に向けて作業が続いています。',*args)
  self.assertEqual(status,'awaiting_summary');self.assertTrue(out[0]['requireAi'])
  obj={'topics':[],'metadata':{}};merge_report(obj,out,'','test',0);self.assertEqual(obj['topics'],[])
 def test_this_year_article_about_last_year_research_is_not_this_year_crop(self):
  text='みかんの生育 2026年11月13日 中央の協会によると、2025年の調査ではみかんの高温被害が報告されました。2025年のアンケート結果をまとめたものです。'
  out,_=automatic_items(text,'みかんの生育',dt.date(2026,11,13),'https://example.com/a',{'name':'TV'},[FOOD],dt.date(2026,11,18))
  self.assertEqual(out,[])
 def test_news_ledger_cannot_claim_a_fetched_article_was_used(self):
  obj={'topics':[]};state={'articles':{'n':{'id':'n','url':'https://example.com/a','status':'awaiting_summary','foodIds':['f']}},'lastRun':{}}
  rows=build_ledger(obj,state)['articles'];self.assertEqual(rows[0]['status'],'pending');self.assertEqual(rows[0]['uses'],[])
 def test_fruit_and_fish_sources_get_causes_without_being_maff(self):
  a=assess({'url':'https://example.com/a','excerpt':'少雨の影響でみかんは小玉となっている。','food':{'category':'fruit'}})
  self.assertEqual(a['status'],'documented');self.assertIn('水分',a['text'])
  a=assess({'url':'https://www.fra.go.jp/a','excerpt':'海水温の上昇の影響で稚魚が育ちにくい可能性がある。','food':{'category':'fish'}})
  self.assertEqual(a['status'],'source_hypothesis');self.assertIn('推測',a['text'])
 def test_negation_and_missing_mechanisms_do_not_get_invented_causes(self):
  a=assess({'url':'https://example.com/a','excerpt':'高温の影響はない。生育の遅れは確認されている。'})
  self.assertEqual(a['status'],'unconfirmed')
  self.assertEqual(assess({'excerpt':'サケの来遊数は前年比60%。'})['status'],'unconfirmed')
 def test_reviewed_article_retains_food_specific_causes_and_uses(self):
  profile={'url':'https://example.com/a','publisher':'TV','title':'みかん','periodStart':'2026-07-01','periodEnd':'2026-11-04','scope':'長崎の取材園','region':'長崎','facts':['小玉の報道'],'reviewNotes':['全国へ一般化しない'],'cause':{'status':'documented','text':'少雨の影響で小玉です。','basis':'取材先'},'summary':'少雨の影響で小玉です。'}
  item=make_item(profile,FOOD,'少雨の影響で小玉です。',dt.date(2026,11,4),'みかん')
  obj={'topics':[],'metadata':{}};merge_report(obj,[item],'','test',0)
  rows=build_ledger(obj,{'articles':{},'lastRun':{}})['articles'];self.assertEqual(rows[0]['status'],'used');self.assertEqual(rows[0]['uses'][0]['foodId'],'f');self.assertEqual(obj['topics'][0]['sourceType'],'news')
if __name__=='__main__':unittest.main()
