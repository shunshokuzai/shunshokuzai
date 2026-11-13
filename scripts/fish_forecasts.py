"""Source-grounded, sea-area-specific FRA forecasts. Never market-price news."""
import calendar
import datetime as dt
import io
import re
import unicodedata
import urllib.request
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from update_data import fetch, USER_AGENT

INDEX='https://www.fra.go.jp/shigen/fisheries_resources/forecast/gyokyouyoho_enngann_okiai.html'
FAMILIES={
    'pacific': ('太平洋いわし類', '太平洋沿岸域（資料に記載の対象海域）'),
    'tsushima': ('対馬暖流系', '東シナ海・日本海（対馬暖流系）'),
    'squid': ('太平洋スルメイカ', '太平洋・根室海峡～オホーツク海等（資料の対象海域）'),
    'buri': ('日本海中部ブリ', '日本海中部（新潟県～兵庫県）'),
}
SPECIES={'マイワシ':'イワシ','カタクチイワシ':'イワシ','ウルメイワシ':'イワシ',
         'マアジ':'アジ','マサバ':'サバ','ゴマサバ':'サバ','マサバ・ゴマサバ':'サバ',
         'スルメイカ':'スルメイカ','ブリ':'ブリ'}


def compact(text):return re.sub(r'\s+','',unicodedata.normalize('NFKC',text))


def official(url):
    parsed=urlparse(url)
    return parsed.scheme=='https' and parsed.hostname=='www.fra.go.jp'


def forecast_links(html,today):
    soup=BeautifulSoup(html,'html.parser');chosen={}
    for link in soup.find_all('a',href=True):
        text=compact(link.get_text());url=urljoin(INDEX,link['href'])
        date=re.search(r'/fri_(\d{8})_',url)
        if not official(url) or not date:continue
        published=dt.datetime.strptime(date.group(1),'%Y%m%d').date()
        if published>today or (today-published).days>240:continue
        for family,(needle,_) in FAMILIES.items():
            if needle in text and (family not in chosen or published>chosen[family][0]):
                chosen[family]=(published,url)
    return chosen


def target_period(text):
    text=compact(text)
    match=re.search(r'今回の予報は[、,]?(\d{4})年(\d{1,2})月から(?:(\d{4})年)?(\d{1,2})月まで',text)
    if not match:raise ValueError('Forecast target period was not explicitly stated')
    year,month,endyear,endmonth=match.groups();year=int(year);month=int(month);endmonth=int(endmonth)
    endyear=int(endyear) if endyear else year
    if endyear<year or endyear-year>1:raise ValueError('Forecast period invalid')
    return dt.date(year,month,1),dt.date(endyear,endmonth,calendar.monthrange(endyear,endmonth)[1])


def forecast_sections(text):
    """Select current outlook blocks under explicit species chapter headings.

    Do not extract figures/tables or combine neighboring species. The older
    stock-assessment discussion after the outlook is deliberately excluded.
    """
    text=compact(text)
    taxa=[r'マサバ(?:太平洋系群)?・ゴマサバ',*[re.escape(s) for s in sorted(SPECIES,key=len,reverse=True) if s!='マサバ・ゴマサバ']]
    pattern=r'('+'|'.join(taxa)+r')(?:太平洋系群等|太平洋系群|対馬暖流系群|長期)?の?漁況予報'
    headings=list(re.finditer(pattern,text));sections={}
    for index,heading in enumerate(headings):
        species=heading.group(1).replace('太平洋系群','')
        block=text[heading.end():headings[index+1].start() if index+1<len(headings) else len(text)]
        start=block.find('今後の見通し')
        if not 0<=start<180:continue
        block=block[start:]
        stop=re.search(r'問い合わせ先|漁況の経過|\d[.．]資源状態|についての説明',block)
        if stop:block=block[:stop.start()]
        if len(block)>1800:
            end=block.rfind('。',0,1800)
            if end<60:continue
            block=block[:end+1]
        if not re.search(r'来遊量|来遊水準',block) or not re.search(r'前年|平年|低水準',block):continue
        # The first-page overview (where present) is short and keeps the
        # age/sea-area distinctions. Later repeated headings do not replace it.
        sections.setdefault(species,block)
    return sections


def overview_sections(text,family):
    """Extract the publication's own overview, retaining opposite regional trends.

    All four current FRA templates have an explicit first-page overview.
    Fail closed if a future template no longer identifies every expected taxon.
    """
    text=unicodedata.normalize('NFKC',text)
    normalized=compact(text);result={}
    if family=='pacific':
        section=re.split(r'漁況\s*[（(]来遊量予測[）)]',text,maxsplit=1)
        if len(section)<2:raise ValueError('Pacific forecast overview heading missing')
        active=None
        for line in section[1].splitlines():
            line=compact(line)
            if line.startswith('問い合わせ'):break
            if line in SPECIES:
                active=line;result[active]=''
            elif active:result[active]+=line
        expected={'マイワシ','カタクチイワシ','ウルメイワシ','マアジ','マサバ・ゴマサバ'}
    elif family=='tsushima':
        section=normalized.split('漁況(来遊水準)',1)
        if len(section)<2:raise ValueError('Tsushima forecast overview heading missing')
        section=re.split('※|問い合わせ',section[1],maxsplit=1)[0]
        marks=list(re.finditer(r'\(\d+\)('+'|'.join(SPECIES)+r'):',section))
        for i,mark in enumerate(marks):
            result[mark.group(1)]=section[mark.end():marks[i+1].start() if i+1<len(marks) else len(section)]
        expected={'マアジ','マサバ','ゴマサバ','マイワシ','ウルメイワシ','カタクチイワシ'}
    elif family=='squid':
        match=re.search(r'スルメイカの来遊量[^。]+。',normalized)
        if match:result['スルメイカ']=match.group(0)
        expected={'スルメイカ'}
    else:
        claims=re.findall(r'\d+歳(?:以上)?魚は.+?(?=\d+歳(?:以上)?魚は|\*|問い合わせ|$)',normalized)
        if claims:result['ブリ']='。'.join(s.rstrip('。') for s in claims)+'。'
        expected={'ブリ'}
    if set(result)!=expected or any(not 8<=len(value)<=500 for value in result.values()):
        raise ValueError('Incomplete or ambiguous forecast overview; previous report retained')
    return result


