#!/usr/bin/env python3
"""MAFF 旬別青果価格CSVの取得・検証とJSON公開ファイルの生成。

初期時点で実データ取得テスト未完了。仕様不明なCSVを無理に解釈しない。
正しい列の確認ができなければ原則停止する（数値の捏造を防ぐ）。
"""
import argparse
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from market_history import MarketHistory, apply_chart, atomic_text, valid_price

BASE=Path(__file__).resolve().parents[1]
DATA=BASE/'data'/'seed.json'
USER_AGENT='ShunShokuzaiPrototype/0.1 (Public data prototype; respectful requests)'
CSV_RE=re.compile(r'/(\d{2})(\d{2})([123])h_syuyo\.csv$',re.I)
YEARS_BACK=5
ALIASES={'かんしょ':'さつまいも','ばれいしょ':'じゃがいも','みかん計':'みかん','りんご計':'りんご','かき計':'かき','ぶどう計':'ぶどう','日本なし':'なし','日本なし計':'なし','りんご計':'りんご','かき計':'かき','ぶどう計':'ぶどう','日本なし計':'なし','洋なし':'洋なし','かんしょ':'さつまいも','ばれいしょ':'じゃがいも','みずな':'水菜','こまつな':'小松菜','ねぎ':'長ねぎ','しゅんぎく':'春菊','セルリー':'セロリ','ちんげんさい':'チンゲンサイ','スイートコーン':'とうもろこし','生しいたけ':'しいたけ','えのきだけ':'えのきたけ','トマト':'トマト','だいこん':'だいこん','にんじん':'にんじん','ねぎ':'長ねぎ','さといも':'さといも','はくさい':'はくさい','キャベツ':'キャベツ'}

def now_iso():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def fetch(url,timeout=16):
    req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT,'Accept':'text/html,text/csv,application/octet-stream,*/*'})
    with urllib.request.urlopen(req,timeout=timeout) as r:
        data=r.read(2_000_000)
        if len(data)>1_999_000:raise ValueError('unexpectedly large file')
        return data

class Hrefs(HTMLParser):
    def __init__(self):super().__init__();self.hrefs=[]
    def handle_starttag(self,tag,attrs):
        if tag=='a':
            h=dict(attrs).get('href');
            if h:self.hrefs.append(h)

def page_csv_urls(year,html=None):
    base=f'https://www.maff.go.jp/j/tokei/syohi/shunbetu/{year}/hinmoku.html'
    body=html if html is not None else fetch(base).decode('utf-8','replace')
    parser=Hrefs();parser.feed(body);found={}
    for href in parser.hrefs:
        u=urllib.parse.urljoin(base,href);m=CSV_RE.search(urllib.parse.urlparse(u).path)
        if not m:continue
        y,mon,ten=map(int,m.groups());stamp=(2000+y,mon,ten)
        if stamp[0]!=year or not 1<=mon<=12:continue
        found[stamp]=u
    return found

def decode_csv(blob):
    for enc in ('utf-8-sig','cp932','shift_jis'):
        try:return blob.decode(enc)
        except UnicodeDecodeError:pass
    raise ValueError('unexpected CSV encoding')

def normalize(name):
    name=re.sub(r'[\s\u3000]+','',str(name))
    return ALIASES.get(name,name)

def number(value):
    value=str(value).strip().replace(',','').replace('，','').replace('円','')
    if value in ('','-','…','x','X','***'):return None
    try:
        n=float(value)
        return n if 0<n<100000 else None
    except (ValueError,TypeError):return None

def _ratio_verified_position(row, known):
    """Read the official MAFF *data* layout, even when headers are multi-row.

    Its main-market table has the sequence quantity(t), value(1,000 yen),
    price(yen/kg).  The quotient value/quantity must reproduce the price.
    A correctly named item PLUS this arithmetic invariant is required; do not
    infer a price from year-on-year percentages or an unrelated numeric column.
    """
    if not row:
        return None
    lead = [(i, normalize(cell)) for i, cell in enumerate(row[:5]) if str(cell).strip()]
    match = next(((i, name) for i, name in lead if name in known), None)
    if not match:
        return None
    name_i, name = match
    # Certain CSV exports have blank separator cells between the three values.
    # Restrict search to the leading six *numeric* cells, not the ratio columns.
    numbers = []
    for k in range(name_i + 1, min(len(row), name_i + 13)):
        raw = str(row[k]).strip().replace(',', '').replace('，', '')
        try:
            val = float(raw)
        except ValueError:
            continue
        if 0 < val < 10_000_000_000:
            numbers.append((k, val))
        if len(numbers) >= 6:
            break
    for triple in zip(numbers, numbers[1:], numbers[2:]):
        (_, quantity), (_, amount), (_, price) = triple
        if quantity <= 0 or amount <= quantity or not 10 <= price < 100_000:
            continue
        # MAFF table: t, thousand-yen, yen/kg.  Quantities rounded to
        # whole tonnes can introduce a modest discrepancy for tiny volumes.
        implied = amount / quantity
        if abs(implied - price) <= max(3.0, price * 0.035):
            return name, float(price)
    return None


