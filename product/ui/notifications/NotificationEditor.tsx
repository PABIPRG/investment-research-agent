import { FieldGroup } from '../shared/FieldGroup.js'
import { useState } from 'react'
import { DetailPanel } from '../DetailPanel.js'
import css from '../Form.module.css'
import { errorText, request } from '../shared/api.js'
import { ChannelFields } from './ChannelFields.js'
import {
  notificationDraft,
  notificationIssue,
  notificationPatch,
  type EditSection,
  type NotificationDraft,
} from './editor-model.js'
import { channelLabels, type Config } from './model.js'
export function NotificationEditor({
  config,
  section,
  close,
  saved,
}: {
  config: Config
  section: EditSection
  close: () => void
  saved: (config: Config) => void
}) {
  const [draft, setDraft] = useState(() => notificationDraft(config, section)),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(''),
    [confirming, setConfirming] = useState(false)
  const change = (patch: Partial<NotificationDraft>) => {
    setDraft((old) => ({ ...old, ...patch }))
    setError('')
    setConfirming(false)
  }
  const title =
    section === 'general'
      ? '提醒总开关'
      : section === 'schedule'
        ? '静默时间'
        : `${channelLabels[section]}设置`
  const issue = notificationIssue(config, section, draft)
  const save = async () => {
    if (issue) {
      setError(issue)
      return
    }
    setBusy(true)
    setError('')
    try {
      saved(await request<Config>('notification-config', notificationPatch(config, section, draft)))
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <DetailPanel
      compact
      title={title}
      close={() => {
        if (!busy) close()
      }}
    >
      <form
        className={css.form}
        onSubmit={(e) => {
          e.preventDefault()
          if (issue) {
            setError(issue)
            return
          }
          setConfirming(true)
        }}
      >
        {issue && (
          <p role="status" className={css.hint}>
            {issue}
          </p>
        )}
        {error && (
          <p role="alert" className={css.error}>
            {error}
          </p>
        )}
        <fieldset disabled={busy || confirming}>
          {section === 'general' ? (
            <FieldGroup title="提醒许可">
              <label className={css.choice}>
                <input
                  type="checkbox"
                  checked={draft.enabled}
                  onChange={(e) => change({ enabled: e.target.checked })}
                />
                允许火火按已确认的约定提醒我
              </label>
              <small>
                关闭后阻止尚未开始的发送；已经交给渠道的消息无法撤回。各项委托的约定仍保留。
              </small>
            </FieldGroup>
          ) : section === 'schedule' ? (
            <FieldGroup title="每日静默时段">
              <label className={css.choice}>
                <input
                  type="checkbox"
                  checked={draft.quiet}
                  onChange={(e) => change({ quiet: e.target.checked })}
                />
                设置每日静默时段
              </label>
              {draft.quiet && (
                <div className={css.grid}>
                  <label>
                    开始时间
                    <input
                      type="time"
                      required
                      value={draft.start}
                      onChange={(e) => change({ start: e.target.value })}
                    />
                  </label>
                  <label>
                    结束时间
                    <input
                      type="time"
                      required
                      value={draft.end}
                      onChange={(e) => change({ end: e.target.value })}
                    />
                  </label>
                </div>
              )}
              <small>
                {config.timezone === 'Asia/Shanghai' ? '北京时间' : config.timezone}
                ；支持跨午夜。开始与结束相同表示全天静默。
              </small>
            </FieldGroup>
          ) : (
            <ChannelFields section={section} config={config} draft={draft} change={change} />
          )}
        </fieldset>
        {confirming && (
          <div className={css.error} role="status">
            <strong>确认保存{title}？</strong>
            <p>
              {section === 'schedule'
                ? '仅调整静默时间，渠道与总开关保持原样。'
                : section === 'general'
                  ? draft.enabled
                    ? '后续符合约定的提醒可以发送。'
                    : '尚未开始的提醒将被阻止，在途消息无法撤回。'
                  : draft.external.clear
                    ? '将清除本渠道凭据并停用此渠道。'
                    : '仅更新本渠道；不会改变已有委托的渠道授权，也不会发送测试消息。'}
            </p>
          </div>
        )}
        <div className={css.actions}>
          {confirming ? (
            <>
              <button
                type="button"
                data-variant={draft.external.clear ? 'danger' : 'primary'}
                disabled={busy}
                onClick={() => void save()}
              >
                {busy ? '保存中…' : '确认保存'}
              </button>
              <button type="button" disabled={busy} onClick={() => setConfirming(false)}>
                返回修改
              </button>
            </>
          ) : (
            <>
              <button data-variant="primary" disabled={!!issue}>
                核对修改
              </button>
              <button type="button" onClick={close}>
                取消
              </button>
            </>
          )}
        </div>
      </form>
    </DetailPanel>
  )
}
