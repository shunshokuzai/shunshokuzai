import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from backfill_history import attach_long_history, parse_produce_pdf, backfill, fish_observation
from market_history import MarketHistory


class LongHistoryTests(unittest.TestCase):
    def test_image_pdf_falls_back_to_same_period_official_html(self):
        raw = '<meta charset="utf-8"><h1>2024年2月4週</h1>'.encode('utf-8')
        with patch('backfill_history.fetch', side_effect=[b'%PDF-image', raw]), patch(
                'backfill_history.read_weekly', side_effect=[ValueError('no table'), {'サバ': {'price': 454}}]):
            source, values = fish_observation((2024, 2, 4), 'https://www.shijou.metro.tokyo.lg.jp/report')
        self.assertTrue(source.endswith('/2024024.html'))
        self.assertEqual(values['サバ']['price'], 454)
        with patch('backfill_history.fetch', side_effect=[b'%PDF-image', raw.replace(b'2024', b'2023')]), patch(
                'backfill_history.read_weekly', side_effect=ValueError('no table')):
            with self.assertRaisesRegex(ValueError, 'period mismatch'):
                fish_observation((2024, 2, 4), 'https://www.shijou.metro.tokyo.lg.jp/report')

    def test_five_completed_years_plus_current_and_matching_fish_brand_only(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = MarketHistory(Path(directory)/'history.json')
            for year, brand in ((2020, '生'), (2021, '生'), (2022, '冷凍'), (2026, '生')):
                archive.put('fish', (year, 10, 1), 'https://www.shijou.metro.tokyo.lg.jp/report',
                            {'サバ': {'price': year, 'brandLabel': brand, 'brandDetail': brand}})
            obj = {'foods': [{'id': 'f', 'name': 'サバ', 'category': 'fish'}],
                   'prices': [{'foodId': 'f'}], 'metadata': {}}
            attach_long_history(obj, archive)
            points = obj['prices'][0]['longHistory']
            self.assertEqual([p['period'][0] for p in points], [2021, 2026])
            self.assertEqual(obj['prices'][0]['longHistoryRange'], [2021, 2026])
            self.assertTrue(all(p['sourceUrl'].startswith('https://') for p in points))

    def test_pdf_requires_matching_period_and_aggregate_and_skips_prefectures(self):
        names = ['だいこん', 'キャベツ', 'はくさい', 'トマト', 'にんじん', 'かぶ', 'ごぼう', 'なす']
        text = '主要卸売市場計 数量 価格(円/kg) 令和４年１０月 下 旬\n'
        text += '\n'.join(f'{name} 100.5 {80+i} 95.0 100.0 100.0 100.0\n千 葉 10.5 999' for i, name in enumerate(names))
        document = MagicMock()
        document.__enter__.return_value.pages = [MagicMock()]
        document.__enter__.return_value.pages[0].extract_text.return_value = text
        with patch('pdfplumber.open', return_value=document):
            values = parse_produce_pdf(b'%PDF-test', names, (2022, 10, 3))
            self.assertEqual(values['だいこん'], 80)
            self.assertNotIn('千葉', values)
            with self.assertRaisesRegex(ValueError, 'period mismatch'):
                parse_produce_pdf(b'%PDF-test', names, (2021, 10, 3))
            document.__enter__.return_value.pages[0].extract_text.return_value = text.replace('主要卸売市場計', '東京都中央卸売市場')
            with self.assertRaises(ValueError):
                parse_produce_pdf(b'%PDF-test', names, (2022, 10, 3))

    def test_no_network_for_cached_history_when_budget_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = MarketHistory(Path(directory)/'history.json')
            archive.put('produce', (2026, 10, 3), 'https://www.maff.go.jp/report', {'キャベツ': 100})
            obj = {'foods': [{'id': 'v', 'name': 'キャベツ', 'category': 'vegetable'}],
                   'prices': [{'foodId': 'v'}], 'metadata': {}}
            with patch('backfill_history.fetch', side_effect=AssertionError('Unexpected request')):
                result = backfill(obj, archive, limit=0)
            self.assertEqual(result['attempted'], 0)
            self.assertEqual(obj['prices'][0]['longHistory'][0]['price'], 100)


if __name__ == '__main__':
    unittest.main()
