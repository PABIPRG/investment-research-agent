import { canFoldProcess, failureCopy } from './failure-model.js'
import css from './TurnFailure.module.css'
export interface FailureNode {
  code?: string
  message?: string
}
export function TurnFailure({ node }: { node: { data: FailureNode } }) {
  const failure = node.data
  const copy = failureCopy(failure.code)
  return (
    <section className={css.failure} data-huohuo-failure role="status" aria-label={copy.title}>
      <strong>{copy.title}</strong>
      <p>{copy.detail}</p>
      {copy.configure && (
        <details className={css.guide}>
          <summary>如何配置模型</summary>
          <ol>
            <li>打开右上角的账号菜单，选择「设置」。</li>
            <li>进入「模型」，填写提供商的 API Key 并保存。</li>
            <li>关闭设置，重新发送刚才的问题。</li>
          </ol>
          <p>密钥只在本机设置表单填写，不需要发给火火。</p>
        </details>
      )}
      {(failure.code || failure.message) && (
        <details className={css.technical}>
          <summary>错误详情</summary>
          {failure.code && <code>{failure.code}</code>}
          {failure.message && <pre>{failure.message}</pre>}
        </details>
      )}
    </section>
  )
}
interface TurnProcessProps {
  node: {
    location?: { turn?: { status?: string; end?: { data?: { reason?: { kind?: string } } } } }
  }
  turnProcess: {
    hasContent: boolean
    foldable: boolean
    open: boolean
    setOpen(open: boolean): void
    spec: { toolCallCount: number; subagentCount: number }
  }
}
/** Keep the native disclosure owner; don't show an empty second failure heading. */
export function TurnProcess({ node, turnProcess }: TurnProcessProps) {
  if (!turnProcess?.hasContent) return null
  const turn = node.location?.turn
  if (turn?.status !== 'closed') return null
  const label = `执行过程${turnProcess.spec.toolCallCount ? ` · ${turnProcess.spec.toolCallCount} 次工具调用` : ''}`
  if (!canFoldProcess(turnProcess.foldable, turn.end?.data?.reason?.kind))
    return <small data-turn-process>{label}</small>
  return (
    <button
      className={css.process}
      data-turn-process
      aria-expanded={turnProcess.open}
      onClick={() => turnProcess.setOpen(!turnProcess.open)}
    >
      {label} {turnProcess.open ? '收起' : '展开'}
    </button>
  )
}
