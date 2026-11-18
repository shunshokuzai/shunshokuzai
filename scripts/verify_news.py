"""Read-only checks of actual news uses and cause provenance, no API calls."""
import json
from pathlib import Path
from news_sources import build_ledger,load_state,canonical
ROOT=Path(__file__).resolve().parents[1]
obj=json.loads((ROOT/'data/seed.json').read_text(encoding='utf-8'))
ledger=build_ledger(obj,load_state());foods={f['id']:f for f in obj['foods']};topics={t['id']:t for t in obj['topics']}
used=[r for r in ledger['articles'] if r['status']=='used'];categories=set();seen=set()
for r in used:
 assert canonical(r['url']) not in seen;seen.add(canonical(r['url']))
 assert r['publisher'] and r['publishedAt'] and r['uses'] and r['checks']
 for u in r['uses']:
  t=topics[u['topicId']];assert t['sourceType']=='news' and t['newsArticleId']==r['id'] and t['foodId']==u['foodId']
  assert canonical(t['sources'][0]['url'])==canonical(r['url']) and len(t['sourceExcerpt'])<=25
  assert t.get('scope') and t.get('observedPeriod') and t.get('causeAssessment')
  c=t['causeAssessment'];assert c['status'] in ('documented','inference','source_hypothesis','unconfirmed')
  if c['status'] in ('inference','source_hypothesis'):assert '推測' in c['text']
  categories.add(foods[t['foodId']]['category'])
# During this development, both requested categories must have actual uses.
assert len(used)>=3 and {'fruit','fish'}.issubset(categories), 'News sources were not successfully acquired for both requested categories'
print('NEWS USES VERIFIED',json.dumps({'usedArticles':len(used),'foods':len({f for r in used for f in r['foodIds']}),'categories':sorted(categories),'articles':[{'publisher':r['publisher'],'title':r['title'],'foods':[foods[f]['name'] for f in r['foodIds']],'publishedAt':r['publishedAt']} for r in used],'held':len(ledger['articles'])-len(used)},ensure_ascii=False),flush=True)