def fetch_pdf(url):
    if not official(url):raise ValueError('Nonofficial forecast PDF')
    req=urllib.request.Request(url,headers={'User-Agent':USER_AGENT})
    with urllib.request.urlopen(req,timeout=40) as response:
        data=response.read(6_000_001)
    if len(data)>6_000_000 or not data.startswith(b'%PDF'):raise ValueError('Forecast PDF invalid or too large')
    return data


def report_items(foods,family,published,url,html,pdf_text,pdf_url,today,overview_text=None):
    soup=BeautifulSoup(html,'html.parser');text=soup.get_text(' ',strip=True)
    pub_marker=f'令和{published.year-2018}年{published.month}月{published.day}日'
    if pub_marker not in compact(text):raise ValueError('Forecast publication date mismatch')
    if f'{published.year}年{published.month}月{published.day}日' not in compact(pdf_text):
        raise ValueError('Forecast PDF date mismatch')
    if FAMILIES[family][0] not in compact(pdf_text):raise ValueError('Forecast PDF family mismatch')
    start,end=target_period(text)
    endyear=f'{end.year}年' if end.year!=start.year else f'(?:{end.year}年)?'
    if not re.search(f'{start.year}年{start.month}月[~〜～-]'+endyear+f'{end.month}月',compact(pdf_text)):
        raise ValueError('Forecast PDF observation period mismatch')
    if start>today+dt.timedelta(days=45) or end<today:return []
    heading=next((h for h in soup.find_all('h1') if FAMILIES[family][0] in compact(h.get_text())),None)
    title=heading.get_text(' ',strip=True) if heading else FAMILIES[family][0]+'漁況予報'
    grouped={}
    overviews=overview_sections(overview_text if overview_text is not None else pdf_text,family)
    detailed=forecast_sections(pdf_text)
    for species,block in overviews.items():
        grouped.setdefault(SPECIES[species],[]).append({'label':species+'の漁況予報・概要（原文）','text':block,'species':species})
    by_name={f['name']:f for f in foods if f['category']=='fish'};items=[]
    for name,sections in grouped.items():
        if name not in by_name:continue
        period=f'{start.year}年{start.month}月～{end.year}年{end.month}月'
        short=[s['species']+'：'+s['text'] for s in sections]
        evidence=[{'label':s['label'],'text':s['text']} for s in sections]
        evidence.extend({'label':s['species']+'の対象条件・海域別予報（原文）','text':detailed[s['species']]}
                        for s in sections if s['species'] in detailed)
        excerpt='予報対象期間：'+period+'。\n'+'\n'.join(s['label']+'：'+s['text'] for s in evidence)
        items.append({'food':by_name[name],'url':url,'publishedAt':published.isoformat(),
                      'reportKey':'fra-'+family+'-'+published.isoformat(),'sourceFamily':'fra-'+family,
                      'sourceName':'水産研究・教育機構 水産資源研究所','sourceTitle':title,
                      'title':name+'：'+FAMILIES[family][1]+'の漁況予報',
                      'observedPeriod':period+'の予報','periodStart':start.isoformat(),'periodEnd':end.isoformat(),
                      'scope':FAMILIES[family][1],'reportType':'来遊量・漁況の見通し（予報）','isForecast':True,
                      'excerpt':excerpt,'summaryExcerpt':'漁況予報：'+''.join(short),
                      'evidenceSections':evidence,'extraSources':[{'name':'予報文（PDF原文）','title':title,
                                                                 'url':pdf_url,'publishedAt':published.isoformat()}],
                      'limitations':'予報の対象海域・魚種・年齢群に限った見通しです。全国の確定漁獲量や市場価格を直接示す資料ではありません。魚種・海域ごとの違いは原文をご確認ください。'})
    return items


def forecast_items(foods,today=None):
    today=today or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    links=forecast_links(fetch(INDEX,timeout=25).decode('utf-8'),today)
    result=[];errors=[]
    for family,(published,url) in links.items():
        try:
            html=fetch(url,timeout=25).decode('utf-8');soup=BeautifulSoup(html,'html.parser')
            pdf=next((urljoin(url,a['href']) for a in soup.find_all('a',href=True)
                      if '予報文' in a.get_text() and a['href'].lower().endswith('.pdf')),None)
            if not pdf:raise ValueError('No official forecast document link')
            import pdfplumber
            with pdfplumber.open(io.BytesIO(fetch_pdf(pdf))) as document:
                first=document.pages[0]
                overview=first.extract_text() or ''
                text='\n'.join(page.extract_text() or '' for page in document.pages[:24])
            items=report_items(foods,family,published,url,html,text,pdf,today,overview)
            if not items:raise ValueError('No current recognizable fish forecast sections')
            result.extend(items);print('FRA FORECAST SOURCE',family,'items',len(items),url,flush=True)
        except Exception as exc:
            errors.append('FRA '+family+': '+type(exc).__name__)
    return result,errors
