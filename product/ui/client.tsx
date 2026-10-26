import { useEffect, useRef, useState } from 'react'
import type { DshUiContext } from './dsh-face.js'
import { read, states, eventNames, label, time, safeSource, message, type Execution, type ExecutionList, type Evidence, type BusinessEvent } from './model.js'
import css from './Query.module.css'
import { NotificationsPage } from './Notifications.js'
import { MandatesPage } from './Mandates.js'
import { InvestmentPage } from './Investment.js'
import { installShell } from './Shell.js'

declare const __HUOHUO_CSS__: string
const panelId = 'huohuo-research'
const brandPath = 'api/huohuo/brand.png'
export const inject = ['slots', 'layout', 'uiWorkspace', 'sessions', 'inputTriggers', 'connection']
interface Resource<T> { data?: T; error?: string; loading: boolean; at?: number }

/** Component-local reads cancel on navigation and never overwrite a newer selection. */
function useRead<T>(kind: Parameters<typeof read>[0], refresh: number, id?: string): Resource<T> {
  const [state, setState] = useState<Resource<T>>({ loading: true })
  useEffect(() => {
    const controller = new AbortController()
    setState(old => ({ ...old, loading: true, error: undefined }))
    void read<T>(kind, controller.signal, id).then(data => {
      if (!controller.signal.aborted) setState({ data, loading: false, at: Date.now() / 1000 })
    }).catch(error => {
      if (!controller.signal.aborted) setState(old => ({ ...old, error: message(error), loading: false }))
    })
    return () => controller.abort()
  }, [kind, id, refresh])
  return state
}
function State({ value }: { value: string }) {
  return <span className={css.status} data-state={value}>{label(states, value, '未知状态')}</span>
}
function Notice({ resource, empty }: { resource: Resource<unknown>; empty?: string }) {
  return <>
    {resource.loading && <p className={css.note} role="status">{resource.data ? '正在刷新，暂时保留上次读取的内容…' : '正在读取…'}</p>}
    {resource.error && <p className={css.error} role="alert">{resource.error}{resource.data ? ' 当前保留上次成功读取的内容，可能已经过期。' : ''}</p>}
    {!resource.loading && !resource.error && empty && <p className={css.empty}>{empty}</p>}
  </>
}
function number(value?: string) {
  return value != null && value !== '' && Number.isFinite(Number(value)) ? Number(value).toFixed(2) : '—'
}
function EvidenceView({ row, current }: { row: Evidence; current: boolean }) {
  const source = safeSource(row.source_url)
  return <article className={css.evidence}>
    <div className={css.rowHeading}><strong>{row.values?.name || '报价证据'}</strong><span className={css.note}>{current ? '当前结果引用' : '历史或尚未被结果引用'}</span></div>
    <p className={css.note}>来源：{row.source === 'eastmoney' ? '东方财富' : row.source || '—'} · {row.status === 'ok' ? '数据可用' : row.status === 'empty' ? '来源无记录' : row.status === 'unavailable' ? '数据不完整' : '采集异常'}</p>
    {row.values && <dl className={css.quote}>
      <div><dt>报价</dt><dd>{number(row.values.price)} <small>元/股</small></dd></div>
      <div><dt>昨收</dt><dd>{number(row.values.previous_close)} <small>元/股</small></dd></div>
      <div><dt>较昨收变化</dt><dd>{number(row.values.change_percent)}<small> %</small></dd></div>
    </dl>}
    <p className={css.note}>报价时间：{time(row.data_as_of)}<br />采集时间：{time(row.observed_at)}</p>
    {!row.data_as_of && <p className={css.note}>来源未提供可用报价时间，不能认定为当前实时行情。</p>}
    {row.reason && <p className={css.note}>采集说明：{label({ provider_failed: '行情源请求失败', provider_rejected_or_malformed: '行情源拒绝请求或返回异常', required_prices_missing: '缺少必要价格', security_not_in_response: '返回内容中没有该证券', unexpected_provider_schema: '行情返回格式异常' }, row.reason, '来源未返回完整可用数据')}</p>}
    {row.limitations?.map((item, i) => <p className={css.note} key={i}>{item}</p>)}
    {source && <a href={source} target="_blank" rel="noreferrer noopener">查看来源</a>}
    <details className={css.meta}><summary>核对证据标识</summary><p>证据 ID：{row.evidence_id}</p><p>执行尝试：{row.attempt_id}</p></details>
  </article>
}
function Detail({ id, refresh, back }: { id: string; refresh: number; back: () => void }) {
  const task = useRead<Execution>('execution', refresh, id)
  const events = useRead<BusinessEvent[]>('events', refresh, id)
  const evidence = useRead<Evidence[]>('evidence', refresh, id)
  const heading = useRef<HTMLHeadingElement>(null)
  useEffect(() => { heading.current?.focus() }, [id])
  return <section className={css.detail} aria-labelledby="huohuo-detail-title">
    <button className={css.textButton} onClick={back}>← 返回列表</button>
    <h2 id="huohuo-detail-title" tabIndex={-1} ref={heading}>研究详情</h2>
    <Notice resource={task} />
    {task.data && <>
      <div className={css.rowHeading}><span className={css.note}>单次研究 · {task.data.scope.entity_id.split(':').at(-1)}</span><State value={task.data.status} /></div>
      <h3 className={css.question}>{task.data.question}</h3>
      <p className={css.note}>提交：{time(task.data.created_at)}<br />更新：{time(task.data.updated_at)}</p>
      <section className={css.section} aria-labelledby="huohuo-result-title">
        <h3 id="huohuo-result-title">研究结果</h3>
        {task.data.result?.summary ? <p className={css.summary}>{task.data.result.summary}</p>
          : task.data.result?.error ? <p className={css.error}>{task.data.result.error}</p>
          : <p className={css.note}>{task.data.status === 'cancelled' ? '这项研究已取消，没有可交付结果。' : task.data.status === 'interrupted' ? '执行已中断。可在对话中明确要求重试。' : '尚无已保存的研究结果。'}</p>}
      </section>
      <details className={css.meta}><summary>研究标识</summary><p>{task.data.execution_id}</p><p>当前修订：{task.data.revision}</p></details>
    </>}
    <section className={css.section} aria-labelledby="huohuo-events-title">
      <h3 id="huohuo-events-title">执行进展</h3><p className={css.note}>这里记录后台已确认的关键进展。</p>
      <Notice resource={events} empty={events.data?.length === 0 ? '暂无执行事件。' : undefined} />
      <ol className={css.timeline}>{events.data?.map(event => <li key={event.seq}><strong>{label(eventNames, event.kind, '其他业务事件')}</strong><time>{time(event.created_at)}</time></li>)}</ol>
    </section>
    <section className={css.section} aria-labelledby="huohuo-evidence-title">
      <h3 id="huohuo-evidence-title">研究证据</h3>
      <Notice resource={evidence} empty={evidence.data?.length === 0 ? '尚无留存证据。' : undefined} />
      {evidence.data?.map(row => <EvidenceView key={row.evidence_id} row={row} current={!!task.data?.result?.evidence_ids?.includes(row.evidence_id) && row.attempt_id === task.data.current_attempt} />)}
    </section>
  </section>
}
function QueryPage({ goChat }: { goChat: () => void }) {
  const [refresh, setRefresh] = useState(0)
  const list = useRead<ExecutionList>('executions', refresh)
  const [selected, setSelected] = useState<string>()
  const [filter, setFilter] = useState('all')
  const listHeading = useRef<HTMLHeadingElement>(null)
  const rows = list.data?.executions.filter(row => filter === 'all' || row.status === filter) ?? []
  const back = () => { setSelected(undefined); requestAnimationFrame(() => listHeading.current?.focus()) }
  return <main className={css.page} data-detail={!!selected}>
    <header className={css.header}>
      <div><p className={css.eyebrow}>火火 · 投研伙伴</p><h1>委托查询</h1><p className={css.note}>查看已交给火火的单次研究、执行进展与证据。</p></div>
      <div className={css.actions}><button className={css.button} onClick={goChat}>回到对话</button><button className={css.button} onClick={() => setRefresh(n => n + 1)} disabled={list.loading}>{list.loading ? '读取中…' : '刷新记录'}</button></div>
    </header>
    <div className={css.body}>
      <section className={css.list} aria-labelledby="huohuo-list-title">
        <div className={css.rowHeading}><h2 id="huohuo-list-title" tabIndex={-1} ref={listHeading}>我的研究</h2><span className={css.note}>{list.data ? `${list.data.executions.length} 条` : ''}</span></div>
        <p className={css.note}>最近读取：{time(list.at)} · 时间按本机时区显示</p>
        <div className={css.filters} aria-label="按研究状态筛选">{Object.entries({ all: '全部', ...states }).map(([value, label]) => <button key={value} className={css.filter} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>)}</div>
        <Notice resource={list} empty={list.data?.executions.length === 0 ? '还没有研究记录。回到对话，告诉火火你想查询哪只股票。' : !rows.length && list.data ? '当前筛选下没有研究记录，可切换到“全部”。' : undefined} />
        <ul className={css.tasks}>{rows.map(row => <li key={row.execution_id}>
          <button className={css.task} aria-pressed={selected === row.execution_id} onClick={() => setSelected(row.execution_id)}>
            <span className={css.rowHeading}><span className={css.code}>{row.scope.entity_id.split(':').at(-1)} · 单次研究</span><State value={row.status} /></span>
            <strong>{row.question}</strong><span className={css.note}>更新于 {time(row.updated_at)}</span>
          </button>
        </li>)}</ul>
        {list.data?.has_more && <p className={css.note}>当前仅展示最近 50 条，尚不支持翻阅更早记录。</p>}
      </section>
      {selected ? <Detail key={selected} id={selected} refresh={refresh} back={back} /> : <section className={css.placeholder}><h2>让每一次研究都有迹可循</h2><p>选择一项研究，查看真实状态、结果与证据。</p><p className={css.note}>当前记录为单次研究；持续跟踪能力尚未开放。</p></section>}
    </div>
  </main>
}
function ResearchPage({ goChat }: { goChat: () => void }) {
  const [legacy,setLegacy]=useState(false)
  return legacy ? <><button className={css.button} onClick={()=>setLegacy(false)}>返回持续委托</button><QueryPage goChat={goChat}/></> : <MandatesPage goChat={goChat} legacy={()=>setLegacy(true)}/>
}
function BrandMark({ size = 32 }: { size?: number }) { return <img src={brandPath} width={size} height={size} className={css.brandMark} alt="火火" /> }
function BrandName() { return <span className={css.brandName}><strong>火火</strong><small>投研伙伴 · 1.0.0</small></span> }
function QueryIcon({ size = 20 }: { size?: number }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="5" y="3" width="14" height="18" rx="2" /><path d="M9 8h6M9 12h6M9 16h4" /></svg>
}

