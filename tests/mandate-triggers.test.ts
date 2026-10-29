import test from 'node:test'
import assert from 'node:assert/strict'
import { mandateHooks, triggerKind, nextTrigger, matchesTrigger } from '../product/ui/mandates/triggers.js'
import type { MandateView } from '../product/ui/mandates/model.js'
const item = (extra: any = {}) => ({mandate:{status:'tracking'}, revision:{contact_policy:{mode:'condition'}}, monitoring:{enabled:true,detail:'每分钟检查行情；来源未知保留未知'}, dependencies:[{hook_type:'market.quote_changed',active:true}],schedules:[],...extra}) as MandateView

test('Hook 从当前已登记依赖和日程投影；未知类型保留、去重，不增加推测的 Hook', () => {
 const x=item({dependencies:[{hook_type:'market.quote_changed',active:true},{hook_type:'market.quote_changed',active:true},{hook_type:'future.event',active:true},{hook_type:'disabled.event',active:false}]})
 assert.deepEqual(mandateHooks(x).map(h=>h.id),['market.quote_changed','future.event'])
 assert.equal(mandateHooks(x)[1].label,'其他变化')
 assert.equal(triggerKind(x),'source')
 assert.equal(matchesTrigger(x,'source'),true)
})
test('定时委托显示真实保存日程，暂停/结束保留定义但不声称会触发',()=>{
 const x=item({revision:{contact_policy:{mode:'scheduled_delivery'}},dependencies:[],schedules:[{enabled:true,next_due_at:'2026-10-30T01:15:00Z',timezone:'Asia/Shanghai'}]})
 assert.equal(triggerKind(x),'scheduled_delivery')
 assert.deepEqual(mandateHooks(x).map(h=>h.id),['schedule.due'])
 assert.match(nextTrigger(x),/09:15/)
 assert.equal(nextTrigger({...x,mandate:{...x.mandate,status:'paused'}}),'恢复委托后再跟进')
 assert.equal(nextTrigger({...x,mandate:{...x.mandate,status:'ended'}}),'已结束')
 assert.match(nextTrigger(item({revision:{contact_policy:{mode:'periodic_check'}},dependencies:[],schedules:[]})),/日程.*核对/)
})
test('未接入与空集合明确表示未知，筛选可组合且不把没有日程当来源订阅',()=>{
 const x=item({dependencies:[],schedules:[],monitoring:{enabled:false,detail:'当前范围尚未接入'}})
 assert.equal(triggerKind(x),'unconnected');assert.equal(matchesTrigger(x,'all'),true)
 assert.deepEqual(mandateHooks(x),[])
 assert.match(nextTrigger(x),/未接入/)
})

test('已暂停来源委托仍按保存定义筛选，不误标成未接入',()=>{
 const x=item({mandate:{status:'paused'},revision:{contact_policy:{mode:'condition'},triggers:[{hook_type:'company.profile_changed'}]},dependencies:[],schedules:[]})
 assert.equal(matchesTrigger(x,'source'),true)
 assert.equal(nextTrigger(x),'恢复委托后再跟进')
 assert.deepEqual(mandateHooks(x).map(h=>h.id),['company.profile_changed'])
})
