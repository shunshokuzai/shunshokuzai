"""Bounded, resumable official price backfill. No AI requests or interpolation."""
import argparse
import datetime as dt
import io
import json
import re
import time
import unicodedata
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

from market_history import MarketHistory, valid_price
from update_data import DATA, decode_csv, fetch, normalize, official_csv_url, parse_csv, save
from update_fish import INDEX, read_weekly, url_index


def parse_produce_pdf(blob, names, stamp):
    """Read only named aggregate rows, never the following prefecture rows.

    The s_syuyo publication explicitly labels quantity(t), price(yen/kg),
    and major wholesale markets total. Unlike h_syuyo it has no amount column.
    """
    import pdfplumber
    if not blob.startswith(b'%PDF'):
        raise ValueError('Expected an official PDF')
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        text = unicodedata.normalize('NFKC', '\n'.join(p.extract_text() or '' for p in pdf.pages))
    compact = re.sub(r'\s+', '', text)
    period = f'令和{stamp[0]-2018}年{stamp[1]}月' + ('上', '中', '下')[stamp[2]-1]
    if ('主要卸売市場計' not in compact or '円/kg' not in compact
            or period not in compact or '数量' not in compact):
        raise ValueError('PDF market, unit or observation period mismatch')
    result = {}
    for line in text.splitlines():
        match = re.match(r'^(.+?)\s+([\d,]+(?:\.\d+)?)\s+([\d,]+)(?:\s|$)', line.strip())
        if not match:
            continue
        label, quantity, price = match.groups()
        name = normalize(label)
        value = float(price.replace(',', ''))
        if name not in names or float(quantity.replace(',', '')) <= 0 or not valid_price(value):
            continue
        if name in result and result[name] != value:
            raise ValueError('Conflicting duplicate aggregate rows')
        result[name] = value
    if len(result) < 8:
        raise ValueError('Insufficient verified aggregate price rows')
    return result


def produce_observation(stamp, names):
    # The 2021/2022 h CSV endpoints are withdrawn, while the official s PDF
    # remains available. Keep the same national market aggregate and unit.
    if stamp[0] >= 2023:
        url = official_csv_url(stamp)
        raw = fetch(url, timeout=20)
        if '主要卸売市場計' not in re.sub(r'\s+', '', decode_csv(raw)):
            raise ValueError('CSV aggregate mismatch')
        values = parse_csv(raw, names)
        if len(values) < 8:
            raise ValueError('Unrecognized aggregate CSV')
        return url, values
    year, month, ten = stamp
    url = f'https://www.maff.go.jp/j/tokei/syohi/shunbetu/{year}/pdf/{year%100:02}{month:02}{ten}s_syuyo.pdf'
    return url, parse_produce_pdf(fetch(url, timeout=25), names, stamp)


def attach_long_history(obj, archive):
    foods = {f['id']: f for f in obj['foods']}
    for row in obj['prices']:
        food = foods[row['foodId']]
        kind = 'fish' if food['category'] == 'fish' else 'produce'
        records = archive.records(kind)
        if not records:
            continue
        end = tuple(records[-1]['stamp'])
        start = (end[0]-5, 1, 1)
        current = next((r['values'][food['name']] for r in reversed(records)
                        if food['name'] in r['values']), None)
        brand = current.get('brandLabel') if isinstance(current, dict) else None
        points = []
        for record in records:
            stamp = record['stamp']
            if tuple(stamp) < start:
                continue
            value = record['values'].get(food['name'])
            price = value.get('price') if isinstance(value, dict) else value
            if not valid_price(price):
                continue
            if kind == 'fish' and (brand is None or value.get('brandLabel') != brand):
                continue
            points.append({'period': stamp, 'price': price, 'sourceUrl': record['sourceUrl'],
                           **({'spec': value.get('brandDetail'),
                               'weightKg': value.get('pieceWeightKg')} if kind == 'fish' else {})})
        row['longHistory'] = points
        row['longHistoryRange'] = [start[0], end[0]]
        row['longHistoryFrequency'] = 'weekly' if kind == 'fish' else 'ten_day'
    obj['metadata']['longHistoryUpdatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def backfill(obj, archive, limit=24, seconds=420):
    """At most limit reports/run, two workers, failed periods retried in 7 days."""
    if limit <= 0:
        attach_long_history(obj, archive)
        return {'attempted': 0, 'succeeded': 0, 'failed': 0}
    today = dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    names = [f['name'] for f in obj['foods'] if f['category'] != 'fish']
    failures = archive.data.setdefault('backfillFailures', {})
    candidates = []
    for kind in ('produce', 'fish'):
        records = archive.records(kind)
        if not records:
            continue
        end = tuple(records[-1]['stamp'])
        if kind == 'fish':
            listing = url_index(fetch(INDEX, timeout=25).decode('utf-8', 'replace'))
        else:
            listing = {(year, month, ten): None for year in range(end[0]-5, end[0]+1)
                       for month in range(1, 13) for ten in (1, 2, 3)}
        pending = []
        for stamp, url in listing.items():
            if stamp[0] < end[0]-5 or stamp > end or archive.get(kind, stamp):
                continue
            key = kind + ':' + '-'.join(map(str, stamp))
            prior = failures.get(key, {})
            if prior.get('retryAfter', '') > today.isoformat():
                continue
            pending.append((kind, stamp, url, key))
        # Balance years: each run adds coverage in every year, rather than
        # filling the newest year while leaving the older years empty.
        pending.sort(key=lambda r: (-r[1][1], -r[1][2], -r[1][0]))
        candidates.append(pending)
    tasks = []
    while any(candidates) and len(tasks) < limit:
        for pending in candidates:
            if pending and len(tasks) < limit:
                tasks.append(pending.pop(0))
    started = time.monotonic()
    result = {'attempted': 0, 'succeeded': 0, 'failed': 0}

    def retrieve(task):
        kind, stamp, url, key = task
        if time.monotonic()-started > seconds:
            return task, None, None, 'time_budget'
        try:
            if kind == 'produce':
                url, values = produce_observation(stamp, names)
            else:
                values = read_weekly(fetch(url, timeout=30), url)
            return task, url, values, None
        except Exception as exc:
            error = f'HTTP {exc.code}' if isinstance(exc, urllib.error.HTTPError) else type(exc).__name__
            return task, url, None, error

    with ThreadPoolExecutor(max_workers=2) as executor:
        for future in as_completed([executor.submit(retrieve, task) for task in tasks]):
            (kind, stamp, _, key), url, values, error = future.result()
            if error == 'time_budget':
                continue
            result['attempted'] += 1
            if error:
                result['failed'] += 1
                failures[key] = {'checkedAt': today.isoformat(), 'error': error,
                                 'sourceUrl': url,
                                 'retryAfter': (today+dt.timedelta(days=7)).isoformat()}
            else:
                archive.put(kind, stamp, url, values)
                failures.pop(key, None)
                result['succeeded'] += 1
            # Checkpoint each completed report; an interrupted run loses no
            # successfully parsed observations and never touches the seed.
            archive.save()
    attach_long_history(obj, archive)
    result['cachedReports'] = {kind: len(archive.records(kind)) for kind in ('produce', 'fish')}
    obj['metadata']['historyBackfillLastRun'] = result
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--limit', type=int, default=24)
    args = parser.parse_args()
    if not args.live:
        return
    obj = json.loads(DATA.read_text(encoding='utf-8'))
    result = backfill(obj, MarketHistory(), limit=min(max(args.limit, 0), 600))
    save(obj)
    print('HISTORY BACKFILL', json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
