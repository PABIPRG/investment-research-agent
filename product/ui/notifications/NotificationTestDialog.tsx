import { useEffect, useRef, useState } from 'react'
import { DetailPanel } from '../DetailPanel.js'
import { request, errorText } from '../shared/api.js'
import { channelLabels, type Config } from './model.js'
import { testStatuses, type NotificationTest } from './test-model.js'
import form from '../Form.module.css'
export function NotificationTestDialog({
  channel,
  config,
  close,
  changed,
}: {
  channel: string
  config: Config
  close: () => void
  changed: () => void
}) {
  const key = useRef(crypto.randomUUID()),
    revision = useRef(config.revision)
  const [receipt, setReceipt] = useState<NotificationTest>(),
    [busy, setBusy] = useState(true),
    [error, setError] = useState('')
  const attempted = useRef(false)
  useEffect(() => {
    const abort = new AbortController()
    request<NotificationTest>(
      'notification-test-command',
      {
        operation: 'prepare',
        channel,
        expected_revision: revision.current,
        request_key: key.current,
      },
      abort.signal,
    )
      .then((r) => {
        if (!abort.signal.aborted) setReceipt(r)
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(errorText(e))
      })
      .finally(() => {
        if (!abort.signal.aborted) setBusy(false)
      })
    return () => abort.abort()
  }, [channel])
  const send = async () => {
    if (!receipt || attempted.current) return
    attempted.current = true
    setBusy(true)
    setError('')
    try {
      setReceipt(
        await request<NotificationTest>('notification-test-command', {
          operation: 'send',
          test_id: receipt.test_id,
          request_key: receipt.request_key,
        }),
      )
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
      changed()
      window.dispatchEvent(new Event('huohuo-notification-test-sent'))
    }
  }
  const inspect = async () => {
    if (!receipt) return
    setBusy(true)
    setError('')
    try {
      setReceipt(
        await request<NotificationTest>('notification-test-command', {
          operation: 'inspect',
          test_id: receipt.test_id,
        }),
      )
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
      changed()
    }
  }
  const cancel = async () => {
    if (busy) return
    if (!receipt || receipt.status !== 'prepared') {
      close()
      return
    }
    setBusy(true)
    setError('')
    try {
      await request('notification-test-command', {
        operation: 'cancel',
        test_id: receipt.test_id,
      })
      changed()
      close()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <DetailPanel compact title={`测试${channelLabels[channel]}提醒`} close={() => void cancel()}>
      <div className={form.form}>
        {busy && !receipt && <p role="status">正在核对已保存的渠道与接收目标…</p>}
        {error && (
          <p role="alert" className={form.error}>
            {error}
          </p>
        )}
        {receipt && (
          <>
            <section className={form.group}>
              <h3>{receipt.target_summary}</h3>
              <p>渠道：{channelLabels[receipt.channel]}</p>
              <p>消息标题：火火 · 测试提醒</p>
              <p>只发送一条固定测试消息，不包含研究结论，不创建或修改委托。</p>
              <p>
                <strong>本次测试忽略静默时间。</strong>仍需提醒总开关开启、渠道启用且配置保持一致。
              </p>
            </section>
            {!busy && (
              <p role="status">
                {attempted.current && receipt.status === 'prepared'
                  ? '发送状态待核对，请使用“核对测试结果”，不要重复发送。'
                  : `${testStatuses[receipt.status] || '状态待核对'}：${receipt.detail}`}
              </p>
            )}
          </>
        )}
        <div className={form.actions}>
          {receipt?.status === 'prepared' && !attempted.current && (
            <button
              type="button"
              data-variant="primary"
              disabled={busy}
              onClick={() => void send()}
            >
              确认发送一条测试提醒
            </button>
          )}
          {receipt && attempted.current && (
            <button type="button" disabled={busy} onClick={() => void inspect()}>
              核对测试结果
            </button>
          )}
          <button type="button" disabled={busy} onClick={() => void cancel()}>
            {attempted.current ? '完成' : '取消'}
          </button>
        </div>
        {busy && receipt && <p role="status">正在处理，请勿重复提交…</p>}
        <small className={form.hint}>
          渠道受理不代表实际送达或已读。网络中断或结果未知时，仅核对记录，不自动重发。
        </small>
      </div>
    </DetailPanel>
  )
}
