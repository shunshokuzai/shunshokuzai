"""Verify the reported regressions with four actual official source pages, no AI.

This development audit also retains validated observations in the candidate
dataset. Routine discovery keeps updating the same stable report IDs later.
"""
import argparse,datetime as dt,json,time
from update_data import DATA,BASE,fetch,save
from update_topics import merge_report
from regional_discovery import parse_alic

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');args=ap.parse_args()
 if not args.live:return
 today=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
 # URLs below are verified 2026 documents, not guessed future publications.
 if today.year!=2026:
  print('2026 cause-source regression audit skipped outside its report year');return
 obj=json.loads(DATA.read_text(encoding='utf-8'))
 source=next(x for x in json.loads((BASE/'data/topic_catalog.json').read_text(encoding='utf-8'))['sources'] if x['id']=='alic-regions')
 probes=[('キャベツ','愛知','s01/p23.html','2026-10-21','documented'),('はくさい','長野','s10/p20.html','2026-10-16','documented'),('はくさい','茨城','s10/p08.html','2026-10-13','inference'),('長ねぎ','千葉','s09/p12.html','2026-11-06','documented')]
 result=[];items=[]
 for name,region,path,regression_date,expected in probes:
  food=next(f for f in obj['foods'] if f['name']==name);url='https://vegetan.alic.go.jp/trend/y2026/'+path
  old=next((t for t in obj['topics'] if t['foodId']==food['id'] and any(s['url']==url for s in t.get('sources',[]))),{})
  entry={'url':url,'title':name+'・'+region+'の生育調査','region':region,'foodIds':[food['id']],'fiscalYear':2026,'sourceUpdatedAt':old.get('sourceUpdatedAt')}
  print('CHECK CAUSE SOURCE',url,flush=True)
  for attempt in range(3):
   try:
    raw=fetch(url,timeout=20);break
   except OSError as error:
    print('CAUSE SOURCE RETRY',url,type(error).__name__,attempt+1,flush=True)
    if attempt==2:raise
    time.sleep(1+attempt)
  found,status=parse_alic(raw,entry,source,[{'foodId':food['id'],'name':name}],today)
  assert len(found)==1,(url,status)
  item=found[0];c=item['causeAssessment']
  if item['periodEnd']==regression_date:assert c['status']==expected,(url,c)
  assert len(item['publicExcerpt'])<=24
  items.extend(found);result.append({'food':name,'region':region,'observation':item['periodEnd'],'causeStatus':c['status'],'summary':item['summaryExcerpt'],'source':url})
 merge_report(obj,items,'','unused',0);save(obj)
 print('OFFICIAL CAUSES VERIFIED',json.dumps(result,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
