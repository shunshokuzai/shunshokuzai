/* News use is derived from published topics, never inferred from crawl success. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.SHUN_NEWS=api;})(typeof window!=='undefined'?window:globalThis,function(){
'use strict';
function canonical(value){try{const u=new URL(value);if(u.protocol!=='https:')return '';u.hash='';for(const k of [...u.searchParams.keys()])if(k.startsWith('utm_')||['page','display','fbclid','gclid'].includes(k))u.searchParams.delete(k);return u.href.replace(/\/$/,'');}catch{return '';}}
function articles(data){
 const topics=new Map((data.topics||[]).map(t=>[t.id,t])),foods=new Set((data.foods||[]).map(f=>f.id));
 const result=new Map();
 for(const r of data.news?.articles||[]){
  if(!canonical(r.url))continue;
  const uses=(r.uses||[]).filter(u=>{const t=topics.get(u.topicId);return t&&t.sourceType==='news'&&t.newsArticleId===r.id&&t.foodId===u.foodId&&foods.has(u.foodId)&&canonical(t.sources?.[0]?.url)===canonical(r.url);});
  const used=uses.length>0;
  const value={...r,status:used?'used':r.status==='used'?'held':r.status,uses,foodIds:used?[...new Set(uses.map(u=>u.foodId))]:(r.foodIds||[]).filter(id=>foods.has(id))};
  const key=canonical(r.url),old=result.get(key);
  if(old){old.uses=[...new Map([...old.uses,...uses].map(u=>[u.topicId,u])).values()];old.foodIds=[...new Set([...old.foodIds,...value.foodIds])];if(old.uses.length)old.status='used';}
  else result.set(key,value);
 }
 return [...result.values()].sort((a,b)=>String(b.publishedAt||'').localeCompare(String(a.publishedAt||'')));
}
function stats(rows){const used=rows.filter(r=>r.status==='used');return {used:used.length,foods:new Set(used.flatMap(r=>r.foodIds)).size,pending:rows.filter(r=>r.status!=='used').length};}
return {articles,stats,canonical};
});
