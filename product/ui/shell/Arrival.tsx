import { ExpandableText } from '../shared/ExpandableText.js'
import { mandateName } from '../business-model.js'
import type { ChatRuntime } from '../dsh-face.js'
import type { MandateView } from '../mandates/model.js'
import { arrivalItem } from './arrival-model.js'
import css from './Arrival.module.css'
import type { Actions } from './types.js'
export function Arrival({
  select,
  input,
  inputActions,
  items,
  error,
}: {
  select: Actions['select']
  input: { draft: string } | undefined
  inputActions: ChatRuntime['inputActions']
  items: MandateView[]
  error: boolean
}) {
  const current = arrivalItem(items)
  const visit = () => {
    if (!current) return
    sessionStorage.setItem(
      'huohuo-return',
      JSON.stringify({ mandate: current.item.mandate.mandate_id }),
    )
    select('huohuo-research')
  }
  return (
    <div className={css.arrival} data-huohuo-arrival>
      <div className={css.task} role="region" aria-label="当前跟进摘要" tabIndex={0}>
        <ExpandableText
          text={current ? `${mandateName(current.item)} · 当前跟进` : '有些事，交给我慢慢跟。'}
          label="跟进对象"
          lines={1}
          tone="muted"
        />
        <h2 title={error ? '暂时没有读到跟进情况' : current?.state.title}>
          {error ? '暂时没有读到跟进情况' : current?.state.title || '今天，先看哪件事？'}
        </h2>
        <p>
          {error
            ? '你仍可以直接提问，已有委托不会因此消失。'
            : current?.state.detail || '可以聊一个投资问题，也可以先整理自己的想法。'}
        </p>
        {current && !error ? (
          <>
            <button data-variant="primary" onClick={visit}>
              {current.state.action} →
            </button>
            <div className={css.goal}>
              <ExpandableText text={current.item.revision.goal} label="研究目标" tone="muted" />
            </div>
          </>
        ) : (
          <div className={css.quick}>
            {['帮我理一理研究思路', '先看看我的持仓'].map((text) => (
              <button
                key={text}
                disabled={!input || !!input.draft}
                onClick={() => {
                  inputActions.setDraft(text)
                  inputActions.submit()
                }}
              >
                {text}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
