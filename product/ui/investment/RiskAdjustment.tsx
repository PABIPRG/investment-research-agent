import { useState } from 'react'
import { DetailPanel } from '../DetailPanel.js'
import { FieldGroup } from '../shared/FieldGroup.js'
import { ApiError, errorText, request } from '../shared/api.js'
import form from '../Form.module.css'
import type { Facts } from './types.js'

export function RiskAdjustment({ facts }: { facts: Facts }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button disabled={!facts.risk_profile} onClick={() => setOpen(true)}>
        手动调整风险偏好
      </button>
      {open && <AdjustmentEditor facts={facts} close={() => setOpen(false)} />}
    </>
  )
}
function AdjustmentEditor({ facts, close }: { facts: Facts; close: () => void }) {
  const [risk, setRisk] = useState(facts.risk_profile?.manual_adjust?.risk_tolerance ?? 0.5)
  const [years, setYears] = useState(facts.risk_profile?.manual_adjust?.horizon_years ?? 3)
  const [preview, setPreview] = useState<{ preview_id: string; after: Facts }>()
  const [busy, setBusy] = useState(false),
    [unknown, setUnknown] = useState(false),
    [error, setError] = useState('')
  const finish = () => {
    window.dispatchEvent(new Event('huohuo-investment-changed'))
    close()
  }
  const perform = async (action: 'preview' | 'commit' | 'inspect-preview') => {
    setBusy(true)
    setError('')
    try {
      if (action === 'preview')
        setPreview(
          await request('investment-command', {
            action,
            command: 'risk_adjust',
            payload: { risk_tolerance: risk, horizon_years: years },
          }),
        )
      else if (action === 'commit') {
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
      title="手动调整风险偏好"
      close={() => {
        if (!busy) close()
      }}
    >
      <div className={form.form}>
        <p>
          原问卷答案、分数和推断画像保留，调整后另存有效画像及历史。此操作不修改持仓或已有委托。
        </p>
        {error && <p role="alert">{error}</p>}
        {preview ? (
          <FieldGroup title="保存前核对">
            <strong>
              当前生效：{facts.risk_profile?.label} → {preview.after.risk_profile?.label}
            </strong>
            <p>
              风险承受度 {risk}，投资期限 {years} 年。短于两年最高为稳健型，五年以上最低为稳健型。
            </p>
          </FieldGroup>
        ) : (
          <FieldGroup title="风险承受度与期限">
            <div className={form.grid}>
              <label>
                风险承受度：{risk}（0 保守、0.5 稳健、1 进取）
                <input
                  aria-label="风险承受度"
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={risk}
                  onChange={(e) => setRisk(Number(e.target.value))}
                />
              </label>
              <label>
                投资期限：{years} 年
                <input
                  aria-label="投资期限"
                  type="range"
                  min="1"
                  max="30"
                  step="1"
                  value={years}
                  onChange={(e) => setYears(Number(e.target.value))}
                />
              </label>
            </div>
          </FieldGroup>
        )}
        <div className={form.actions}>
          <button
            data-variant="primary"
            disabled={busy}
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
