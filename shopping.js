/* Shared, deterministic selection rules. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.SHUN_SHOPPING=api;})(typeof window!=='undefined'?window:globalThis,function(){
'use strict';
function observationEnd(p){
 const v=(p.historyPeriods||[]).at(-1);
 if(!Array.isArray(v)||v.length!==3)return '';
 const [y,m,n]=v;if(!Number.isInteger(y)||m<1||m>12||n<1)return '';
 const fish=p.longHistoryFrequency==='weekly'||/週/.test(p.period||'');
 const day=fish?Math.min(n*7,new Date(Date.UTC(y,m,0)).getUTCDate()):n===3?new Date(Date.UTC(y,m,0)).getUTCDate():n*10;
 return y+'-'+String(m).padStart(2,'0')+'-'+String(day).padStart(2,'0');
}
function eligiblePrice(p,today){
 if(!p||p.sample||p.stale||p.classificationUncertain||!Number.isFinite(p.normalRatio)||p.normalRatio<=0||p.normalRatio>=100)return false;
 if((p.historicalSampleCount??p.historicalYears?.length??0)<3||!/^https:\/\//.test(p.sourceUrl||''))return false;
 if(p.normalRatioRange&&(!Array.isArray(p.normalRatioRange)||p.normalRatioRange.length!==2||p.normalRatioRange.some(v=>!Number.isFinite(v))||p.normalRatioRange[1]>=100))return false;
 const end=observationEnd(p),age=(Date.parse(today)-Date.parse(end))/86400000;
 return !!end&&Number.isFinite(age)&&age>=0&&age<=35;
}
function eligibleRecipes(recipes,prices,today){
 const map=new Map(prices.filter(p=>eligiblePrice(p,today)).map(p=>[p.foodId,p]));
 return recipes.filter(r=>Array.isArray(r.ingredients)&&new Set(r.ingredients.map(i=>i.foodId)).size>=2&&r.ingredients.every(i=>i.grams>=50&&map.has(i.foodId)))
 .map(r=>({...r,matched:r.ingredients.map(i=>({...i,price:map.get(i.foodId)}))}))
 .sort((a,b)=>a.matched.reduce((s,i)=>s+i.price.normalRatio,0)/a.matched.length-b.matched.reduce((s,i)=>s+i.price.normalRatio,0)/b.matched.length);
}
function retailForFood(records,foodId,region){
 return records.filter(r=>r.foodId===foodId&&r.regionId===region&&Number.isFinite(r.price)&&r.price>0)
 .sort((a,b)=>String(b.observationEnd).localeCompare(String(a.observationEnd))||String(a.specification).localeCompare(String(b.specification),'ja'));
}
function retailCoverage(records,region,foodId){
 const valid=records.filter(r=>(!foodId||r.foodId===foodId)&&Number.isFinite(r.price)&&r.price>0);
 const byRegion=new Map();
 for(const r of valid){if(!byRegion.has(r.regionId))byRegion.set(r.regionId,new Set());byRegion.get(r.regionId).add(r.foodId);}
 return {totalFoods:new Set(valid.map(r=>r.foodId)).size,selectedFoods:byRegion.get(region)?.size||0,byRegion:Object.fromEntries([...byRegion].map(([k,v])=>[k,v.size])),cityCount:[...byRegion.keys()].filter(k=>k!=='national').length};
}
function topicLevel(t){
 if(t.geographicLevel)return t.geographicLevel;
 const u=t.sources?.[0]?.url||'';
 if(u.includes('/press/nousan/engei/'))return 'national_outlook';
 if(u.includes('shijou.metro.tokyo'))return 'market';
 if(/fra.go.jp|jafic.or.jp/.test(u))return 'sea_area';
 return 'regional';
}
return {observationEnd,eligiblePrice,eligibleRecipes,retailForFood,retailCoverage,topicLevel};
});
