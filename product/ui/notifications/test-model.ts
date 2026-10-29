export type NotificationTest = {
  test_id: string
  request_key: string
  channel: string
  target_summary: string
  status: string
  detail: string
  ignores_quiet_hours: boolean
  created_at: number
  updated_at: number
  expires_at: number
}
export const testStatuses: Record<string, string> = {
  prepared: '待确认发送',
  cancelled: '已取消，未发送',
  in_flight: '请求在途',
  delivered: '已保存到应用内',
  accepted: '渠道已受理',
  failed: '发送失败',
  unknown: '结果未知，勿自动重发',
}
