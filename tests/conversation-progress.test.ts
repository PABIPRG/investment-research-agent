import test from 'node:test'
import assert from 'node:assert/strict'
import { conversationProgress } from '../product/ui/activity/conversation-model.js'
import type { ChatList, ChatSummary } from '../product/ui/history.js'
const row = (id: string, extra: Partial<ChatSummary> = {}): ChatSummary => ({id,title:id,running:false,blank:false,updatedAt:1000,projectionValues:{agentPreset:'huohuo'},...extra})
const list = (rows: ChatSummary[], projectionsBySession: any = {}): ChatList => ({ids:rows.map(r=>r.id),byId:Object.fromEntries(rows.map(r=>[r.id,r])),phase:'ready',projectionsBySession})
const ready = (values:any) => ({state:'ready' as const,values})
const derive = (l:ChatList, statuses:any=new Map(), extra:any={}) => conversationProgress(l,statuses,{connected:true,archiveReady:true,archived:[],...extra})

test('会话实时false覆盖旧true，等待确认与运行分开；未运行不冒充已完成',()=>{
 const result=derive(list([row('a',{running:true}),row('b')]),new Map([['a',{running:false}],['b',{running:true,pendingInteraction:{kind:'approval'}}]]))
 assert.equal(result.rows.find(r=>r.id==='a')?.state,'idle')
 assert.equal(result.rows.find(r=>r.id==='b')?.state,'waiting_user')
})
test('只沿可见火火父目录发现子任务；普通fork是独立对话，后台与归档不混入',()=>{
 const result=derive(list([row('root'),row('fork',{parentId:'root'}),row('foreign',{projectionValues:{agentPreset:'standard'}}),row('archived'),row('orphan',{origin:'subagent',parentId:'root'}),row('blank',{blank:true})],{root:ready({subagentCatalog:[{id:'c',mode:'one-shot',createdAt:2000,label:'查资料'}]}),foreign:ready({subagentCatalog:[{id:'hidden',mode:'one-shot'}]})}),new Map([['c',{running:true}]]),{archived:['archived']})
 assert.deepEqual(result.rows.map(r=>r.id).sort(),['c','fork','root'])
 assert.equal(result.rows.find(r=>r.id==='c')?.rootId,'root')
 assert.equal(result.rows.find(r=>r.id==='c')?.state,'running')
})
test('子任务停止与本轮完成必须有不同事实，未读取状态保留未知',()=>{
 const l=list([row('root')],{root:ready({subagentCatalog:[{id:'c',mode:'continuable',createdAt:1,label:'研究'}]}),c:ready({subagentTiming:{lastTurnCompleted:true}})})
 assert.equal(derive(l).rows.find(r=>r.id==='c')?.state,'unknown')
 assert.equal(derive(l,new Map([['c',{running:false}]])).rows.find(r=>r.id==='c')?.state,'turn_completed')
 l.projectionsBySession!.c=ready({subagentTiming:{lastTurnCompleted:false}})
 assert.equal(derive(l,new Map([['c',{running:false}]])).rows.find(r=>r.id==='c')?.state,'turn_stopped')
})
test('外部和未知模式、断线、未完成基线不折叠成空闲或零任务',()=>{
 const l=list([row('root')],{root:ready({subagentCatalog:[{id:'e',mode:'external',createdAt:1},{id:'u',mode:'unknown',createdAt:1}]})})
 assert.equal(derive(l).rows.find(r=>r.id==='e')?.state,'external')
 assert.equal(derive(l).complete,false)
 assert.equal(derive(l).rows.find(r=>r.id==='u')?.state,'unknown')
 const lost=derive(l,new Map([['root',{running:true}]]),{connected:false})
 assert.ok(lost.rows.every(r=>r.state==='unknown'));assert.equal(lost.complete,false)
 assert.equal(derive({...l,phase:'pending'}).ready,false)
 assert.equal(derive(l,new Map(),{archiveReady:false}).ready,false)
})
test('目录读取失败标记不完整；循环与重复条目不无限展开，单个子任务只计一次',()=>{
 const l=list([row('root')],{root:ready({subagentCatalog:[{id:'c',mode:'one-shot',createdAt:1},{id:'c',mode:'one-shot',createdAt:1}]}),c:ready({subagentCatalog:[{id:'root',mode:'one-shot',createdAt:1}]})})
 const result=derive(l)
 assert.deepEqual(result.rows.map(r=>r.id).sort(),['c','root'])
 assert.equal(derive(list([row('root')],{root:{state:'error',values:{}}})).complete,false)
})
