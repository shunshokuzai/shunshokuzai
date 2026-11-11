#!/usr/bin/env python3
"""Gemini Search Grounding connector. Disabled without --live and API key.

Only publishes search-grounded excerpts with at least one URL. Does not
claim independent fact-checking. Respect quota: max requests configured by
MAX_AI_REQUESTS and only runs when explicitly requested with --live.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from update_data import BASE, DATA, now_iso, save

BASE_API='https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'

def grounded_result(name,key,model,year,timeout=45):
    prompt=(f'今日時点の{year}年の日本国内の「{name}」について、直近45日以内に発表された'
        '生育・出荷・収穫・漁獲・品質の動向を、一次資料（自治体、農水省、漁協、産地団体）優先で調べてください。'
        '確認できる個別の動向がなければ必ず「新しい公表資料を確認できません」と明記してください。'
        '100〜150文字程度の日本語で、中立的にまとめてください。数量や増減の数字、年号を推測で補わないでください。'
        '推測と確認された事実は明確に分けてください。')
    req=urllib.request.Request(BASE_API.format(model=model),data=json.dumps({'contents':[{'parts':[{'text':prompt}]}],
        'tools':[{'google_search':{}}],'generationConfig':{'temperature':0.1,'maxOutputTokens':450}}).encode('utf-8'),
        headers={'Content-Type':'application/json','x-goog-api-key':key},method='POST')
    with urllib.request.urlopen(req,timeout=timeout) as res:raw=json.load(res)
    candidates=raw.get('candidates') or []
    if not candidates:return None
    candidate=candidates[0]
    text=''.join(part.get('text','') for part in candidate.get('content',{}).get('parts',[]) if isinstance(part,dict))
    text=re.sub(r'\s+',' ',text).strip()
    grounding=candidate.get('groundingMetadata') or {}
    sources=[]
    for entry in grounding.get('groundingChunks',[]):
        obj=entry.get('web') or {}
        uri=obj.get('uri','')
        if uri.startswith('https://') and uri not in [x['url'] for x in sources]:
            sources.append({'url':uri,'name':obj.get('title') or uri.split('/')[2],'publishedAt':None})
    # Without grounding URLs, do not publish any alleged new fact.
    if len(text)<24 or not sources or '新しい公表資料を確認できません' in text:return None
    if len(text)>200:text=text[:197]+'…' # body length guard, never use to assert source verification
    return {'summary':text,'sources':sources[:6]}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true');ap.add_argument('--model',default=os.getenv('GEMINI_MODEL','gemini-2.5-flash-lite'))
    args=ap.parse_args()
    if not args.live:
        print('AI connector is disabled. Add --live and an API key for a real test.');return
    key=os.environ.get('GEMINI_API_KEY','')
    if not key:
        print('GEMINI_API_KEY missing. No AI request was sent.');return
    maxreq=min(max(int(os.getenv('MAX_AI_REQUESTS','6')),0),10)
    if maxreq<=0:print('MAX_AI_REQUESTS=0. Skipped.');return
    obj=json.loads(DATA.read_text(encoding='utf-8'))
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    chosen=[f for f in obj['foods'] if today.month in f['seasonMonths']]
    priority=['サンマ','くり','みかん','かき','キャベツ','りんご','サバ','さつまいも','れんこん']
    chosen.sort(key=lambda f:(priority.index(f['name']) if f['name'] in priority else 999,f['name']))
    # Rotate through seasonal foods across weekly runs instead of always querying
    # the same first six foods.
    cursor_key=f'{today.year}-{today.month:02d}'
    if obj['metadata'].get('topicCursorMonth')!=cursor_key:
        obj['metadata']['topicCursor']=0
        obj['metadata']['topicCursorMonth']=cursor_key
    start=int(obj['metadata'].get('topicCursor',0))%max(len(chosen),1)
    batch=[chosen[(start+i)%len(chosen)] for i in range(min(maxreq,len(chosen)))]
    topics=obj['topics'];changed=0;attempted=0
    for f in batch:
        attempted+=1
        try:res=grounded_result(f['name'],key,args.model,today.year)
        except Exception as exc:
            print('WARN search',f['name'],str(exc),file=sys.stderr);continue
        if res is None:
            print('No supported recent information',f['name']);continue
        old=next((t for t in topics if t['id']=='latest-'+f['id']),None)
        if old and old['summary']==res['summary']:
            print('unchanged',f['name']);continue
        new={'id':'latest-'+f['id'],'foodId':f['id'],'title':f['name']+'の今年の動向',
             'summary':res['summary'],'kind':'ai_grounded','verified':False,'yearSpecific':True,
             'sources':res['sources'],'publishedAt':None,'observedPeriod':None,
             'aiGenerated':True,'tag':'AI要約（出典あり・未検証）','retrievedAt':now_iso()}
        topics=[t for t in topics if t['id']!=new['id']];topics.insert(0,new);changed+=1
        print('Grounded sources',f['name'],len(res['sources']))
    if attempted:
        obj['metadata']['topicCursor']=(start+attempted)%max(len(chosen),1)
    if changed:
        obj['topics']=topics;obj['metadata']['topicsStatus']='partial_live';obj['metadata']['lastTopicRetrievedAt']=now_iso();obj['metadata']['updatedAt']=now_iso();save(obj)
        print('Published',changed,'new source-linked AI summaries (not independently verified)')
    elif attempted:
        obj['metadata']['lastTopicAttemptAt']=now_iso()
        save(obj)
        print('No new summaries; moved cursor for next search run.')
    else: print('No candidates. Dataset preserved.')

if __name__=='__main__':main()