/** Product-owned metadata adaptation for rc2's fixed document-title presenter. */
function brandMetadata() {
  const originalTitle = document.title
  const icons = [...document.querySelectorAll<HTMLLinkElement>('link[rel="icon"], link[rel="shortcut icon"], link[rel="apple-touch-icon"]')]
  const previous = icons.map(link => ({ link, href: link.getAttribute('href'), type: link.getAttribute('type') }))
  for (const link of icons) { link.href = brandPath; link.type = 'image/png' }
  const rewrite = () => {
    const next = document.title.replace(/(^| — )DeepSeek Harness$/, '$1火火')
    if (next !== document.title) document.title = next
  }
  rewrite()
  const observer = new MutationObserver(rewrite)
  observer.observe(document.head, { subtree: true, childList: true, characterData: true })
  return () => {
    observer.disconnect(); document.title = originalTitle
    for (const { link, href, type } of previous) {
      if (href === null) link.removeAttribute('href'); else link.setAttribute('href', href)
      if (type === null) link.removeAttribute('type'); else link.setAttribute('type', type)
    }
  }
}
export function apply(ctx: DshUiContext): void {
  installShell(ctx)
  ctx.slots.inject('main', () => ctx.slots.register({ name: 'main', key: 'huohuo-notifications', label: '消推配置', inject: () => ({ visit: (mandate: string, decision: string) => { sessionStorage.setItem('huohuo-return', JSON.stringify({mandate,decision})); ctx.layout.selectPanel('huohuo-research') } }) }, NotificationsPage))
  ctx.slots.inject('main', () => ctx.slots.register({ name: 'main', key: 'huohuo-investment', label: '持仓与自选' }, InvestmentPage))
  ctx.effect(() => { const style = document.createElement('style'); style.dataset.huohuo = 'query'; style.textContent = __HUOHUO_CSS__; document.head.append(style); return () => style.remove() }, '火火样式')
  ctx.effect(brandMetadata, '火火品牌元数据')
  ctx.slots.inject('sidebar.brand.mark', () => ctx.slots.register({ name: 'sidebar.brand.mark', priority: -100 }, BrandMark))
  ctx.slots.inject('sidebar.brand.name', () => ctx.slots.register({ name: 'sidebar.brand.name', priority: -100 }, BrandName))
  ctx.slots.inject('conversation.hero.brand.mark', () => ctx.slots.register({ name: 'conversation.hero.brand.mark', priority: -100 }, BrandMark))
  ctx.slots.inject('main', () => ctx.slots.register({ name: 'main', key: panelId, label: '委托查询', inject: () => ({ goChat: () => { ctx.layout.selectPanel(null); ctx.uiWorkspace.startSession(undefined, { agentPreset: 'huohuo' }) } }) }, ResearchPage))
  ctx.slots.inject('sidebar.panellist', () => ctx.slots.register({ name: 'sidebar.panellist', id: panelId, order: -100, label: '委托查询' }, QueryIcon))
}
