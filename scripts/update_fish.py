#!/usr/bin/env python3
"""東京都・豊洲市場の週間市況PDFから、生鮮魚の公表中値を抽出。

公開原表がレイアウト変更した場合には更新せず現状のスナップショットを保存。
各年の同月・同週の中値だけを比較する参考平年比で、月またぎで以前の
比較値を使い回すことは禁止する。需給・サイズ・産地差の注意書きを保持。
"""
import argparse
import datetime as dt
import io
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from update_data import BASE, DATA, fetch, now_iso, save
from market_history import MarketHistory, apply_chart, valid_price

INDEX='https://www.shijou.metro.tokyo.lg.jp/torihiki/week/suisan'
# Refers only to a particular product specification within the official PDF.
FISH_ROWS={'サンマ':'サンマ','サバ':'サバ','アジ':'アジ','イワシ':'イワシ',
 'カツオ':'カツオ','マグロ':'マグロ','カレイ':'カレイ','キンメダイ':'キンメダイ',
 'スルメイカ':'スルメイカ','カキ':'ムキカキ','ハマチ':'ハマチ'}


def norm(s):
    return re.sub(r'[\s\u3000ー\-・．.]+','',str(s or '')).replace('ｽﾙﾒｲｶ','スルメイカ')


def url_index(html):
    """Read year/month/week heading and link context from the official index."""
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser')
    year=month=None; found={}
    for tag in soup.find_all(['h1','h2','h3','h4','h5','h6','a']):
        label=tag.get_text(' ',strip=True).translate(str.maketrans('０１２３４５６７８９','0123456789'))
        if tag.name!='a':
            match=re.search(r'(20\d{2})\s*年',label)
            if match:
                year=int(match.group(1));month=None;continue
            match=re.fullmatch(r'\s*(\d{1,2})\s*月\s*',label)
            if match and year:month=int(match.group(1))
            continue
        match=re.search(r'第\s*(\d)\s*週',label)
        if match and year and month:
            link=urljoin(INDEX,tag.get('href') or '')
            if urlparse(link).netloc.endswith('tokyo.lg.jp') and link.startswith('https://'):
                found[(year,month,int(match.group(1)))]=link
    return found


def number(s):
    s=norm(s).replace(',','').replace('，','')
    try:
        value=int(s)
        return value if 10 <= value <= 150000 else None
    except (TypeError,ValueError):return None


def parse_piece_size(size,food):
    """Parse market sizes to an approximate body-weight per piece.

    Never infer from species alone. Values are approximate midpoints and are not
    a per-piece market quotation. Incomplete source => no converted price.
    """
    raw=str(size or '').strip().replace('～','-').replace('−','-').replace('–','-')
    raw=raw.replace('㎏','kg').replace('Ｋｇ','kg').replace('ｇ','g').replace('Ｇ','g')
    raw=re.sub(r'\s+','',raw).lower()
    if food=='カキ':return None
    unit='杯' if food=='スルメイカ' else '尾'
    # x-y fish or squid per 5kg box, average box count = midpoint
    m=re.search(r'(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(?:入|尾|杯)/5kg',raw)
    if m:
        lo,hi=map(float,m.groups())
        if lo>0 and hi>=lo and hi<=200:return round(5/((lo+hi)/2),8)
    # individual mass, grams or kilograms
    m=re.search(r'(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(g|kg)/(?:尾|杯)',raw)
    if m:
        lo,hi,scale=m.groups();lo=float(lo);hi=float(hi)
        if lo>0 and hi>=lo:return round((lo+hi)/2/(1000 if scale=='g' else 1),8)
    m=re.search(r'(\d+(?:\.\d+)?)(g|kg)/(?:尾|杯)',raw)
    if m:
        value,scale=m.groups();value=float(value)
        if value>0:return round(value/(1000 if scale=='g' else 1),8)
    # In some market reports the entire column means 'main size', so /尾 is omitted.
    m=re.search(r'(?<![\d.])(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)(g|kg)(?!/5kg)',raw)
    if m:
        lo,hi,scale=m.groups();lo=float(lo);hi=float(hi)
        if lo>0 and hi>=lo:return round((lo+hi)/2/(1000 if scale=='g' else 1),8)
    m=re.fullmatch(r'(?:約)?(\d+(?:\.\d+)?)(g|kg)',raw)
    if m:
        val,scale=m.groups();return round(float(val)/(1000 if scale=='g' else 1),8)
    return None


