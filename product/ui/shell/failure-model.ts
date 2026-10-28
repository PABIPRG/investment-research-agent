export function failureCopy(code?: string) {
  if (code === 'MISSING_CREDENTIAL')
    return {
      title: '这次回答未能开始',
      detail:
        '发送这条问题时，没有可用的模型 API Key。请在右上角「设置 → 模型」确认当前提供商的配置后，重新发送。',
      configure: true,
    }
  if (code === 'INTERRUPTED' || code === 'ACCOUNT_SIGNED_OUT')
    return {
      title: '这次回答已停止',
      detail:
        code === 'ACCOUNT_SIGNED_OUT'
          ? '模型账户已退出。重新登录后，你可以继续提问。'
          : '问题已保留，你可以继续输入或重新发送。',
      configure: false,
    }
  return {
    title: '这次没能完成回答',
    detail: '问题已保留。你可以查看错误详情，排除原因后再发送；不会自动重试。',
    configure: false,
  }
}

/** Match DSH's closed-Turn disclosure boundary; other terminal reasons stay expandable. */
export function canFoldProcess(foldable: boolean, reason?: string): boolean {
  return foldable && !['aborted', 'interrupted', 'error'].includes(reason || '')
}
