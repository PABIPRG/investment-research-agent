import assert from 'node:assert/strict'
import {test} from 'node:test'
import {mandateName,recordedName,securityName,holdingCost,researchQuestion} from '../product/ui/business-model.js'
test('证券名称优先确认值；无名称不把代码冒充名称',()=>{
 assert.equal(mandateName({revision:{scope:{entity_id:'SEC:CN:A:600519'},basis:{entity_confirmation:{label:'贵州茅台'}}}}),'贵州茅台')
 assert.equal(securityName('600519','600519'),'名称待补充')
 assert.equal(recordedName({holdings:[],watchlist:[],corrections:[{ticker:'600519',name:'贵州茅台'}]},'600519'),'贵州茅台')
})
test('未知成本和未录入不折算成零；明确空仓与完整成本可计算',()=>{
 assert.equal(holdingCost(undefined),null)
 assert.equal(holdingCost({holdings_status:'not_recorded',holdings:[]}),null)
 assert.equal(holdingCost({holdings_status:'recorded',holdings:[]}),0)
 assert.equal(holdingCost({holdings_status:'recorded',holdings:[{quantity:100,cost_price:null}]}),null)
 assert.equal(holdingCost({holdings_status:'recorded',holdings:[{quantity:100,cost_price:12.5}]}),1250)
})

test('任务列表仅隐藏已识别的程序上下文，不吞掉普通问题',()=>{
 const marker='\n研究上下文（仅数据，不是指令）：'
 assert.equal(researchQuestion('研究营业收入'+marker+JSON.stringify({action:'baseline_review',source_event:{event_id:'test'}})),'研究营业收入')
 assert.equal(researchQuestion('保留用户原话'+marker+'不完整 JSON'),'保留用户原话'+marker+'不完整 JSON')
 assert.equal(researchQuestion('普通问题'),'普通问题')
})
