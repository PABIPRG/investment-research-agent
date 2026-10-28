import { DetailPanel } from '../DetailPanel.js'
import {
  pct,
  verification,
  participation,
  instant,
  ruleLabels,
  previewState,
  type Strategy,
  type StrategyView,
  type Edit,
  actionLabels,
  runLabels,
} from './model.js'
import css from '../Business.module.css'
export function StrategyDetails({
  strategy: s,
  view,
  close,
  edit,
}: {
  strategy: Strategy
  view: StrategyView
  close: () => void
  edit: (e: Edit) => void
}) {
  const attr = view.attribution.strategies?.find(
      (r: any) => r.strategy_id === s.id || r.subjects?.includes(s.id),
    ),
    preview = view.previews?.[s.id] ?? view.preview
  const runs = view.runs.filter((r) => r.strategy_id === s.id || r.subjects?.includes(s.id))
  const ownPreview = preview.strategy_id === s.id
  return (
    <DetailPanel title={`${s.name} · 验证记录`} close={close}>
      <p>
        {s.securities.map((x) => x.name).join('、')} · {ruleLabels[s.kind]} ·{' '}
        {participation[s.status]} · {verification[s.verification_status]}
      </p>
      {s.rationale && <p>{s.rationale}</p>}
      <dl className={css.metrics}>
        <div>
          影子收益 <b>{pct(attr?.return_pct)}</b>
        </div>
        <div>
          最大回撤 <b>{pct(attr?.max_drawdown_pct)}</b>
        </div>
        <div>
          已平仓模拟 <b>{attr?.closed_trades ?? '—'} 笔</b>
        </div>
      </dl>
      <div className={css.tools}>
        {['backtest', 'shadow', 'evolve'].map((action) => (
          <button
            key={action}
            disabled={action !== 'backtest' && s.status !== 'active'}
            onClick={() => edit({ action, strategy: s })}
          >
            {actionLabels[action]}
          </button>
        ))}
      </div>
      {s.status === 'candidate' && (
        <p className={css.note}>先运行回测，再开始影子验证。参与验证与样本外达标是两个独立状态。</p>
      )}
      <h3>样本内与样本外</h3>
      {!s.backtest?.out_of_sample ? (
        <p>尚未完成回测。</p>
      ) : (
        <>
          <p>{s.backtest.reason}</p>
          <div className={css.tableWrap}>
            <table className={css.table}>
              <thead>
                <tr>
                  <th>范围</th>
                  <th>成交数</th>
                  <th>胜率</th>
                  <th>平均成交收益</th>
                  <th>组合收益</th>
                  <th>组合最大回撤</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['样本内', 'in_sample'],
                  ['样本外', 'out_of_sample'],
                ].map(([name, key]) => {
                  const r = s.backtest[key]
                  return (
                    <tr key={key}>
                      <td>{name}</td>
                      <td>{r?.n_evaluated ?? '—'}</td>
                      <td>{pct(r?.win_rate_pct)}</td>
                      <td>{pct(r?.avg_simulated_return_pct)}</td>
                      <td>{pct(r?.portfolio?.portfolio_return_pct)}</td>
                      <td>{pct(r?.portfolio?.portfolio_max_drawdown_pct)}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </>
      )}
      <h3>进化预案</h3>
      <p>{ownPreview ? previewState(preview) : '尚未生成这项策略的预案。'}</p>
      {ownPreview &&
        preview.actions?.map((a: any, i: number) => (
          <p key={i}>
            <strong>
              {(
                { promote: '升级', demote: '观察', retire: '停止', mutate: '生成新候选' } as Record<
                  string,
                  string
                >
              )[a.type] ?? '候选动作'}
            </strong>{' '}
            · {a.reason || a.name}
          </p>
        ))}
      {ownPreview && preview.valid && preview.actions?.length > 0 && (
        <button
          onClick={() => edit({ action: 'apply', strategy: s, token: preview.preview_token })}
        >
          查看并确认应用
        </button>
      )}
      <h3>运行与行情依据</h3>
      {!runs.length && <p>尚无运行记录。完成计算后可在这里核对范围与来源。</p>}
      {runs.map((r) => (
        <details key={r.id}>
          <summary>
            {actionLabels[r.action]} · {runLabels[r.status]} · {instant(r.created_at)}
          </summary>
          {r.result?.backtest?.reason && <p>{r.result.backtest.reason}</p>}
          {r.result?.evolution && (
            <p>
              {r.result.evolution.data_note ||
                (r.result.evolution.actions?.length
                  ? `${r.result.evolution.actions.length} 项候选动作；${r.result.evolution.applied ? '已应用' : '尚未应用'}`
                  : '当前没有调整动作')}
            </p>
          )}
          {r.result?.skipped && <p>{r.result.skipped}</p>}
          {r.error && <p role="alert">{r.error}</p>}
          {r.evidence.map((ev: any, i: number) => (
            <p key={i}>
              {s.securities.find((x) => x.code === ev.code)?.name || '市场基准'} · {ev.source}
              <br />
              {ev.actual_window.join(' — ')} · {ev.bars} 根日线 ·{' '}
              {ev.adjustment === 'qfq' ? '前复权' : '原始口径'}
              <br />
              采集于 {instant(ev.fetched_at)}
            </p>
          ))}
          <small>记录标识：{r.id}</small>
        </details>
      ))}
      <details>
        <summary>规则参数与模拟口径</summary>
        <p>
          {Object.entries(s.params)
            .map(([k, v]) => `${k}: ${v}`)
            .join(' · ')}
        </p>
        <p>{view.model_note}</p>
        <p>
          策略版本 {s.revision} · 更新于 {instant(s.updated_at)}
        </p>
      </details>
      {s.status !== 'retired' && (
        <p>
          <button onClick={() => edit({ action: 'retire', strategy: s })}>停止这项策略验证</button>
        </p>
      )}
    </DetailPanel>
  )
}
