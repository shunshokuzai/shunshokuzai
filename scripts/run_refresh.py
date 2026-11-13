#!/usr/bin/env python3
"""Daily pipeline: run independently, keep previous values if remote sources fail.

The public seed JSON stores update result and timestamps to make stale/failure
states visible. Never writes secrets or raw API responses to publishable data.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from update_data import BASE,DATA,now_iso,save


def run_step(script,env=None):
    try:
        r=subprocess.run([sys.executable,str(BASE/'scripts'/script),'--live'],cwd=BASE,env=env,check=False,timeout=600)
    except subprocess.TimeoutExpired:
        print('ERROR update step timed out:',script,file=sys.stderr)
        return 'error'
    return 'ok' if r.returncode==0 else 'error'


def run_pipeline(today=None,ai_key=None,force_gemini=False):
    jst=dt.timezone(dt.timedelta(hours=9))
    local=today or dt.datetime.now(jst)
    status={}
    status['vegetableFruit']=run_step('update_data.py')
    status['fish']=run_step('update_fish.py')
    status['history']=run_step('backfill_history.py')
    daily_history=run_step('estat_history.py')
    if daily_history=='error':status['history']='error'
    scheduled=force_gemini or local.weekday() in (1,3,5)  # Tue/Thu/Sat, manual verification override
    key=ai_key if ai_key is not None else os.getenv('GEMINI_API_KEY','')
    if scheduled:
        env=os.environ.copy()
        if key:env['GEMINI_API_KEY']=key
        if not key:env['SOURCES_ONLY']='true'
        status['topics']=run_step('update_topics.py',env)
        saved=json.loads(DATA.read_text(encoding='utf-8'))['metadata']
        status['gemini']=('api_key_missing' if not key else
                          saved.get('topicGeminiStateLastRun','error') if status['topics']=='ok' else 'error')
    else:
        status['topics']='not_scheduled';status['gemini']='not_scheduled'
    obj=json.loads(DATA.read_text(encoding='utf-8'))
    meta=obj['metadata']
    meta['version']='0.10.0'
    meta['lastAutomaticCheckAt']=now_iso()
    meta['autoRefreshStatus']=status
    meta['autoRefreshConfigured']=True
    if status['vegetableFruit']=='ok':meta['lastVegetableFruitSuccessAt']=now_iso()
    if status['fish']=='ok':meta['lastFishSuccessAt']=now_iso()
    if status['gemini']=='ok':meta['lastGeminiSuccessAt']=now_iso()
    if status.get('topics')=='ok':meta['lastTopicsSuccessAt']=now_iso()
    foods={f['id']:f for f in obj['foods']}
    details={}
    for name,is_fish in (('vegetableFruit',False),('fish',True)):
        prices=[p for p in obj['prices'] if (foods[p['foodId']]['category']=='fish')==is_fish and not p.get('stale')]
        details[name]={'status':status[name],'checkedAt':now_iso(),'activePriceCount':len(prices),
                       'referenceRatioCount':sum(p.get('normalRatio') is not None for p in prices),
                       'chartPointCount':sum(len(p.get('history',[])) for p in prices)}
    details['topics']={'status':status.get('topics'),'checkedAt':now_iso(),
                      'sourceItemCount':meta.get('topicSourceCountLastRun',0),
                      'addedOrUpdatedCount':meta.get('topicAddedLastRun',0),
                      'sourceFailureCount':len(meta.get('topicSourceErrorsLastRun',[])),
                      'aiState':status['gemini'],'aiRequestsToday':meta.get('aiRequestBudget',{}).get('attempted',0)}
    details['history']={'status':status['history'],'checkedAt':now_iso(),
                        **meta.get('historyBackfillLastRun',{}),
                        'dailyFallback':meta.get('estatHistoryLastRun',{})}
    meta['lastStepResults']=details
    meta['updateHistory']=(meta.get('updateHistory',[])+[{'checkedAt':now_iso(),'steps':details}])[-20:]
    save(obj)
    print('UPDATE STATUS',json.dumps(status,ensure_ascii=False))
    return status


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');ap.add_argument('--force-gemini',action='store_true',help='Run a Gemini test even outside Tue/Thu/Sat');args=ap.parse_args()
    if not args.live:print('No refresh requested; add --live.');return
    results=run_pipeline(force_gemini=args.force_gemini or os.getenv('FORCE_GEMINI','').lower()=='true')
    if any(s=='error' for s in results.values()):
        print('WARNING: Some sources failed; old snapshots preserved. Check logs.',file=sys.stderr)

if __name__=='__main__':main()
