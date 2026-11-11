"""Offline check of the deployment files and synthetic data tests.

Never touches the Gemini API or the external market websites.
"""
import json
from pathlib import Path
base=Path(__file__).resolve().parents[1]
required=[base/'index.html',base/'app.js',base/'data.js',base/'styles.css',base/'data/seed.json',base/'.github/workflows/update.yml']
for f in required:
    assert f.is_file(), f'MISSING: {f.relative_to(base)}'
seed=json.loads((base/'data/seed.json').read_text(encoding='utf-8'))
assert len(seed.get('foods',[]))>=100
assert len(seed.get('topics',[]))>=20
assert len(seed.get('prices',[]))>=40
js=(base/'data.js').read_text(encoding='utf-8')
assert js.startswith('window.SHUN_DATA = ')
assert seed['foods'][0]['name'] in js
workflow=(base/'.github/workflows/update.yml').read_text(encoding='utf-8')
for s in ['workflow_dispatch:','scripts/run_refresh.py --live','upload-pages-artifact','deploy-pages','GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}']:
    assert s in workflow, f'MISSING IN WORKFLOW: {s}'
for filepath in (base/'app.js',base/'data.js',base/'index.html',base/'styles.css'):
    assert 'AIzaSy' not in filepath.read_text(encoding='utf-8'), f'POSSIBLE KEY IN {filepath.name}'
print('OK: 公開用ファイル・公開データ・GitHub Actions設定（オフライン検査）')
