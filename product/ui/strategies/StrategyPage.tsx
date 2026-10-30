import { useSnapshot } from '../shared/useSnapshot.js'
import { ReadFeedback } from '../shared/ReadFeedback.js'
import { ReadStatus } from '../shared/ReadStatus.js'
import { useEffect, useState } from 'react'
import { request, errorText } from '../shared/api.js'
import {
  actionLabels,
  resultNotice,
  participation,
  verification,
  ruleLabels,
  runLabels,
  pct,
  type StrategyView,
  type Edit,
} from './model.js'
import { BackgroundPanel } from './BackgroundPanel.js'
import { RunHistory } from './RunHistory.js'
import { CommandDialog } from './CommandDialog.js'
import { StrategyDetails } from './StrategyDetails.js'
import page from '../shared/Page.module.css'
import css from '../Business.module.css'
import local from './Strategy.module.css'
export function StrategyPage() {
  const [commandError, setError] = useState('')
  const [notice, setNotice] = useState(''),
    [revision, refresh] = useState(0),
    [selected, setSelected] = useState<string>(),
    [edit, setEdit] = useState<Edit>()
  const snapshot = useSnapshot<StrategyView>(
    `strategies:${revision}`,
    (signal) => request('strategies', undefined, signal),
    {
      paused: !!edit,
      pollMs: (data) =>
        data.runs.some((r) => r.status === 'running')
          ? 3000
          : data.automation?.enabled
            ? 60000
            : undefined,
    },
  )
  const view = snapshot.data,
    loading = snapshot.loading,
    error = commandError || snapshot.error
  const strategy = view?.strategies.find((s) => s.id === selected)
  const hasStrategies = !!view?.strategies.length
  const active = view?.strategies.filter((s) => s.status === 'active').length ?? 0
  const openEdit = (e: Edit) => {
    setSelected(undefined)
    setEdit(e)
  }
  return (
    <main className={`${page.surface} ${css.page}`}>
      <header className={`${page.header} ${css.header} ${local.routeHeader}`}>
        <div>
          <h1>验证与演进</h1>
          <p className={css.note}>研究策略 · 回测 · 影子验证</p>
        </div>
        <div className={css.tools}>
          {hasStrategies && (
            <button data-variant="primary" onClick={() => setEdit({ action: 'create' })}>
              新增策略
            </button>
          )}
          {active > 0 && (
            <button
              disabled={!active || loading}
              onClick={() => setEdit({ action: 'evolve', poolVersion: view!.state_version })}
            >
              生成全池预案
            </button>
          )}
          <button disabled={loading || snapshot.refreshing} onClick={snapshot.refresh}>
            刷新记录
          </button>
        </div>
      </header>
      <ReadFeedback error={error} notice={notice} />
      <ReadStatus loading={loading} hasData={view !== undefined} label="正在读取策略与验证记录…" />
      {view && (
        <>
          {hasStrategies && (
            <div className={local.summary}>
              <span>
                策略 <b>{view.strategies.length}</b>
              </span>
              <span>
                参与验证 <b>{active}</b>
              </span>
              <span>
                有效影子日期 <b>{view.attribution.days_of_data}</b>
              </span>
              <span>
                影子组合收益 <b>{pct(view.attribution.overall?.return_pct)}</b>
              </span>
            </div>
          )}
          {hasStrategies && <BackgroundPanel view={view} edit={openEdit} />}
          {view.preview.actions?.length > 0 && (
            <section className={local.proposal}>
              <h2>全池进化预案</h2>
              <p>
                {view.preview.valid ? '待你确认，尚未应用' : '依据已变化或预案已过期，请重新生成'}
              </p>
              {view.preview.actions.map((a: any, i: number) => (
                <p key={i}>
                  <strong>
                    {view.strategies.find((s) => s.id === (a.sid || a.parent))?.name ||
                      a.name ||
                      '新候选'}
                  </strong>{' '}
                  · {a.reason || a.name}
                </p>
              ))}
              <button
                disabled={!view.preview.valid}
                onClick={() =>
                  setEdit({
                    action: 'apply',
                    poolVersion: view.state_version,
                    token: view.preview.preview_token,
                  })
                }
              >
                查看并确认应用
              </button>
            </section>
          )}
          {!view.strategies.length ? (
            <section className={local.empty} aria-label="建立策略">
              <h2>先建立一项策略</h2>
              <p>选择证券与规则，保存后可运行历史回测和影子验证。</p>
              <button data-variant="primary" onClick={() => setEdit({ action: 'create' })}>
                建立第一项策略
              </button>
            </section>
          ) : (
            <div className={css.tableWrap}>
              <table className={css.table}>
                <thead>
                  <tr>
                    {[
                      '策略 / 证券',
                      '规则',
                      '参与状态',
                      '样本外验证',
                      '影子收益 / 回撤',
                      '下一步',
                    ].map((x) => (
                      <th key={x}>{x}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {view.strategies.map((s) => {
                    const attr = view.attribution.strategies?.find(
                      (r: any) => r.strategy_id === s.id,
                    )
                    return (
                      <tr key={s.id}>
                        <td>
                          <strong>{s.name}</strong>
                          <small>{s.securities.map((x) => x.name).join('、')}</small>
                        </td>
                        <td>
                          {ruleLabels[s.kind]}
                          <small>版本 {s.revision}</small>
                        </td>
                        <td>{participation[s.status]}</td>
                        <td>
                          {verification[s.verification_status]}
                          <small>{s.backtest?.reason}</small>
                        </td>
                        <td>
                          {pct(attr?.return_pct)} / {pct(attr?.max_drawdown_pct)}
                        </td>
                        <td>
                          <button onClick={() => setSelected(s.id)}>查看记录</button>
                          {s.status === 'candidate' && (
                            <button onClick={() => openEdit({ action: 'backtest', strategy: s })}>
                              运行回测
                            </button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          {!hasStrategies && <BackgroundPanel view={view} edit={openEdit} />}
          {view.runs.some((r) => r.status === 'running') && (
            <section className={local.running}>
              <h2>正在运行</h2>
              {view.runs
                .filter((r) => r.status === 'running')
                .map((r) => (
                  <p key={r.id}>
                    {view.strategies.find((s) => s.id === r.strategy_id)?.name} ·{' '}
                    {actionLabels[r.action]} · {runLabels[r.status]}{' '}
                    <button
                      onClick={() =>
                        void request('strategy-command', { operation: 'cancel', run_id: r.id })
                          .then(() => refresh((v) => v + 1))
                          .catch((e) => setError(errorText(e)))
                      }
                    >
                      停止计算
                    </button>
                  </p>
                ))}
            </section>
          )}
          <p className={`${css.note} ${local.disclaimer}`}>
            影子验证使用虚拟资金；模拟收益与实际持仓收益分开。后台只按已确认计划执行，候选保存与预案应用须另行确认。
          </p>
          <RunHistory view={view} open={setSelected} />
          {strategy && (
            <StrategyDetails
              strategy={strategy}
              view={view}
              close={() => setSelected(undefined)}
              edit={openEdit}
            />
          )}
        </>
      )}
      {edit && (
        <CommandDialog
          edit={edit}
          close={() => {
            setEdit(undefined)
            refresh((v) => v + 1)
          }}
          done={(r: any) => {
            setEdit(undefined)
            setNotice(resultNotice(r, edit.action))
            refresh((v) => v + 1)
          }}
        />
      )}
    </main>
  )
}
