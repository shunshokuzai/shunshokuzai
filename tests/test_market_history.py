import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from market_history import MarketHistory, apply_chart, atomic_text, valid_price
from update_data import update_live, official_csv_url, apply_prices
from update_fish import read_weekly, same_brand


class HistoryTests(unittest.TestCase):
    def test_same_period_correction_replaces_without_duplicate(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = MarketHistory(Path(directory) / 'history.json')
            for price in (100, 110):
                archive.put('produce', (2026, 10, 3), 'https://www.maff.go.jp/source.csv', {'キャベツ': price})
            archive.save()
            restored = MarketHistory(archive.path)
            self.assertEqual(len(restored.records('produce')), 1)
            self.assertEqual(restored.get('produce', (2026, 10, 3))['values']['キャベツ'], 110)

    def test_chart_crosses_year_boundary_and_has_source_for_each_point(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = MarketHistory(Path(directory) / 'history.json')
            for stamp in ((2026, 12, 3), (2027, 1, 1)):
                archive.put('produce', stamp, 'https://www.maff.go.jp/' + str(stamp), {'キャベツ': 100})
            row = {}
            apply_chart(row, archive.chart('produce', 'キャベツ', (2027, 1, 1), 12), 'produce')
            self.assertEqual(row['historyLabels'], ['2026年12月下旬', '2027年1月上旬'])
            self.assertEqual(len(row['historySources']), 2)

    def test_fish_chart_retains_each_weeks_actual_size(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = MarketHistory(Path(directory) / 'history.json')
            for stamp, weight in (((2026, 10, 4), .1), ((2026, 11, 1), .2)):
                archive.put('fish', stamp, 'https://www.shijou.metro.tokyo.lg.jp/report',
                            {'サンマ': {'price': 1000, 'pieceWeightKg': weight, 'pieceWeightSpec': str(weight)}})
            row = {}
            apply_chart(row, archive.chart('fish', 'サンマ', (2026, 11, 1), 8), 'fish')
            self.assertEqual(row['historyPieceWeights'], [.1, .2])
            self.assertEqual(row['history'], [1000, 1000])

    def test_nonfinite_values_never_enter_history(self):
        for value in (float('nan'), float('inf'), True, -1, 0):
            self.assertFalse(valid_price(value))

    def test_corrupt_archive_is_not_replaced_with_empty_history(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.json'
            path.write_text('{broken', encoding='utf-8')
            with self.assertRaises(json.JSONDecodeError):
                MarketHistory(path)
            self.assertEqual(path.read_text(encoding='utf-8'), '{broken')

    def test_atomic_replace_failure_preserves_previous_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            path.write_text('original', encoding='utf-8')
            with patch('market_history.os.replace', side_effect=OSError('disk unavailable')):
                with self.assertRaises(OSError):
                    atomic_text(path, 'replacement')
            self.assertEqual(path.read_text(encoding='utf-8'), 'original')

    def test_missing_indexes_fall_back_to_same_official_csv_series(self):
        # Synthetic unit-test CSVs. These values are never published as data.
        names = ['キャベツ', 'だいこん', 'はくさい', 'トマト', 'なす', 'にんじん', 'きゅうり', 'みかん']
        obj = {'foods': [{'id': str(i), 'name': n, 'category': 'vegetable'} for i, n in enumerate(names)],
               'prices': [], 'metadata': {}}
        stamp = (2026, 10, 3)
        def csv_blob(price):
            return ('主要卸売市場計\n品目,卸売価格(円/kg)\n' +
                    '\n'.join(f'{name},{price}' for name in names)).encode('utf-8')
        def index(year):
            if year != 2026:
                raise OSError('index not available')
            return {stamp: official_csv_url(stamp)}
        with tempfile.TemporaryDirectory() as directory:
            archive = MarketHistory(Path(directory) / 'history.json')
            with patch('update_data.page_csv_urls', side_effect=index), \
                 patch('update_data.fetch', side_effect=lambda url: csv_blob(80 if '/2026/' in url else 100)), \
                 patch('update_data.time.sleep'):
                update_live(obj, archive)
            row = obj['prices'][0]
            self.assertEqual(row['normalRatio'], 80)
            self.assertEqual(row['historicalYears'], [2021, 2022, 2023, 2024, 2025])
            self.assertEqual(row['yearAgoRatio'], 80)

    def test_new_period_clears_old_baseline_provenance(self):
        obj = {'foods': [{'id': 'v-1', 'name': 'キャベツ', 'category': 'vegetable'}],
               'prices': [{'foodId': 'v-1', 'historicalYears': [2023], 'historicalPrices': [10]}], 'metadata': {}}
        apply_prices(obj, {'キャベツ': 100}, {}, (2026, 11, 1), 'https://www.maff.go.jp/new.csv')
        self.assertEqual(obj['prices'][0]['historicalYears'], [])
        self.assertIsNone(obj['prices'][0]['normalRatio'])


class OfficialArchiveTests(unittest.TestCase):
    def test_shift_jis_archive_matches_published_primary_rows(self):
        # Source excerpt: Tokyo market 2023-11 week 1. The second row of アジ
        # has a different grade; it must not replace the primary quote.
        rows = [
            ['アジ', '44.0', '98', '↓', '89', '↓', '長崎', '中', '1,620', '659', '432', '117', '125', '160-200g/尾'],
            ['', '', '', '', '', '', '静岡', '中小', '756', '702', '648', '130', '157', '100-110g/尾'],
            ['サバ', '27.8', '133', '↑', '109', '↑', '岩手ほか', '－', '756', '421', '216', '95', '89', '7-10入/5kg'],
            ['イワシ', '7.1', '76', '↓', '111', '↑', '北海道ほか', '－', '1,620', '691', '324', '123', '122', '100-110g/尾'],
            ['サンマ', '19.5', '75', '↓', '57', '↓', '岩手', '生', '7,560', '1,102', '864', '95', '131', '110-130g/尾']]
        html = '<meta charset="shift_jis"><h1>水産物の週間市況 卸売価格</h1><table>' + ''.join(
            '<tr>' + ''.join('<td>' + cell + '</td>' for cell in row) + '</tr>' for row in rows) + '</table>'
        values = read_weekly(html.encode('cp932'), 'https://www.spt.metro.tokyo.lg.jp/shijou/torihiki/03/suisan/2023111.html')
        self.assertEqual({k: v['price'] for k, v in values.items()},
                         {'アジ': 659, 'サバ': 421, 'イワシ': 691, 'サンマ': 1102})

    def test_different_grades_are_excluded_from_baseline(self):
        self.assertFalse(same_brand({'brandLabel': '生'}, {'brandLabel': '解凍'}))
        self.assertFalse(same_brand({'brandLabel': '中'}, {'brandLabel': '中小'}))
        self.assertTrue(same_brand({'brandLabel': '中'}, {'brandLabel': '中'}))


if __name__ == '__main__':
    unittest.main()
