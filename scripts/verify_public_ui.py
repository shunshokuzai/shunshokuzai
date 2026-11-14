"""Read-only checks against the actual published app on desktop and mobile widths."""
import json
import datetime as dt
import re
import os
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright, expect

URL=os.getenv('PUBLIC_APP_URL','https://shunshokuzai.github.io/shunshokuzai/')
OUT=Path('ui-results');OUT.mkdir(exist_ok=True)

def run():
 results=[]
 with sync_playwright() as p:
  browser=p.chromium.launch()
  for label,width,height,mobile in [('desktop',1280,900,False),('mobile',390,844,True)]:
   context=browser.new_context(viewport={'width':width,'height':height},is_mobile=mobile,has_touch=mobile,
      locale='ja-JP',timezone_id='Asia/Tokyo')
   page=context.new_page();errors=[]
   page.on('pageerror',lambda error:errors.append(str(error)))
   response=page.goto(URL,wait_until='networkidle',timeout=60000)
   assert response and response.status==200
   expect(page.get_by_role('heading',name='今年の生育・出荷・漁況',exact=True)).to_be_visible()
   assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Homepage overflows viewport'
   page.screenshot(path=str(OUT/(label+'-home.png')))
   monitor=page.evaluate('window.SHUN_DATA.metadata.foodResearchStatus')
   ids=page.evaluate('window.SHUN_DATA.foods.map(f=>f.id)')
   assert monitor and set(monitor)==set(ids), 'Monitoring status does not cover every food'
   if dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime('%Y-%m-%d')=='2026-11-14':
    chestnut=page.locator('.topic-row[data-detail="f-069"]')
    expect(chestnut).to_have_count(1);chestnut.click()
    expect(page.locator('#detailContent .detail-summary')).to_contain_text('収穫始期')
    expect(page.locator('#detailContent .detail-summary')).to_contain_text('25.3g')
    expect(page.locator('#detailContent .detail-summary')).to_contain_text('32.5g')
    page.get_by_text('この食材の調査状況',exact=True).click()
    expect(page.locator('.research-status')).to_contain_text('高知県')
    page.screenshot(path=str(OUT/(label+'-chestnut.png')))
    page.locator('#closeDetail').click()
   # A food which previously had little year-specific context now has a
   # scoped source summary and genuine observations in both recovered years.
   release_checks=dt.datetime.now(dt.timezone(dt.timedelta(hours=9))).strftime('%Y-%m-%d')=='2026-11-13'
   celery=page.locator('.topic-row').filter(has=page.get_by_role('heading',name='セロリ：2026年11月の見通し（刊行時点の産地情報）',exact=True))
   if release_checks:
    expect(celery).to_have_count(1);celery.click()
   elif celery.count():celery.first.click()
   else:
    if mobile:page.locator('#mobileMenu').click()
    page.locator('.nav-item[data-page="prices"]').click()
    page.locator('#priceSearch').fill('セロリ')
    page.locator('#priceResults .food-row').first.click()
   detail=page.locator('#detailContent')
   if release_checks:
    expect(detail.locator('.detail-summary')).to_contain_text('静岡')
    expect(detail.locator('.detail-summary')).to_contain_text('根腐れ')
    expect(detail).to_contain_text('独立検証前')
   page.get_by_role('button',name='年ごとに比較',exact=True).click()
   graph=page.locator('#longHistoryPanel')
   legend=graph.locator('.history-legend').inner_text()
   if release_checks:
    assert '2021年' in legend and '2022年' in legend
    assert '2021年（未取得）' not in legend and '2022年（未取得）' not in legend
   expect(graph.locator('svg')).to_be_visible()
   expect(graph).to_contain_text('旬別公表値ではありません')
   table_toggle=graph.locator('details>summary').first
   table_toggle.click()
   first=graph.locator('tbody tr').first
   if release_checks:expect(first).to_contain_text('2021年')
   if first.locator('details>summary').count():
    expect(first).to_contain_text('日別再集計')
    first.locator('details>summary').click()
    daily=first.locator('a[href*="file-download"]')
    assert daily.count()>0
    assert all(urlparse(a.get_attribute('href')).scheme=='https' for a in daily.all())
   elif release_checks:raise AssertionError('Recovered observation lacks daily provenance')
   table_toggle.click()
   graph.scroll_into_view_if_needed();page.screenshot(path=str(OUT/(label+'-five-year-chart.png')))
   page.locator('#closeDetail').click()
   # Seasonal reports may expire; their current-release checks must not
   # force an old forecast to remain visible in future months.
   if not page.locator('.topic-row').count():
    if mobile:page.locator('#mobileMenu').click()
    page.locator('.nav-item[data-page="topics"]').click()
   saury=page.locator('.topic-row').filter(has=page.get_by_role('heading',name='サンマ：道東・三陸・常磐の中短期漁況予報',exact=True))
   if release_checks:expect(saury).to_have_count(1)
   if saury.count():
    saury.first.click()
    expect(detail.locator('.detail-summary')).to_contain_text('11月9日')
    for area in ('道東','三陸','常磐'):expect(detail.locator('.detail-summary')).to_contain_text(area)
    assert all(urlparse(a.get_attribute('href')).scheme=='https' for a in detail.locator('.source-links a').all())
    page.locator('#closeDetail').click()
   salmon=page.locator('.topic-row').filter(has=page.get_by_role('heading',name=re.compile('サケ：11道県の来遊速報')))
   if release_checks:expect(salmon).to_have_count(1)
   if salmon.count():
    salmon.first.click()
    for word in ('沿岸の漁獲','河川等の捕獲','期間途中の速報'):
     expect(detail.locator('.detail-summary')).to_contain_text(word)
    if release_checks:expect(detail.locator('.detail-summary')).to_contain_text('2,391,004')
    page.locator('#closeDetail').click()
   # The same hiragana query must find the katakana food on both viewports.
   if mobile:page.locator('#mobileMenu').click()
   page.locator('.nav-item[data-page="prices"]').click()
   page.locator('#priceSearch').fill('きゃべつ')
   expect(page.locator('#priceResults .food-row')).to_have_count(1)
   expect(page.locator('#priceResults .food-label')).to_contain_text('キャベツ')
   expect(page.locator('#priceResults .price-indicator')).to_have_count(1)
   assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Price search overflows viewport'
   page.screenshot(path=str(OUT/(label+'-search.png')))
   if mobile:page.locator('#mobileMenu').click()
   page.locator('.nav-item[data-page="about"]').click()
   overview=page.get_by_text('全'+str(len(ids))+'品目の調査状況を見る',exact=True)
   overview.click()
   expect(page.locator('table').filter(has=page.get_by_role('columnheader',name='新着一覧の最終確認')).locator('tbody tr')).to_have_count(len(ids))
   assert not errors,errors
   results.append({'viewport':label,'size':[width,height],'javascriptErrors':errors,
     'checked':['scoped crop summary','2021/2022 graph data','daily CSV provenance','saury forecast','salmon observations','hiragana search','viewport overflow']})
   context.close()
  browser.close()
 (OUT/'result.json').write_text(json.dumps({'url':URL,'results':results},ensure_ascii=False,indent=2),encoding='utf-8')
 print('PUBLIC UI VERIFIED',json.dumps(results,ensure_ascii=False),flush=True)

if __name__=='__main__':run()
