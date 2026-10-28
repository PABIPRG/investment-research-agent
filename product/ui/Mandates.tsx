import page from './shared/Page.module.css'
import business from './Business.module.css'
import { MandateDetail } from './mandates/MandateDetail.js'
import { MandateTable } from './mandates/MandateTable.js'
import { useMandates } from './mandates/useMandates.js'
import type { ReactNode } from 'react'
export function MandatesPage({ switcher }: { goChat: () => void; switcher: ReactNode }) {
  const model = useMandates()
  const { items, loading, busy, error, filter, setFilter } = model
  return (
    <main className={`${page.surface} ${business.page}`}>
      <header className={`${page.header} ${business.header}`}>
        <div>
          <h1>我的委托</h1>
          <p className={business.note}>
            {items.filter((x) => x.mandate.status === 'tracking').length} 项跟踪 ·{' '}
            {items.filter((x) => !x.baseline).length} 项尚无研究基准
          </p>
        </div>
        <div className={business.tools}>
          <button onClick={() => model.setRefresh((n) => n + 1)} disabled={loading || busy}>
            刷新记录
          </button>
        </div>
      </header>
      {switcher}
      <p className={business.note}>你交代火火持续关注的研究；按各项约定跟进并保留依据。</p>
      {error && (
        <p role="alert">
          {error} {items.length ? '当前内容可能过期。' : ''}
        </p>
      )}
      {loading && <p role="status">{items.length ? '正在刷新，保留上次内容…' : '正在读取委托…'}</p>}
      <div className={business.tabs}>
        {Object.entries({ all: '全部', tracking: '跟进中', paused: '已暂停', ended: '已结束' }).map(
          ([value, label]) => (
            <button key={value} aria-pressed={filter === value} onClick={() => setFilter(value)}>
              {label}
            </button>
          ),
        )}
      </div>
      <MandateTable model={model} />
      {model.current && <MandateDetail key={model.current.mandate.mandate_id} model={model} />}
    </main>
  )
}
