"""Cause explanations are source-scoped; absence of evidence never becomes a disaster claim."""
import re,unicodedata
from urllib.parse import urlparse

def unknown():
 return {'status':'unconfirmed','text':'原因は未確認です。取得・整理できた根拠だけでは、現在の状態に至った理由を特定できません。資料に原因の記載がない場合と、アプリがまだ読み取れていない場合があります。別の地域の天候を原因として補っていません。','basis':'原因を示す同じ産地・対象期間の記述を確認できず'}

def progress_text(growth,shipping):
 phrases={'遅い':'平年より遅れています','やや遅い':'平年よりやや遅れています','早い':'平年より早く進んでいます','やや早い':'平年よりやや早く進んでいます','平年並み':'平年並みに進んでいます'}
 result=[]
 for noun,value in [('生育',growth),('出荷',shipping)]:
  if value and value not in ('-','―','—','－'):
   result.append(noun+'は'+phrases[value] if value in phrases else noun+'の進度は「'+value+'」と報告されています')
 return '。'.join(result)+'。' if result else ''

def migrate_legacy(topics):
 """Rephrase our own old table captions without pretending to re-fetch prose."""
 count=0
 for t in topics:
  if t.get('aiGenerated') or not (t.get('sourceFamily') or '').startswith('regional-alic-regions-'):continue
  m=re.match(r'(.+?)の調査。作況：([^、。]+)',t.get('summary',''))
  if not m:continue
  growth=re.search(r'生育進度：([^、。]+)',t['summary']);shipping=re.search(r'出荷進度：([^、。]+)',t['summary'])
  t['summary']=m[1]+'の調査では、'+progress_text(growth[1] if growth else None,shipping[1] if shipping else None)+'作況は「'+m[2]+'」と報告されています。原因の説明はまだ確認できていないため、本文を追加調査します。'
  t['causeAssessment']=unknown();t['summaryVersion']=7
  t['tag']='調査表の記録を文章化（原因本文は未確認）'
  count+=1
 return count

def regional_cause(sections):
 """Conservative, reviewed paraphrases of explicit links in the latest survey only.

 Weather co-occurrence alone cannot establish damage. Unsupported/negated
 mechanisms remain unknown. Source prose is kept in memory, never republished.
 """
 growth=sections.get('生育状況','');outlook=sections.get('今後の生育・出荷の見込み','')
 for sentence in re.split('[。\n]',growth):
  if any(x in sentence for x in ('ない','なく','認められず','見られず','みられず','発生せず','被害なし','懸念','恐れ','おそれ','可能性','心配')):continue
  months=list(dict.fromkeys(re.findall(r'(\d{1,2})月',sentence)))
  period='・'.join(m+'月' for m in months)
  rain=(period+'の' if period else '')+'雨'
  if re.search(r'雨.{0,30}湿害.{0,12}(によ|の影響).{0,25}活着不良',sentence) and '生育ムラ' in sentence:
   return {'status':'documented','text':rain+'で畑が過湿となり、一部で苗の根付きが悪く、生育にばらつきが出ています。出典が示すのは一部の畑への影響であり、生育・出荷の遅れ全体がこれだけで説明できるとは限りません。','basis':'最新調査の「生育状況」に雨・湿害と活着不良、生育ムラの因果関係の記載'}
  if re.search(r'長雨.{0,16}日照不足.{0,8}(によ|の影響)',sentence) and '作柄不良' in sentence and '小玉' in sentence:
   recovery='ただし、調査時点ではその影響から回復しつつあります。' if '回復' in sentence else ''
   return {'status':'documented','text':rain+'が続いて日射が足りなかったため、作柄が悪化し、玉が大きくなりにくい状態になりました。'+recovery,'basis':'最新調査の「生育状況」に長雨・日照不足と作柄、小玉への影響の記載'}
  if re.search(r'(大雨|長雨).{0,30}(影響|ため).{0,20}根傷み',sentence):
   effects='そのため株が失われたり、生育が遅れたりし、細めのものが多いと報告されています。' if re.search(r'根傷み[^。]*。そのため.{0,30}欠株.{0,20}生育遅れ.{0,20}細物',growth) else ''
   return {'status':'documented','text':rain+'の影響で根が傷んだことが、産地の生育状況として報告されています。'+effects,'basis':'最新調査の「生育状況」に雨と根傷みの関係の記載'}
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
 # Fruit/fish source prose used to fall through solely because its publisher
 # was not MAFF. Recognize explicit links, retaining attribution/uncertainty.
 text=unicodedata.normalize('NFKC',item.get('causeEvidence') or item.get('excerpt',''))
 causes=[('水不足|少雨|干ばつ|乾燥','水分の不足'),('日照不足|日照時間.{0,4}少','日照の不足'),('高温|猛暑|暑さ','高温'),('低温|気温.{0,4}低下','気温の低下'),('長雨|多雨|降水量.{0,4}多','雨の多さ'),('海水温.{0,8}(上昇|高)|高水温','海水温の上昇'),('親潮.{0,6}(弱|勢力)','親潮の変化')]
 effects=[('小玉|小ぶり|肥大.{0,5}(鈍|不良)|大きくなら','果実が大きくなりにくいこと'),('着色不良|色づき.{0,4}(遅|悪)','色づきの遅れ'),('生育.{0,5}遅|仕上がり.{0,5}遅','生育の遅れ'),('裂果|割れ','果実が割れる被害'),('来遊.{0,5}遅|回遊.{0,5}変|分布.{0,5}変','来遊や分布の変化'),('稚魚.{0,12}(育|生残|生存)','稚魚の育ち・生残への影響')]
 for sentence in re.split('[。\n]',text):
  sentence=re.sub(r'\s+','',sentence)
  if not re.search('影響|によ|ため|要因|原因|招|つなが',sentence):continue
  if re.search('影響.{0,8}(ない|なし|認められず)|原因.{0,6}(ではない|ではなく)|関連.{0,5}(ない|不明)',sentence):continue
  for cp,cn in causes:
   cm=re.search(cp,sentence)
   if not cm:continue
   for ep,en in effects:
    em=re.search(ep,sentence)
    if not em or abs(cm.start()-em.start())>100:continue
    hypothetical=bool(re.search('可能性|考えられ|とみられ|推測|かもしれ',sentence))
    forecast=bool(re.search('懸念|おそれ|恐れ|見込|予測',sentence))
    status='source_hypothesis' if hypothetical else 'documented'
    explanation=('推測（出典の見解）：' if hypothetical else '出典は、')+cn+'と'+en+'を関連付けています。'
    if forecast:explanation+='これは懸念・見通しの説明で、起きた被害を確定したものではありません。'
    return {'status':status,'text':explanation,'basis':'この食材の出典本文にある原因・背景の記述（自動抽出）'}
 result=unknown()
 if item.get('food',{}).get('category') in ('fruit','fish') or '熟度' in item.get('reportType','') or '速報' in item.get('reportType',''):
  result['text']='この資料は観測値や見通しを中心とした情報で、変化の原因までは確認できていません。原因を説明する産地・海域の取材は、別の資料として掲載します。'
 return result
