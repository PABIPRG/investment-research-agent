import { useEffect, useRef, useState } from 'react'
import { deliveryLabels, decisionText, channelLabels } from './Notifications.js'
import css from './Query.module.css'
import { InvestmentContext } from './InvestmentContext.js'
import { time, safeSource } from './model.js'

type Scope = { entity_id: string; exchange: string; operation: string }
type View = { mandate: { mandate_id: string; current_revision: number; status: string }; generation: number; revision: { goal: string; scope: Scope; basis: { contact_note?: string }; contact_policy?: { reminder_time?: string; channels?: string[] } }; baseline_revision?: number; baseline: { summary?: string } | null; executions: { execution_id: string; status: string; result?: { error?: string; summary?: string } }[]; evidence: any[]; decisions?: any[]; notifications?: any[]; sources?: any[]; source_check?: {status:string;detail:string}; monitoring: { detail: string } }
const statuses: Record<string,string> = { tracking: '跟进中', paused: '已暂停', ended: '已结束', pending_requirements: '待补充', queued: '等待研究', running: '研究中', succeeded: '研究完成', failed: '研究失败', cancelled: '已撤销', interrupted: '研究中断' }
const sourceReasons: Record<string,string> = { provider_timeout:'资料源响应超时', provider_failed:'资料源采集失败', requested_period_or_metric_not_covered:'来源没有覆盖指定期间或指标', requested_value_unavailable:'来源中的指标值缺失或无法作为数值使用', requested_metric_ambiguous:'来源对同一指标返回多条记录，口径尚不能确定', provider_schema_invalid:'来源返回的资料格式无法核验', no_source_records:'来源未返回记录' }
function sourceReason(reason: string): string { return sourceReasons[reason] || reason }
async function api(path: string, signal?: AbortSignal, body?: unknown) {
  const response = await fetch(`api/huohuo/${path}`, { method: body ? 'POST' : 'GET', headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined, signal, cache: 'no-store' })
  const data = await response.json()
  if (!response.ok) throw new Error(response.status === 403 ? '无权访问此实例。请重新连接。' : data.detail || '读取失败，请稍后重试。')
  return data
}
export function MandatesPage({ goChat, legacy }: { goChat: () => void; legacy: () => void }) {
  const [items,setItems]=useState<View[]>([]), [selected,setSelected]=useState<string | undefined>(()=>{try{return JSON.parse(sessionStorage.getItem('huohuo-return')||'{}').mandate}catch{return undefined}}), [refresh,setRefresh]=useState(0)
  const [loading,setLoading]=useState(true), [error,setError]=useState(''), [busy,setBusy]=useState(false), [feedback,setFeedback]=useState('')
  const [filter,setFilter]=useState('all'), [editing,setEditing]=useState(false), [goal,setGoal]=useState(''),[note,setNote]=useState('')
  const [contactChannels,setContactChannels]=useState<string[]>(['app'])
  const [reminder,setReminder]=useState(false),[reminderTime,setReminderTime]=useState('09:00')
  const pending=useRef<{ fingerprint: string; key: string }>()
  const heading=useRef<HTMLHeadingElement>(null)
  useEffect(()=>{
    const controller=new AbortController();setLoading(true);setError('')
    api('mandates',controller.signal).then(data=>{if(!controller.signal.aborted){setItems(data.items);setLoading(false)}}).catch(e=>{if(!controller.signal.aborted){setError(e.message);setLoading(false);if(e.message.includes('无权'))setItems([])}})
    return ()=>controller.abort()
  },[refresh])
  useEffect(()=>{if(items.some(x=>x.executions.some(e=>['queued','running'].includes(e.status))||x.mandate.status==='tracking'&&!x.executions.length)){const timer=setTimeout(()=>setRefresh(x=>x+1),3000);return ()=>clearTimeout(timer)}},[items])
  const returnDecision=(()=>{try{return JSON.parse(sessionStorage.getItem('huohuo-return')||'{}').decision}catch{return undefined}})()
  const current=items.find(x=>x.mandate.mandate_id===selected)
  useEffect(()=>{if(current&&returnDecision){const el=document.getElementById(returnDecision);el?.scrollIntoView({block:'center'});el?.focus()}},[current,returnDecision])
  useEffect(()=>{setEditing(false);setFeedback('');heading.current?.focus()},[selected])
  const command=async(action:string)=>{
    if(!current)return
    if(action==='end'&&!confirm('结束后不能恢复这项委托。确认结束？'))return
    if(action==='pause'&&!confirm('暂停后撤销新的研究和发送资格。已交给渠道的在途请求可能仍会送达。确认暂停？'))return
    const payload={action,mandate_id:selected,expected_revision:current.mandate.current_revision,expected_generation:current.generation,...(action==='revise'?{goal,scope:current.revision.scope,contact_note:note,reminder_time:reminder?reminderTime:null,contact_channels:contactChannels}:{})}
    const fingerprint=JSON.stringify(payload)
    if(pending.current?.fingerprint!==fingerprint)pending.current={fingerprint,key:crypto.randomUUID()}
    setBusy(true);setFeedback('')
    try{const updated=await api('mandate-command',undefined,{...payload,request_key:pending.current.key});setItems(old=>old.map(x=>x.mandate.mandate_id===selected?updated:x));setEditing(false);setFeedback('已保存，当前状态以详情为准。');pending.current=undefined}
    catch(e){setFeedback((e as Error).message)}finally{setBusy(false)}
  }
  const rows=items.filter(x=>filter==='all'||x.mandate.status===filter)
  return <main className={css.page} data-detail={!!current}>
    <header className={css.header}><div><p className={css.eyebrow}>火火 · 投研伙伴</p><h1>委托查询</h1><p className={css.note}>查看明确交代的研究、范围与留存证据。</p></div><div className={css.actions}><button className={css.button} onClick={goChat}>回到对话创建委托</button><button className={css.button} onClick={()=>setRefresh(x=>x+1)} disabled={loading||busy}>{loading?'读取中…':'刷新记录'}</button><button className={css.textButton} onClick={legacy}>单次研究记录</button></div></header>
    {error&&<p role="alert" className={css.error}>{error} {items.length?'已显示内容可能过期。':''}</p>}
    {loading&&<p role="status" className={css.note}>{items.length?'正在刷新，保留上次内容…':'正在读取委托…'}</p>}
    <div className={css.body}><section className={css.list} aria-label="我的委托"><h2>我的委托</h2><div className={css.filters}>{Object.entries({all:'全部',tracking:'跟进中',paused:'已暂停',ended:'已结束'}).map(([value,label])=><button className={css.filter} key={value} aria-pressed={filter===value} onClick={()=>setFilter(value)}>{label}</button>)}</div>
      {!loading&&!error&&!rows.length&&<p className={css.empty}>{items.length?'当前筛选没有委托，请切换“全部”。':'还没有委托。回到对话，明确告诉火火研究对象、范围与希望跟进的问题。'}</p>}
      <ul className={css.tasks}>{rows.map(x=><li key={x.mandate.mandate_id}><button className={css.task} aria-pressed={selected===x.mandate.mandate_id} onClick={()=>setSelected(x.mandate.mandate_id)}><span className={css.rowHeading}><span>{x.revision.scope.entity_id.split(':').at(-1)}</span><span className={css.status}>{statuses[x.mandate.status]}</span></span><strong>{x.revision.goal}</strong><span className={css.note}>版本 {x.mandate.current_revision} · {statuses[x.executions[0]?.status]||'等待初次调度'}</span></button></li>)}</ul></section>
      {current?<section className={css.detail}><button className={css.textButton} onClick={()=>setSelected(undefined)}>← 返回列表</button><h2 ref={heading} tabIndex={-1}>委托详情</h2><h3 className={css.question}>{current.revision.goal}</h3><p>{statuses[current.mandate.status]} · 版本 {current.mandate.current_revision}</p><p className={css.note}>范围：{current.revision.scope.entity_id} / {current.revision.scope.exchange} / {current.revision.scope.operation==='quote_snapshot'?'报价快照':current.revision.scope.operation==='company_profile'?'公司资料':'财务摘要'}</p><p className={css.note}>{current.monitoring.detail}</p><details className={css.meta}><summary>完整研究范围</summary><pre className={css.evidenceValues}>{JSON.stringify(current.revision.scope,null,2)}</pre></details>
        <section className={css.section}><h3>约定与管理</h3><p>{current.revision.basis.contact_note||'尚无补充约定'}</p><div className={css.actions}>
          <button className={css.button} disabled={busy||loading||!!error||current.mandate.status==='ended'} onClick={()=>{setContactChannels(current.revision.contact_policy?.channels||['app']);setGoal(current.revision.goal);setNote(current.revision.basis.contact_note||'');setReminder(!!current.revision.contact_policy?.reminder_time);setReminderTime(current.revision.contact_policy?.reminder_time||'09:00');setEditing(true)}}>修改约定</button>
          {current.mandate.status==='paused'?<button className={css.button} disabled={busy||loading||!!error} onClick={()=>command('resume')}>恢复委托</button>:<button className={css.button} disabled={busy||loading||!!error||current.mandate.status==='ended'} onClick={()=>command('pause')}>暂停委托</button>}
          <button className={css.button} disabled={busy||loading||!!error||current.mandate.status==='ended'} onClick={()=>command('end')}>结束委托</button></div>
          <p className={css.note}>允许联系渠道：{(current.revision.contact_policy?.channels||['app']).map(c=>channelLabels[c]||c).join('、')}</p>{editing&&<form className={css.editForm} onSubmit={e=>{e.preventDefault();void command('revise')}}><fieldset disabled={busy}><legend>本委托允许的联系渠道</legend>{Object.entries(channelLabels).map(([c,label])=><label className={css.checkLabel} key={c}><input type="checkbox" checked={contactChannels.includes(c)} onChange={e=>setContactChannels(old=>e.target.checked?[...old,c]:old.filter(x=>x!==c))}/>{label}</label>)}<p className={css.note}>外部渠道需先在消推配置中保存并启用。保存约定后，本委托可通过所选渠道发送研究摘要；在途请求无法撤回。</p></fieldset><label>研究目标<textarea required maxLength={4000} value={goal} onChange={e=>setGoal(e.target.value)}/></label><label>联系与研究约定<textarea required maxLength={1000} value={note} onChange={e=>setNote(e.target.value)}/></label><label className={css.checkLabel}><input type="checkbox" checked={reminder} onChange={e=>setReminder(e.target.checked)}/>每天按约提醒（即使没有新变化）</label>{reminder&&<label>每日提醒时间（北京时间）<input type="time" required value={reminderTime} onChange={e=>setReminderTime(e.target.value)}/></label>}<p className={css.note}>未勾选时仅重要变化联系；资料未知时保留记录，自动复核预算为 0，不自动追加模型费用。</p><p className={css.note}>保存后产生新版本，旧研究资格将撤销。研究对象保持不变。</p><div className={css.actions}><button className={css.button} disabled={busy}>确认保存</button><button type="button" className={css.textButton} onClick={()=>setEditing(false)}>取消修改</button></div></form>}
          {feedback&&<p role="status" className={css.note}>{feedback}</p>}</section>
        <InvestmentContext key={current.mandate.mandate_id} current={current} updated={()=>setRefresh(x=>x+1)}/>
        <section className={css.section}><h3>初次研究与基准</h3>{current.baseline&&<p className={css.note}>基准形成于委托版本 {current.baseline_revision}；后续约定修改不会改写历史证据。</p>}<p className={css.summary}>{current.baseline?.summary||'尚无有效研究基准。'}</p>{current.executions.map(x=><div key={x.execution_id}><p>{statuses[x.status]||x.status}</p>{x.result?.error&&<p className={css.error}>{x.result.error}</p>}{x.result?.summary&&<p>{x.result.summary}</p>}</div>)}</section>
        <section className={css.section}><h3>持续复核与联系决定</h3>
          {current.source_check&&<p className={css.note}>来源检查：{current.source_check.status==='ok'?'内容已核对':sourceReason(current.source_check.detail)}</p>}
          {!current.decisions?.length&&<p className={css.note}>尚无联系决定；缺少资料不等于条件不成立。</p>}
          {current.decisions?.map(d=><article className={css.evidence} key={d.decision_id} id={d.decision_id} tabIndex={-1} aria-label={d.decision_id===returnDecision?'本次回访的联系决定':'联系决定'}><strong>{({met:'条件成立',unmet:'条件不成立',unknown:'尚不能判断',error:'执行或条件评估失败'} as Record<string,string>)[d.condition_result]}</strong><p>{decisionText(d.detail,d.reason_code)}</p><p className={css.note}>{({send:'已决定联系',suppress:'保持静默',defer:'暂缓处理',aggregate:'合并展示'} as Record<string,string>)[d.decision]} · {time(d.created_at)}</p><details><summary>决定与证据引用</summary><p>{d.decision_id}</p><p>{d.evidence_ref||'无有效证据引用'}</p></details></article>)}
          {current.notifications?.map(n=><p key={`${n.decision_id}:${n.channel}`}>{channelLabels[n.channel]||n.channel} · {deliveryLabels[n.status]}：{n.detail||'等待发送资格核验'}</p>)}
          <details><summary>来源内容版本（非发布时间）</summary>{current.sources?.map(src=><p className={css.note} key={src.event_id}>{src.source} · {src.version.slice(0,12)} · 观察于 {time(src.observed_at)}</p>)}</details>
        </section>
        <section className={css.section}><h3>留存证据</h3>{!current.evidence.length&&<p className={css.note}>尚无证据。采集失败不会算作研究成功。</p>}{current.evidence.map(ev=><article className={css.evidence} key={ev.evidence_id}><strong>{ev.values?.name||({eastmoney:'东方财富','akshare.stock_financial_abstract':'新浪财务摘要（AKShare）','akshare.stock_profile_cninfo':'巨潮公司资料（AKShare）'} as Record<string,string>)[ev.source]||ev.source||'来源未提供'}</strong>
          <p className={css.note}>状态：{ev.status==='ok'?'数据可用':ev.status==='empty'?'来源无记录':ev.status==='unavailable'?'数据未覆盖':'采集失败'} · 采集时间：{time(ev.observed_at)}</p>
          {ev.source_url?.includes('example.invalid')&&<p className={css.note}>明确合成验收数据，不代表真实行情。</p>}
          {ev.reason&&<p className={css.note}>{sourceReason(ev.reason)}</p>}
          {ev.values?.price&&<dl className={css.quote}><div><dt>报价</dt><dd>{ev.values.price} <small>元/股</small></dd></div><div><dt>昨收</dt><dd>{ev.values.previous_close??'—'} <small>元/股</small></dd></div><div><dt>较昨收变化</dt><dd>{ev.values.change_percent??'—'} <small>%</small></dd></div></dl>}
          {ev.values?.metric&&<><p>指标：{ev.values.metric} · 报告期：{ev.values.period}</p><p className={css.note}>摘要原始口径，单位尚未核验。</p>{ev.values.records?.map((r:any,i:number)=><p key={i}>{r['指标']}：{String(r[ev.values.period]??'—')}</p>)}</>}
          {ev.values?.profile?.map((r:any,i:number)=><dl key={i}>{Object.entries(r).map(([k,v])=><div key={k}><dt>{k}</dt><dd>{String(v??'—')}</dd></div>)}</dl>)}
          {ev.limitations?.map((x:string,i:number)=><p className={css.note} key={i}>{x}</p>)}
          {safeSource(ev.source_url)&&<a href={safeSource(ev.source_url)!} target="_blank" rel="noreferrer noopener">查看资料来源</a>}
          <details className={css.meta}><summary>核对证据标识与范围</summary><p>{ev.evidence_id}</p><p>{JSON.stringify(ev.scope)}</p></details></article>)}</section>
      </section>:<section className={css.placeholder}><h2>持续交代，逐次核对</h2><p>选择一项委托，查看研究进展、证据和管理操作。</p></section>}
    </div></main>
}
