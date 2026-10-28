import test from 'node:test'
import assert from 'node:assert/strict'
import {createRiskTools} from '../product/chat/risk-tools.js'
import {createPersonalizationTools} from '../product/chat/personalization-tools.js'
import {createPositionRiskTools} from '../product/chat/position-risk-tools.js'
import {createInvestmentTools,investmentQuestion} from '../product/chat/investment-tools.js'
import {createPersonalizationBridge} from '../product/ui/personalization/bridge.js'
import {runPositionAttempt} from '../distribution/position-worker.js'
import {createResearchReviewTools} from '../product/chat/research-review-tools.js'
const exec={agent:{session:{id:'inheritance-session'}},callId:'inheritance-test',signal:new AbortController().signal} as any
const pid='00000000-0000-4000-8000-000000000001'
const confirmed={answers:[{id:'business-confirm',selected:['确认执行']}]}
test('结构化研究由桥绑定会话与调用身份，不能从参数覆盖画像或主体',async()=>{
  const original=globalThis.fetch
  try{
    let calls=0
    globalThis.fetch=async(url,init)=>{
      calls++;assert.equal(new URL(String(url)).pathname,'/research-reviews/run')
      const body=JSON.parse(String(init?.body))
      assert.equal(body.session_id,exec.agent.session.id);assert.equal(body.call_id,exec.callId)
      assert.equal(body.arguments.signal.risk_score,null)
      return Response.json({guard_status:'unknown',review_id:'fixture'})
    }
    const t=createResearchReviewTools('http://127.0.0.1:18880','fixture')[0]
    const a={confirmation_id:'fixture',signal:{action:'无法判断',risk_score:null,confidence:null,target_price:null,reasoning:'缺合格材料'},perspectives:[]}
    assert.equal((await t.execute(a,exec) as any).data.guard_status,'unknown')
    for(const field of ['profile','principal','session_id','authorized'])await assert.rejects(()=>t.execute({...a,[field]:'fake'},exec))
    await assert.rejects(()=>t.execute({...a,signal:{...a.signal,risk_score:NaN}},exec))
    assert.equal(calls,1)
  }finally{globalThis.fetch=original}
})
test('聊天阅读工具绑定同一学习服务，模型不能覆盖来源、时间或证券兴趣',async()=>{
  const original=globalThis.fetch
  try{
    let calls=0
    globalThis.fetch=async(url,init)=>{
      calls++;assert.equal(new URL(String(url)).pathname,'/personalization/record')
      const body=JSON.parse(String(init?.body));assert.equal(body.surface,'assistant')
      assert.match(body.session_id,/^chat:[0-9a-f]{64}$/);assert.match(body.request_key,/^chat:[0-9a-f]{64}$/)
      assert.equal(body.card_id,'card-fixture');assert.equal(body.action,'analyze')
      assert.equal(body.ticker,undefined);return Response.json({ignored:1,stored:0})
    }
    const t=createPersonalizationTools('http://127.0.0.1:18880','fixture').find(t=>t.name==='record_personalized_interaction')!
    const a={card_id:'card-fixture',action:'analyze'}
    assert.equal((await t.execute(a,exec) as any).data.ignored,1)
    for(const field of ['surface','session_id','timestamp','ticker','context'])await assert.rejects(()=>t.execute({...a,[field]:'forged'},exec))
    assert.equal(calls,1)
  }finally{globalThis.fetch=original}
})
test('自然语言完整映射仍逐项展示原生确认；取消不保存',async()=>{
  const original=globalThis.fetch
  try{
    const bank=['horizon','loss_tolerance','goal'].map(qid=>({qid,title:qid,options:['选项甲','选项乙']}))
    let commits=0,asks=0;const questions:any[]=[]
    globalThis.fetch=async(url,init)=>{
      const path=new URL(String(url)).pathname
      if(path.endsWith('/risk-parse'))return Response.json({answers:bank.map(q=>({qid:q.qid,option:1}))})
      if(path.endsWith('/preview'))return Response.json({preview_id:pid,after:{risk_profile:{label:'稳健型',score:6,max_score:15,answers:bank.map(q=>({qid:q.qid,label:'选项乙'}))}}})
      if(path.endsWith('/commit')){commits++;return Response.json({saved:true})}
      return Response.json({risk_questionnaire:{quick:bank}})
    }
    for(const consent of [false,true]){
      const t=createRiskTools('http://127.0.0.1:18880','fixture',async(q)=>{asks++;questions.push(q);return consent?confirmed:{cancelled:true}})[0]
      const r:any=await t.execute({tier:'quick',statement:'合成自然语言偏好'},exec)
      assert.equal(consent?r.data.saved:r.saved,consent)
    }
    assert.equal(asks,2);assert.equal(commits,1)
    assert.ok(questions[0][0].question.includes('goal：选项乙'))
    assert.ok(questions[0][0].question.includes('合成自然语言偏好'))
  }finally{globalThis.fetch=original}
})
test('本机偏好保存先读取真实影响，取消和未知结果不新建操作',async()=>{
  const original=globalThis.fetch
  try{
    let commits=0
    globalThis.fetch=async(url)=>{
      if(String(url).endsWith('/commit')){commits++;throw Error('lost receipt')}
      return Response.json({preview_id:pid,payload:{action:'clear'},before:{learning:{record_count:7},cards:{cards:[]}}})
    }
    for(const consent of [false,true]){
      const t=createPersonalizationTools('http://127.0.0.1:18880','fixture',async(q)=>{
        assert.ok((q as any)[0].question.includes('7 条'))
        return consent?confirmed:{cancelled:true}
      }).find(t=>t.name==='commit_personalization_change')!
      const result:any=await t.execute({preview_id:pid},exec)
      if(consent){assert.equal(result.error,'submission_unknown');assert.equal(result.preview_id,pid)}
      else assert.equal(result.saved,false)
    }
    assert.equal(commits,1)
  }finally{globalThis.fetch=original}
})
test('偏好已有回执直接回查，不再次询问或提交',async()=>{
  const original=globalThis.fetch
  try{
    let calls=0
    globalThis.fetch=async()=>{calls++;return Response.json({receipt:{saved:true}})}
    const t=createPersonalizationTools('http://127.0.0.1:18880','fixture',async()=>assert.fail('already committed')).find(t=>t.name==='commit_personalization_change')!
    assert.equal((await t.execute({preview_id:pid},exec) as any).reconciled,true);assert.equal(calls,1)
  }finally{globalThis.fetch=original}
})
test('持仓风险确认包含持续作用范围、冻结成本和实际阈值',()=>{
  const question=investmentQuestion({command:'position_risk',payload:{operation:'global',config:{monitoring_disabled:false,take_profit:{enabled:true,mode:'percent',value:.12},stop_loss:{enabled:true,mode:'percent',value:.06},effective_at:null,expires_at:null}},impact:{plans:[{ticker:'600519',status:'active',targets:{take_profit:{basis_cost:10,resolved_price:11.2}}}],notice:'后续录入持仓也应用；仅应用内联系，不下单。'}})
  for(const text of ['12%','6%','600519','11.2','激活成本 10','后续录入持仓','不下单'])assert.ok(question.includes(text))
})
test('偏好桥拒绝身份、会话和任意地址覆盖，回执只走固定 GET',async()=>{
  const original=globalThis.fetch
  try{
    let calls=0
    globalThis.fetch=async(url,init)=>{calls++;assert.equal(new URL(String(url)).pathname,'/personalization/previews/'+pid);assert.equal(init?.method,'GET');return Response.json({receipt:{saved:true}})}
    const bridge=createPersonalizationBridge('http://127.0.0.1:18880','fixture')
    const request=(body:any)=>new Request('http://localhost/api/huohuo/personalization',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})
    assert.equal((await bridge(request({operation:'inspect',preview_id:pid}))).status,200)
    for(const body of [{operation:'record',session_id:'fake'},{operation:'read',principal:'other'},{operation:'inspect',preview_id:'../../worker'},{operation:'http://127.0.0.1:1'}])assert.equal((await bridge(request(body))).status,400)
    assert.equal(calls,1)
  }finally{globalThis.fetch=original}
})
test('价格执行直接走程序，观察失败不阻断，不初始化 DSH',async()=>{
  const original=globalThis.fetch
  try{
    let calls=0
    globalThis.fetch=async(url)=>{calls++;assert.ok(String(url).endsWith('/position-run'));return Response.json({status:'succeeded'})}
    const result=await runPositionAttempt({host:'127.0.0.1',port:18880,worker_token:'fixture'} as any,{attempt_id:pid,execution_id:pid,lease_token:'fixture'},exec.signal,()=>{throw Error('observer')})
    assert.equal(result,'completed');assert.equal(calls,1)
  }finally{globalThis.fetch=original}
})


test('持仓价格跟进不显示为缺少 Agent 研究基准', async()=>{
  const {arrivalStatus}=await import('../product/ui/shell/arrival-model.js')
  const {mandateName}=await import('../product/ui/business-model.js')
  const view={mandate:{status:'tracking'},display_name:'合成持仓公司',revision:{scope:{entity_id:'SEC:CN:A:600519'},basis:{}},position_risk:{basis_cost:100,resolved_price:94,kind:'stop_loss',reason:'position_target_consumed'},baseline:null,executions:[]} as any
  assert.equal(mandateName(view),'合成持仓公司')
  assert.match(arrivalStatus(view).title,/已触发/)
  assert.doesNotMatch(arrivalStatus(view).detail,/研究基准/)
})
