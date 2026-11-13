import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from market_history import MarketHistory
from update_data import cache_produce
from verify_consistency import verify


class ConsistencyTests(unittest.TestCase):
    def test_values_sources_and_reference_years_must_match_the_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            archive=MarketHistory(Path(directory)/'history.json')
            for year in range(2023,2027):
                cache_produce(archive,(year,10,3),f'https://www.maff.go.jp/{year}',{'キャベツ':100})
            obj={'foods':[{'id':'v','name':'キャベツ','category':'vegetable'}],
                 'prices':[{'foodId':'v','price':100,'sourceUrl':'https://www.maff.go.jp/2026',
                            'longHistory':[{'period':[2026,10,3],'price':100,'sourceUrl':'https://www.maff.go.jp/2026'}],
                            'normalRatio':100,'normalPrice':100,'historicalYears':[2023,2024,2025],
                            'historicalPrices':[100,100,100],
                            'historicalSources':[f'https://www.maff.go.jp/{year}' for year in range(2023,2026)]}]}
            self.assertEqual(verify(obj,archive),1)
            altered=copy.deepcopy(obj);altered['prices'][0]['longHistory'][0]['price']=200
            with self.assertRaisesRegex(AssertionError,'History price mismatch'):verify(altered,archive)
            altered=copy.deepcopy(obj);altered['prices'][0]['historicalYears'][0]=2020
            with self.assertRaisesRegex(AssertionError,'Out-of-range'):verify(altered,archive)
            altered=copy.deepcopy(obj);altered['prices'][0]['normalRatio']=80
            with self.assertRaisesRegex(AssertionError,'ratio mismatch'):verify(altered,archive)


if __name__=='__main__':unittest.main()
