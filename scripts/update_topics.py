#!/usr/bin/env python3
"""Source-first, free-tier Gemini summarization of government food reports.

No Google Search grounding is used: it is not part of the free tier for Gemini
3.1 Flash-Lite. The source is fetched independently from an official page,
then its exact text is supplied to the model; source URLs are NEVER invented by
Gemini. When the model is unavailable, source extracts remain available and AI
failure is reported accurately instead of claiming success.
"""
import argparse
import calendar
import datetime as dt
import json
import hashlib
import os
import re
import sys
import urllib.error
import urllib.request
import unicodedata

from bs4 import BeautifulSoup
from update_data import BASE, DATA, fetch, now_iso, normalize, save

API = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
MODEL = 'gemini-3.1-flash-lite'
MAFF_DOMAIN = 'www.maff.go.jp'
SUMMARY_VERSION = 6


def recent_forecast_url(today, getter=fetch):
    """Look for MAFF's late-previous-month press release, without a search API.

    The issuance date is not guaranteed to be the last calendar day.
    Only the canonical MAFF path is accepted; responses must include the
    expected report heading. Old/future months never masquerade as 'latest'.
    """
    start = today.replace(day=1) - dt.timedelta(days=1)
    for back in range(7):
        date = start - dt.timedelta(days=back)
        path = f'https://{MAFF_DOMAIN}/j/press/nousan/engei/{date:%y%m%d}.html'
        try:
            body = getter(path, timeout=15)
        except Exception:
            continue
        soup = BeautifulSoup(body.decode('utf-8', 'replace'), 'html.parser')
        title = soup.title.get_text(' ', strip=True) if soup.title else ''
        if '野菜の生育状況及び価格見通し' in title and ('令和' in soup.get_text(' ', strip=True) or '年' in title):
            return path, body, date.isoformat()
    raise ValueError('MAFF vegetable forecast publication not found for the current month')


def forecast_items(html, foods, url, published):
    """Extract only explicitly named rows in MAFF's monthly vegetable table."""
    soup = BeautifulSoup(html.decode('utf-8', 'replace'), 'html.parser')
    allowed = {f['name']: f for f in foods if f['category'] == 'vegetable'}
    rows = []
    for tr in soup.find_all('tr'):
        cells = tr.find_all(['th', 'td'], recursive=False)
        if len(cells) < 3:
            continue
        texts = [re.sub(r'\s+', ' ', c.get_text(' ', strip=True)).strip() for c in cells]
        # MAFF table sometimes has an initial rowspan cell or a fourth price
        # outlook column. The food name must be an entire first cell.
        name = normalize(texts[0].split('（')[0].split('(')[0])
        if name not in allowed:
            continue
        details = texts[-2] if len(texts) >= 4 else texts[1]
        outlook = texts[-1]
        if len(details) < 28 or not any(k in details for k in ('出荷','生育','収穫','入荷','産地','小玉','作業','肥大')):
            continue
        excerpt = f'出荷・生育について：{details[:1000]}\n価格の見通し：{outlook[:240]}'
        target = dt.date.fromisoformat(published).replace(day=1) + dt.timedelta(days=32)
        title = soup.title.get_text(' ', strip=True).split('：')[0] if soup.title else '野菜の生育状況及び価格見通し'
        rows.append({'food': allowed[name], 'url': url, 'publishedAt': published,
                     'excerpt': excerpt, 'outlook': outlook,
                     'sourceTitle': title, 'observedPeriod': f'{target.year}年{target.month}月の見通し',
                     'sourceFamily': 'maff-vegetable', 'isForecast': True,
                     'periodStart': f'{target.year}-{target.month:02}-01',
                     'periodEnd': f'{target.year}-{target.month:02}-{calendar.monthrange(target.year,target.month)[1]}',
                     'scope': '資料に記載の主産地（産地・卸売会社等への聞き取り）',
                     'reportType': '生育・出荷状況と今後の見通し',
                     'limitations': '聞き取りに基づく見通しで、確定した収穫実績ではありません。資料中の「平年並み」は90～110%を目安とし、アプリの価格判定（85～115%）とは基準が異なります。',
                     'evidenceSections': [{'label': '生育・出荷', 'text': details[:1000]},
                                          {'label': '価格の見通し', 'text': outlook[:240]}]})
    return list({x['food']['id']: x for x in rows}.values())


