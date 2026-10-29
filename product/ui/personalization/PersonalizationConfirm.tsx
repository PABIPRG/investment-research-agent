import { useState } from 'react'
import { DetailPanel } from '../DetailPanel.js'
import { request, errorText, ApiError } from '../shared/api.js'
import { personalizationQuestion } from '../../personalization-summary.js'
import type { PersonalPreview } from './model.js'
import form from '../Form.module.css'
export function PersonalizationConfirm({
  preview,
  close,
  saved,
}: {
  preview: PersonalPreview
  close: () => void
  saved: () => void
}) {
  const [busy, setBusy] = useState(false),
    [unknown, setUnknown] = useState(false),
    [error, setError] = useState(''),
    [conflict, setConflict] = useState(false)
  const perform = async () => {
    setBusy(true)
    setError('')
    try {
      if (unknown) {
        const r = await request<{ receipt?: { saved: boolean } }>('personalization', {
          operation: 'inspect',
          preview_id: preview.preview_id,
        })
        if (r.receipt?.saved) {
          saved()
          return
        }
        setUnknown(false)
        setError('尚无保存回执，请核对后确认或取消。')
      } else {
        await request('personalization', {
          operation: 'commit',
          preview_id: preview.preview_id,
          request_key: preview.preview_id,
        })
        saved()
      }
    } catch (e) {
      setError(errorText(e))
      if (e instanceof ApiError && e.status === 409) setConflict(true)
      else if (!unknown) {
        setUnknown(true)
        setError('提交结果待核对，请查询原回执。')
      }
    } finally {
      setBusy(false)
    }
  }
  return (
    <DetailPanel
      compact
      title="确认本机偏好变更"
      close={() => {
        if (!busy) close()
      }}
    >
      <div className={form.form}>
        <p style={{ whiteSpace: 'pre-wrap' }}>{personalizationQuestion(preview)}</p>
        {error && <p role="alert">{error}</p>}
        <div className={form.actions}>
          <button data-variant="primary" disabled={busy || conflict} onClick={() => void perform()}>
            {unknown ? '核对保存结果' : '确认保存'}
          </button>
          <button disabled={busy} onClick={close}>
            {conflict ? '返回刷新后重新预览' : '关闭'}
          </button>
        </div>
      </div>
    </DetailPanel>
  )
}