def parse_rows(tables):
    """Return market middle price for the FIRST product row of each fish kind.

    Standard market PDF has 14 columns, with high/middle/low at 8/9/10.
    A nonmatching layout is rejected, not guessed from surrounding numbers.
    """
    found={}
    for table in tables:
        for row in table:
            if not row or len(row)<14:continue
            label=norm(row[0]); mid=number(row[9]); high=number(row[8]); low=number(row[10])
            if not mid or not high or not low or not (low<=mid<=high):continue
            for food,item in FISH_ROWS.items():
                if food in found:continue
                if label==norm(item):
                    # Do not confuse frozen/thawed/foreign secondary rows with the first (fresh) row.
                    found[food]={'price':mid,'yearAgoRatio':number(row[12]),'previousRatio':number(row[11]),
                                 'brandLabel':norm(row[7]),
                                 'brandDetail':re.sub(r'\s+',' ',str(row[6] or '')+' '+str(row[7] or '')+'・'+str(row[13] or '')).strip(),
                                 'pieceWeightKg':parse_piece_size(row[13],food),
                                 'pieceWeightSpec':str(row[13] or '').strip()}
    return found


def read_pdf(blob):
    if not blob.startswith(b'%PDF'):raise ValueError('not a PDF document')
    import pdfplumber
    with pdfplumber.open(io.BytesIO(blob)) as pdf:
        if len(pdf.pages)<1:raise ValueError('empty PDF')
        tables=[]
        for page in pdf.pages[:2]:
            text=page.extract_text() or ''
            if '市況' not in text and '卸売' not in text:continue
            tables.extend(page.extract_tables(table_settings={'vertical_strategy':'lines','horizontal_strategy':'lines'}) or [])
        fish=parse_rows(tables)
    if len(fish)<4:raise ValueError('PDF table schema unverified (less than 4 fish parsed)')
    return fish


def read_weekly(blob,url):
    """Official source may be a PDF or an archived HTML table (older years)."""
    if blob.startswith(b'%PDF'):return read_pdf(blob)
    from bs4 import BeautifulSoup
    # Archived pages declare Shift_JIS. Decoding them as UTF-8 first destroys
    # fish names and makes an otherwise valid 14-column table unrecognizable.
    soup=BeautifulSoup(blob,'html.parser')
    # Some archive HTML pages link to an original weekly PDF.
    for a in soup.find_all('a',href=True):
        href=urljoin(url,a['href']);u=urlparse(href)
        if (u.scheme=='https' and u.netloc.endswith('tokyo.lg.jp')
            and (u.path.lower().endswith('.pdf') or '/documents/d/' in u.path)):
            try:return read_pdf(fetch(href,timeout=35))
            except Exception:pass
    tables=[]
    for table in soup.find_all('table'):
        rows=[]
        for tr in table.find_all('tr'):
            cells=tr.find_all(['td','th'],recursive=False)
            if len(cells)>=14:
                rows.append([cell.get_text(' ',strip=True) for cell in cells])
        if rows:tables.append(rows)
    if '卸売価格' not in soup.get_text():
        raise ValueError('Archived page has no market price table heading')
    fish=parse_rows(tables)
    if len(fish)<4:raise ValueError('archived HTML is not a recognizable 14-column market table')
    return fish

def compute_ratio(price,historical):
    vals=[x for x in historical if valid_price(x)]
    if len(vals)<3:return None,None
    mean=round(sum(vals)/len(vals),1)
    return mean,round(price/mean*100,1)


def apply_fish(obj,latest,annual,stamp,link,hist_links,weekly):
    food_by_name={f['name']:f for f in obj['foods'] if f['category']=='fish'}
    old={p['foodId']:p for p in obj['prices']}; updated=0
    for name,datum in latest.items():
        f=food_by_name.get(name)
        if not f:continue
        past=annual.get(name,{})
        years=sorted(y for y in past if stamp[0]-5<=y<stamp[0] and valid_price(past[y]))
        base,ratio=compute_ratio(datum['price'],[past[y] for y in years]);old_row=old.get(f['id'],{})
        if not (base and ratio):
            # never retain last month's baseline in a newly observed week
            years=[]
        periods={(stamp[0],stamp[1],k) if isinstance(k,int) else k:v for k,v in weekly.items()}
        ordered=sorted(k for k in periods if k<=stamp and name in periods[k])
        vals=[periods[week][name]['price'] for week in ordered]
        labels=[f'{s[0]}年{s[1]}月第{s[2]}週' for s in ordered]
        old[f['id']]={**old_row,'foodId':f['id'],'price':datum['price'],'unit':'円/kg',
            'normalPrice':base,'normalRatio':ratio,'yearAgoRatio':datum.get('yearAgoRatio'),
            'previousRatio':datum.get('previousRatio'), 'historicalSampleCount':len(years),
            'history':vals,'historyLabels':labels,'historicalYears':years,
            'historicalPrices':[past[y] for y in years],
            'historicalSources':[hist_links[y] for y in years],
            'sourceType':'東京都中央卸売市場 豊洲市場・水産物週間市況',
            'priceStatistic':'豊洲市場・中値（円/kg）','market':'豊洲市場',
            'sourceUrl':link,'period':f'{stamp[0]}年{stamp[1]}月第{stamp[2]}週',
            'publishedAt':None,'retrievedAt':dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date().isoformat(),
            'sample':False,'stale':False,'statisticalItem':name,'brandDetail':datum.get('brandDetail'),
            'pieceWeightKg':datum.get('pieceWeightKg'),
            'pieceWeightSpec':datum.get('pieceWeightSpec') or 'サイズ記載なし',
            'pieceWeightBasis':'市場公表サイズ帯からの代表重量による換算（実際の1尾単価ではありません）' if datum.get('pieceWeightKg') else '市場のサイズ情報がないため換算できません',
            'normalRatioBasis':f'{stamp[1]}月第{stamp[2]}週・過去{len(years)}年中値単純平均' if ratio else '比較年数不足',
            'note':'魚の参考平年比は東京都の公式指標ではありません。過去3年以上の同月・同週の中値を単純平均して比較（最大5年）。産地・魚体サイズ・銘柄等の年差があり厳密な同一品質比較ではありません。'}
        updated+=1
    if not updated:raise ValueError('No recognized fish to publish')
    updated_ids={food_by_name[n]['id'] for n in latest if n in food_by_name}
    for food_id,item in old.items():
        if food_id not in updated_ids and any(f['id']==food_id for f in food_by_name.values()):
            item['stale']=True;item['normalRatio']=None
    obj['prices']=list(old.values()); obj['metadata']['fishPriceCount']=updated
    obj['metadata']['fishPriceSourceUrl']=link;obj['metadata']['fishPriceObservationPeriod']=f'{stamp[0]}年{stamp[1]}月第{stamp[2]}週'
    obj['metadata']['lastFishCheckedAt']=now_iso();obj['metadata']['updatedAt']=now_iso()
    return updated


