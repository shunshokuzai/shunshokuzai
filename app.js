(()=>{'use strict';
const D=window.SHUN_DATA;const names={vegetable:'野菜',fruit:'果物',fish:'魚'};
const art=(f)=>window.SHUN_ART?window.SHUN_ART(f):escaped(f.emoji);
const matchesFood=(food,query)=>window.SHUN_SEARCH?window.SHUN_SEARCH.matches(food,query):food.name.includes(query);
const get=(id)=>document.getElementById(id);const escaped=(s)=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const urlSafe=(str)=>{try{let u=new URL(str);return ['https:','http:'].includes(u.protocol)?u.href:'#'}catch{return '#'}};
const now=new Date(), todayJst=now.toLocaleDateString('en-CA',{timeZone:'Asia/Tokyo',year:'numeric',month:'2-digit',day:'2-digit'}), currentMonth=Number(todayJst.slice(5,7));
let saved=[];try{saved=JSON.parse(localStorage.getItem('shun-favs')||'[]');if(!Array.isArray(saved))saved=[]}catch{}
const state={page:'topics',category:'all',query:'',sort:'default',priceOnly:'all',month:currentMonth,calendarCategory:'all',fav:saved,region:'national',lastFocus:null,customFishWeights:{}};

function topicDate(t){
if(/^\d{4}-\d{2}-\d{2}/.test(t.publishedAt||''))return t.publishedAt.slice(0,10);
if(/^\d{4}-\d{2}-\d{2}/.test(t.sourceUpdatedAt||''))return t.sourceUpdatedAt.slice(0,10);
if(t.periodEnd&&!t.isForecast)return t.periodEnd;
const m=String(t.observedPeriod||'').match(/(20\d{2})年(\d{1,2})月(?:(\d{1,2})日)?/);
return m?m[1]+'-'+m[2].padStart(2,'0')+'-'+(m[3]||'01').padStart(2,'0'):'';
}
function topicFamily(t){
if(t.sourceFamily)return t.sourceFamily;
const s=t.sources?.[0]||{};
if((s.url||'').includes('/press/nousan/engei/'))return 'maff-vegetable';
if((s.name||'').includes('週間市況'))return (s.name||'').includes('水産')?'tokyo-fish':'tokyo-fruit';
return s.url||t.id;
}
function activeFoodTopics(topics,foodId,today){
const forecastEnd=t=>{
if(t.periodEnd)return t.periodEnd;
const text=String(t.observedPeriod||'');
const range=text.match(/(20\d{2})年(\d{1,2})月?[～〜~－-](?:(20\d{2})年)?(\d{1,2})月/);
const month=text.match(/(20\d{2})年(\d{1,2})月/);
if(!range&&!month)return '';
const year=range?Number(range[3]||range[1])+(range[3]?0:Number(range[4])<Number(range[2])?1:0):Number(month[1]);
const mon=Number(range?range[4]:month[2]);if(mon<1||mon>12)return '';
return year+'-'+String(mon).padStart(2,'0')+'-'+new Date(Date.UTC(year,mon,0)).getUTCDate();
};
const candidates=topics.filter(t=>{
if(t.foodId!==foodId||!t.yearSpecific||!t.sources?.length)return false;
const date=topicDate(t);if(!date||date>today)return false;
if(t.seasonalRecord&&t.reportYear===Number(today.slice(0,4)))return true;
const forecast=t.isForecast||/予報|見通し/.test(t.observedPeriod||'');
if(forecast){const end=forecastEnd(t);return end?end>=today:date.slice(0,4)===today.slice(0,4)}
return Date.parse(today)-Date.parse(date)<=65*86400000;
}).sort((a,b)=>topicDate(b).localeCompare(topicDate(a))||String(a.id).localeCompare(String(b.id)));
const seen=new Set();return candidates.filter(t=>{const key=topicFamily(t);if(seen.has(key))return false;seen.add(key);return true});
}

const foodMap=new Map(D.foods.map(f=>[f.id,f]));const priceMap=new Map(D.prices.map(p=>[p.foodId,p]));const topicToday=todayJst;const activeTopics=D.foods.flatMap(f=>activeFoodTopics(D.topics,f.id,topicToday));const topicMap=new Map(D.foods.map(f=>[f.id,activeTopics.filter(t=>t.foodId===f.id)[0]]).filter(([,t])=>t));
const isMonth=(food,m)=>food.seasonMonths.includes(m);
const officialTopics=()=>activeTopics.length;
const priceStatus=(p)=>{if(!p||p.stale||p.normalRatio==null||p.classificationUncertain)return ['判定待ち','demo'];return p.normalRatio<85?['安い','low']:p.normalRatio>115?['高い','high']:['普通','mid']};
const priceIndicator=(id)=>{const [label,kind]=priceStatus(priceMap.get(id));const text=kind==='demo'?'未判定':label;return `<span class="price-indicator ${kind}" role="img" aria-label="価格判定：${text}" title="${kind==='demo'?'平年比未算出・価格未収録・推計誤差による判定保留':`参考平年比による判定：${label}`}"><i aria-hidden="true"></i></span>`};
const tone=f=>['vegetable','fruit','fish'].indexOf(f.category)===0?((f.id.charCodeAt(f.id.length-1)%2)?'tone-2':'tone-3'):f.category==='fruit'?'tone-0':'tone-3';
const relatedTopic=f=>topicMap.get(f.id);
// Market data uses yen per kilogram. A one-fish price is a calculated reference
// obtained only when the source gives a size/box count or the visitor supplies a weight.
const weightOf=(p,f)=>{
 if(!p||f.category!=='fish'||f.name==='カキ')return null;
 const override=state.customFishWeights[f.id];
 return (Number.isFinite(override)&&override>0?override:(Number.isFinite(p.pieceWeightKg)&&p.pieceWeightKg>0?p.pieceWeightKg:null));
};
const fishUnit=(f)=>f.name==='スルメイカ'?'杯':'尾';
const oneFish=(p,f)=>{const w=weightOf(p,f);return w==null?null:Math.round(p.price*w)};
const formatCurrency=(amount)=>Math.round(amount).toLocaleString('ja-JP');
const priceValue=(p,f)=>{
 if(f.category!=='fish')return `${formatCurrency(p.price)} <small>円/kg</small>`;
 const amount=oneFish(p,f);
 return amount==null?`<span class="weight-missing">— <small>円/${fishUnit(f)}</small></span><small class="kg-fallback">${formatCurrency(p.price)}円/kg（原統計）</small>`
 :`<span>約 ${formatCurrency(amount)} <small>円/${fishUnit(f)}</small></span><small class="kg-fallback">${formatCurrency(p.price)}円/kg × ${(weightOf(p,f)*1000).toLocaleString('ja-JP',{maximumFractionDigits:0})}g</small>`;
};

function seedNotice(){const st=D.metadata.autoRefreshStatus||{};
 const failed=Object.entries(st).filter(([,v])=>v==='error'||v==='api_key_missing');
 const alert=failed.length?`<div class="update-warning" role="status">⚠ 自動更新の一部に未解決の問題があります：${failed.map(([k])=>({vegetableFruit:'青果価格',fish:'魚価格',gemini:'Gemini要約',topics:'旬の話題',history:'過年度価格'}[k]||k)).join('・')}。最終取得済みの公的データを表示しています。詳細は「情報の見方・出典」をご確認ください。</div>`:'';
 const veg=D.prices.filter(p=>!p.sample&&foodMap.get(p.foodId)?.category!=='fish').length;const fish=D.prices.filter(p=>foodMap.get(p.foodId)?.category==='fish').length;return `${alert}<div class="notice"><span class="notice-icon">ⓘ</span><div><strong>青果${veg}品目＋魚${fish}品目の公的市場価格を収録。</strong> 青果は${escaped(D.metadata.priceObservationPeriod||'対象期間未確認')}、魚は${escaped(D.metadata.fishPriceObservationPeriod||'対象期間未確認')}の市況です。魚の「約○円/尾・杯」は<strong>卸売の円/kg × 公表サイズ帯等の代表重量</strong>による独自換算で、実際の1尾の取引価格・小売価格ではありません。重量不明の魚、むき身のカキは換算せず、元の円/kgを表示します。参考平年比は過去の同時期と比較した目安です。<a href="#" data-page="about">計算方法と出典 ↗</a></div></div>`}

function pricePreview(food){
 const p=priceMap.get(food.id);
 if(!p||!Number.isFinite(p.price))return '<span class="preview-price muted">卸売価格：未収録</span>';
 const displayed=food.category==='fish'?oneFish(p,food):p.price;
 const unit=food.category==='fish'?fishUnit(food):'kg';
 const amount=displayed==null?`${formatCurrency(p.price)}円/kg`:`${food.category==='fish'?'約 ':''}${formatCurrency(displayed)}円/${unit}`;
 return `<span class="preview-price"><b>卸売参考価格 ${amount}</b>${p.stale?' <span class="old-price">旧期間</span>':''}</span>`;
}

function topline(title,sub,eyebrow='SEASONAL GUIDE'){return `<div class="page-intro"><span class="eyebrow">✦ ${eyebrow}</span><h1>${title}</h1><p>${sub}</p></div>`}
function pill(text,kind=''){return `<span class="badge ${kind}">${escaped(text)}</span>`}
function favoriteBtn(food){return `<button class="fav-button ${state.fav.includes(food.id)?'on':''}" data-fav="${food.id}" title="${state.fav.includes(food.id)?'お気に入りから削除':'お気に入りに登録'}" aria-label="お気に入り">${state.fav.includes(food.id)?'♥':'♡'}</button>`}
function featureCard(f,i){let t=relatedTopic(f);return `<button type="button" class="feature-card" data-detail="${f.id}"><div class="feature-visual ${tone(f)}"><span class="emoji">${art(f)}</span></div><div class="card-body"><div class="card-line"><span class="card-category">${names[f.category]} · いまが旬</span>${pill(t?.yearSpecific?'今年の資料あり':'季節の情報')}</div><div class="food-name-line"><h3>${escaped(f.name)}</h3>${priceIndicator(f.id)}</div>${pricePreview(f)}<p>${escaped(t?.summary??`${f.seasonStart}月〜${f.seasonEnd}月ごろに旬を迎える食材です。`)}</p><div class="card-foot">くわしく見る &nbsp;→</div></div></button>`}
function topicRow(t,i){const f=foodMap.get(t.foodId);if(!f)return '';const badge=t.aiGenerated?'AI要約・自動チェック':t.yearSpecific?'公的資料に基づく要約':'季節の一般情報';return `<button type="button" class="topic-row" data-detail="${f.id}" data-topic="${escaped(t.id)}"><span class="topic-thumb ${tone(f)}">${art(f)}</span><div class="topic-body"><div class="topic-meta"><span>${names[f.category]}</span>${pill(badge,t.aiGenerated?'demo':'')}<span>·</span><span>${t.publishedAt?escaped(t.publishedAt)+' 公表':t.sourceUpdatedAt?escaped(t.sourceUpdatedAt)+' 更新':'公表日未確認'}</span></div><div class="topic-title-line"><h3>${escaped(t.title)}</h3>${priceIndicator(f.id)}</div>${pricePreview(f)}<p>${escaped(t.summary)}</p>${t.yearSpecific?`<div class="small-note">対象：${escaped(t.observedPeriod||'資料参照')} · 出典${(t.sources||[]).length}件（詳細で確認）</div>`:''}</div><span class="row-arrow">›</span></button>`}
function renderTopics(){let focusNames=['サンマ','くり','りんご','なす'];let focus=focusNames.map(n=>D.foods.find(f=>f.name===n)).filter(f=>f&&isMonth(f,currentMonth));if(focus.length<4)focus=[...focus,...D.foods.filter(f=>isMonth(f,currentMonth)&&!focus.includes(f))].slice(0,4);
const inSeason=D.foods.filter(f=>isMonth(f,currentMonth)).length;const recent=[...topicMap.values()].filter(t=>t.yearSpecific && foodMap.has(t.foodId));const general=D.topics.filter(t=>!t.yearSpecific&&foodMap.has(t.foodId)&&isMonth(foodMap.get(t.foodId),currentMonth));
return `${seedNotice()}
<div class="stat-grid"><div class="stat-card"><span class="stat-symbol">✦</span><span><small>${currentMonth}月の旬の食材</small><strong>${inSeason}</strong><em>品目</em></span></div><div class="stat-card"><span class="stat-symbol">↗</span><span><small>公的市場価格</small><strong>${D.prices.filter(p=>!p.sample).length}</strong><em>品目</em></span></div><div class="stat-card"><span class="stat-symbol">▤</span><span><small>公的資料に基づく話題</small><strong>${officialTopics()}</strong><em>件</em></span></div></div>
<section class="section"><div class="section-head"><div><h2>🍁 ${currentMonth}月の注目食材</h2><p>旬の食材をピックアップ</p></div><button class="text-link" data-page="calendar">旬カレンダーを見る ↗</button></div><div class="feature-grid">${focus.map(featureCard).join('')}</div></section>
<section class="section"><div class="section-head"><div><h2>今年の生育・出荷・漁況</h2><p>一次資料をもとに現時点で確認できた情報です。予報と実績は区別しています。</p></div><span class="highlight-tag">出典付き ${recent.length} 品目</span></div><div class="topic-list">${recent.length?recent.map(topicRow).join(''):empty('今年の話題はまだありません','Geminiで新情報を取得すると追加されます。')}</div></section>
<section class="section"><div class="section-head"><div><h2>旬の豆知識</h2><p>毎年の旬についての一般的な説明です。今年の作柄情報ではありません。</p></div><span class="highlight-tag">季節の説明 ${general.length} 件</span></div><div class="topic-list">${general.map(topicRow).join('')}</div></section>
<div class="mini-insight"><strong>ℹ &nbsp;更新の状況</strong><br>掲載価格の対象：青果 ${escaped(D.metadata.priceObservationPeriod||'未取得')}／魚 ${escaped(D.metadata.fishPriceObservationPeriod||'未取得')}。データ更新：${escaped(D.metadata.updatedAt||'未取得')}。AI要約は取得した公的原文から作成し、独立検証前であることを明記します。</div>`}
function filteredPrices(){let arr=D.prices.filter(p=>{let f=foodMap.get(p.foodId);return f&&(state.category==='all'||f.category===state.category)&&matchesFood(f,state.query.trim())&&(state.priceOnly==='all'||priceStatus(p)[1]===state.priceOnly)});
if(state.sort==='cheap')arr.sort((a,b)=>(a.normalRatio??999)-(b.normalRatio??999));if(state.sort==='expensive')arr.sort((a,b)=>(b.normalRatio??-1)-(a.normalRatio??-1));if(state.sort==='name')arr.sort((a,b)=>foodMap.get(a.foodId).name.localeCompare(foodMap.get(b.foodId).name,'ja'));if(state.sort==='price')arr.sort((a,b)=>{const fa=foodMap.get(a.foodId),fb=foodMap.get(b.foodId);const aa=fa.category==='fish'?oneFish(a,fa):a.price,bb=fb.category==='fish'?oneFish(b,fb):b.price;return (aa??Infinity)-(bb??Infinity)});return arr}
function priceRow(p){const f=foodMap.get(p.foodId),[label,kind]=priceStatus(p);return `<div class="food-row" data-detail="${f.id}" tabindex="0" role="button" aria-label="${escaped(f.name)}の詳細を見る"><div class="food-label"><span class="row-food-emoji ${tone(f)}">${art(f)}</span><span><div class="food-name-line"><strong>${escaped(f.name)}</strong>${priceIndicator(f.id)}</div><small>${names[f.category]} · ${p.stale?'旧期間の価格・要確認':p.sample?'検証用サンプル':'公的卸売統計'}</small></span></div><div class="number">${priceValue(p,f)}</div><div>${pill(label,kind)}</div><div class="number ${p.normalRatio!=null?(p.normalRatio>115?'ratio-up':p.normalRatio<85?'ratio-down':''):''}">${p.normalRatio!=null?p.normalRatio+'%':'—'} <small>${'参考平年比'}</small></div><div class="number">${p.yearAgoRatio!=null?p.yearAgoRatio+'%':'—'} <small>${f.category==='fish'?'前年同期比':'前年同旬比'}</small></div><div>${favoriteBtn(f)}</div></div>`}

function priceTable(arr){return arr.length?`<div class="price-table"><div class="table-head"><span>食材名</span><span>市場価格（魚：1尾換算）</span><span>価格判定</span><span>参考平年比*</span><span>前年同期比*</span><span></span></div>${arr.map(priceRow).join('')}</div>`:empty('条件に合う価格情報がありません','検索語や絞り込みを変更してください。未収録の品目は価格一覧に表示しません。')}
function empty(t,sub){return `<div class="empty"><span style="font-size:37px">🌱</span><strong>${escaped(t)}</strong><span>${escaped(sub)}</span></div>`}
function renderPrices(){const arr=filteredPrices();return `${topline('食材の価格を調べる','野菜・果物は1kg当たりの卸売価格、魚は市場のkg単価から1尾の参考価格を換算。','MARKET PRICE')}${seedNotice()}<div class="toolbar"><label class="search-box"><span aria-hidden="true">⌕</span><input type="search" id="priceSearch" placeholder="食材名で検索（例：りんご・リンゴ・林檎）" value="${escaped(state.query)}" aria-label="食材名で検索"></label><select class="select" id="priceSort" aria-label="並べ替え"><option value="default">並べ替え</option><option value="cheap" ${state.sort==='cheap'?'selected':''}>平年比が安い順（未算出は末尾）</option><option value="expensive" ${state.sort==='expensive'?'selected':''}>平年比が高い順</option><option value="price" ${state.sort==='price'?'selected':''}>卸売価格が安い順</option><option value="name" ${state.sort==='name'?'selected':''}>名前順</option></select></div><div class="chip-row">${[['all','すべて'],['vegetable','🥬 野菜'],['fruit','🍎 果物'],['fish','🐟 魚']].map(([v,l])=>`<button class="chip ${state.category===v?'active':''}" data-category="${v}">${l}</button>`).join('')}<span class="results-count">${arr.length}件 / ${D.prices.length}件</span></div><div class="chip-row" style="margin-top:-5px">${[['all','判定すべて'],['low','安い'],['mid','普通'],['high','高い'],['demo','判定待ち']].map(([v,l])=>`<button class="chip ${state.priceOnly===v?'active':''}" data-pricestatus="${v}">${l}</button>`).join('')}</div><div id="priceResults">${priceTable(arr)}</div><div class="legend-note"><div class="legend-row"><strong>価格判定の色：</strong>${pill('安い','low')}${pill('普通','mid')}${pill('高い','high')}${pill('判定待ち','demo')}</div>魚の円/尾は<strong>公表された魚体サイズ等から代表重量を仮定し、円/kgを掛けた換算概算</strong>です。実際に尾単位で取引された価格ではありません。魚の「参考平年比」は過去3〜5年の<strong>同月・同週の中値</strong>の単純平均を基準とした独自指標です。青果も比較できる同旬の過去データが3年以上揃った場合に参考値を計算します。規格や主産地の差があるため目安です。暫定閾値は85%未満／85〜115%／115%超。比較できない食材は判定を保留します。</div><p class="small-note">青果出典：<a href="${urlSafe(D.metadata.priceSourceUrl)}" target="_blank" rel="noopener noreferrer">農林水産省（${escaped(D.metadata.priceObservationPeriod||'期間未記録')}、主要市場計・平均卸売単価）↗</a>。魚出典：<a href="${urlSafe(D.metadata.fishPriceSourceUrl)}" target="_blank" rel="noopener noreferrer">東京都豊洲市場（${escaped(D.metadata.fishPriceObservationPeriod||'期間未記録')}、中値）↗</a>。市場・集計方式・対象期間が異なります。いずれも小売価格ではありません。</p>`}
function renderCalendar(){let chosen=D.foods.filter(f=>isMonth(f,state.month)&&(state.calendarCategory==='all'||state.calendarCategory===f.category));return `${topline('旬カレンダー',`月ごとの旬の食材を探せます。産地・栽培方法などによって旬は異なります。`,'SEASON CALENDAR')}
<div class="month-control"><button id="prevMonth" aria-label="前の月">‹</button><strong>${state.month}月の旬</strong><button id="nextMonth" aria-label="次の月">›</button></div><div class="chip-row">${[['all','すべて'],['vegetable','🥬 野菜'],['fruit','🍎 果物'],['fish','🐟 魚']].map(([v,l])=>`<button class="chip ${state.calendarCategory===v?'active':''}" data-calcategory="${v}">${l}</button>`).join('')}<span class="results-count">${chosen.length}品目</span></div><div class="calendar-grid">${chosen.map(f=>`<button class="calendar-card" data-detail="${f.id}"><span class="cal-emoji">${art(f)}</span><strong>${escaped(f.name)}</strong>${priceIndicator(f.id)}<small>${names[f.category]}</small></button>`).join('')}</div><div class="mini-insight"><strong>📅 &nbsp;旬カレンダーについて</strong><br>掲載しているのは一般的な旬の「目安」です。実際の収穫期・漁期は、産地、品種、海域、漁法、施設栽培などで変化します。現在は全国一律の参考情報です。</div>`}
function renderFavorites(){let foods=state.fav.map(id=>foodMap.get(id)).filter(Boolean);return `${topline('お気に入り','気になる食材を保存して、いつでもまとめて確認できます。','YOUR FAVORITES')}${foods.length?`<div class="calendar-grid">${foods.map(f=>`<button class="calendar-card" data-detail="${f.id}"><span class="cal-emoji">${art(f)}</span><strong>${escaped(f.name)}</strong>${priceIndicator(f.id)}<small>${names[f.category]}</small></button>`).join('')}</div>`:empty('まだお気に入りはありません','価格一覧の♡、または食材の詳細から登録できます。')}<p class="small-note">お気に入りは、この端末のブラウザ内に保存されます。別の端末とは同期されません。</p>`}
function renderAbout(){let m=D.metadata;let veg=D.prices.filter(p=>foodMap.get(p.foodId)?.category!=='fish').length;let fish=D.prices.filter(p=>foodMap.get(p.foodId)?.category==='fish').length;
let vegReady=D.prices.filter(p=>foodMap.get(p.foodId)?.category!=='fish'&&p.normalRatio!=null&&!p.stale).length;
let fishReady=D.prices.filter(p=>foodMap.get(p.foodId)?.category==='fish'&&p.normalRatio!=null&&!p.stale).length;
let aiCount=D.topics.filter(t=>t.aiGenerated&&(!t.summaryProvider||t.summaryProvider==='Gemini')).length;
let refresh=m.autoRefreshStatus||{};
let statusLabel=(k)=>({ok:'取得処理成功',error:'取得失敗・前回の情報を維持',not_connected:'未設定',api_key_missing:'APIキー未登録',not_scheduled:'本日は更新対象外',daily_limit:'本日の上限に達したため原文抜粋を掲載',no_new_sources:'新しい原文なし',sources_only:'公的原文の抜粋を掲載'}[refresh[k]]||'未確認');
let statuses=[['青果の実際の卸売価格',`${veg}品目（${m.priceObservationPeriod||'未取得'}）`],
['魚の卸売価格と価格推移',`${fish}品目（${m.fishPriceObservationPeriod||'未取得'}）`],
['魚の参考平年比・判定',`${fishReady}品目が計算済み`],
['青果の平年比・判定',`${vegReady}品目が計算済み`],
['旬の話題（公的資料）',`${officialTopics()}件`],
['Geminiによる原文要約',`${aiCount}件掲載（自動更新：${statusLabel('gemini')}）`],
['青果統計の自動更新',statusLabel('vegetableFruit')],
['魚の統計の自動更新',statusLabel('fish')],
['過年度価格の追加取得',statusLabel('history')],
['旬カレンダー','一般的な目安を掲載']];return `${topline('情報の見方・出典','集計方法が異なる青果と魚の価格を区別し、参考平年比の限界も明示します。','DATA TRANSPARENCY')}
<div class="info-card"><h2>現在の実装状況</h2>${statuses.map(([a,b])=>`<div class="source-item"><strong>${escaped(a)}</strong><span class="status-pill ${b.includes('待ち')||b.includes('未接続')||b.includes('失敗')||b.includes('未設定')||b.includes('未登録')?'':'ok'}">${escaped(b)}</span></div>`).join('')}<p class="small-note">今の価格をリアルタイム表示しているわけではありません。最新の取得確認：${escaped(m.lastAutomaticCheckAt||'未実行')}。各価格と話題の対象期間・出典を個別に確認してください。</p></div>
<div class="info-card"><h2>価格と判定の読み方</h2><h3>色の意味</h3><p>${pill('安い','low')} 平年比85%未満、${pill('普通','mid')} 85%以上115%以下、${pill('高い','high')} 115%超。計算できない品目には灰色の点を表示します。価格が安い／高いとは、<strong>採用した統計指標での比較</strong>であり、小売価格や品質を保証するものではありません。</p><h3>青果の卸売価格</h3><p>農林水産省の青果物卸売市場調査（${escaped(m.priceObservationPeriod||'未取得')}）。主要卸売市場計の1kg当たり平均卸売単価です。平年比は過去3年以上の同月・同旬の統計を照合できた場合に独自算出し、未算出の品目は判定しません。</p><h3>魚の市場価格と1尾換算（重要）</h3><p>魚の一覧価格と価格推移は、原則として円/kgから代表魚体重量を掛けて換算した<strong>1尾あたりの概算</strong>です。スルメイカは1杯換算します。重量データのないマグロ・カレイは詳細画面で重量を入力すると試算できます。むき身のカキは1個換算できません。<strong>1尾・1杯で実際に取引された値ではなく、小売価格でもありません。</strong></p><p>東京都中央卸売市場・豊洲市場の「水産物の週間市況」（現在の対象：${escaped(m.fishPriceObservationPeriod||'未取得')}）。<strong>高値・中値・安値のうち「中値（円/kg）」</strong>を採用しました。これは青果の加重平均価格とは異なり、店舗販売価格でもありません。規格（生鮮・中型・むき身等）は食材の詳細に記載します。</p><h3>魚の独自参考平年比（重要）</h3><p>魚ごとに、原則として直近5年の同月・同週の同じ魚種・銘柄区分の「中値」を取得し、比較可能な3年以上の単純平均で基準価格を作ります。対象週の中値 ÷ その基準価格 × 100 を四捨五入した参考平年比を、3段階に色分けしています。<strong>東京都が発表した公式の平年比ではありません。</strong> 年により産地・サイズ・等級や流通構成が異なるため、厳密な同一規格比較ではありません。</p><h3>魚の価格推移</h3><p>入手できた週別中値に各週の公表サイズに基づく代表重量を掛けた参考換算グラフです（重量不明の魚は円/kgを維持）。週ごとに主産地やサイズが変わることがあります。<strong>価格推移は複数週、参考平年比は過去3〜5年の同月同週</strong>であり、比較期間が異なります。</p><h3>過去5年＋今年のグラフ</h3><p>食材の詳細で、過去5年と今年の時系列、および年ごとの季節比較を切り替えられます。青果は旬別、魚は週別です。長期比較は円/kgに統一し、2021〜2022年の青果はe-Statの日別統計を数量で加重平均した参考推計を含みます。旬別公表値とは区別して表示します。魚は同じ銘柄区分の中値を使います。年による産地・サイズの差には注意してください。未取得・欠測・取引のない期間は線をつながず、年別の取得時点数と各値の出典を表示します。</p><h3>前年同旬比・前年同期比</h3><p>青果は前年同旬比、魚は東京都の週間市況に記載された前年同期の中値比です。どちらも「平年比」と異なります。</p><h3>Geminiについて</h3><p>Gemini APIで取得済みの公的原文から出典付きAI要約を作る機能を搭載しています。実行にはサーバー側のAPIキー設定が必要です。現在のGemini要約掲載件数：${aiCount}件。一部の追加資料はChatGPTで原文に基づき整理しています。AI要約は独立した裏付けがない場合は未検証と明示し、原文を短く抜粋した情報とは区別しています。</p></div>
<div class="info-card"><h2>参照した一次資料</h2>${m.sources.map(s=>`<div class="source-item"><div><a href="${urlSafe(s.url)}" target="_blank" rel="noopener noreferrer">↗ ${escaped(s.name)}</a><div class="small-note">${escaped(s.purpose)}</div></div></div>`).join('')}<p class="small-note">平年比を算出できた食材は、詳細画面の「参考平年比の計算に使った価格」から年度別資料を確認できます。</p></div>
<div class="info-card"><h2>自動更新について</h2><p>青果・水産統計の更新処理は毎日確認、旬の話題の登録先確認は毎日行い、Geminiによる要約は火・木・土に新しい原文を取得した場合に行います。過年度価格は取得済み資料を再利用し、未取得分を1回24資料まで追加します。取得できなかった資料は7日後以降に再試行します。<strong>単体のHTMLファイルは保存日時点のスナップショットで、自動的に通信・更新するものではありません。</strong></p><div class="small-note">最終自動確認：${escaped(m.lastAutomaticCheckAt||'未実行')} ／ 青果：${escaped(statusLabel('vegetableFruit'))} ／ 魚：${escaped(statusLabel('fish'))} ／ Gemini：${escaped(statusLabel('gemini'))}</div></div>`}
function toggleFav(id){if(!foodMap.has(id))return;if(state.fav.includes(id)){state.fav=state.fav.filter(x=>x!==id);toast('お気に入りから削除しました')}else{state.fav.push(id);toast('お気に入りに登録しました')}try{localStorage.setItem('shun-favs',JSON.stringify(state.fav))}catch{}refresh({preserve:true})}
function chartSeries(p,f){
const weight=f.category==='fish'?weightOf(p,f):null;
const custom=Number.isFinite(state.customFishWeights[f.id])&&state.customFishWeights[f.id]>0;
const weekly=f.category==='fish'&&f.name!=='カキ'&&p.historyPieceWeights?.length===p.history.length&&p.historyPieceWeights.every(w=>Number.isFinite(w)&&w>0);
const converted=weight!=null&&(custom||weekly||!p.historyPieceWeights);
const vals=converted?p.history.map((v,i)=>Math.round(v*(weekly&&!custom?p.historyPieceWeights[i]:weight))):p.history;
const unit=converted?`円/${fishUnit(f)}（参考換算）`:'円/kg';
const note=converted?(weekly&&!custom?'各週の公表サイズ帯から代表重量を求め、各週の円/kgに掛けた概算です。サイズ帯の変化も価格推移に影響します。':`各期を同じ${(weight*1000).toLocaleString('ja-JP',{maximumFractionDigits:0})}g/${fishUnit(f)}で換算した試算です。`):f.category==='fish'?'一部の期で1尾重量が確認できないため、グラフは公表された円/kgで表示しています。':'公的統計の円/kgを表示しています。';
return {vals,unit,note};}
function sparkSvg(p,f){if(!p?.history?.length)return `<p class="small-note">同じ集計条件で比較できる価格推移データはまだありません。</p>`;
const {vals,unit,note}=chartSeries(p,f);
const labels=p.historyLabels||vals.map((_,i)=>`第${i+1}期`);const min=Math.min(...vals)*.78,max=Math.max(...vals)*1.18,diff=max-min||1;
const pt=vals.map((v,i)=>[46+i*(328/Math.max(1,vals.length-1)),145-118*(v-min)/diff]);const points=pt.map(x=>x.join(',')).join(' ');
const showLabel=i=>i===0||i===vals.length-1||i%Math.ceil(vals.length/4)===0;
return `<div class="chart-wrap"><div class="chart-head"><b>${p.historyLabels?`${escaped(p.historyLabels[0]||'対象期間')}からの価格推移`:'参考価格の推移'}</b><span>${unit}</span></div><svg class="chart-svg" viewBox="0 0 420 207" role="img" aria-label="${escaped('価格推移：'+labels.map((l,i)=>`${l} ${vals[i]}${unit}`).join('、'))}"><path d="M46 25H374M46 85H374M46 145H374" stroke="#e2ece3" stroke-dasharray="3 4" fill="none"/><polyline fill="none" stroke="#318452" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" points="${points}"/>${pt.map(([x,y],i)=>`<circle cx="${x}" cy="${y}" r="4.5" fill="#318452" stroke="white" stroke-width="1.8"/><title>${escaped(labels[i]+' '+vals[i]+unit)}</title>${vals.length<=8||showLabel(i)?`<text x="${x}" y="${Math.max(16,y-13)}" text-anchor="middle" font-size="10.5" font-weight="700" fill="#2e5941">${vals[i].toLocaleString('ja-JP')}</text>`:''}${showLabel(i)?`<text x="${x}" y="171" text-anchor="middle" font-size="9" fill="#4a6151">${escaped((labels[i]||'').replace(/^\d{4}年/,''))}</text>`:''}`).join('')}</svg><p class="small-note">${escaped(note)} 実際の1尾売価・小売価格ではありません。</p>${p.historySources?.length?`<details class="small-note"><summary>各時点の価格と出典を確認</summary><div class="source-links">${labels.map((l,i)=>`<a href="${urlSafe(p.historySources[i])}" target="_blank" rel="noopener noreferrer">${escaped(l)}：${formatCurrency(vals[i])}${unit} ↗</a>`).join('')}</div></details>`:`<p class="small-note">対象：${escaped(labels.join('、'))}</p>`}</div>`}


function adjacentHistory(a,b,kind){
if(Number.isInteger(a.sequence)&&Number.isInteger(b.sequence))return b.sequence===a.sequence+1;
const [ay,am,ap]=a.period,[by,bm,bp]=b.period;
if(ay===by&&am===bm)return bp===ap+1;
const nextMonth=by*12+bm===ay*12+am+1;
return nextMonth&&bp===1&&(kind==='fish'?ap>=4:ap===3);
}
function historySegments(points,kind){
const segments=[];let segment=[];
for(const point of points){if(segment.length&&!adjacentHistory(segment[segment.length-1],point,kind)){segments.push(segment);segment=[]}segment.push(point)}
if(segment.length)segments.push(segment);return segments;
}
function dailySourceLinks(point,food){
const docs=typeof D!=='undefined'?(D.metadata.produceDailySourceSets?.[point.period.join('-')]||[]):[];
const filtered=docs.filter(d=>d.category===(food.category==='fruit'?'果実':'野菜'));
return filtered.length?'<details><summary>日別CSV '+filtered.length+'件</summary>'+filtered.map(d=>'<a href="'+urlSafe(d.url)+'" target="_blank" rel="noopener noreferrer">'+escaped(d.date)+' CSV ↗</a><br>').join('')+'</details>':'';
}
function longHistoryPanel(p,f,mode='timeline'){
const points=(p.longHistory||[]).filter(v=>Number.isFinite(v.price)&&v.price>0);
const range=p.longHistoryRange||[now.getFullYear()-5,now.getFullYear()];
const years=Array.from({length:range[1]-range[0]+1},(_,i)=>range[0]+i);
const kind=f.category==='fish'?'fish':'produce';
const label=v=>v.period[0]+'年'+v.period[1]+'月'+(kind==='fish'?'第'+v.period[2]+'週':['上旬','中旬','下旬'][v.period[2]-1]);
const counts=years.map(y=>({year:y,count:points.filter(v=>v.period[0]===y).length}));
const summary=counts.map(v=>v.year+'年 '+v.count+'時点').join('／');
if(!points.length)return '<div class="chart-wrap"><h4>過去5年＋今年の価格推移</h4><p class="small-note">この食材の過年度価格は未取得です。公的資料を取得できた期間から表示します。</p></div>';
const colors=['#58768b','#ae681e','#8260a9','#347a9c','#5c8436','#af4c55'];
const upper=Math.max(...points.map(v=>v.price))*1.12;
const x=v=>mode==='seasonal'?46+328*((v.period[1]-1)+(v.period[2]-.5)/(kind==='fish'?5:3))/12:46+328*((v.period[0]-range[0])+((v.period[1]-1)+(v.period[2]-.5)/(kind==='fish'?5:3))/12)/years.length;
const y=v=>151-121*v.price/upper;
const series=mode==='seasonal'?years.map((year,i)=>({color:colors[i%colors.length],points:points.filter(v=>v.period[0]===year)})):[{color:'#318452',points}];
const lines=series.map(s=>historySegments(s.points,kind).map(segment=>'<polyline fill="none" stroke="'+s.color+'" stroke-width="2" points="'+segment.map(v=>x(v).toFixed(2)+','+y(v).toFixed(2)).join(' ')+'"/>').join('')+s.points.map(v=>'<circle cx="'+x(v).toFixed(2)+'" cy="'+y(v).toFixed(2)+'" r="2.4" fill="'+s.color+'"><title>'+escaped(label(v)+' '+v.price+'円/kg'+(v.spec?'／'+v.spec:''))+'</title></circle>').join('')).join('');
const ticks=mode==='seasonal'?[1,3,5,7,9,12].map(m=>[46+328*(m-.5)/12,m+'月']):years.map((year,i)=>[46+328*(i+.5)/years.length,year+'年']);
const chart='<svg class="chart-svg" viewBox="0 0 420 194" role="img" aria-label="'+escaped(f.name+'の'+range[0]+'年から'+range[1]+'年の卸売価格推移。'+summary+'。欠測区間は線をつないでいません。下の表で値と出典を確認できます。')+'"><path d="M46 30H374M46 90H374M46 151H374" stroke="#e2ece3" stroke-dasharray="3 4" fill="none"/>'+[0,.5,1].map(r=>'<text x="40" y="'+(154-121*r)+'" text-anchor="end" font-size="9" fill="#4a6151">'+Math.round(upper*r).toLocaleString('ja-JP')+'</text>').join('')+lines+ticks.map(([tx,text])=>'<text x="'+tx+'" y="175" text-anchor="middle" font-size="9" fill="#4a6151">'+text+'</text>').join('')+'</svg>';
return '<section id="longHistoryPanel" class="chart-wrap"><div class="chart-head"><b>過去5年＋今年の価格推移</b><span>卸売・円/kg</span></div><div class="history-switch" role="group" aria-label="長期グラフの表示"><button type="button" data-history-mode="timeline" data-food="'+f.id+'" aria-pressed="'+(mode==='timeline')+'">時系列</button><button type="button" data-history-mode="seasonal" data-food="'+f.id+'" aria-pressed="'+(mode==='seasonal')+'">年ごとに比較</button></div>'+chart+(mode==='seasonal'?'<div class="history-legend">'+counts.map((v,i)=>'<span style="color:'+colors[i%colors.length]+'">● '+v.year+'年'+(!v.count?'（未取得）':'')+'</span>').join('')+'</div>':'')+'<p class="small-note">'+escaped(summary)+'。公表値を確認できた期間のみ表示し、欠測・未取得・取引なしの区間は補間していません。'+(kind==='fish'?'豊洲市場の同じ銘柄区分の中値です。産地・サイズの違いがあるため、比較は目安です。1尾換算の直近グラフとは単位が異なります。':'主要卸売市場計の卸売平均価格です。2021〜2022年の「日別再集計」は数量加重平均による参考推計で、旬別公表値ではありません。')+'</p><details class="small-note"><summary>長期データの価格・規格・出典（'+points.length+'時点）</summary><div class="history-table-wrap"><table class="history-table"><thead><tr><th>対象期間</th><th>円/kg</th>'+(kind==='fish'?'<th>産地・規格</th>':'')+'<th>出典</th></tr></thead><tbody>'+points.map(v=>'<tr><td>'+escaped(label(v))+'</td><td>'+formatCurrency(v.price)+(v.estimate?'（日別再集計）':'')+'</td>'+(kind==='fish'?'<td>'+escaped(v.spec||'未確認')+'</td>':'')+'<td><a href="'+urlSafe(v.sourceUrl)+'" target="_blank" rel="noopener noreferrer">原表 ↗</a>'+(v.estimate?dailySourceLinks(v,f):'')+'</td></tr>').join('')+'</tbody></table></div></details></section>';
}


function researchOverview(){
const status=D.metadata.foodResearchStatus;if(!status)return '';
const collected=D.foods.filter(f=>topicMap.has(f.id)).length;
return '<div class="info-card"><h2>全食材の継続調査</h2><p>登録した公的機関・JA等の新着一覧を毎日確認し、未掲載の食材を優先して資料本文を調べます。根拠を取得できた食材から更新します。掲載中の今年情報：'+collected+'／'+D.foods.length+'品目。新着一覧の確認と、本文の確認・掲載は別の段階です。</p><details><summary>全'+D.foods.length+'品目の調査状況を見る</summary><div class="history-table-wrap"><table class="history-table"><thead><tr><th>食材</th><th>分類</th><th>今年の掲載情報</th><th>新着一覧の最終確認</th><th>本文の最終確認</th></tr></thead><tbody>'+D.foods.map(f=>{const r=status[f.id]||{};return '<tr><td><button type="button" class="text-link" data-detail="'+f.id+'">'+escaped(f.name)+'</button></td><td>'+names[f.category]+'</td><td>'+(topicMap.has(f.id)?'資料あり':'未掲載')+'</td><td>'+escaped((r.lastIndexCheckedAt||'未確認').slice(0,10))+(r.indexStatus==='partial'?'（一部）':r.indexStatus==='error'?'（取得失敗）':'')+'</td><td>'+escaped((r.lastArticleCheckedAt||'未確認').slice(0,10))+'</td></tr>';}).join('')+'</tbody></table></div></details></div>';
}

function foodResearchInfo(f){
const r=D.metadata.foodResearchStatus?.[f.id];if(!r)return '';
const date=value=>value?new Date(value).toLocaleString('ja-JP',{timeZone:'Asia/Tokyo'}):'未確認';
const status=r.indexStatus==='ok'?'登録先の新着一覧を確認':r.indexStatus==='partial'?'登録先の一部を確認（取得できない情報源あり）':'今回、新着一覧を確認できませんでした';
const result=r.lastArticleResult==='source_text_found'?'食材に関する本文の記述を確認':r.lastArticleResult==='dedicated_pdf_parser_needed'?'PDFの形式に対応が必要':r.lastArticleResult?'対象期間や本文の条件を確認できず掲載保留':'該当資料の本文は未確認';
const sources=(D.metadata.topicDiscoverySources||[]).filter(s=>(r.sourceIds||[]).includes(s.id));
return '<details class="topic-evidence research-status"><summary>この食材の調査状況</summary><p>'+escaped(status)+'</p><p class="small-note">新着一覧の最終確認：'+escaped(date(r.lastIndexCheckedAt))+'<br>本文の最終確認：'+escaped(date(r.lastArticleCheckedAt))+'<br>'+escaped(result)+'</p>'+(!r.candidateCount?'<p class="small-note">今回確認した新着一覧では、食材名を含む候補リンクを検出していません。</p>':'')+'<p class="small-note">確認範囲は登録した情報源に限られます。調査を行っても、新しい情報が見つからないことがあります。</p><div class="source-links">'+sources.map(s=>'<a href="'+urlSafe(s.url)+'" target="_blank" rel="noopener noreferrer">↗ '+escaped(s.name)+'</a>').join('')+'</div></details>';
}

function topicEvidence(t){
return '<div class="topic-context"><span>'+escaped(t.scope||'対象地域は原文参照')+'</span><span>'+escaped(t.reportType||'公的資料の記述')+'</span></div>'+(t.evidenceSections?.length?'<details class="topic-evidence"><summary>根拠の原文・見通しを確認</summary>'+t.evidenceSections.map(s=>'<div><strong>'+escaped(s.label)+'</strong><p>'+escaped(s.text)+'</p></div>').join('')+(t.limitations?'<p class="small-note">'+escaped(t.limitations)+'</p>':'')+'<p class="small-note">'+(t.aiGenerated?'原文にない数値や一部の見通し表現を自動チェックしています。意味全体・産地・対象期間の照合には限界があり、別工程による検証は未実施です。確認処理が進行中という表示ではありません。原文もご確認ください。':'出典に基づく根拠情報を掲載しています。')+'</p></details>':'');
}


function extraTopicCards(f,main){
const others=activeTopics.filter(t=>t.foodId===f.id&&t.id!==main?.id);
if(!others.length)return '';
return '<div class="related-reports"><h4>この食材のほかの公的資料（'+others.length+'件）</h4>'+others.map(t=>'<details class="related-report"><summary>'+escaped(t.title)+'</summary><p class="small-note">対象：'+escaped(t.observedPeriod||'原文参照')+'／公表：'+escaped(t.publishedAt||'未確認')+'</p><p>'+escaped(t.summary)+'</p>'+topicEvidence(t)+'<div class="source-links">'+(t.sources||[]).map(s=>'<a href="'+urlSafe(s.url)+'" target="_blank" rel="noopener noreferrer">↗ '+escaped(s.title||s.name||'原文')+'</a>').join('')+'</div></details>').join('')+'</div>';
}

function fishHistoryTable(p,f){if(p.stale||!p.historicalPrices?.length || !p.normalPrice)return '';const statistic=f.category==='fish'?'中値':'卸売平均価格';return `<div class="info-card" style="margin-top:12px"><h3 style="margin:0 0 8px">参考平年比の計算に使った価格</h3><p class="small-note">${escaped(p.normalRatioBasis||'')}。年度をクリックすると元資料が開きます。</p><div class="comparison-grid">${p.historicalYears.map((year,i)=>`<a href="${urlSafe(p.historicalSources[i])}" target="_blank" rel="noopener noreferrer"><small>${year}年 ↗</small><strong>${formatCurrency(p.historicalPrices[i])}円/kg</strong>${p.historicalEstimates?.[i]?'<small>日別再集計・参考推計</small>':''}${p.historicalSpecs?.[i]?`<small>${escaped(p.historicalSpecs[i])}</small>`:''}</a>`).join('')}</div><p class="small-note">過去${p.historicalYears.length}年の比較年平均（単純平均）：${formatCurrency(p.normalPrice)}円/kg<br>今年の${statistic}：${formatCurrency(p.price)}円/kg<br>参考平年比：${p.normalRatio}%${p.normalRatioRange?`（丸め誤差を考慮した範囲：${p.normalRatioRange[0]}〜${p.normalRatioRange[1]}%）`:""}（今年の${statistic} ÷ 同時期の比較年平均 × 100）</p></div>`}
function fishWeightPanel(p,f){if(f.category!=='fish')return '';if(f.name==='カキ')return `<div class="legend-note"><strong>1個単価は換算できません。</strong> 公表値は殻付きでなく、むき身1kgの卸売価格です。むき身の数量と個数が対応しないため、1個価格を推定しません。</div>`;
const kg=weightOf(p,f);const hasOfficial=Number.isFinite(p.pieceWeightKg)&&p.pieceWeightKg>0;
return `<div class="fish-weight-panel"><strong>🐟 1${fishUnit(f)}あたりの参考価格の計算</strong><p>${hasOfficial?`サイズの目安：${escaped(p.pieceWeightSpec||'市場のサイズ情報')}。${escaped(p.pieceWeightBasis||'')}。`:'市場の表には1尾の重量が記載されていないため、初期値は設定していません。'}<br>1${fishUnit(f)}の重量を変えると、1${fishUnit(f)}価格と推移グラフを試算できます（実際の販売単価ではありません）。</p><div class="weight-controls"><label for="fishWeightInput">1${fishUnit(f)}の重量（kg）</label><input id="fishWeightInput" type="number" min="0.01" max="500" step="0.01" inputmode="decimal" value="${kg??''}" placeholder="例：0.8"><button type="button" data-apply-weight="${f.id}">この重さで計算</button></div><p class="small-note">元の公的価格：${formatCurrency(p.price)}円/kg。${!hasOfficial?'入力値は利用者による仮定で、市場の実測値ではありません。':''}</p></div>`;}

function openDetail(id,topicId){let f=foodMap.get(id);if(!f)return;const p=priceMap.get(id),t=(topicId?D.topics.find(t=>t.id===topicId):null)||relatedTopic(f);const status=p?priceStatus(p):null;const box=get('overlay');if(box.hidden)state.lastFocus=document.activeElement;const text=t?.yearSpecific?t.summary:`${f.name}の旬は地域・品種・漁期等で異なります。`;const src=t?.sources||[];
get('detailContent').innerHTML=`<div class="detail-top ${tone(f)}"><button type="button" class="detail-close" id="closeDetail" aria-label="閉じる">×</button><span class="big-emoji">${art(f)}</span></div><div class="detail-inner"><span class="eyebrow">${names[f.category]} · 食材の詳細</span><div class="detail-title-line"><div class="food-name-line"><h2 id="detailTitle">${escaped(f.name)}</h2>${priceIndicator(f.id)}</div><button class="fav-detail" data-fav="${f.id}">${state.fav.includes(id)?'♥ お気に入り済み':'♡ お気に入りに登録'}</button></div><p class="detail-sub">旬の目安：${f.seasonStart}月 ～ ${f.seasonEnd}月</p><h3>📰 今年の生育・出荷・漁況</h3>${t?.yearSpecific?`${pill(t.aiGenerated?'AI要約・自動チェック':'公的資料を確認して要約',t.aiGenerated?'demo':'')}<p class="detail-summary">${escaped(text)}</p>${topicEvidence(t)}<div class="source-links"><span class="small-note">対象期間：${escaped(t.observedPeriod||'要出典確認')}</span><span class="small-note">公表日：${escaped(t.publishedAt||'不明')}</span>${t.sourceUpdatedAt?`<span class="small-note">出典の更新日：${escaped(t.sourceUpdatedAt)}</span>`:''}<span class="small-note">アプリ反映：${escaped(String(t.retrievedAt||'未記録').slice(0,10))}</span>${src.map(x=>`<a href="${urlSafe(x.url)}" target="_blank" rel="noopener noreferrer">↗ ${escaped(x.name||'出典原文を確認')}</a>`).join('')}</div>`:`<p class="detail-summary">この食材の今年の状況について、出典付きの情報はまだ収録されていません。</p>`}
${extraTopicCards(f,t)}${foodResearchInfo(f)}<h3>📈 ${f.category==='fish'?'1尾あたりの参考価格':'卸売価格'} ${p?pill(f.category==='fish'?'東京都豊洲市場の公的統計':'農林水産省の公的統計'):pill('データ未収録','demo')}</h3>${p?`<div class="detail-stats"><div class="detail-stat"><small>${f.category==='fish'?'市場1'+fishUnit(f)+'参考換算（卸売）':escaped(p.priceStatistic||p.market||'卸売価格・円/kg')}</small><strong>${f.category==='fish'?(oneFish(p,f)==null?'換算不可':`約 ${formatCurrency(oneFish(p,f))} <em>円/${fishUnit(f)}</em>`):`${formatCurrency(p.price)} <em>円/kg</em>`}</strong></div><div class="detail-stat"><small>${f.category==='fish'?'参考平年比と判定':'平年比と判定'}</small><strong>${p.normalRatio!=null?p.normalRatio+'%':'—'}</strong> ${pill(status[0],status[1])}</div></div><p class="small-note">${f.category==='fish'?'前年同期比':'前年同旬比'}：${p.yearAgoRatio!=null?p.yearAgoRatio+'%':'未公表'}（前年を100%）。統計上の品目：${escaped(p.statisticalItem||f.name)}${p.brandDetail?`／主な規格：${escaped(p.brandDetail)}`:''}</p>${f.category==='fish'?fishWeightPanel(p,f):''}${sparkSvg(p,f)}${longHistoryPanel(p,f)}${p.historicalPrices?fishHistoryTable(p,f):''}${p.note?`<div class="legend-note">${escaped(p.note)}</div>`:''}<div class="source-links"><span class="small-note">対象期間：${escaped(p.period)}</span><span class="small-note">出典の公表日：${escaped(p.publishedAt||'未確認')}</span><span class="small-note">アプリ反映：${escaped(p.retrievedAt||'未記録')}</span><a href="${urlSafe(p.sourceUrl)}" target="_blank" rel="noopener noreferrer">↗ ${f.category==='fish'?'東京都の週間市況（原表）':'農林水産省の統計原表'}</a></div>`:`<div class="empty"><strong>卸売価格は未収録です</strong><span>${f.category==='fish'?'豊洲の週間市況に掲載されない魚種・銘柄、または中値がないため未収録です。':'対象旬に取引がない等の可能性があります。'}</span></div>`}</div>`;box.hidden=false;document.body.style.overflow='hidden';get('closeDetail').focus()}
function closeDetail(){get('overlay').hidden=true;document.body.style.overflow='';state.lastFocus?.focus?.()}
function toast(msg){let el=get('toast');el.textContent=msg;el.classList.add('show');clearTimeout(window.__toastTimeout);window.__toastTimeout=setTimeout(()=>el.classList.remove('show'),2700)}
function updateChrome(){const labels={topics:'旬の話題',prices:'食材の価格',calendar:'旬カレンダー',favorites:'お気に入り',about:'情報の見方・出典'};get('breadcrumbPage').textContent=labels[state.page];document.querySelectorAll('.nav-item').forEach(b=>b.classList.toggle('active',b.dataset.page===state.page));get('asideMonth').textContent=`${currentMonth}月の旬`;
get('todayLabel').textContent=`${Number(todayJst.slice(0,4))}年${currentMonth}月${Number(todayJst.slice(8,10))}日`;}
function refresh(opts={}){const focus=opts.preserve&&document.activeElement?.id, pos=opts.preserve?window.scrollY:0;
const html={topics:renderTopics,prices:renderPrices,calendar:renderCalendar,favorites:renderFavorites,about:renderAbout}[state.page]()+ (state.page==="about"?researchOverview():"");get('content').innerHTML=html;updateChrome();if(opts.preserve){window.scrollTo(0,pos);if(focus)get(focus)?.focus()} }
function pageTo(page){if(!['topics','prices','calendar','favorites','about'].includes(page))return;closeDetail();state.page=page;state.query='';get('sidebar').classList.remove('open');let shade=get('mobileShade');if(shade)shade.classList.remove('show');refresh();window.scrollTo({top:0,behavior:'instant'});history.replaceState({},'',`#${page}`)}
get('sidebar').insertAdjacentHTML('afterend','<div id="mobileShade" class="mobile-shade"></div>');
document.addEventListener('click',e=>{if(e.target.closest('#closeDetail')){closeDetail();return}const fav=e.target.closest('[data-fav]');if(fav){e.stopPropagation();toggleFav(fav.dataset.fav);return}
const weightBtn=e.target.closest('[data-apply-weight]');if(weightBtn){const val=Number(get('fishWeightInput')?.value);if(!Number.isFinite(val)||val<0.01||val>500){toast('0.01～500kgの重量を入力してください');return}state.customFishWeights[weightBtn.dataset.applyWeight]=val;const pricePane=get('priceResults');if(pricePane)pricePane.innerHTML=priceTable(filteredPrices());openDetail(weightBtn.dataset.applyWeight);toast('指定した重量で参考価格を再計算しました');return}
const historyBtn=e.target.closest('[data-history-mode]');if(historyBtn){const food=foodMap.get(historyBtn.dataset.food);get('longHistoryPanel').outerHTML=longHistoryPanel(priceMap.get(food.id),food,historyBtn.dataset.historyMode);get('longHistoryPanel').querySelector('[data-history-mode="'+historyBtn.dataset.historyMode+'"]').focus();return}
const nav=e.target.closest('[data-page]');if(nav){e.preventDefault();pageTo(nav.dataset.page);return}
const detail=e.target.closest('[data-detail]');if(detail){openDetail(detail.dataset.detail,detail.dataset.topic);return}
const cat=e.target.closest('[data-category]');if(cat){state.category=cat.dataset.category;refresh({preserve:true});return}
const pricestatus=e.target.closest('[data-pricestatus]');if(pricestatus){state.priceOnly=pricestatus.dataset.pricestatus;refresh({preserve:true});return}
const cal=e.target.closest('[data-calcategory]');if(cal){state.calendarCategory=cal.dataset.calcategory;refresh({preserve:true});return}
if(e.target.closest('#prevMonth')){state.month=state.month===1?12:state.month-1;refresh({preserve:true});return}
if(e.target.closest('#nextMonth')){state.month=state.month===12?1:state.month+1;refresh({preserve:true});return}
if(e.target.closest('#sideCalendar')){pageTo('calendar');return}
if(e.target.closest('#mobileMenu')){get('sidebar').classList.add('open');get('mobileShade').classList.add('show');return}
if(e.target.closest('#mobileShade')){get('sidebar').classList.remove('open');get('mobileShade').classList.remove('show');return}
if(e.target.closest('#regionBtn')){get('regionPopover').hidden=!get('regionPopover').hidden;get('regionBtn').setAttribute('aria-expanded',String(!get('regionPopover').hidden));return}
const region=e.target.closest('[data-region]');if(region){get('regionPopover').hidden=true;if(region.dataset.region==='ehime')toast('愛媛県版は全国版での実データ検証後に対応します');else toast('全国版を表示しています');return}
if(!e.target.closest('#regionPopover'))get('regionPopover').hidden=true;
});
get('overlayBackdrop').addEventListener('click',closeDetail);document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(!get('overlay').hidden)closeDetail();else get('regionPopover').hidden=true}if((e.key==='Enter'||e.key===' ')&&e.target.matches('.food-row')){e.preventDefault();openDetail(e.target.dataset.detail)} });
document.addEventListener('input',e=>{if(e.target.id==='priceSearch'){state.query=e.target.value;const node=get('priceResults');node.innerHTML=priceTable(filteredPrices());const cnt=document.querySelector('.results-count');if(cnt)cnt.textContent=`${filteredPrices().length}件 / ${D.prices.length}件`}});
document.addEventListener('change',e=>{if(e.target.id==='priceSort'){state.sort=e.target.value;refresh({preserve:true})}});
if(!D||!Array.isArray(D.foods)){get('content').innerHTML='<div class="empty"><strong>データの読み込みに失敗しました</strong><span>data.js の存在を確認してください。</span></div>';return}
const hash=location.hash.slice(1);if(['topics','prices','calendar','favorites','about'].includes(hash))state.page=hash;refresh();
})();
