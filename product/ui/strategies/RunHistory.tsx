import { actionLabels, runLabels, instant, type StrategyView, type Run } from './model.js'
import css from '../Business.module.css'
import local from './Strategy.module.css'
export function outcome(r: Run) {
  if (r.error) return r.error
  if (r.result?.skipped) return r.result.skipped
  if (r.action === 'schedule' && r.result?.automation) {
    const plan = r.result.automation
    return plan.enabled
      ? `${plan.strategy_ids.length} 项策略，工作日 ${plan.daily_time}（北京时间）；候选和预案应用仍需确认`
      : '后台计划已停止，既有验证记录保留'
  }
  if (r.action === 'accept_suggestion') return '已保存为待验证候选；未自动加入后台计划'
  if (r.action === 'events')
    return `${r.result?.event_count ?? 0} 条来源事件；${r.result?.note || '候选单独研究，保存仍需确认'}`
  if (r.action === 'recall')
    return `${r.result?.suggestions?.length ?? 0} 项召回建议；${r.result?.note || '等待确认，不沿用旧验证结论'}`
  if (r.result?.backtest) return r.result.backtest.reason
  if (r.result?.evolution) {
    const e = r.result.evolution
    return (
      e.data_note ||
      (e.applied
        ? `${e.actions?.length ?? 0} 项调整已应用`
        : `${e.actions?.length ?? 0} 项候选已生成；未在本次运行中应用`)
    )
  }
  return r.action === 'create'
    ? '已保存候选，等待回测'
    : r.action === 'retire'
      ? '已停止参与验证'
      : '查看关联记录与依据'
}
export function RunHistory({ view, open }: { view: StrategyView; open: (id: string) => void }) {
  if (!view.runs.length) return null
  return (
    <details className={local.history}>
      <summary>最近运行记录 · {view.runs.length} 条（最多 30 条）</summary>
      <div className={css.tableWrap}>
        <table className={css.table}>
          <thead>
            <tr>
              <th>操作 / 时间</th>
              <th>范围</th>
              <th>结果</th>
              <th>关联记录</th>
            </tr>
          </thead>
          <tbody>
            {view.runs.map((r) => {
              const subjects = view.strategies.filter(
                (s) => s.id === r.strategy_id || r.subjects?.includes(s.id),
              )
              return (
                <tr key={r.id}>
                  <td>
                    {actionLabels[r.action]}
                    <small>{instant(r.created_at)}</small>
                  </td>
                  <td>
                    {r.action === 'schedule'
                      ? '后台约定'
                      : r.action === 'events'
                        ? '计划内证券新闻'
                        : r.action === 'recall'
                          ? '计划内归档'
                          : r.strategy_id === 'strategy_pool'
                            ? '全池'
                            : subjects[0]?.name || '策略记录'}
                  </td>
                  <td>
                    <strong>{runLabels[r.status] || '状态待核对'}</strong>
                    <small>{outcome(r)}</small>
                  </td>
                  <td>
                    {subjects.map((s) => (
                      <button key={s.id} onClick={() => open(s.id)}>
                        {s.name}
                      </button>
                    ))}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </details>
  )
}
