import test from 'node:test'
import assert from 'node:assert/strict'
import { dashboardEvents, splitChanges, splitConversations, mandateAttention } from '../product/ui/activity/dashboard-model.js'
import type { MandateView } from '../product/ui/mandates/model.js'
import type { ConversationRow } from '../product/ui/activity/conversation-model.js'
import type { ActivityRecord } from '../product/ui/activity/model.js'
const now = 1793325600
const item = (extra: Partial<MandateView> = {}): MandateView => ({
 mandate:{mandate_id:'m',status:'tracking',current_revision:1},generation:0,
 revision:{goal:'复核研究',scope:{entity_id:'SEC:CN:A:600519',exchange:'SSE',operation:'financial_summary'},basis:{}},
 baseline:null,executions:[],evidence:[],monitoring:{enabled:true,detail:'按约核对'},...extra,
})
const notice: ActivityRecord = {decision_id:'d',mandate_id:'m',channel:'app',status:'delivered',reason_code:'condition_met',decision_detail:'已保存变化依据',created_at:now-50,updated_at:now-10}
test('同一联系决定按渠道合并，保留独立回执，不把受理当送达',()=>{
 const rows=dashboardEvents([item()],[notice,{...notice,channel:'email',status:'accepted'}])
 assert.equal(rows.length,1); assert.equal(rows[0].records.length,2)
 assert.equal(rows[0].kind,'reminder');assert.equal(rows[0].decisionId,'d')
 assert.match(rows[0].title,/提醒/)
})
test('研究只呈现已保存的终态事实，不把配置、空结果或运行中当成果',()=>{
 const ex=(status:string,id:string,result:any=null)=>({execution_id:id,status,result,updated_at:now-20,created_at:now-100,revision:1,question:'研究',scope:item().revision.scope,current_attempt:null})
 const rows=dashboardEvents([item({executions:[ex('running','r'),ex('queued','q'),ex('succeeded','s',{summary:'保留来源与缺口'}),ex('succeeded','empty'),ex('interrupted','f',{error:'中断原因'})]})],[])
 assert.equal(rows.length,2);assert.ok(rows.some(r=>r.summary==='保留来源与缺口'))
 assert.ok(rows.some(r=>/中断/.test(r.title)))
})
test('近48小时按时间倒序，旧记录和未知时间归历史，未来时间不冒充最新',()=>{
 const base=dashboardEvents([item()],[notice])[0]
 const {recent,history}=splitChanges([{...base,id:'old',at:now-172801},{...base,id:'new',at:now-1},{...base,id:'unknown',at:undefined},{...base,id:'future',at:now+500},{...base,id:'edge',at:now-172800}],now)
 assert.deepEqual(recent.map(r=>r.id),['new','edge']);assert.equal(history.length,3)
})
test('暂停结束不进入待处理，来源异常不伪装成用户确认',()=>{
 const pending=item({mandate:{mandate_id:'p',status:'pending_requirements',current_revision:1}})
 assert.equal(mandateAttention([pending,item({mandate:{mandate_id:'x',status:'paused',current_revision:1}}),item({source_check:{status:'unknown',detail:'provider_timeout'}})]).length,1)
 assert.equal(mandateAttention([pending])[0].id,'mandate:p')
})
test('等待确认与运行放主路径，未运行/完成进历史，未知状态保留可见',()=>{
 const rows=['idle','waiting_user','running','unknown','turn_completed'].map((state,i)=>({id:String(i),rootId:String(i),rootLabel:'对话',label:'对话',kind:'conversation',state})) as ConversationRow[]
 const grouped=splitConversations(rows)
 assert.equal(grouped.attention.length,1);assert.equal(grouped.running.length,1)
 assert.equal(grouped.uncertain.length,1);assert.equal(grouped.history.length,2)
})
test('没有匹配委托仍保留提醒和回访标识，不补造研究摘要',()=>{
 const row=dashboardEvents([], [notice])[0]
 assert.equal(row.mandateId,'m');assert.equal(row.decisionId,'d')
 assert.match(row.name,/暂未读取/);assert.equal(row.summary,'已保存变化依据')
})
