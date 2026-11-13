import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from update_data import parse_csv, commodity_label


def blob(rows):
    return ('青果物卸売市場調査 主要卸売市場計\n品目,品目コード,数量(t),価額(千円),価格(円/kg)\n'+'\n'.join(rows)).encode('utf-8')


class ProduceSchemaTests(unittest.TestCase):
    def test_low_volume_rounding_intervals_keep_the_actual_published_price(self):
        # Official 2026-10 late-period row: tonnes are rounded independently.
        data=blob(['ふき,32300,4,1869,528,131,100,****,43'])
        self.assertEqual(parse_csv(data,['ふき']),{'ふき':528})
        self.assertEqual(parse_csv(blob(['ふき,32300,4,1869,1200']),['ふき']),{})

    def test_domestic_and_imported_fruit_never_substitute_for_each_other(self):
        rows=['キウイフルーツ,49300,85,57897,680','キウイフルーツ,50800,700,503662,720',
              'メロン計,47000,442,310598,703','メロン,50700,200,101400,507',
              '西洋なし,43499,752,297239,395']
        out=parse_csv(blob(rows),['キウイフルーツ','メロン','洋なし'])
        self.assertEqual(out,{'キウイフルーツ':720,'メロン':703,'洋なし':395})
        self.assertEqual(parse_csv(blob(rows[:1]),['キウイフルーツ']),{})
        self.assertEqual(parse_csv(blob(rows[3:4]),['メロン']),{})
        self.assertIn('輸入',commodity_label('キウイフルーツ'))

    def test_zero_rounded_tonnes_can_have_a_valid_low_volume_quote(self):
        self.assertEqual(parse_csv(blob(['ふき,32300,0,105,528']),['ふき']),{'ふき':528})

    def test_conflicting_rows_and_nonfinite_numbers_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_csv(blob(['キャベツ,31700,100,10000,100','キャベツ,31700,100,20000,200']),['キャベツ'])
        self.assertEqual(parse_csv(blob(['キャベツ,31700,100,10000,nan']),['キャベツ']),{})

    def test_legacy_five_digit_quantity_is_not_misread_as_a_commodity_code(self):
        self.assertEqual(parse_csv('品目,卸売数量,卸売価額,卸売価格\nキャベツ,35000,3500000,100'.encode(),['キャベツ']),{'キャベツ':100})


if __name__=='__main__':unittest.main()
