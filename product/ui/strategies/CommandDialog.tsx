import { useEffect, useState } from 'react'
import { DetailPanel } from '../DetailPanel.js'
import { request, errorText } from '../shared/api.js'
import { ScheduleForm } from './ScheduleForm.js'
import { StrategyForm } from './StrategyForm.js'
import { actionLabels, type Edit } from './model.js'
import css from '../Business.module.css'
import form from '../Form.module.css'
export function CommandDialog({
  edit,
  close,
  done,
}: {
  edit: Edit
  close: () => void
  done: (result: any) => void
}) {
  const [preview, setPreview] = useState<any>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState('')
  const prepare = async (payload: any) => {
    setBusy(true)
    setError('')
    try {
      setPreview(
        await request('strategy-command', {
          operation: 'prepare',
          request_key: crypto.randomUUID(),
          action: edit.action,
          payload,
        }),
      )
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  useEffect(() => {
    if (edit.payload) void prepare(edit.payload)
    else if (!['create', 'backtest', 'schedule'].includes(edit.action))
      void prepare({
        ...(edit.strategy
          ? { strategy_id: edit.strategy.id, revision: edit.strategy.revision }
          : { scope: 'pool', state_version: edit.poolVersion }),
        ...(edit.token ? { preview_token: edit.token } : {}),
      })
  }, [])
  const commit = async () => {
    setBusy(true)
    setError('')
    try {
      const r = await request('strategy-command', {
        operation: 'commit',
        preview_id: preview.preview_id,
        request_key: preview.request_key,
      })
      done(r)
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10)
  return (
    <DetailPanel compact title={actionLabels[edit.action]} close={close}>
      {error && (
        <p className={form.error} role="alert">
          {error}
        </p>
      )}
      {!preview && edit.action === 'schedule' && edit.schedule && (
        <ScheduleForm
          initial={edit.schedule}
          strategies={edit.strategies || []}
          busy={busy}
          submit={(p) => void prepare(p)}
        />
      )}
      {!preview && edit.action === 'create' && (
        <StrategyForm submit={(p) => void prepare(p)} busy={busy} />
      )}
      {!preview && edit.action === 'backtest' && (
        <form
          className={form.form}
          onSubmit={(e) => {
            e.preventDefault()
            const data = new FormData(e.currentTarget)
            void prepare({
              strategy_id: edit.strategy!.id,
              revision: edit.strategy!.revision,
              start_date: data.get('start'),
              end_date: data.get('end'),
            })
          }}
        >
          <p>
            <strong>{edit.strategy?.name}</strong> · 样本内/外 70 / 30
          </p>
          <label>
            开始日期
            <input
              type="date"
              name="start"
              required
              defaultValue={new Date(Date.now() - 730 * 86400000).toISOString().slice(0, 10)}
              disabled={busy}
            />
          </label>
          <label>
            结束日期
            <input
              type="date"
              name="end"
              max={yesterday}
              required
              defaultValue={yesterday}
              disabled={busy}
            />
          </label>
          <p className={css.note}>40–1095 个自然日。模拟不含费用、滑点和涨跌停成交约束。</p>
          <div className={form.actions}>
            <button data-variant="primary" type="submit" disabled={busy}>
              预览回测范围
            </button>
          </div>
        </form>
      )}
      {preview && (
        <>
          <p>{preview.summary}</p>
          <p className={css.note}>
            {edit.action === 'schedule'
              ? '这次确认更新上述后台约定；新候选和预案应用仍需另行确认，不进行真实交易。'
              : '这次确认只执行上面的操作，不进行真实交易，也不启用后台自动运行。'}
          </p>
          <div className={css.tools}>
            <button data-variant="primary" disabled={busy} onClick={() => void commit()}>
              确认执行
            </button>
            <button disabled={busy} onClick={close}>
              暂不执行
            </button>
          </div>
        </>
      )}
      {busy && (
        <p role="status">
          {preview ? '正在执行。可以关闭后从运行记录查看进度。' : '正在准备预览…'}
        </p>
      )}
    </DetailPanel>
  )
}
