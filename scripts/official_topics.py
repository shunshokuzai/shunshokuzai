"""Extract current, explicitly named fruit/fish commentary from Tokyo reports."""
import datetime as dt
import io
import re
import unicodedata

from bs4 import BeautifulSoup
from update_data import fetch
from update_fish import url_index

INDEXES = {
    'fish': 'https://www.shijou.metro.tokyo.lg.jp/torihiki/week/suisan',
    'fruit': 'https://www.shijou.metro.tokyo.lg.jp/torihiki/week/kajitsu',
}
ALIASES = {'りんご': ['りんご', 'リンゴ'], 'みかん': ['みかん', 'ミカン'],
           'かき': ['柿', 'かき'], 'ぶどう': ['ぶどう', 'ブドウ'],
           'なし': ['日本なし', '日本ナシ'], 'カキ': ['ムキカキ', 'むきかき'],
           'スルメイカ': ['スルメイカ', 'スルメ'], 'キウイフルーツ': ['キウイ']}


def report_text(blob):
    if blob.startswith(b'%PDF'):
        import pdfplumber
        with pdfplumber.open(io.BytesIO(blob)) as pdf:
            text = '\n'.join(page.extract_text() or '' for page in pdf.pages[:4])
    else:
        text = BeautifulSoup(blob, 'html.parser').get_text(' ', strip=True)
    return unicodedata.normalize('NFKC', text)


def commentary_items(text, foods, category, stamp, url):
    text = unicodedata.normalize('NFKC', text)
    # Quotes must come from prose commentary, never by converting price-table
    # numbers into a fabricated explanation of supply or production.
    markers = list(re.finditer(r'(?:市場概況|市場概\s*況|主要鮮魚別に見ると)', text))
    if not markers:
        return []
    section = re.sub(r'\s+', '', text[markers[-1].end():])
    if len(section) < 40:
        return []
    sentences = [s + '。' for s in section.split('。') if s.strip()]
    candidates = [f for f in foods if f['category'] == category]
    result = []
    for food in candidates:
        aliases = [food['name'], *ALIASES.get(food['name'], [])]
        selected = []
        for i, sentence in enumerate(sentences):
            if not any(alias in sentence for alias in aliases):
                continue
            selected.append(sentence)
            # A following sentence such as "数量は前週比..." belongs to this
            # food only until another named food begins. Keep source context.
            if i + 1 < len(sentences) and sentences[i + 1].startswith(('数量は', '価格は', '入荷量は')):
                selected.append(sentences[i + 1])
        excerpt = ''.join(dict.fromkeys(selected))[:1200]
        if len(excerpt) < 24:
            continue
        period = f'{stamp[0]}年{stamp[1]}月第{stamp[2]}週'
        result.append({'food': food, 'url': url, 'publishedAt': None,
                       'reportKey': 'tokyo-' + category + '-' + '-'.join(map(str, stamp)),
                       'sourceName': '東京都中央卸売市場・週間市況（' + ('水産' if category == 'fish' else '果実') + '）',
                       'sourceTitle': period + 'の週間市況', 'observedPeriod': period,
                       'title': food['name'] + '：' + period + 'の入荷・市場動向',
                       'excerpt': excerpt})
    return result


def weekly_items(foods, category, today=None):
    today = today or dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).date()
    index = INDEXES[category]
    listing = url_index(fetch(index, timeout=25).decode('utf-8'))
    recent = [s for s in listing if s[0] == today.year and (s[0], s[1]) <= (today.year, today.month)]
    if not recent:
        raise ValueError('No current weekly commentary source')
    stamp = max(recent)
    # Do not relabel a report from an earlier season as current information.
    if today - dt.date(stamp[0], stamp[1], 1) > dt.timedelta(days=65):
        raise ValueError('Weekly commentary source is too old')
    url = listing[stamp]
    return commentary_items(report_text(fetch(url, timeout=35)), foods, category, stamp, url)
