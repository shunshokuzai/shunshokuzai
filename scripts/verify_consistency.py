"""Check every published history point and baseline against its source archive."""
import json
from market_history import MarketHistory
from update_data import DATA, same_produce_schema


def verify(obj,archive):
    foods={f['id']:f for f in obj['foods']};checked=0
    for row in obj['prices']:
        food=foods[row['foodId']];kind='fish' if food['category']=='fish' else 'produce'
        records=archive.records(kind)
        if not records:continue
        latest=records[-1];stamp=tuple(latest['stamp'])
        datum=latest['values'].get(food['name'])
        if not row.get('stale'):
            assert datum is not None, 'Current price missing from source: '+food['name']
            value=datum['price'] if kind=='fish' else datum
            assert row['price']==value, 'Current price differs from source: '+food['name']
            assert row['sourceUrl']==latest['sourceUrl'], 'Current source URL mismatch'
        for point in row.get('longHistory',[]):
            source=archive.get(kind,point['period'])
            assert source and point['sourceUrl']==source['sourceUrl'], 'History source mismatch'
            value=source['values'][food['name']]
            assert point['price']==(value['price'] if kind=='fish' else value), 'History price mismatch'
            if kind=='produce':assert same_produce_schema(source), 'Old commodity-series parser in published history'
            elif datum is not None:assert value.get('brandLabel')==datum.get('brandLabel'), 'Different fish brands mixed'
            checked+=1
        if row.get('normalRatio') is not None:
            years=row['historicalYears'];values=row['historicalPrices'];sources=row['historicalSources']
            assert 3<=len(years)<=5 and len(years)==len(set(years))==len(values)==len(sources), 'Invalid baseline years'
            for year,price,url in zip(years,values,sources):
                assert stamp[0]-5<=year<stamp[0], 'Out-of-range baseline year'
                record=archive.get(kind,(year,stamp[1],stamp[2]))
                assert record and record['sourceUrl']==url, 'Baseline source mismatch'
                value=record['values'][food['name']]
                assert price==(value['price'] if kind=='fish' else value), 'Baseline price mismatch'
            mean=round(sum(values)/len(values),1)
            assert row['normalPrice']==mean, 'Baseline average mismatch'
            assert row['normalRatio']==round(row['price']/mean*100,1), 'Baseline ratio mismatch'
    return checked


if __name__=='__main__':
    obj=json.loads(DATA.read_text(encoding='utf-8'))
    print('VERIFIED PUBLISHED PRICE POINTS',verify(obj,MarketHistory()),flush=True)