def same_brand(current, previous):
    # Compare the same fresh/product grade, never substitute frozen or thawed
    # secondary rows for a missing primary quote. Origin/size differences are
    # retained in each source-linked observation and disclosed in the app.
    return current.get('brandLabel') == previous.get('brandLabel')


def update_live(obj, archive=None):
    import bs4  # noqa - dependency checked by requirements.txt
    archive=archive if archive is not None else MarketHistory()
    listing=url_index(fetch(INDEX,timeout=25).decode('utf-8','replace'))
    today=dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
    this_year=[s for s in listing if today.year-1<=s[0]<=today.year and (s[0],s[1])<=(today.year,today.month)]
    if not this_year:raise ValueError('no this-year official weekly price links')
    stamp=max(this_year);link=listing[stamp];print('latest PDF',stamp,link)
    latest=read_weekly(fetch(link,timeout=35),link)
    archive.put('fish',stamp,link,latest)
    print('recognized fish',len(latest))
    weekly={stamp:latest}
    for period in sorted(s for s in listing if s<stamp)[-7:]:
        earlier=listing[period]
        try:
            cached=archive.get('fish',period)
            weekly[period]=cached['values'] if cached else read_weekly(fetch(earlier,timeout=35),earlier)
            archive.put('fish',period,earlier,weekly[period])
        except Exception as e:print('WARN recent graph',period,e,file=sys.stderr)
        time.sleep(.2)
    annual={name:{} for name in latest};hist_links={}
    for year in range(stamp[0]-5,stamp[0]):
        url=listing.get((year,stamp[1],stamp[2]))
        if not url:continue
        try:
            past_stamp=(year,stamp[1],stamp[2]);cached=archive.get('fish',past_stamp)
            old=cached['values'] if cached else read_weekly(fetch(url,timeout=35),url)
            archive.put('fish',past_stamp,url,old);hist_links[year]=url
            for name in latest:
                if name in old and same_brand(latest[name],old[name]):annual[name][year]=old[name]['price']
        except Exception as e:print('WARN historical fish',year,e,file=sys.stderr)
        time.sleep(.2)
    updated=apply_fish(obj,latest,annual,stamp,link,hist_links,weekly)
    by_id={p['foodId']:p for p in obj['prices']}
    for food in obj['foods']:
        if food['category']!='fish' or food['name'] not in latest:continue
        row=by_id[food['id']]
        apply_chart(row,archive.chart('fish',food['name'],stamp,8),'fish')
        row['historicalSpecs']=[archive.get('fish',(y,stamp[1],stamp[2]))['values'][food['name']].get('brandDetail') for y in row['historicalYears']]
    archive.save()
    obj['metadata']['fishReferenceRatioCount']=sum(p.get('normalRatio') is not None and not p.get('stale') for p in obj['prices'] if p['foodId'] in {f['id'] for f in obj['foods'] if f['category']=='fish'})
    obj['metadata']['fishRatioDisclaimer']='過去3～5年の同月・同週・同じ銘柄区分の豊洲市場中値の単純平均を基準とする参考平年比。年による主産地・サイズの差に注意。'
    return updated


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');args=parser.parse_args()
    if not args.live:print('No fish prices changed; use --live.');return
    obj=json.loads(DATA.read_text(encoding='utf-8'))
    count=update_live(obj);save(obj);print('Updated',count,'fish prices')

if __name__=='__main__':main()
