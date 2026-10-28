import {
  actionLabels,
  instant,
  ruleLabels,
  runLabels,
  type Edit,
  type StrategyView,
  type StrategySchedule,
} from './model.js'
import css from '../Business.module.css'
import local from './Strategy.module.css'
export function BackgroundPanel({
  view,
  edit,
}: {
  view: StrategyView
  edit: (value: Edit) => void
}) {
  const plan = view.automation
  if (!plan) return null
  const policy: StrategySchedule = {
    revision: plan.revision,
    enabled: plan.enabled,
    daily_time: plan.daily_time,
    strategy_ids: plan.strategy_ids,
    actions: plan.actions,
    retest_days: plan.retest_days,
    lookback_days: plan.lookback_days,
    event_candidates: plan.event_candidates,
    archive_recall: plan.archive_recall,
  }
  const pending = view.suggestions?.filter((s) => s.status === 'pending') ?? []
  return (
    <section className={local.background} aria-label="策略后台与候选建议">
      <div className={local.backgroundHead}>
        <div>
          <h2>
            后台验证 <span className={local.status}>{plan.enabled ? '已开启' : '未开启'}</span>
          </h2>
          <p className={css.note}>
            {plan.enabled
              ? `${plan.strategy_ids.length} 项策略 · 下次 ${plan.next_at ? instant(plan.next_at) : '等待调度'} · 新候选与应用动作等你确认`
              : view.strategies.length
                ? '约定自动验证的范围与时间；保存计划后才会运行。'
                : '建立策略后，可约定自动验证的范围与时间。'}
          </p>
        </div>
        <button
          onClick={() =>
            edit({ action: 'schedule', schedule: policy, strategies: view.strategies })
          }
        >
          {plan.enabled ? '调整或停止后台计划' : '设置后台计划'}
        </button>
      </div>
      {pending.length > 0 && (
        <div className={local.proposal}>
          <h2>待确认候选 · {pending.length}</h2>
          {pending.map((s) => (
            <article key={s.id}>
              <strong>{s.document.candidate.name}</strong>
              <p>
                {s.source_kind === 'archive' ? '归档召回建议' : '事件研究建议'} ·{' '}
                {ruleLabels[s.document.candidate.kind]} ·{' '}
                {s.document.candidate.securities.map((x) => x.name).join('、')}
              </p>
              <p>{s.document.candidate.rationale}</p>
              <p className={css.note}>尚未保存为策略，未开始验证。{instant(s.created_at)}</p>
              <details>
                <summary>查看规则与来源</summary>
                <p>
                  {Object.entries(s.document.candidate.params)
                    .map(([k, v]) => `${k}=${v}`)
                    .join('，')}
                </p>
                {s.document.evidence.map((e: any, i: number) => (
                  <p key={i}>
                    {e.source || '策略归档'} · {e.observed_at ? instant(e.observed_at) : e.date}{' '}
                    {e.regime || ''}
                    {e.evidence_ref && <small>来源引用：{e.evidence_ref}</small>}
                  </p>
                ))}
              </details>
              <button
                onClick={() =>
                  edit({ action: 'accept_suggestion', payload: { suggestion_id: s.id } })
                }
              >
                查看并确认保存
              </button>
            </article>
          ))}
        </div>
      )}
      {!!view.background_jobs?.length && (
        <details>
          <summary>最近后台执行</summary>
          {view.background_jobs.slice(0, 12).map((job) => (
            <p key={job.id}>
              <strong>
                {view.strategies.find((s) => s.id === job.strategy_id)?.name || '范围内归档'}
              </strong>{' '}
              · {actionLabels[job.action]} · {runLabels[job.status] || job.status}
              <small>
                {instant(job.updated_at)}
                {job.error ? ` · ${job.error}` : ''}
              </small>
            </p>
          ))}
        </details>
      )}
      {!!view.planner_jobs?.length && (
        <details>
          <summary>事件候选研究进度</summary>
          {view.planner_jobs.slice(0, 8).map((job) => (
            <p key={job.id}>
              {runLabels[job.status] || job.status} · {instant(job.updated_at)}
              {job.error ? ` · ${job.error}` : ''}
            </p>
          ))}
        </details>
      )}
    </section>
  )
}
