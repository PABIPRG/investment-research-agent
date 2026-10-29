import page from '../shared/Page.module.css'
import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { mandateName, researchQuestion, securityName } from '../business-model.js'
import business from '../Business.module.css'
import { DetailPanel } from '../DetailPanel.js'
import { states, time, type ExecutionList } from '../model.js'
import { Detail } from './ResearchDetail.js'
import { Notice, State, useRead } from './Resource.js'
export function QueryPage({ goChat, switcher }: { goChat: () => void; switcher: ReactNode }) {
  const [names, setNames] = useState<Record<string, string>>({})
  useEffect(() => {
    const abort = new AbortController()
    Promise.all(
      ['mandates', 'investment'].map((path) =>
        fetch(`api/huohuo/${path}`, { signal: abort.signal }).then((r) => (r.ok ? r.json() : null)),
      ),
    )
      .then(([m, f]) => {
        const result: Record<string, string> = {}
        for (const x of [
          ...(f?.holdings || []),
          ...(f?.watchlist || []),
          ...(f?.corrections || []),
        ])
          if (x.name && x.name !== x.ticker) result[x.ticker] = x.name
        for (const x of m?.items || [])
          if (x.revision.basis?.entity_confirmation?.label)
            result[x.revision.scope.entity_id.split(':').at(-1)] = mandateName(x)
        setNames(result)
      })
      .catch(() => {})
    return () => abort.abort()
  }, [])
  const [refresh, setRefresh] = useState(0)
  const list = useRead<ExecutionList>('executions', refresh)
  const [selected, setSelected] = useState<string>()
  const [filter, setFilter] = useState('all')
  const listHeading = useRef<HTMLHeadingElement>(null)
  const rows =
    list.data?.executions.filter((row) => filter === 'all' || row.status === filter) ?? []
  const back = () => {
    setSelected(undefined)
    requestAnimationFrame(() => listHeading.current?.focus())
  }
  return (
    <main className={`${page.surface} ${business.page}`}>
      <header className={`${page.header} ${business.header}`}>
        <div>
          <h1 ref={listHeading} tabIndex={-1}>
            我的委托
          </h1>
          <p className={business.note}>
            {list.data?.executions.length ?? '—'} 条记录 · 最近读取 {time(list.at)}
          </p>
        </div>
        <button disabled={list.loading} onClick={() => setRefresh((n) => n + 1)}>
          刷新记录
        </button>
      </header>
      {switcher}
      <p className={business.note}>
        完成一次研究后结束，不会持续跟进；查看你在对话中提交过的研究及结果。
      </p>
      <div className={business.tabs} aria-label="按研究状态筛选">
        {Object.entries({ all: '全部', ...states }).map(([value, label]) => (
          <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>
            {label}
          </button>
        ))}
      </div>
      <Notice resource={list} />
      <div className={business.tableWrap}>
        <table className={business.table}>
          <thead>
            <tr>
              {['对象 / 问题', '状态', '结果 / 限制', '更新时间', '操作'].map((label) => (
                <th key={label}>{label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {list.data && !list.error && !rows.length && (
              <tr>
                <td colSpan={5} className={business.empty}>
                  {filter === 'all' ? '还没有一次性研究记录。' : '当前筛选条件下没有研究记录。'}
                  {filter === 'all' ? (
                    <button onClick={goChat}>去对话中发起研究</button>
                  ) : (
                    <button onClick={() => setFilter('all')}>查看全部</button>
                  )}
                </td>
              </tr>
            )}
            {rows.map((row) => (
              <tr key={row.execution_id}>
                <td>
                  <strong>
                    {securityName(
                      row.scope.entity_id,
                      names[row.scope.entity_id.split(':').at(-1)!],
                    )}
                  </strong>
                  <small>{researchQuestion(row.question)}</small>
                  <small>{row.scope.entity_id.split(':').at(-1)}</small>
                </td>
                <td>
                  <State value={row.status} />
                </td>
                <td>{row.result?.summary || row.result?.error || '尚无已保存结果'}</td>
                <td>{time(row.updated_at)}</td>
                <td>
                  <button onClick={() => setSelected(row.execution_id)}>详情</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {list.data?.has_more && (
        <p className={business.note}>当前仅展示最近 50 条，尚不支持翻阅更早记录。</p>
      )}
      {selected && (
        <DetailPanel title="一次性研究详情" close={back}>
          <Detail key={selected} id={selected} refresh={refresh} names={names} />
        </DetailPanel>
      )}
    </main>
  )
}
