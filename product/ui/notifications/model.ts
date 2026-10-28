export const channelLabels: Record<string, string> = {
  app: '应用内',
  wecom: '企业微信',
  serverchan: 'Server 酱',
  email: '邮件',
}
export const fields: Record<string, Record<string, string>> = {
  wecom: { key: '机器人密钥' },
  serverchan: { sendkey: 'SendKey' },
  email: {
    host: 'SMTP 主机',
    port: 'SMTP 端口',
    username: 'SMTP 用户名',
    password: 'SMTP 密码',
    sender: '发件邮箱',
    destination: '收件邮箱',
  },
}
export const secretFields = ['key', 'sendkey', 'password']
export type Config = {
  revision: number
  enabled: boolean
  channels: string[]
  timezone: string
  quiet_hours: { start: string; end: string } | null
  external_status: string
  external: Record<
    string,
    { configured: boolean; secret_saved: Record<string, boolean>; [key: string]: any }
  >
}
export const deliveryLabels: Record<string, string> = {
  queued: '等待投递',
  deferred: '静默延期',
  retry: '等待安全重试',
  in_flight: '请求在途',
  accepted: '渠道已受理，送达未确认',
  delivered: '已到达应用内',
  unknown: '结果未知，等待对账',
  failed: '投递失败',
  cancelled: '已阻止发送',
}
export function decisionText(detail: string, reason: string) {
  if (/^judgement_unknown:/.test(detail || '')) return '当前证据不足，尚不能判断是否发生重要变化'
  const readable = (detail || '')
    .replace(/^notable_change=(?:met|unmet|unknown)\s*/, '')
    .replace(/^（(.*)）$/, '$1')
  return (
    readable ||
    (
      {
        condition_met: '变化满足联系约定',
        no_material_change: '没有值得联系的新变化',
        condition_unknown: '资料不足，暂不能判断',
        research_failed: '研究执行失败',
        due_reminder: '按约到期提醒',
        quiet_hours: '处于静默时段',
      } as Record<string, string>
    )[reason] ||
    '请回访委托核对判断依据'
  )
}
