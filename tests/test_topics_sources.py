import sys
import datetime as dt
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from official_topics import commentary_items
from update_topics import merge_report, requests_used_today


class SourceTopicTests(unittest.TestCase):
    def test_daily_ai_budget_uses_japan_date_even_across_utc_midnight(self):
        metadata={'lastTopicAttemptAt':'2026-11-11T16:00:00+00:00',
                  'topicGeminiSucceededLastRun':6,'topicGeminiFailedLastRun':0}
        self.assertEqual(requests_used_today(metadata,dt.date(2026,11,12)),6)
        self.assertEqual(requests_used_today(metadata,dt.date(2026,11,13)),0)
        metadata['aiRequestBudget']={'date':'2026-11-12','attempted':6}
        self.assertEqual(requests_used_today(metadata,dt.date(2026,11,12)),6)

    def test_table_numbers_are_not_rewritten_as_supply_news(self):
        foods = [{'id': 'fish-1', 'name': 'サバ', 'category': 'fish'}]
        self.assertEqual(commentary_items('サバ 100 200 300', foods, 'fish',
                                         (2026, 11, 1), 'https://www.shijou.metro.tokyo.lg.jp/report'), [])

    def test_weekly_fruit_prose_and_fish_following_sentence_stay_separate(self):
        foods=[{'id':'a','name':'サバ','category':'fish'},{'id':'b','name':'イワシ','category':'fish'}]
        text='主要鮮魚別に見ると、サバは千葉主体に入荷。前週に比べ数量は27%増加、価格は0.5割安。イワシは鹿児島主体に入荷。前週に比べ数量は41%増加。'
        items=commentary_items(text,foods,'fish',(2026,11,1),'https://www.shijou.metro.tokyo.lg.jp/report')
        self.assertIn('27%',items[0]['excerpt'])
        self.assertNotIn('41%',items[0]['excerpt'])
        fruit=[{'id':'c','name':'みかん','category':'fruit'}]
        text='概況。品目別にみると、「みかん」の1日平均入荷量は、前週比26%の増加となった。'
        self.assertEqual(len(commentary_items(text,fruit,'fruit',(2026,11,1),'https://www.shijou.metro.tokyo.lg.jp/report')),1)

    def test_commentary_keeps_following_quantity_sentence(self):
        foods = [{'id': 'fish-1', 'name': 'サバ', 'category': 'fish'}]
        text = '主要鮮魚別に見ると、サバは岩手と宮城主体に入荷。数量は前週に比べ33%増加し、価格は0.5割安。'
        items = commentary_items(text, foods, 'fish', (2026, 11, 1),
                                 'https://www.shijou.metro.tokyo.lg.jp/report')
        self.assertEqual(len(items), 1)
        self.assertIn('33%', items[0]['excerpt'])
        self.assertIsNone(items[0]['publishedAt'])
        self.assertEqual(items[0]['observedPeriod'], '2026年11月第1週')

    def test_unchanged_verified_source_does_not_repeat_ai_request(self):
        obj = {'foods': [], 'topics': [], 'metadata': {}}
        item = {'food': {'id': 'v-1', 'name': 'キャベツ'}, 'url': 'https://www.maff.go.jp/source',
                'publishedAt': '2026-10-30', 'excerpt': 'キャベツは長雨で生育が遅れ、出荷量は平年を下回る見通し。'}
        with patch('update_topics.ai_summarize', return_value='キャベツは長雨の影響で生育が遅れており、出荷量は平年を下回る見通しとされる。') as mock:
            self.assertEqual(merge_report(obj, [item], 'test', 'test', 6)['aiAttempted'], 1)
            self.assertEqual(merge_report(obj, [item], 'test', 'test', 6)['aiAttempted'], 0)
            self.assertEqual(mock.call_count, 1)
            item['excerpt'] += '翌週は回復を見込む。'
            self.assertEqual(merge_report(obj, [item], 'test', 'test', 6)['aiAttempted'], 1)
            self.assertEqual(len(obj['topics']), 1)

    def test_rate_limit_stops_remaining_ai_requests_but_keeps_source_items(self):
        obj = {'foods': [], 'topics': [], 'metadata': {}}
        items = [{'food': {'id': str(i), 'name': 'キャベツ'}, 'url': 'https://www.maff.go.jp/source',
                  'publishedAt': '2026-10-30', 'excerpt': 'キャベツは長雨で生育が遅れ、出荷量は平年を下回る見通し。'} for i in range(3)]
        with patch('update_topics.ai_summarize', side_effect=RuntimeError('Gemini API HTTP 429')) as mock:
            result = merge_report(obj, items, 'test', 'test', 6)
        self.assertEqual(mock.call_count, 1)
        self.assertEqual(result['aiFailed'], 1)
        self.assertEqual(len(obj['topics']), 3)
        self.assertFalse(any(t['aiGenerated'] for t in obj['topics']))


if __name__ == '__main__':
    unittest.main()
