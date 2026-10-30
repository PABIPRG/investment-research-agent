import test from 'node:test'
import assert from 'node:assert/strict'
import {ingest,acknowledge,type ReminderState} from '../product/ui/reminders/model.js'
const initial:ReminderState={scope:'',seen:[],pending:[]}
const row=(id:string,created_at:number)=>({id,created_at,kind:'test' as const,title:'测试',body:'已明确确认'})
test('首次历史只建立基线；新ID排队不依赖客户端/服务端时钟一致',()=>{
 const baseline=ingest(initial,{scope:'one',items:[row('history',1000)]},true)
 assert.equal(baseline.pending.length,0)
 const first=ingest(baseline,{scope:'one',items:[row('history',1000),row('new',1)]})
 assert.deepEqual(first.pending.map(x=>x.id),['new'])
 const next=ingest(first,{scope:'one',items:[row('new',2),row('second',3)]})
 assert.deepEqual(next.pending.map(x=>x.id),['new','second'])
 assert.deepEqual(acknowledge(next,'new').pending.map(x=>x.id),['second'])
 assert.equal(ingest(acknowledge(next,'new'),{scope:'one',items:[row('new',4)]}).pending.length,1)
})
test('刷新恢复待回应ID；更换实例不会带入上一实例的内容',()=>{
 assert.equal(ingest(initial,{scope:'one',items:[row('saved',1)]},true,['saved']).pending.length,1)
 const next=ingest({scope:'old',seen:[],pending:[row('old',9)]},{scope:'new',items:[]},true)
 assert.equal(next.pending.length,0)
})
