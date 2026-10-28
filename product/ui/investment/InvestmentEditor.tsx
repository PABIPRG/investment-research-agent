import { useEffect, useRef, useState } from 'react'
import { DetailPanel } from '../DetailPanel.js'
import css from '../Form.module.css'
import { ApiError, errorText, request } from '../shared/api.js'
import { initialDraft, previewCommand, type InvestmentDraft } from './editor-model.js'
import { InvestmentFields } from './InvestmentFields.js'
import { InvestmentPreview } from './InvestmentPreview.js'
import type { EditTarget, Facts, Preview } from './types.js'
export function InvestmentEditor({
  target,
  close,
  saved,
}: {
  target: EditTarget
  close: () => void
  saved: (version: number) => void
}) {
  const [draft, setDraft] = useState(() => initialDraft(target)),
    [preview, setPreview] = useState<Preview>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('')
  const requestId = useRef(crypto.randomUUID())
  const step = useRef<HTMLDivElement>(null)
  const previewVisible = !!preview
  useEffect(() => {
    step.current?.focus()
  }, [previewVisible])
  const change = (patch: Partial<InvestmentDraft>) => {
    setDraft((old) => ({ ...old, ...patch }))
    setPreview(undefined)
    setError('')
  }
  const showPreview = async () => {
    setBusy(true)
    setError('')
    try {
      const command = previewCommand(target, draft, requestId.current)
      setPreview(await request<Preview>('investment-command', { action: 'preview', ...command }))
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  const commit = async () => {
    if (!preview) return
    setBusy(true)
    setError('')
    try {
      const result = await request<{ facts: Facts }>('investment-command', {
        action: 'commit',
        preview_id: preview.preview_id,
        request_key: preview.preview_id,
      })
      window.dispatchEvent(new Event('huohuo-investment-changed'))
      saved(result.facts.version)
    } catch (e) {
      setError(errorText(e))
      if (e instanceof ApiError && e.status === 409) setPreview(undefined)
    } finally {
      setBusy(false)
    }
  }
  const title =
    target.kind === 'holding'
      ? target.position
        ? '校正持仓'
        : '添加持仓'
      : {
          watchlist: '添加自选',
          trade: '记录已发生成交',
          revision: '更正成交',
          remove: '移除自选',
        }[target.kind]
  return (
    <DetailPanel
      title={title}
      close={() => {
        if (!busy) close()
      }}
    >
      <div ref={step} tabIndex={-1} className={css.steps} aria-label="记录步骤">
        {preview ? (
          <>
            <span>1 填写记录</span>
            <strong>2 核对并保存</strong>
          </>
        ) : (
          <>
            <strong>1 填写记录</strong>
            <span>2 核对并保存</span>
          </>
        )}
      </div>
      {error && (
        <p role="alert" className={css.error}>
          {error}
        </p>
      )}
      {preview ? (
        <>
          <InvestmentPreview preview={preview} target={target} draft={draft} />
          <div className={css.actions}>
            <button data-variant="primary" disabled={busy} onClick={() => void commit()}>
              {busy ? '正在保存…' : '确认保存'}
            </button>
            <button disabled={busy} onClick={() => setPreview(undefined)}>
              返回修改
            </button>
          </div>
        </>
      ) : (
        <form
          className={css.form}
          onSubmit={(e) => {
            e.preventDefault()
            void showPreview()
          }}
        >
          <fieldset disabled={busy}>
            {target.kind === 'remove' ? (
              <p>
                移除 <strong>{target.watch?.name}</strong>（{target.watch?.ticker}
                ）的自选记录？持仓和委托不会改变。
              </p>
            ) : (
              <InvestmentFields target={target} draft={draft} change={change} disabled={busy} />
            )}
          </fieldset>
          <div className={css.actions}>
            <button data-variant="primary" disabled={busy || !draft.security}>
              {busy ? '正在核对…' : '下一步：核对影响'}
            </button>
            <button type="button" disabled={busy} onClick={close}>
              取消
            </button>
          </div>
        </form>
      )}
    </DetailPanel>
  )
}
