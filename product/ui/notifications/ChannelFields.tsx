import css from '../Form.module.css'
import { FieldGroup } from '../shared/FieldGroup.js'
import type { EditSection, NotificationDraft } from './editor-model.js'
import { channelLabels, fields, secretFields, type Config } from './model.js'
export function ChannelFields({
  section,
  config,
  draft,
  change,
}: {
  section: EditSection
  config: Config
  draft: NotificationDraft
  change: (patch: Partial<NotificationDraft>) => void
}) {
  return (
    <>
      <FieldGroup title="渠道启用">
        <label className={css.choice}>
          <input
            type="checkbox"
            checked={draft.channelEnabled}
            onChange={(e) => change({ channelEnabled: e.target.checked })}
          />
          启用{channelLabels[section]}
        </label>
        {!config.enabled && (
          <p className={css.hint}>提醒总开关当前关闭。保存渠道后仍不会发送提醒。</p>
        )}
      </FieldGroup>
      {section === 'app' ? (
        <p className={css.hint}>在应用内保留提醒及证据回访，不会发送到外部渠道。</p>
      ) : (
        <FieldGroup title="连接配置" hint="凭据仅在此安全表单中填写。">
          <div className={css.grid}>
            {Object.entries(fields[section]).map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  type={
                    secretFields.includes(key) ? 'password' : key === 'port' ? 'number' : 'text'
                  }
                  autoComplete="off"
                  min={key === 'port' ? 1 : undefined}
                  max={key === 'port' ? 65535 : undefined}
                  maxLength={1000}
                  disabled={!!draft.external.clear}
                  value={String(draft.external[key] ?? '')}
                  placeholder={
                    secretFields.includes(key) && config.external[section]?.secret_saved?.[key]
                      ? '已保存，留空保持不变'
                      : undefined
                  }
                  onChange={(e) =>
                    change({
                      external: {
                        ...draft.external,
                        [key]: key === 'port' ? Number(e.target.value) : e.target.value,
                      },
                    })
                  }
                />
              </label>
            ))}
          </div>
          <small>保存仅更新本渠道配置。委托还需明确允许使用该渠道；不会自动发送测试消息。</small>
          {config.external[section]?.configured && (
            <details>
              <summary>清除已保存配置</summary>
              <label className={css.choice}>
                <input
                  type="checkbox"
                  checked={!!draft.external.clear}
                  onChange={(e) =>
                    change({
                      external: e.target.checked ? { clear: true } : {},
                      channelEnabled: e.target.checked ? false : draft.channelEnabled,
                    })
                  }
                />
                保存时清除本渠道凭据；恢复时需重新填写
              </label>
            </details>
          )}
        </FieldGroup>
      )}
    </>
  )
}
