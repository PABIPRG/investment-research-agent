import { useId, useState } from 'react'
import { DetailPanel } from '../DetailPanel.js'
import { FieldGroup } from '../shared/FieldGroup.js'
import { ApiError, errorText, request } from '../shared/api.js'
import form from '../Form.module.css'
import css from './RiskAdjustment.module.css'
import {
  adjustmentDefaults,
  toleranceLabel,
  toleranceOptions,
  validHorizon,
} from './risk-adjustment-model.js'
import { RiskAdjustmentPreview } from './RiskAdjustmentPreview.js'
import type { Facts, Preview } from './types.js'

export function RiskAdjustment({ facts }: { facts: Facts }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button disabled={!facts.risk_profile} onClick={() => setOpen(true)}>
        调整风险偏好
      </button>
      {open && <AdjustmentEditor facts={facts} close={() => setOpen(false)} />}
    </>
  )
}
function AdjustmentEditor({ facts, close }: { facts: Facts; close: () => void }) {
  const defaults = adjustmentDefaults(facts.risk_profile)
  const [risk, setRisk] = useState(defaults.risk)
  const [years, setYears] = useState(defaults.years)
  const [currentLabel, setCurrentLabel] = useState(facts.risk_profile?.label)
  const [preview, setPreview] = useState<Preview>()
  const [busy, setBusy] = useState(false),
    [unknown, setUnknown] = useState(false),
    [error, setError] = useState('')
  const id = useId()
  const valid = validHorizon(years)
  const finish = () => {
    window.dispatchEvent(new Event('huohuo-investment-changed'))
    close()
  }
  const perform = async (action: 'preview' | 'commit' | 'inspect-preview') => {
    if (action === 'preview' && !valid) return
    setBusy(true)
    setError('')
    try {
      if (action === 'preview') {
        const next = await request<Preview>('investment-command', {
          action,
          command: 'risk_adjust',
          payload: { risk_tolerance: risk, horizon_years: Number(years) },
        })
        setPreview(next)
        setCurrentLabel(next.before.risk_profile?.label)
      } else if (action === 'commit') {
        await request('investment-command', {
          action,
          preview_id: preview!.preview_id,
          request_key: preview!.preview_id,
        })
        finish()
      } else {
        const r = await request<{ receipt?: { saved: boolean } }>('investment-command', {
          action,
          preview_id: preview!.preview_id,
        })
        if (r.receipt?.saved) finish()
        else {
          setUnknown(false)
          setError('尚无保存回执；请核对原预览后确认或取消。')
        }
      }
    } catch (e) {
      setError(errorText(e))
      if (e instanceof ApiError && e.status === 409) {
        setPreview(undefined)
        setUnknown(false)
        setCurrentLabel(undefined)
        setError('偏好已更新，原输入已保留；请再次预览，核对最新生效档位。')
      } else if (action === 'commit') {
        setUnknown(true)
        setError('保存结果待核对，请先查询原回执。')
      }
    } finally {
      setBusy(false)
    }
  }
  return (
    <DetailPanel
      compact
      title={preview ? '确认风险偏好调整' : '调整风险偏好'}
      close={() => {
        if (!busy) close()
      }}
    >
      <div className={form.form}>
        {error && (
          <p role="alert" className={form.error}>
            {error}
          </p>
        )}
        {preview ? (
          <RiskAdjustmentPreview
            before={preview.before}
            after={preview.after}
            risk={risk}
            years={years}
          />
        ) : (
          <>
            <div className={css.intro}>
              <strong>
                {currentLabel ? '当前生效：' + currentLabel : '当前偏好已更新，请重新预览核对'}
              </strong>
              <p>
                告诉火火你愿意接受的波动，以及这笔资金预计何时使用。下一步会先核对结果，确认后才保存。
              </p>
            </div>
            <FieldGroup
              title="你愿意接受多大的投资波动？"
              hint={
                facts.risk_profile?.manual_adjust
                  ? '已带入上次确认的选择；请按现在的实际感受调整。'
                  : '选择最接近自己实际感受的一项。已按当前生效偏好带入，可重新选择。'
              }
            >
              <fieldset className={css.choices} disabled={busy}>
                <legend className={css.note}>接受波动的意愿</legend>
                {toleranceOptions.map((option) => {
                  const selected = toleranceLabel(risk) === option.label
                  return (
                    <label key={option.value} className={css.choice} data-selected={selected}>
                      <input
                        type="radio"
                        name={id + '-risk'}
                        value={option.value}
                        checked={selected}
                        onChange={() => setRisk(option.value)}
                        aria-describedby={id + '-risk-' + option.value}
                      />
                      <strong>{option.label}</strong>
                      <span id={id + '-risk-' + option.value}>{option.description}</span>
                    </label>
                  )
                })}
              </fieldset>
            </FieldGroup>
            <FieldGroup
              title="这笔投资资金预计多久后要用？"
              hint="填写资金预计可以留在投资中的时间，不是对单只股票持有时间的要求。"
            >
              <div className={css.horizon}>
                <label htmlFor={id + '-years'}>预计投资年数</label>
                <div className={css.yearField}>
                  <input
                    id={id + '-years'}
                    type="number"
                    inputMode="numeric"
                    min="1"
                    max="30"
                    step="1"
                    required
                    value={years}
                    placeholder="填写年数"
                    disabled={busy}
                    aria-describedby={id + '-years-hint'}
                    aria-invalid={!!years && !valid}
                    onChange={(event) => setYears(event.target.value)}
                  />
                  <span>年</span>
                </div>
                <div className={css.presets} role="group" aria-label="常用投资期限">
                  {[1, 3, 5, 10].map((value) => (
                    <button
                      key={value}
                      type="button"
                      disabled={busy}
                      aria-pressed={years === String(value)}
                      onClick={() => setYears(String(value))}
                    >
                      {value} 年
                    </button>
                  ))}
                </div>
                <small id={id + '-years-hint'}>
                  {years && !valid
                    ? '请填写 1–30 之间的整数年。'
                    : '支持 1–30 年；选择常用期限后也可以直接修改年数。'}
                </small>
              </div>
            </FieldGroup>
            <p className={css.note}>
              调整用于火火的研究提示和建议校准。原问卷及历史记录会保留，持仓与已有委托保持原状。
            </p>
          </>
        )}
        {!preview && !valid && <p className={css.note}>填写投资年数后，即可预览调整结果。</p>}
        <div className={form.actions}>
          <button
            data-variant="primary"
            disabled={busy || (!preview && !valid)}
            onClick={() =>
              void perform(preview ? (unknown ? 'inspect-preview' : 'commit') : 'preview')
            }
          >
            {busy
              ? '正在核对…'
              : preview
                ? unknown
                  ? '核对保存结果'
                  : '确认保存调整'
                : '预览调整结果'}
          </button>
          {preview && (
            <button disabled={busy || unknown} onClick={() => setPreview(undefined)}>
              返回修改
            </button>
          )}
          <button disabled={busy} onClick={close}>
            取消
          </button>
        </div>
      </div>
    </DetailPanel>
  )
}