def parse_csv(blob, food_names):
    """Parse MAFF main-market CSV with explicit or numerically verified layout.

    Older site parser only accepted a single row carrying both 品目 and 卸売価格;
    the official table uses merged/multiple header lines. Its real numeric
    table layout is validated against the MAFF publication definition.
    """
    rows = list(csv.reader(io.StringIO(decode_csv(blob))))
    known = set(food_names)
    out = {}
    for row in rows:
        result = _ratio_verified_position(row, known)
        if result:
            out[result[0]] = round(result[1], 1)
    # Fallback for explicitly labelled normalized CSV distributions (test and
    # optional alternative CSV formats): only if first strategy found none.
    if out:
        return out
    for i, row in enumerate(rows):
        h = [re.sub(r'[\s\u3000（）()]+', '', c) for c in row]
        names = [j for j, c in enumerate(h) if c in ('品目','野菜及び果実')]
        price = [j for j, c in enumerate(h) if ('卸売価格' in c and '比' not in c and '前年' not in c)]
        if not names or not price:
            continue
        ix, px = names[0], price[0]
        # Here the header itself explicitly verifies which column is price.
        for record in rows[i + 1:]:
            if max(ix, px) >= len(record):
                continue
            n = normalize(record[ix]); value = number(record[px])
            if n in known and value is not None:
                out[n] = round(value, 1)
        if out:
            break
    return out

def save(obj):
    text=json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)
    atomic_text(DATA,text+'\n')
    atomic_text(BASE/'data.js','window.SHUN_DATA = '+json.dumps(obj,ensure_ascii=False,separators=(',',':'),allow_nan=False)+';\n')

def apply_prices(obj,prices,history_by_name,stamp,source_url):
    """Publish observed prices even if the five-year baseline is unavailable.

    Existing price entries of other foods are kept. A ratio is computed only
    when at least three independent, comparable historical observations exist.
    A simple arithmetic mean is an *experimental* baseline, NOT a MAFF
    officially published average. Comparing nonmatching markets is prohibited.
    """
    foods={f['name']:f for f in obj['foods']}
    food_category={f['id']:f.get('category') for f in obj['foods']}
    old={p['foodId']:p for p in obj['prices']}
    changed=0
    for name,price in prices.items():
        if name not in foods: continue
        food=foods[name]
        hist=[float(x) for x in history_by_name.get(name,[]) if valid_price(x)]
        baseline=round(sum(hist)/len(hist),1) if len(hist)>=3 else None
        ratio=round(100*price/baseline,1) if baseline else None
        previous=old.get(food['id'],{})
        old[food['id']]={**previous,'foodId':food['id'],'price':round(price,1),'unit':'円/kg',
          'normalPrice':baseline,'normalRatio':ratio,'normalRatioBasis':f'過去{len(hist)}年の同月・同旬の単純平均' if ratio else '比較年数不足','previousRatio':None,
          'yearAgoRatio':None,'historicalYears':[],'historicalPrices':[],'historicalSources':[],
          'history':previous.get('history',[]), 'sourceType':'農林水産省 青果物卸売市場調査（旬別）',
          'sourceUrl':source_url,'period':f'{stamp[0]}年{stamp[1]}月 {("上旬","中旬","下旬")[stamp[2]-1]}',
          'publishedAt':None,'retrievedAt':dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat(),
          'sample':False,'market':'主要卸売市場計','priceStatistic':'主要卸売市場計・卸売平均価格（円/kg）','historicalSampleCount':len(hist),'stale':False,
          'note':'平年比は過去5年同旬の資料が3年分以上揃った場合の単純平均による参考値。農林水産省の公式平年比ではありません。市場構成等の差に注意。'}
        changed+=1
    if not changed:raise ValueError('No recognizable prices: keeping existing data')
    # Historical snapshot prices of foods not published this period must not be treated as current.
    for ident,oldrow in old.items():
        if ident not in {foods[name]['id'] for name in prices if name in foods} and food_category.get(ident) in ('vegetable','fruit'):
            oldrow['stale']=True
            oldrow['normalRatio']=None
    obj['prices']=list(old.values()); meta=obj['metadata']
    meta['priceStatus']='real_snapshot';meta['lastCheckedAt']=now_iso();meta['updatedAt']=now_iso()
    meta['priceObservationPeriod']=f'{stamp[0]}年{stamp[1]}月{("上旬","中旬","下旬")[stamp[2]-1]}'
    meta['priceSourceUrl']=source_url
    return changed

def official_csv_url(stamp):
    year,month,ten=stamp
    return f'https://www.maff.go.jp/j/tokei/syohi/shunbetu/{year}/csv/{year%100:02d}{month:02d}{ten}h_syuyo.csv'