def extract_summary(excerpt):
    """Fallback excerpt, explicitly attributed to the official publication."""
    text = excerpt.replace('出荷・生育について：', '').replace('\n価格の見通し：', '。価格見通し：')
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'。+', '。', text).strip()
    # Avoid chopping the middle of a claim when possible.
    if len(text) > 165:
        p = text.rfind('。', 80, 165)
        text = text[:p+1] if p >= 80 else text[:162]+'…'
    return text


def validate_summary(text, excerpt):
    """Reject detectable unsupported numbers and changes in certainty.

    This is a limited automatic check, not a claim of semantic verification.
    Full source excerpts remain visible next to every generated summary.
    """
    normalized = lambda value: unicodedata.normalize('NFKC', value).replace(',', '')
    numeric = lambda value: set(re.findall(r'\d+(?:\.\d+)?', normalized(value)))
    if not numeric(text).issubset(numeric(excerpt)):
        raise ValueError('Gemini summary introduced numbers absent from the source')
    # A single sentence can contain an observed growth condition followed by
    # a price forecast. Check clauses, not the certainty of the whole sentence.
    outlook = '見通し|見込|予想|予測|予定|可能性'
    for metric in ('出荷量', '出荷数量', '入荷量', '価格'):
        claims = [s for s in re.split('[。\n]', text) if metric in s]
        evidence = [s for s in re.split('[。、\n]', excerpt) if metric in s]
        if evidence and all(re.search(outlook, s) for s in evidence):
            if any(not re.search(outlook, s) for s in claims):
                raise ValueError('Gemini summary converted an outlook into an observed result')
    return text


