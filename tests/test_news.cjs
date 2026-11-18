const {test}=require('node:test'),assert=require('node:assert/strict'),N=require('../news.js');
const topic={id:'t',foodId:'f',sourceType:'news',newsArticleId:'n',sources:[{url:'https://example.com/article/1'}]};
const row={id:'n',url:'https://example.com/article/1?utm_source=x',status:'used',foodIds:['f'],uses:[{topicId:'t',foodId:'f'}]};
const data={foods:[{id:'f'}],topics:[topic],news:{articles:[row]}};
test('dashboard counts only articles actually used by a matching published summary',()=>{assert.equal(N.stats(N.articles(data)).used,1);assert.equal(N.stats(N.articles({...data,topics:[]})).used,0);});
test('a collected or AI-pending article cannot masquerade as a used article',()=>{const d={...data,topics:[],news:{articles:[{...row,status:'pending',uses:[]}]}};assert.equal(N.stats(N.articles(d)).pending,1);assert.equal(N.stats(N.articles(d)).used,0);});
test('syndication/tracking and multiple food uses never inflate the article count',()=>{assert.equal(N.articles({...data,news:{articles:[row,{...row,url:'https://example.com/article/1?display=1'}]}}).length,1);});
test('incorrect food, topic, source or non-HTTPS links are not accepted as provenance',()=>{for(const t of [{...topic,foodId:'other'},{...topic,newsArticleId:'other'},{...topic,sourceType:'official'},{...topic,sources:[{url:'https://example.com/different'}]}])assert.equal(N.stats(N.articles({...data,topics:[t]})).used,0);assert.deepEqual(N.articles({...data,news:{articles:[{...row,url:'javascript:alert(1)'}]}}),[]);});
