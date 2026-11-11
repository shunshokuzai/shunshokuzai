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

def parse_csv(blob,food_names):
    """Conservative parser: requires explicit field headers '品目' and '卸売価格'.

    Handles a 1-line header or a two-line header whose column names are
    shared between adjacent rows. If unverifiable, returns empty dict.
    """
    rows=list(csv.reader(io.StringIO(decode_csv(blob))))
    known=set(food_names);out={}
    for i,row in enumerate(rows):
        norm=[re.sub(r'\s+','',s) for s in row]
        namecols=[k for k,v in enumerate(norm) if ('品目' in v or '野菜及び果実' in v) and ('価格' not in v)]
        pricecols=[k for k,v in enumerate(norm) if '卸売価格' in v and ('比' not in v and '前年' not in v)]
        # A two-row header is merged only if indices unambiguously align.
        if namecols and not pricecols and i+1<len(rows):
            pricecols=[k for k,v in enumerate(rows[i+1]) if '卸売価格' in v and '比' not in v]
        if not namecols or not pricecols: continue
        # Official table may have two price columns: wholesale price itself
        # and the prior-year comparison. Use only the *first*, following
        # quantity and amount. Never read the last comparison column.
        priceidx=pricecols[0]
        header=' '.join(norm)
        preceding=' '.join(norm[max(0,priceidx-2):priceidx])
        if len(pricecols)>1 and not ('卸売数量' in header and '卸売価額' in header):
            continue
        nameidx=namecols[0]
        for data_row in rows[i+1:]:
            if max(nameidx,priceidx)>=len(data_row):continue
            name=normalize(data_row[nameidx])
            if name not in known:continue
            val=number(data_row[priceidx])
            if val is not None:out[name]=round(val,1)
        if out:return out
    return out

def save(obj):
    text=json.dumps(obj,ensure_ascii=False,indent=2)
    DATA.write_text(text+'\n',encoding='utf-8')
    (BASE/'data.js').write_text('window.SHUN_DATA = '+json.dumps(obj,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')

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
        hist=[float(x) for x in history_by_name.get(name,[]) if isinstance(x,(float,int)) and x>0]
        baseline=round(sum(hist)/len(hist),1) if len(hist)>=3 else None
        ratio=round(100*price/baseline,1) if baseline else None
        old[food['id']]={'foodId':food['id'],'price':round(price,1),'unit':'円/kg',
          'normalPrice':baseline,'normalRatio':ratio,'normalRatioBasis':f'過去{len(hist)}年の同月・同旬の単純平均' if ratio else '比較年数不足','previousRatio':None,
          'yearAgoRatio':None,'history':[], 'sourceType':'農林水産省 青果物卸売市場調査（旬別）',
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

def update_live(obj):
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    current_year=now.year; all_urls={}
    for year in range(current_year-YEARS_BACK,current_year+1):
        try:
            url_map=page_csv_urls(year);all_urls.update(url_map)
            print('index',year,'files',len(url_map))
        except Exception as exc:print('WARN index',year,str(exc),file=sys.stderr)
        time.sleep(.3)
    candidates=sorted([k for k in all_urls if k[0]==current_year and k[1]<=now.month],reverse=True)
    if not candidates:raise ValueError('No recent official CSV links (check source page)')
    stamp=candidates[0];source=all_urls[stamp];print('Latest candidate',stamp,source)
    known=[f['name'] for f in obj['foods'] if f['category']!='fish']
    latest=parse_csv(fetch(source),known)
    if len(latest)<8:raise ValueError(f'CSV schema requires validation: parsed {len(latest)} known food prices; nothing published')
    # Historical comparator: exact matching month and ten-day period for the previous 5 years.
    history_by_name={name:[] for name in latest}; comparison_detail={name:[] for name in latest}
    for year in range(current_year-YEARS_BACK,current_year):
        link=all_urls.get((year,stamp[1],stamp[2]));
        if not link:continue
        try:
            past=parse_csv(fetch(link),known)
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
        if row.get('normalPrice'):
            row['historicalYears']=[x[0] for x in pairs]
            row['historicalPrices']=[x[1] for x in pairs]
            row['historicalSources']=[x[2] for x in pairs]
    # Chart four most recently released ten-day periods of the same year (never synthetic).
    recent=sorted(k for k in all_urls if k[0]==stamp[0] and k<=stamp)[-4:]
    recent_data=[]
    for s in recent:
        if s==stamp: data=latest
        else:
            try:data=parse_csv(fetch(all_urls[s]),known)
            except Exception as exc:
                print('WARN recent price graph',s,exc,file=sys.stderr);continue
        recent_data.append((s,data))
    for name,ident in by_name.items():
        if ident not in by_id or by_id[ident].get('stale'):continue
        points=[(ss,v[name]) for ss,v in recent_data if name in v]
        if len(points)>=2:
            row=by_id[ident]
            row['history']=[val for _,val in points]
            row['historyLabels']=[f'{ss[1]}月{("上旬","中旬","下旬")[ss[2]-1]}' for ss,_ in points]
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
        result=update_live(obj);save(obj);print('Updated',result,'official prices (with 3+ comparable years)')
    else:print('Use --inspect-csv or --live. No data changed.')

if __name__=='__main__':main()
