"""Cause explanations are source-scoped; absence of evidence never becomes a disaster claim."""
import re,unicodedata
from urllib.parse import urlparse

def unknown():
 return {'status':'unconfirmed','text':'原因は未確認です。取得・整理できた根拠だけでは、現在の状態に至った理由を特定できません。資料に原因の記載がない場合と、アプリがまだ読み取れていない場合があります。別の地域の天候を原因として補っていません。','basis':'原因を示す同じ産地・対象期間の記述を確認できず'}

def regional_cause(sections):
 """Conservative, reviewed paraphrases of explicit links in the latest survey only.

 Weather co-occurrence alone cannot establish damage. Unsupported/negated
 mechanisms remain unknown. Source prose is kept in memory, never republished.
 """
 growth=sections.get('生育状況','');outlook=sections.get('今後の生育・出荷の見込み','')
 for sentence in re.split('[。\n]',growth):
  if any(x in sentence for x in ('ない','なく','認められず','見られず','みられず','発生せず','被害なし','懸念','恐れ','おそれ','可能性','心配')):continue
  if re.search(r'雨.{0,30}湿害.{0,12}(によ|の影響).{0,25}活着不良',sentence) and '生育ムラ' in sentence:
   return {'status':'documented','text':'雨で畑が過湿となり、一部で苗の根付きが悪く、生育にばらつきが出ています。出典が示すのは一部の畑への影響であり、生育・出荷の遅れ全体がこれだけで説明できるとは限りません。','basis':'最新調査の「生育状況」に雨・湿害と活着不良、生育ムラの因果関係の記載'}
  if re.search(r'長雨.{0,16}日照不足.{0,8}(によ|の影響)',sentence) and '作柄不良' in sentence and '小玉' in sentence:
   recovery='ただし、調査時点ではその影響から回復しつつあります。' if '回復' in sentence else ''
   return {'status':'documented','text':'雨が続いて日射が足りなかったため、作柄が悪化し、玉が大きくなりにくい状態になりました。'+recovery,'basis':'最新調査の「生育状況」に長雨・日照不足と作柄、小玉への影響の記載'}
  if re.search(r'(大雨|長雨).{0,30}(影響|ため).{0,20}根傷み',sentence):
   return {'status':'documented','text':'雨の影響で根が傷んだことが、生育不良の背景として報告されています。根の状態が悪化すると水分や養分を吸収しにくくなると考えられますが、この仕組み自体はアプリによる一般的な解釈です。','basis':'最新調査の「生育状況」に雨と根傷みの関係の記載'}
  if re.search(r'(降雨|雨).{0,12}(ため|影響).{0,12}定植作業.{0,8}遅',sentence):
   return {'status':'documented','text':'雨が続いて畑に苗を植える作業が遅れたことが、出典で説明されています。','basis':'最新調査の「生育状況」に降雨と定植作業の遅れの記載'}
 # Association is explicitly a tentative interpretation, never a factual cause.
 if re.search(r'日照時間も多くなり.{0,15}活着も良く.{0,15}良好',growth) and not re.search('ない|なく|ず|懸念',growth):
  return {'status':'inference','text':'推測：日照の回復が苗の根付きや生育を支えた可能性があります。根拠は、同じ調査に日照の増加と良好な活着・生育が併記されていることです。寄与の大きさや因果関係は確認できていません。','basis':'最新調査の「生育状況」に日照回復と良好な生育を併記（因果の断定はしない）'}
 return unknown()

def assess(item):
 if item.get('causeAssessment'):return item['causeAssessment']
 # MAFF government text is already published in evidenceSections, scoped to
 # the individual commodity. Preserve the publisher's uncertainty/negation.
 host=urlparse(item.get('url','')).hostname or ''
 if host=='www.maff.go.jp':
  for section in item.get('evidenceSections',[]):
   for sentence in re.split('。',section.get('text','')):
    if re.search(r'(影響(?:により|で)|により|のため|による)',sentence) and len(sentence)<420:
     return {'status':'documented','text':'出典の説明：'+sentence.strip()+'。','basis':section.get('label','資料の該当箇所')+'（出典の記述。見通し・懸念を含む場合は未確定）'}
 return unknown()