def ai_summarize(excerpt, key, model=MODEL, timeout=40):
    """Summarize an observed public source. No tools, paid-only search or URLs."""
    prompt = ('以下は公的機関が実際に公表した文章です。記載されている事実だけを使い、'
        '食材の生育・入荷・市場動向について100～150字程度で要約してください。'
        '主産地、生育または入荷の現状、変動理由、今後の見通しのうち原文にある項目を優先する。'
        '市場への入荷量を全国の収穫量・漁獲量と言い換えない。来遊量の予報を確定した漁獲量と言い換えない。前週比と前年比を混同しない。'
        '見通しを確定した結果のように書かない。資料にない数値や地域、原因を加えない。'
        '余計な挨拶・注釈・Markdownは付けない。\n\n' + excerpt)
    payload = {'contents':[{'parts':[{'text':prompt}]}],
               'generationConfig':{'temperature':0.1,'maxOutputTokens':450}}
    req = urllib.request.Request(API.format(model=model),
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type':'application/json','x-goog-api-key':key}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result = json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f'Gemini API HTTP {e.code}') from e

    parts = (result.get('candidates') or [{}])[0].get('content',{}).get('parts',[])
    text = re.sub(r'\s+',' ',''.join(p.get('text','') for p in parts if isinstance(p,dict))).strip()
    if not 28 <= len(text) <= 240:
        raise ValueError('Gemini returned no usable text')
    return validate_summary(text, excerpt)


def requests_used_today(metadata,today):
    budget=metadata.get('aiRequestBudget',{})
    if budget:
        return max(0,int(budget.get('attempted',0))) if budget.get('date')==today.isoformat() else 0
    try:
        previous=dt.datetime.fromisoformat(metadata.get('lastTopicAttemptAt','')).astimezone(dt.timezone(dt.timedelta(hours=9))).date()
    except (ValueError,TypeError):
        return 0
    return (metadata.get('topicGeminiSucceededLastRun',0)+metadata.get('topicGeminiFailedLastRun',0)
            if previous==today else 0)


def merge_report(obj, items, key, model, request_limit, on_attempt=None):
    """Publish each source item, try AI for up to the explicit free-tier budget."""
    topics = list(obj['topics'])
    attempts = 0; success = 0; changed = 0; failures = 0
    blocked = False
    attempted_foods=set()
    for item in items:
        f = item['food']; ident = f"{item.get('reportKey') or 'forecast-'+item['publishedAt']}-{f['id']}"
        if item.get('requireAi') and not key and not (next((t for t in topics if t['id']==ident and t.get('aiGenerated')),None)):
            continue
        fingerprint = hashlib.sha256(item['excerpt'].encode('utf-8')).hexdigest()
        old = next((t for t in topics if t['id'] == ident), None)
        if old and 'sourceFingerprint' not in old:
            # Migrate already published summaries without spending the daily
            # budget to regenerate the same report or downgrading them.
            old['sourceFingerprint'] = fingerprint
        # An official excerpt can be upgraded into an AI summary on a later
        # run, without producing duplicate articles for the same report.
        unchanged = old and old.get('sourceFingerprint') == fingerprint
        skip_ai = unchanged and (old.get('aiGenerated') or not key or blocked or attempts >= request_limit)
        metadata_same = old and all(old.get(k)==item.get(k) for k in ('sourceUpdatedAt','seasonalRecord','reportYear'))
        if skip_ai and old.get('summaryVersion') == SUMMARY_VERSION and metadata_same:
            continue
        summary = old['summary'] if unchanged and old.get('aiGenerated') else (item.get('summaryExcerpt') or extract_summary(item['excerpt']))
        generated = bool(unchanged and old.get('aiGenerated'))
        if generated:
            try:
                validate_summary(summary, item['excerpt'])
            except ValueError:
                summary = extract_summary(item['excerpt']); generated = False
        provider = old.get('summaryProvider','Gemini') if generated and old else 'Gemini'
        if item.get('preparedSummary'):
            summary = validate_summary(item['preparedSummary'], item['excerpt'])
            generated = True; provider = item['summaryProvider']
        if not item.get('preparedSummary') and not skip_ai and key and not blocked and attempts < request_limit and f['id'] not in attempted_foods:
            attempted_foods.add(f['id'])
            obj['metadata'].setdefault('aiFoodLastAttemptAt',{})[f['id']]=now_iso()
            if on_attempt:on_attempt()
            attempts += 1
            try:
                summary = ai_summarize(item['excerpt'], key, model)
                success += 1; generated = True; provider = 'Gemini'
            except Exception as exc:
                failures += 1
                blocked = 'HTTP 429' in str(exc) or 'HTTP 403' in str(exc)
                # Never include API keys, raw response bodies or request URLs.
                print('WARN Gemini summarize', f['name'], type(exc).__name__,
                      str(exc)[:110] if not isinstance(exc,urllib.error.HTTPError) else f'HTTP {exc.code}',
                      file=sys.stderr)
        if item.get('requireAi') and not generated:
            continue
        new = {
            'id':ident, 'foodId':f['id'],
            'title':item.get('title') or f"{f['name']}：{item.get('observedPeriod') or '生育・出荷の公的情報'}",
            'summary':summary, 'kind':'ai_source_summary' if generated else item.get('kind','official_excerpt'),
            'verified':not generated, 'yearSpecific':True,
            'sources':[{'name':item.get('sourceName','農林水産省・野菜の生育状況及び価格見通し'),
                        'title':item.get('sourceTitle','野菜の生育状況及び価格見通し'),
                        'url':item['url'],'publishedAt':item['publishedAt']}, *item.get('extraSources',[])],
            'publishedAt':item['publishedAt'], 'observedPeriod':item.get('observedPeriod') or (
                f'{(dt.date.fromisoformat(item["publishedAt"]).replace(day=1)+dt.timedelta(days=32)).month}月の見通し'
                if item.get('publishedAt') else '資料参照（対象期間未確認）'),
            'sourceFingerprint':fingerprint,
            'sourceFamily': item.get('sourceFamily'), 'isForecast': item.get('isForecast',False),
            'periodStart': item.get('periodStart'), 'periodEnd': item.get('periodEnd'),
            'sourceUpdatedAt':item.get('sourceUpdatedAt'),'seasonalRecord':item.get('seasonalRecord'),
            'reportYear':item.get('reportYear'),
            'summaryVersion': SUMMARY_VERSION,
            'sourceExcerpt': item.get('publicExcerpt',item['excerpt']),
            'scope': item.get('scope', '資料に記載の対象地域'),
            'reportType': item.get('reportType', '公的資料の記述'),
            'evidenceSections': item.get('evidenceSections', [{'label': '原文の該当箇所', 'text': item['excerpt']}]),
            'limitations': item.get('limitations', '品目全体の全国的な状況を保証する資料ではありません。'),
            'automaticChecks': ['数値の原文照合', '見通しの断定化チェック'] if generated else item.get('nonAiChecks',['原文抜粋']),
            'aiGenerated':generated, 'summaryProvider':provider if generated else None,
            'tag':provider+'要約（一次資料から・独立検証前）' if generated else item.get('nonAiTag','公的原文を短く抜粋（Gemini未使用）'),
            'retrievedAt':now_iso(),
        }
        topics = [t for t in topics if t['id'] != ident]
        topics.insert(0, new);changed += 1
    if changed:
        obj['topics'] = topics
        obj['metadata']['topicsStatus'] = 'source_first'
        obj['metadata']['lastTopicRetrievedAt'] = now_iso()
        obj['metadata']['updatedAt'] = now_iso()
    obj['metadata']['topicSourceCountLastRun'] = len(items)
    obj['metadata']['topicAddedLastRun'] = changed
    obj['metadata']['topicGeminiSucceededLastRun'] = success
    obj['metadata']['topicGeminiFailedLastRun'] = failures
    return {'sourceItems':len(items),'added':changed,'aiSuccess':success,'aiFailed':failures,'aiAttempted':attempts}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--live',action='store_true')
    ap.add_argument('--model', default=os.getenv('GEMINI_MODEL',MODEL))
    args=ap.parse_args()
    if not args.live:
        print('No network activity without --live.');return
    if args.model!=MODEL:raise ValueError('Only the configured free-tier model is enabled')
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    key=os.getenv('GEMINI_API_KEY','')
    limit=min(max(int(os.getenv('MAX_AI_REQUESTS','6')),0),6)
    obj=json.loads(DATA.read_text(encoding='utf-8'))
    used=requests_used_today(obj['metadata'],today)
    limit=min(limit,max(0,6-used))
    if os.getenv('SOURCES_ONLY','').lower()=='true':key=''
    items=[];source_errors=[]
    try:
        url,html,published=recent_forecast_url(today)
        items.extend(forecast_items(html,obj['foods'],url,published))
    except Exception as error:
        source_errors.append('MAFF forecast: '+type(error).__name__)
    from official_topics import weekly_items
    for category in ('fish','fruit'):
        try:items.extend(weekly_items(obj['foods'],category,today))
        except Exception as error:source_errors.append(category+': '+type(error).__name__)
    from fish_forecasts import forecast_items as fish_forecast_items
    try:
        forecasts,errors=fish_forecast_items(obj['foods'],today)
        items.extend(forecasts);source_errors.extend(errors)
    except Exception as error:source_errors.append('FRA forecasts: '+type(error).__name__)
    from additional_fish_topics import additional_items
    extra,errors=additional_items(obj['foods'],today)
    items.extend(extra);source_errors.extend(errors)
    from regional_topics import regional_items
    regional,errors=regional_items(obj['foods'],today)
    items.extend(regional);source_errors.extend(errors)
    from topic_discovery import collect,publish_monitor,load_state
    discovered,errors=collect(obj,today,limit=min(24,max(0,int(os.getenv('MAX_DISCOVERY_ARTICLES','8')))))
    items.extend(discovered);source_errors.extend(errors)
    if not items and not obj['metadata'].get('topicDiscoveryLastRun',{}).get('checkedIndexes'):
        raise ValueError('All topic sources unavailable; previous topics retained')
    # New foods precede already-covered foods, and existing AI texts are reused.
    covered={t['foodId'] for t in obj['topics'] if t.get('yearSpecific')}
    last_ai=obj['metadata'].get('aiFoodLastAttemptAt',{})
    items.sort(key=lambda item:(not item.get('requireAi',False),item['food']['id'] in covered,last_ai.get(item['food']['id'],'')))
    reserved=0
    def reserve_attempt():
        nonlocal reserved
        reserved+=1
        obj['metadata']['aiRequestBudget']={'date':today.isoformat(),'attempted':used+reserved,'dailyLimit':6}
        # Reserve before the request so cancellation cannot silently restore
        # already used quota on the next run.
        save(obj)
    result=merge_report(obj,items,key,args.model,limit,on_attempt=reserve_attempt)
    publish_monitor(obj,load_state(),today)
    obj['metadata']['aiRequestBudget']={'date':today.isoformat(),'attempted':used+result['aiAttempted'],'dailyLimit':6}
    obj['metadata']['topicSourceErrorsLastRun']=source_errors
    print('SOURCE WARNINGS',json.dumps(source_errors,ensure_ascii=False))
    obj['metadata']['topicGeminiStateLastRun']=('ok' if result['aiSuccess'] else 'error' if result['aiFailed']
        else 'sources_only' if not key else 'daily_limit' if used>=6 else 'no_new_sources')
    obj['metadata']['lastTopicAttemptAt']=now_iso()
    save(obj)
    print('SOURCE-FIRST TOPICS',json.dumps(result,ensure_ascii=False))
    # 'ok' must not be used when all attempted Gemini requests failed.
    if result['aiAttempted'] and not result['aiSuccess']:
        raise RuntimeError('Gemini text summarization unavailable; official source excerpts retained. Check model and free-tier quota.')
    if not key and os.getenv('SOURCES_ONLY','').lower()!='true':
        raise RuntimeError('GEMINI_API_KEY missing; official source excerpts retained.')

if __name__ == '__main__':
    main()
