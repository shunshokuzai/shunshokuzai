"""Run the price updaters on a development branch, without any AI API calls."""
import copy
import json

from update_data import DATA, save, update_live as produce
from update_fish import update_live as fish


def main():
    obj = json.loads(DATA.read_text(encoding='utf-8'))
    report = {}
    for name, updater in (('produce', produce), ('fish', fish)):
        candidate = copy.deepcopy(obj)
        try:
            count = updater(candidate)
            obj = candidate
            ids = {f['id'] for f in obj['foods'] if (f['category'] == 'fish') == (name == 'fish')}
            prices = [p for p in obj['prices'] if p['foodId'] in ids and not p.get('stale')]
            report[name] = {'status': 'ok', 'updated': count,
                            'ratios': sum(p.get('normalRatio') is not None for p in prices),
                            'chartPoints': sum(len(p.get('history', [])) for p in prices),
                            'maxChartPoints': max((len(p.get('history', [])) for p in prices), default=0)}
        except Exception as error:
            report[name] = {'status': 'error', 'error': str(error)}
    save(obj)
    print('LIVE PRICE VALIDATION', json.dumps(report, ensure_ascii=False), flush=True)
    if any(r['status'] == 'error' for r in report.values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
