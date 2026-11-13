"""Read-only audit of unmapped official commodity names and missing prices."""
import csv
import io
import json

from market_history import MarketHistory
from update_data import DATA, decode_csv, fetch, normalize, parse_csv, _ratio_verified_position


def main():
    obj = json.loads(DATA.read_text(encoding='utf-8'))
    known = {f['name'] for f in obj['foods'] if f['category'] != 'fish'}
    latest = MarketHistory().records('produce')[-1]
    raw = fetch(latest['sourceUrl'])
    rows = list(csv.reader(io.StringIO(decode_csv(raw))))
    print('OFFICIAL CSV HEADERS', json.dumps(rows[:6],ensure_ascii=False))
    matches={}
    for row in rows:
        if row and normalize(row[0]) in known:matches.setdefault(normalize(row[0]),[]).append(row[:5])
    print('DUPLICATE OFFICIAL LABELS',json.dumps({k:v for k,v in matches.items() if len(v)>1},ensure_ascii=False))
    unmapped = []
    for row in rows:
        labels = {normalize(c) for c in row[:5] if c.strip()}
        result = _ratio_verified_position(row, labels)
        if result and result[0] not in known:
            unmapped.append({'officialItem': result[0], 'price': result[1], 'leadingCells': row[:9]})
    print('UNMAPPED OFFICIAL ITEMS', json.dumps(unmapped, ensure_ascii=False))
    print('LOW VOLUME ROWS', json.dumps([r for r in rows if any(normalize(c) in ('ふき','洋なし','西洋なし','アボカド','キウイフルーツ') for c in r[:5])], ensure_ascii=False))
    try:print('CURRENT VERIFIED COUNT', len(parse_csv(raw, known)))
    except ValueError as exc:print('CURRENT PRICE SCHEMA CONFLICT',str(exc))


if __name__ == '__main__':
    main()