def update_live(obj, archive=None):
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    archive=archive if archive is not None else MarketHistory()
    current_year=now.year; all_urls={}
    # The public index currently lists three calendar years. Older index pages
    # can disappear while their official CSV documents remain available.
    for year in range(current_year-2,current_year+1):
        try:
            url_map=page_csv_urls(year);all_urls.update(url_map)
            print('index',year,'files',len(url_map))
        except Exception as exc:print('WARN index',year,str(exc),file=sys.stderr)
        time.sleep(.3)
    candidates=sorted([k for k in all_urls if k[0]>=current_year-1 and k[1]<=12
                       and dt.date(k[0],k[1],(1,11,21)[k[2]-1])<=now.date()],reverse=True)
    if not candidates:raise ValueError('No recent official CSV links (check source page)')
    stamp=candidates[0];source=all_urls[stamp];print('Latest candidate',stamp,source)
    known=[f['name'] for f in obj['foods'] if f['category']!='fish']
    latest=parse_csv(fetch(source),known)
    if len(latest)<8:raise ValueError(f'CSV schema requires validation: parsed {len(latest)} known food prices; nothing published')
    archive.put('produce',stamp,source,latest)
    # Historical comparator: exact matching month and ten-day period for the previous 5 years.
    history_by_name={name:[] for name in latest}; comparison_detail={name:[] for name in latest}
    for year in range(stamp[0]-YEARS_BACK,stamp[0]):
        past_stamp=(year,stamp[1],stamp[2])
        link=all_urls.get(past_stamp) or official_csv_url(past_stamp)
        try:
            cached=archive.get('produce',past_stamp)
            if cached:
                past=cached['values'];link=cached['sourceUrl']
            else:
                raw=fetch(link)
                if '主要卸売市場計' not in re.sub(r'\s+','',decode_csv(raw)):
                    raise ValueError('Historical CSV does not identify the same market aggregate')
                past=parse_csv(raw,known)
                if len(past)<8:raise ValueError('Historical CSV schema unverified')
                archive.put('produce',past_stamp,link,past)
            for name in latest:
                if name in past:
                    history_by_name[name].append(past[name]);comparison_detail[name].append((year,past[name],link))
        except Exception as e:print('WARN historical data',year,str(e),file=sys.stderr)
        time.sleep(.25)
    changed=apply_prices(obj,latest,history_by_name,stamp,source)
    by_id={p['foodId']:p for p in obj['prices']};by_name={f['name']:f['id'] for f in obj['foods']}
    for name,pairs in comparison_detail.items():
        if name not in by_name:continue
        row=by_id[by_name[name]]
        row['historicalYears']=[x[0] for x in pairs]
        row['historicalPrices']=[x[1] for x in pairs]
        row['historicalSources']=[x[2] for x in pairs]
        if stamp[0]-1 in row['historicalYears']:
            prior=pairs[row['historicalYears'].index(stamp[0]-1)][1]
            row['yearAgoRatio']=round(100*row['price']/prior,1)
    # Chart up to twelve released ten-day periods (never synthetic).
    recent=sorted(k for k in all_urls if k<=stamp)[-12:]
    recent_data=[]
    for s in recent:
        if s==stamp: data=latest
        else:
            try:
                cached=archive.get('produce',s)
                data=cached['values'] if cached else parse_csv(fetch(all_urls[s]),known)
                if len(data)<8:raise ValueError('Recent CSV schema unverified')
                archive.put('produce',s,all_urls[s],data)
            except Exception as exc:
                print('WARN recent price graph',s,exc,file=sys.stderr);continue
        recent_data.append((s,data))
    for name,ident in by_name.items():
        if ident not in by_id or by_id[ident].get('stale'):continue
        points=archive.chart('produce',name,stamp,12)
        apply_chart(by_id[ident],points,'produce')
    archive.save()
    obj['metadata']['produceReferenceRatioCount']=sum(p.get('normalRatio') is not None and not p.get('stale') for p in obj['prices'] if p['foodId'] in {f['id'] for f in obj['foods'] if f['category']!='fish'})
    return changed

def ingest_csv(obj,path):
    """Validation path using files manually downloaded from MAFF (safe until schema verified)."""
    data=Path(path).read_bytes()
    known=[f['name'] for f in obj['foods'] if f['category']!='fish']
    prices=parse_csv(data,known)
    print('Recognized prices',len(prices))
    for k,v in list(prices.items())[:20]:print(k,v)
    if len(prices)<8:raise ValueError('No 8 unambiguous prices; CSV layout must be reviewed')
    return prices

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--live',action='store_true',help='Fetch current & historical official CSVs')
    ap.add_argument('--inspect-csv',help='Inspect a local CSV; do not modify published content')
    args=ap.parse_args();obj=json.loads(DATA.read_text(encoding='utf-8'))
    if args.inspect_csv:ingest_csv(obj,args.inspect_csv)
    elif args.live:
        result=update_live(obj);save(obj);print('Updated',result,'official prices; reference ratios:',obj['metadata'].get('produceReferenceRatioCount',0))
    else:print('Use --inspect-csv or --live. No data changed.')

if __name__=='__main__':main()
