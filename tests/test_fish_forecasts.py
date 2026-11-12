import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from fish_forecasts import forecast_links, target_period, forecast_sections, report_items, overview_sections
from official_topics import weekly_period


class FishForecastTests(unittest.TestCase):
    def test_overview_keeps_opposite_sea_area_trends_and_both_mackerel_species(self):
        text='''漁況（来遊量予測）
マイワシ
西では前年を上回るが、東では前年を下回る。全体として前年を下回る。
カタクチイワシ
西は低水準、北では前年を上回る。
ウルメイワシ
海域によって異なるが、全体として前年並。
マアジ
前年を下回る海域が多い。
マサバ・ゴマサバ
マサバ、ゴマサバともに低水準。
問い合わせ先'''
        result=overview_sections(text,'pacific')
        self.assertIn('上回る',result['マイワシ'])
        self.assertIn('下回る',result['マイワシ'])
        self.assertIn('ともに低水準',result['マサバ・ゴマサバ'])
        with self.assertRaises(ValueError):overview_sections(text.replace('マサバ・ゴマサバ\n',''),'pacific')

    def test_only_published_official_latest_family_links_are_selected(self):
        html='''<a href="/home/kenkyushokai/press/pr2026/fri_20260803_ukiuo-pac-1st.html">太平洋いわし類</a>
        <a href="/home/kenkyushokai/press/pr2026/fri_20261220_ukiuo-pac-2nd.html">太平洋いわし類</a>
        <a href="https://example.com/fri_20261030_bad.html">太平洋いわし類</a>'''
        links=forecast_links(html,dt.date(2026,11,12))
        self.assertEqual(links['pacific'][0],dt.date(2026,8,3))
        self.assertEqual(len(links),1)

    def test_explicit_forecast_dates_cross_new_year_without_inference(self):
        self.assertEqual(target_period('今回の予報は、2026年11月から2027年3月までの日本海。'),
                         (dt.date(2026,11,1),dt.date(2027,3,31)))
        self.assertEqual(target_period('今回の予報は、2026年8月から12月まで。')[1],dt.date(2026,12,31))
        with self.assertRaises(ValueError):target_period('今年の冬の予報。')
        self.assertEqual(weekly_period('2027年1月第1週（12月25日～12月31日）',(2027,1,1)),('2026-12-25','2026-12-31'))
        self.assertEqual(weekly_period('10月30日～11月5日',(2026,11,1)),('2026-10-30','2026-11-05'))

    def test_forecast_species_blocks_do_not_leak_past_stock_numbers(self):
        text='''マアジ対馬暖流系群の漁況予報 今後の見通し（2026年11月～2027年3月）
        対象海域：東シナ海・日本海。（1）来遊量：前年並み。漁況の経過 1.資源状態 2025年は30万トン。
        マサバ対馬暖流系群の漁況予報 今後の見通し（2026年11月～2027年3月）
        対象海域：日本海。（1）来遊量：前年を上回る。漁況の経過 2025年は20万トン。'''
        sections=forecast_sections(text)
        self.assertNotIn('上回る',sections['マアジ'])
        self.assertNotIn('30万トン',sections['マアジ'])
        self.assertIn('上回る',sections['マサバ'])

    def test_publication_pdf_family_and_period_are_checked_before_publication(self):
        foods=[{'id':'f','name':'ブリ','category':'fish'}]
        html='<h1>日本海中部ブリ長期漁況予報</h1>令和8年11月11日。今回の予報は、2026年11月から2027年3月まで。'
        text='2026年11月11日 日本海中部ブリ長期漁況予報 今後の見通し（2026年11月～2027年3月）漁況（来遊量）0歳魚は前年を下回る。2歳以上魚は前年並。問い合わせ先'
        args=(foods,'buri',dt.date(2026,11,11),'https://www.fra.go.jp/report',html,text,'https://www.fra.go.jp/report.pdf',dt.date(2026,11,12))
        items=report_items(*args)
        self.assertEqual(len(items),1)
        self.assertEqual(items[0]['periodEnd'],'2027-03-31')
        self.assertTrue(items[0]['isForecast'])
        self.assertIn('0歳魚',items[0]['excerpt'])
        self.assertIn('2歳以上魚',items[0]['excerpt'])
        altered=list(args);altered[5]=text.replace('2026年11月～','2026年10月～')
        with self.assertRaises(ValueError):report_items(*altered)


if __name__=='__main__':unittest.main()
