import page from './shared/Page.module.css'
import { ReadStatus } from './shared/ReadStatus.js'
import { useEffect, useState } from 'react'
import business from './Business.module.css'
import type { EditSection } from './notifications/editor-model.js'
import { channelLabels, decisionText, deliveryLabels, type Config } from './notifications/model.js'
import { NotificationTestDialog } from './notifications/NotificationTestDialog.js'
import { NotificationTestHistory } from './notifications/NotificationTestHistory.js'
import { NotificationEditor } from './notifications/NotificationEditor.js'
import css from './Query.module.css'
import { errorText, request } from './shared/api.js'
type Receipt = {
  decision_id: string
  mandate_id: string
  channel: string
  status: string
  decision_detail: string
  reason_code: string
  detail: string
}
export function NotificationsPage({
  visit,
}: {
  visit: (mandate: string, decision: string) => void
}) {
  const [config, setConfig] = useState<Config>(),
    [rows, setRows] = useState<Receipt[]>([]),
    [section, setSection] = useState<EditSection>(),
    [revision, setRevision] = useState(0),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [testChannel, setTestChannel] = useState<string>(),
    [testRefresh, setTestRefresh] = useState(0)
  useEffect(() => {
    const abort = new AbortController()
    setLoading(true)
    setError('')
    void Promise.all([
      request<Config>('notification-config', undefined, abort.signal),
      request<{ items: Receipt[] }>('notifications', undefined, abort.signal),
    ])
      .then(([cfg, data]) => {
        if (!abort.signal.aborted) {
          setConfig(cfg)
          setRows(data.items)
        }
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(errorText(e))
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false)
      })
    return () => abort.abort()
  }, [revision])
  return (
    <main className={`${page.surface} ${business.page}`}>
      <header className={`${page.header} ${business.header}`}>
        <div>
          <h1>提醒方式</h1>
          <p className={business.note}>选择联系渠道，安排不被打扰的时间</p>
        </div>
        <button disabled={loading} onClick={() => setRevision((n) => n + 1)}>
          刷新
        </button>
      </header>
      <ReadStatus loading={loading} hasData={config !== undefined} />
      {error && <p role="alert">{error} 已显示的配置可能过期。</p>}
      {notice && <p role="status">{notice}</p>}
      {config && (
        <>
          <div className={business.metrics}>
            <span>
              提醒 <b>{config.enabled ? '已开启' : '已关闭'}</b>
            </span>
            <button onClick={() => setSection('general')}>调整总开关</button>
            <span>
              静默时间{' '}
              <b>
                {config.quiet_hours
                  ? `${config.quiet_hours.start}–${config.quiet_hours.end}`
                  : '未设置'}
              </b>
            </span>
            <button onClick={() => setSection('schedule')}>调整时间</button>
          </div>
          <div className={business.tableWrap}>
            <table className={business.table}>
              <thead>
                <tr>
                  {['渠道', '状态', '适用范围', '操作'].map((label) => (
                    <th key={label}>{label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(channelLabels).map(([key, label]) => (
                  <tr key={key}>
                    <td>
                      <strong>{label}</strong>
                    </td>
                    <td>
                      {!config.channels.includes(key)
                        ? '未启用'
                        : key === 'app'
                          ? '已启用'
                          : config.external[key]?.configured
                            ? '配置已保存'
                            : '待补充配置'}
                      {!config.enabled && config.channels.includes(key) && (
                        <small>受总开关关闭影响</small>
                      )}
                    </td>
                    <td>{key === 'app' ? '应用内提醒及证据回访' : '仅用于明确允许此渠道的委托'}</td>
                    <td>
                      <button
                        aria-label={`配置${label}`}
                        disabled={loading || !!error}
                        onClick={() => setSection(key as EditSection)}
                      >
                        配置
                      </button>
                      <button
                        aria-label={`测试${label}提醒`}
                        disabled={
                          loading ||
                          !!error ||
                          !config.enabled ||
                          !config.channels.includes(key) ||
                          (key !== 'app' && !config.external[key]?.configured)
                        }
                        onClick={() => setTestChannel(key)}
                      >
                        发送测试提醒
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className={business.note}>
            渠道配置与委托授权分别管理。配置已保存不代表消息已经送达。开启总开关并启用渠道后，可手动发送测试提醒；测试会忽略静默时间。
          </p>
        </>
      )}
      {section && config && (
        <NotificationEditor
          key={section}
          section={section}
          config={config}
          close={() => setSection(undefined)}
          saved={(next) => {
            setConfig(next)
            setSection(undefined)
            setNotice('修改已保存。')
          }}
        />
      )}
      {testChannel && config && (
        <NotificationTestDialog
          key={testChannel}
          channel={testChannel}
          config={config}
          changed={() => setTestRefresh((n) => n + 1)}
          close={() => {
            setTestChannel(undefined)
            setTestRefresh((n) => n + 1)
          }}
        />
      )}
      <NotificationTestHistory refresh={revision + testRefresh} />
      <details className={css.section}>
        <summary>联系与回访记录 · {rows.length} 条</summary>
        {config && !error && !rows.length && (
          <p className={business.note}>尚无投递记录，保持静默的原因可在委托详情查看。</p>
        )}
        {rows.map((row) => (
          <article key={`${row.decision_id}:${row.channel}`} className={css.evidence}>
            <h3>
              {channelLabels[row.channel]} · {deliveryLabels[row.status] || '状态待核对'}
            </h3>
            <p>{decisionText(row.decision_detail, row.reason_code)}</p>
            <button onClick={() => visit(row.mandate_id, row.decision_id)}>回访委托与证据</button>
          </article>
        ))}
      </details>
    </main>
  )
}
