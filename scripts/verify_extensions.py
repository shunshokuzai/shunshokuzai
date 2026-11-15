"""Verify the public retail, source-allocation and recipe datasets without network."""
import json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'data/seed.json').read_text(encoding='utf-8'))
ids={f['id'] for f in data['foods']};retail=data['retail'];rows=retail['records']
assert len(rows)>1000 and len(retail['regions'])>=50,'Regional retail observations missing'
for r in rows:
 assert r['foodId'] in ids and isinstance(r['price'],(int,float)) and math.isfinite(r['price']) and r['price']>0
 assert r['unit'] and r['specification'] and r['observationEnd'] and r['sourceUrl'].startswith('https://')
 assert r['taxIncluded'] is True
plans=data['metadata']['foodSourcePlan']
assert set(plans)==ids,'Every food must expose a verified source plan or an explicit unconfirmed state'
assert sum(bool(p['regions']) for p in plans.values())>=35
assert {'茨城','熊本','愛媛'}.issubset({r['name'] for r in plans['f-069']['regions']})
for r in data['recipes']:
 assert len({i['foodId'] for i in r['ingredients']})>=2
 assert all(i['foodId'] in ids and i['grams']>=50 for i in r['ingredients'])
 assert len(r['steps'])>=3 and r['pantry']
regional=[t for t in data['topics'] if (t.get('sourceFamily') or '').startswith('regional-')]
assert regional,'New regional observations have not been validated'
print('EXTENSIONS VERIFIED',json.dumps({'retailRecords':len(rows),'retailFoods':len({r['foodId'] for r in rows}),'cities':len(retail['regions']),'sourcePlansWithEvidence':sum(bool(p['regions']) for p in plans.values()),'regionalReports':[{'title':t['title'],'scope':t.get('scope'),'summary':t['summary']} for t in regional],'recipes':len(data['recipes']),'sourcePlanningWarnings':data['metadata'].get('sourcePlanningWarnings')},ensure_ascii=False),flush=True)
