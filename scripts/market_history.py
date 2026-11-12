"""Source-linked market observations retained across automatic refreshes.

Only successfully parsed official observations belong here. Failed requests do
not erase earlier observations. A period, market series and food identify an
observation; repeated refreshes replace corrections rather than add duplicates.
"""
import json
import math
import os
import tempfile
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[1] / 'data' / 'market_history.json'


def atomic_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n',
                                         dir=path.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def valid_price(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and 0 < value < 150000)


def period_key(stamp):
    return '-'.join(map(str, stamp))


class MarketHistory:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else DEFAULT_PATH
        self.data = (json.loads(self.path.read_text(encoding='utf-8'))
                     if self.path.exists() else {'version': 1, 'produce': {}, 'fish': {}})
        if self.data.get('version') != 1 or any(
                not isinstance(self.data.get(kind), dict) for kind in ('produce', 'fish')):
            raise ValueError('Unrecognized history archive; refusing to overwrite it')

    def get(self, kind, stamp):
        return self.data[kind].get(period_key(stamp))

    def put(self, kind, stamp, source, values):
        if not source.startswith('https://') or not values:
            raise ValueError('History requires a source and observed values')
        for value in values.values():
            price = value.get('price') if isinstance(value, dict) else value
            if not valid_price(price):
                raise ValueError('History contains an invalid price')
        self.data[kind][period_key(stamp)] = {
            'stamp': list(stamp), 'sourceUrl': source, 'values': values}

    def save(self):
        atomic_text(self.path, json.dumps(self.data, ensure_ascii=False, indent=2,
                                         allow_nan=False) + '\n')

    def records(self, kind, end=None):
        rows = self.data[kind].values()
        return sorted((r for r in rows if end is None or tuple(r['stamp']) <= tuple(end)),
                      key=lambda r: tuple(r['stamp']))

    def chart(self, kind, name, end, limit):
        result = []
        for record in self.records(kind, end):
            value = record['values'].get(name)
            price = value.get('price') if isinstance(value, dict) else value
            if not valid_price(price):
                continue
            result.append({'stamp': record['stamp'], 'price': price,
                           'sourceUrl': record['sourceUrl'],
                           'pieceWeightKg': value.get('pieceWeightKg') if isinstance(value, dict) else None,
                           'pieceWeightSpec': value.get('pieceWeightSpec') if isinstance(value, dict) else None})
        return result[-limit:]


def apply_chart(row, points, kind):
    if not points:
        return
    row['history'] = [p['price'] for p in points]
    row['historyPeriods'] = [p['stamp'] for p in points]
    row['historySources'] = [p['sourceUrl'] for p in points]
    row['historyLabels'] = [
        f'{p["stamp"][0]}年{p["stamp"][1]}月' +
        (('上旬', '中旬', '下旬')[p['stamp'][2] - 1] if kind == 'produce'
         else f'第{p["stamp"][2]}週') for p in points]
    if kind == 'fish':
        row['historyPieceWeights'] = [p['pieceWeightKg'] for p in points]
        row['historyPieceSpecs'] = [p['pieceWeightSpec'] for p in points]
