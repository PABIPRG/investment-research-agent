import { Select } from '../shared/Select.js'
import type { MandateController } from './useMandates.js'
import { mandateHooks, matchesTrigger, triggerLabels } from './triggers.js'
import business from '../Business.module.css'
import controls from '../shared/Controls.module.css'
import css from './Triggers.module.css'
export function TriggerFilter({ model }: { model: MandateController }) {
  const { items, filter, trigger, setTrigger } = model
  const statusRows = items.filter((x) => filter === 'all' || x.mandate.status === filter)
  const rows = statusRows.filter((x) => matchesTrigger(x, trigger))
  const hooks = [...new Map(rows.flatMap(mandateHooks).map((h) => [h.id, h])).values()]
  return (
    <div className={`${controls.controls} ${css.root}`}>
      <label className={css.filter}>
        跟进方式
        <Select value={trigger} onChange={(e) => setTrigger(e.target.value)}>
          {Object.entries(triggerLabels).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
              {value === 'all'
                ? ''
                : `（${statusRows.filter((x) => matchesTrigger(x, value)).length}）`}
            </option>
          ))}
        </Select>
      </label>
      <details className={css.hooks}>
        <summary>什么时候会继续跟进 · {hooks.length} 类</summary>
        <p className={business.note}>
          这里展示当前筛选中已约定的跟进条件。暂停或结束后不再继续跟进；是否提醒你，还取决于联系约定。
        </p>
        {hooks.length ? (
          <ul>
            {hooks.map((h) => (
              <li key={h.id}>
                <strong>{h.label}</strong>
                <span>{h.description}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className={business.note}>当前筛选暂无可展示的跟进条件。</p>
        )}
      </details>
    </div>
  )
}
export function TriggerSummary({ item }: { item: MandateController['items'][number] }) {
  const hooks = mandateHooks(item)
  return (
    <section>
      <h3>什么时候继续跟进</h3>
      {hooks.length ? (
        <ul>
          {hooks.map((h) => (
            <li key={h.id}>
              <strong>{h.label}</strong>：{h.description}
            </li>
          ))}
        </ul>
      ) : (
        <p>暂未接入自动跟进，已保存的委托和研究记录仍保留。</p>
      )}
      <p className={business.note}>
        暂停或结束后不再继续跟进。到时提醒与定时检查的具体时间，可在联系约定中核对。
      </p>
    </section>
  )
}
