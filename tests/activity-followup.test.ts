import test from 'node:test'
import assert from 'node:assert/strict'
import { followupProgress } from '../product/ui/activity/followup.js'
import type { MandateView } from '../product/ui/mandates/model.js'
const item = (extra:any={}) => ({mandate:{mandate_id:'m',status:'tracking'},revision:{contact_policy:{mode:'condition'},scope:{entity_id:'SEC:CN:A:600519'},basis:{},goal:'研究'},executions:[],monitoring:{enabled:true,detail:'每分钟检查行情'},...extra}) as MandateView

test('只按保存的执行记录区分研究中与等待开始，跟进配置不等于正在执行',()=>{
 const rows=followupProgress([item(),item({mandate:{mandate_id:'q',status:'tracking'},executions:[{status:'queued',updated_at:2}]}),item({mandate:{mandate_id:'r',status:'tracking'},executions:[{status:'running',updated_at:3}]})])
 assert.deepEqual(rows.map(r=>r.kind),['running','queued','waiting'])
 assert.equal(rows.find(r=>r.kind==='running')?.updatedAt,3)
 assert.match(rows.find(r=>r.kind==='waiting')!.detail,/每分钟/)
})
test('暂停或结束不按残留执行记录显示为正在跟进',()=>{
 assert.equal(followupProgress([item({mandate:{status:'paused'},executions:[{status:'running'}]}),item({mandate:{status:'ended'}})]).length,0)
})
test('来源问题、执行失败与未接通明确展示，不冒充正常等待',()=>{
 const rows=followupProgress([item({monitoring:{enabled:false,detail:'当前范围尚未接入'}}),item({executions:[{status:'failed',updated_at:3}]}),item({source_check:{status:'unknown',detail:'provider_timeout'}})])
 assert.deepEqual(rows.map(r=>r.kind),['attention','attention','unavailable'])
 assert.match(rows[1].detail,/超时/)
})
test('定时等待以已保存日程为准，缺失日程不声称已安排',()=>{
 const revision={...item().revision,contact_policy:{mode:'scheduled_delivery'}}
 const waiting=followupProgress([item({revision,monitoring:{enabled:false,detail:''},schedules:[{enabled:true,next_due_at:'2026-10-30T01:15:00Z',timezone:'Asia/Shanghai'}]})])[0]
 assert.equal(waiting.kind,'waiting');assert.match(waiting.detail,/09:15/)
 assert.equal(followupProgress([item({revision,monitoring:{enabled:false,detail:''},schedules:[]})])[0].kind,'unavailable')
})
