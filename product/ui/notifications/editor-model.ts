import { fields, secretFields, type Config } from './model.js'
export type EditSection = 'general' | 'schedule' | 'app' | 'wecom' | 'serverchan' | 'email'
export type NotificationDraft = {
  enabled: boolean
  quiet: boolean
  start: string
  end: string
  channelEnabled: boolean
  external: Record<string, string | number | boolean>
}
export function notificationDraft(config: Config, section: EditSection): NotificationDraft {
  const external = Object.fromEntries(
    Object.keys(fields[section] || {}).map((key) => [
      key,
      secretFields.includes(key)
        ? ''
        : (config.external[section]?.[key] ?? (key === 'port' ? 587 : '')),
    ]),
  )
  return {
    enabled: config.enabled,
    quiet: !!config.quiet_hours,
    start: config.quiet_hours?.start || '22:00',
    end: config.quiet_hours?.end || '08:00',
    channelEnabled: config.channels.includes(section),
    external,
  }
}
/** Only the opened editor's scope is merged; other saved settings remain intact. */
export function notificationPatch(config: Config, section: EditSection, draft: NotificationDraft) {
  const channel = !['general', 'schedule'].includes(section)
  const channels = channel
    ? draft.channelEnabled && !draft.external.clear
      ? [...new Set([...config.channels, section])]
      : config.channels.filter((c) => c !== section)
    : config.channels
  return {
    expected_revision: config.revision,
    enabled: section === 'general' ? draft.enabled : config.enabled,
    channels,
    timezone: config.timezone,
    quiet_hours:
      section === 'schedule'
        ? draft.quiet
          ? { start: draft.start, end: draft.end }
          : null
        : config.quiet_hours,
    external: channel && section !== 'app' ? { [section]: draft.external } : {},
  }
}

export function notificationIssue(
  config: Config,
  section: EditSection,
  draft: NotificationDraft,
): string {
  return notificationPatch(config, section, draft).channels.length
    ? ''
    : '至少保留一个渠道。若希望停止全部提醒，请关闭提醒总开关。'
}
