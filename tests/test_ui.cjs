const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../app.js'),'utf8');
function context(){
  const ctx=vm.createContext({state:{customFishWeights:{}}});
  const weight=source.slice(source.indexOf('const weightOf='),source.indexOf('const oneFish='));
  const series=source.slice(source.indexOf('function chartSeries('),source.indexOf('function sparkSvg('));
  const status=source.slice(source.indexOf('const priceStatus='),source.indexOf('const priceIndicator='));
  vm.runInContext(weight+series+status+';this.series=chartSeries;this.status=priceStatus;',ctx);
  return ctx;
}
test('fish trend uses the weight published for each week',()=>{
  const result=context().series({price:1000,pieceWeightKg:.2,history:[1000,1000],historyPieceWeights:[.1,.2]}, {id:'f',name:'サンマ',category:'fish'});
  assert.deepEqual(Array.from(result.vals),[100,200]);
});
test('missing weekly weights keep the public kg series',()=>{
  const result=context().series({pieceWeightKg:.2,history:[1000,2000],historyPieceWeights:[null,.2]}, {id:'f',name:'サンマ',category:'fish'});
  assert.deepEqual(Array.from(result.vals),[1000,2000]);
  assert.equal(result.unit,'円/kg');
});
test('an explicit user weight is applied consistently',()=>{
  const ctx=context();ctx.state.customFishWeights.f=.5;
  const result=ctx.series({pieceWeightKg:.2,history:[1000,2000],historyPieceWeights:[.1,.2]}, {id:'f',name:'サンマ',category:'fish'});
  assert.deepEqual(Array.from(result.vals),[500,1000]);
});
test('shelled oysters are never converted to one oyster',()=>{
  const ctx=context();ctx.state.customFishWeights.f=.5;
  const result=ctx.series({pieceWeightKg:.2,history:[1000],historyPieceWeights:[.1]}, {id:'f',name:'カキ',category:'fish'});
  assert.equal(result.unit,'円/kg');
});
test('classification includes both boundaries in normal and ignores stale values',()=>{
  const ctx=context();
  assert.equal(ctx.status({normalRatio:84.9})[1],'low');
  assert.equal(ctx.status({normalRatio:85})[1],'mid');
  assert.equal(ctx.status({normalRatio:115})[1],'mid');
  assert.equal(ctx.status({normalRatio:115.1})[1],'high');
  assert.equal(ctx.status({normalRatio:120,stale:true})[1],'demo');
  assert.equal(ctx.status({normalRatio:null})[1],'demo');
});
