import { Select } from '../shared/Select.js'
import { securityName } from '../business-model.js'
import { useState } from 'react'
import { DetailPanel } from '../DetailPanel.js'
import { FieldGroup } from '../shared/FieldGroup.js'
import { request, ApiError, errorText } from '../shared/api.js'
import { positionRiskQuestion } from '../../position-risk-summary.js'
import {
  targetNames,
  type PositionRiskView,
  type RiskEdit,
  type RuleTarget,
  type TargetKind,
} from './position-risk-model.js'
import { localTime } from './types.js'
import form from '../Form.module.css'
type DraftTarget = { enabled: boolean; mode: RuleTarget['mode']; value: string }
const draft = (t?: RuleTarget): DraftTarget => ({
  enabled: t?.enabled ?? true,
  mode: t?.mode ?? 'percent',
  value: t?.value == null ? '' : String(t.mode === 'percent' ? t.value * 100 : t.value),
})
export function RiskPlanEditor({
  view,
  edit,
  name,
  close,
}: {
  view: PositionRiskView
  edit: RiskEdit
  name?: string
  close: () => void
}) {
  const config =
    edit.operation === 'global'
      ? view.config.global
      : view.config.overrides[edit.ticker!] || view.config.global
  const [targets, setTargets] = useState<Record<TargetKind, DraftTarget>>({
    take_profit: draft(config?.take_profit),
    stop_loss: draft(config?.stop_loss),
  })
  const [disabled, setDisabled] = useState(config?.monitoring_disabled ?? false),
    [effective, setEffective] = useState(
      config?.effective_at ? localTime(config.effective_at) : '',
    ),
    [expires, setExpires] = useState(config?.expires_at ? localTime(config.expires_at) : '')
  const [preview, setPreview] = useState<any>(),
    [busy, setBusy] = useState(false),
    [unknown, setUnknown] = useState(false),
    [error, setError] = useState('')
  const configurable = edit.operation === 'global' || edit.operation === 'override'
  const label = edit.ticker
    ? `${securityName(edit.ticker, name, view.plans.find((p) => p.ticker === edit.ticker)?.name)}（${edit.ticker}）`
    : ''
  const finish = () => {
    window.dispatchEvent(new Event('huohuo-investment-changed'))
    close()
  }
  const prepare = async () => {
    setBusy(true)
    setError('')
    try {
      const payload: any = { ...edit }
      if (configurable)
        payload.config = {
          monitoring_disabled: disabled,
          effective_at: effective ? new Date(effective).toISOString() : null,
          expires_at: expires ? new Date(expires).toISOString() : null,
          ...Object.fromEntries(
            (['take_profit', 'stop_loss'] as TargetKind[]).map((kind) => {
              const t = targets[kind]
              return [
                kind,
                {
                  enabled: disabled ? false : t.enabled,
                  mode: t.mode,
                  value:
                    disabled || !t.enabled
                      ? null
                      : Number(t.value) / (t.mode === 'percent' ? 100 : 1),
                },
              ]
            }),
          ),
        }
      setPreview(
        await request('investment-command', {
          action: 'preview',
          command: 'position_risk',
          payload,
        }),
      )
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  const save = async () => {
    setBusy(true)
    setError('')
    try {
      if (unknown) {
        const r = await request<{ receipt?: { saved: boolean } }>('investment-command', {
          action: 'inspect-preview',
          preview_id: preview.preview_id,
        })
        if (r.receipt?.saved) finish()
        else {
          setUnknown(false)
          setError('尚无保存回执；请核对原预览后确认或取消。')
        }
      } else {
        await request('investment-command', {
          action: 'commit',
          preview_id: preview.preview_id,
          request_key: preview.preview_id,
        })
        finish()
      }
    } catch (e) {
      setError(errorText(e))
      if (e instanceof ApiError && e.status === 409) {
        setPreview(undefined)
        setUnknown(false)
      } else if (!unknown) {
        setUnknown(true)
        setError('保存结果待核对，请先查询原回执。')
      }
    } finally {
      setBusy(false)
    }
  }
  return (
    <DetailPanel
      title={edit.operation === 'global' ? '全局持仓风险配置' : `${label} 持仓风险`}
      close={() => {
        if (!busy) close()
      }}
    >
      <div className={form.form}>
        {error && <p role="alert">{error}</p>}
        {preview ? (
          <>
            <p style={{ whiteSpace: 'pre-wrap' }}>{positionRiskQuestion(preview)}</p>
            <div className={form.actions}>
              <button data-variant="primary" disabled={busy} onClick={() => void save()}>
                {unknown ? '核对保存结果' : '确认保存风险计划'}
              </button>
              <button disabled={busy || unknown} onClick={() => setPreview(undefined)}>
                返回修改
              </button>
              <button disabled={busy} onClick={close}>
                取消
              </button>
            </div>
          </>
        ) : (
          <form
            className={form.form}
            onSubmit={(e) => {
              e.preventDefault()
              void prepare()
            }}
          >
            <fieldset disabled={busy} className={form.form}>
              {configurable ? (
                <>
                  <p>
                    目标按激活时成本计算；成本变化后保持原线，重新布防才采用新成本。价格比较由程序执行，不额外调用研究模型。
                  </p>
                  <label className={form.choice}>
                    <input
                      type="checkbox"
                      checked={disabled}
                      onChange={(e) => setDisabled(e.target.checked)}
                    />
                    停用此范围的持仓风险监测
                  </label>
                  {view.suggestion && (
                    <button
                      type="button"
                      disabled={disabled}
                      onClick={() =>
                        setTargets({
                          take_profit: {
                            enabled: true,
                            mode: 'percent',
                            value: String(view.suggestion!.take_profit_pct * 100),
                          },
                          stop_loss: {
                            enabled: true,
                            mode: 'percent',
                            value: String(view.suggestion!.stop_loss_pct * 100),
                          },
                        })
                      }
                    >
                      填入当前画像建议（仍需核对确认）
                    </button>
                  )}
                  <div className={form.grid}>
                    {(['take_profit', 'stop_loss'] as TargetKind[]).map((kind) => {
                      const t = targets[kind],
                        change = (fields: Partial<DraftTarget>) =>
                          setTargets((old) => ({ ...old, [kind]: { ...old[kind], ...fields } }))
                      return (
                        <FieldGroup key={kind} title={targetNames[kind]}>
                          <label className={form.choice}>
                            <input
                              type="checkbox"
                              checked={t.enabled}
                              disabled={disabled}
                              onChange={(e) => change({ enabled: e.target.checked })}
                            />
                            启用{targetNames[kind]}
                          </label>
                          {edit.operation === 'override' && (
                            <label>
                              目标方式
                              <Select
                                value={t.mode}
                                disabled={disabled || !t.enabled}
                                onChange={(e) =>
                                  change({ mode: e.target.value as RuleTarget['mode'], value: '' })
                                }
                              >
                                <option value="percent">相对激活成本百分比</option>
                                <option value="price">绝对价格</option>
                              </Select>
                            </label>
                          )}
                          <label>
                            {t.mode === 'percent' ? '幅度（%）' : '目标价格（元）'}
                            <input
                              type="number"
                              min="0"
                              step="0.01"
                              required={!disabled && t.enabled}
                              disabled={disabled || !t.enabled}
                              value={t.value}
                              onChange={(e) => change({ value: e.target.value })}
                            />
                          </label>
                        </FieldGroup>
                      )
                    })}
                  </div>
                  <div className={form.grid}>
                    <label>
                      生效时间（留空为确认后，本机时区）
                      <input
                        type="datetime-local"
                        value={effective}
                        onChange={(e) => setEffective(e.target.value)}
                      />
                    </label>
                    <label>
                      到期时间（可选，本机时区）
                      <input
                        type="datetime-local"
                        value={expires}
                        onChange={(e) => setExpires(e.target.value)}
                      />
                    </label>
                  </div>
                </>
              ) : (
                <p>
                  {edit.operation === 'rearm'
                    ? `重新布防${edit.kind ? targetNames[edit.kind] : ''}，将按当前成本建立新的激活代次并撤销旧代次资格。`
                    : '删除这只持仓的独立配置，重新继承全局设置；请在下一步核对实际影响。'}
                </p>
              )}
            </fieldset>
            <div className={form.actions}>
              <button data-variant="primary" disabled={busy}>
                预览风险计划
              </button>
              <button type="button" disabled={busy} onClick={close}>
                取消
              </button>
            </div>
          </form>
        )}
      </div>
    </DetailPanel>
  )
}
