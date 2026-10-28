import { useState } from 'react'
import type { Strategy, StrategySchedule } from './model.js'
import form from '../Form.module.css'
import css from '../Business.module.css'
import { FieldGroup } from '../shared/FieldGroup.js'
export function ScheduleForm({
  initial,
  strategies,
  busy,
  submit,
}: {
  initial: StrategySchedule
  strategies: Strategy[]
  busy: boolean
  submit: (value: StrategySchedule) => void
}) {
  const [value, setValue] = useState(initial)
  const change = (key: keyof StrategySchedule, next: unknown) =>
    setValue((v) => ({ ...v, [key]: next }))
  return (
    <form
      className={form.form}
      onSubmit={(e) => {
        e.preventDefault()
        submit(value)
      }}
    >
      <label className={form.choice}>
        <input
          type="checkbox"
          checked={value.enabled}
          disabled={busy}
          onChange={(e) => change('enabled', e.target.checked)}
        />
        启用后台验证
      </label>
      <p className={css.note}>
        关闭后停止排队任务，在途结果不会写入；既有记录保留。再次启用按新约定继续。
      </p>
      {value.enabled && (
        <>
          <FieldGroup title="执行范围" hint="只验证你明确选中的策略。">
            <fieldset disabled={busy}>
              {strategies.map((s) => (
                <label className={form.choice} key={s.id}>
                  <input
                    type="checkbox"
                    checked={value.strategy_ids.includes(s.id)}
                    onChange={(e) =>
                      change(
                        'strategy_ids',
                        e.target.checked
                          ? [...value.strategy_ids, s.id]
                          : value.strategy_ids.filter((id) => id !== s.id),
                      )
                    }
                  />
                  {s.name} · {s.securities.map((x) => x.name).join('、')}
                </label>
              ))}
              {!strategies.length && <p>先保存一项策略，再约定后台范围。</p>}
            </fieldset>
          </FieldGroup>
          <FieldGroup title="验证动作">
            <fieldset disabled={busy}>
              {(
                [
                  ['backtest', '定期回测'],
                  ['shadow', '更新影子验证'],
                  ['evolve', '生成演进预案'],
                ] as const
              ).map(([key, name]) => (
                <label className={form.choice} key={key}>
                  <input
                    type="checkbox"
                    checked={value.actions.includes(key)}
                    onChange={(e) =>
                      change(
                        'actions',
                        e.target.checked
                          ? [...value.actions, key]
                          : value.actions.filter((a) => a !== key),
                      )
                    }
                  />
                  {name}
                </label>
              ))}
            </fieldset>
          </FieldGroup>
          <FieldGroup title="执行时间与样本">
            <div className={form.grid}>
              <label>
                工作日执行时间（北京时间）
                <input
                  type="time"
                  required
                  min="16:00"
                  max="23:59"
                  value={value.daily_time}
                  disabled={busy}
                  onChange={(e) => change('daily_time', e.target.value)}
                />
              </label>
              <label>
                回测间隔（天）
                <input
                  type="number"
                  required
                  min={1}
                  max={365}
                  value={value.retest_days}
                  disabled={busy}
                  onChange={(e) => change('retest_days', Number(e.target.value))}
                />
              </label>
            </div>
            <label>
              回测样本长度（自然日）
              <input
                type="number"
                required
                min={40}
                max={1095}
                value={value.lookback_days}
                disabled={busy}
                onChange={(e) => change('lookback_days', Number(e.target.value))}
              />
            </label>
          </FieldGroup>
          <FieldGroup title="候选建议" hint="建议只进入候选记录，应用时仍需你确认。">
            <label className={form.choice}>
              <input
                type="checkbox"
                checked={value.event_candidates}
                disabled={busy}
                onChange={(e) => change('event_candidates', e.target.checked)}
              />
              按上述时间读取范围内证券新闻，生成候选建议（最多 20 只）
            </label>
            <label className={form.choice}>
              <input
                type="checkbox"
                checked={value.archive_recall}
                disabled={busy}
                onChange={(e) => change('archive_recall', e.target.checked)}
              />
              市场环境匹配时，建议召回范围内的归档策略
            </label>
            <p className={css.note}>
              休市或没有新行情时不会补造影子收益。新候选、归档召回和演进预案均需另行确认，不自动交易或应用。
            </p>
          </FieldGroup>
        </>
      )}
      <div className={form.actions}>
        <button
          data-variant="primary"
          type="submit"
          disabled={
            busy || (value.enabled && (!value.strategy_ids.length || !value.actions.length))
          }
        >
          预览后台约定
        </button>
      </div>
    </form>
  )
}
