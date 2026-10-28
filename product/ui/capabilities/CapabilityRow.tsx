import type { Capability } from './model.js'
import { statusLabels, usagePrompt } from './model.js'
import css from './Capabilities.module.css'
export function CapabilityRow({
  item,
  investment,
  strategy,
  start,
}: {
  item: Capability
  investment: () => void
  strategy: () => void
  start: (prompt: string) => void
}) {
  const prompt = usagePrompt(item)
  return (
    <details className={css.row}>
      <summary>
        <span className={css.name}>
          {item.title}
          <span className={css.kind}>
            {item.kind === 'skill' ? 'Skill' : 'Tool'} · {item.category}
          </span>
        </span>
        <span className={css.status} data-status={item.status}>
          {statusLabels[item.status]}
        </span>
        <span className={css.purpose}>
          {item.description.replace(`${item.title}：`, '').split('。')[0]}
        </span>
      </summary>
      <div className={css.detail}>
        <p>{item.description}</p>
        <p className={css.note}>{item.note}</p>
        <dl>
          <div>
            <dt>来源</dt>
            <dd>{item.source}</dd>
          </div>
          <div>
            <dt>内部名称</dt>
            <dd>
              <code>{item.id}</code>
            </dd>
          </div>
        </dl>
        {prompt && (
          <>
            <p className={css.note}>点击后会打开新对话并准备问题，你可以补充信息后发送。</p>
            <button onClick={() => start(prompt)}>在新对话中使用 →</button>
          </>
        )}
        {item.action === 'strategy' && <button onClick={strategy}>管理策略与验证记录 →</button>}
        {item.action === 'investment' && <button onClick={investment}>管理投资记录 →</button>}
      </div>
    </details>
  )
}
