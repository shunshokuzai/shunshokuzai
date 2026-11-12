"""Reproducible coverage and alternate-source diagnostics (no AI)."""
import io
import json
import urllib.error
from collections import Counter

from backfill_history import parse_produce_pdf
from market_history import MarketHistory
from update_data import DATA, fetch
from update_fish import INDEX, read_weekly, url_index


def main():
    obj = json.loads(DATA.read_text(encoding='utf-8'))
    archive = MarketHistory()
    for kind in ('produce', 'fish'):
        print('HISTORY COVERAGE', kind, json.dumps(Counter(r['stamp'][0] for r in archive.records(kind))))
    print('LONG CHART POINTS', sum(len(p.get('longHistory', [])) for p in obj['prices']))
    names = [f['name'] for f in obj['foods'] if f['category'] != 'fish']
    for suffix in ('pdf/22103s_syuyo.pdf', 'csv/22103s_syuyo.csv', 'csv/22103h_syuyo.csv'):
        url = 'https://www.maff.go.jp/j/tokei/syohi/shunbetu/2022/' + suffix
        try:
            raw = fetch(url, timeout=15)
            print('ALTERNATE SOURCE', url, 'bytes', len(raw))
            if raw.startswith(b'%PDF'):
                values = parse_produce_pdf(raw, names, (2022, 10, 3))
                print('VERIFIED 2022 PDF', json.dumps(values, ensure_ascii=False))
        except urllib.error.HTTPError as exc:
            print('ALTERNATE SOURCE', url, 'HTTP', exc.code)
        except Exception as exc:
            print('ALTERNATE SOURCE', url, type(exc).__name__, str(exc)[:160])
    failures = [key for key in archive.data.get('backfillFailures', {}) if key.startswith('fish:')]
    if failures:
        listing = url_index(fetch(INDEX).decode('utf-8', 'replace'))
        for key in failures[:2]:
            stamp = tuple(map(int, key.split(':')[1].split('-')))
            url = listing[stamp]
            raw = fetch(url, timeout=25)
            try:
                print('RECHECK FISH', stamp, len(read_weekly(raw, url)))
            except Exception as exc:
                print('RECHECK FISH FAILED', stamp, url, type(exc).__name__, str(exc)[:160])
                if raw.startswith(b'%PDF'):
                    import pdfplumber
                    with pdfplumber.open(io.BytesIO(raw)) as pdf:
                        print('TABLE DIAGNOSTIC', json.dumps((pdf.pages[0].extract_tables() or [])[:1], ensure_ascii=False)[:1800])
    assert all(p.get('sourceUrl', '').startswith('https://') for row in obj['prices'] for p in row.get('longHistory', []))


if __name__ == '__main__':
    main()
