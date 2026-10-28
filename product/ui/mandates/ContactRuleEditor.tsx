import { Select } from '../shared/Select.js'
import css from '../Query.module.css'
export type RuleCondition =
  | { type: 'semantic'; claim: 'notable_change' }
  | {
      type: 'numeric'
      metric: string
      operator: string
      threshold: number
    }
  | { type: 'all' | 'any'; conditions: RuleCondition[] }
export type ContactRule = {
  mode: 'condition' | 'scheduled_delivery' | 'periodic_check' | 'due_reminder'
  condition?: RuleCondition
  time?: string
  trading_days_only?: boolean
  notify_on?: string
  cooldown_minutes?: number
}
export const semanticCondition: RuleCondition = { type: 'semantic', claim: 'notable_change' }
const metricNames: Record<string, string> = {
  price: '价格（元/股）',
  pct_change: '涨跌幅（%）',
  volume_ratio: '量比',
  turnover: '换手率（%）',
  amount_yi: '成交额（亿元）',
  rsi_14: 'RSI(14)',
  macd_hist: 'MACD 柱',
}
function ConditionEditor({
  value,
  change,
  metrics,
  depth = 0,
}: {
  value: RuleCondition
  change: (v: RuleCondition) => void
  metrics: string[]
  depth?: number
}) {
  return (
    <fieldset>
      <legend>{depth ? '子条件' : '满足什么条件'}</legend>
      <Select
        aria-label="条件类型"
        value={value.type}
        onChange={(e) => {
          const type = e.target.value
          change(
            type === 'semantic'
              ? semanticCondition
              : type === 'numeric'
                ? { type, metric: metrics[0], operator: '>=', threshold: 0 }
                : { type: type as 'all' | 'any', conditions: [semanticCondition] },
          )
        }}
      >
        <option value="semantic">有证据的重要变化</option>
        {!!metrics.length && <option value="numeric">指标达到阈值</option>}
        {depth < 4 && (
          <>
            <option value="all">以下条件全部满足</option>
            <option value="any">以下任一条件满足</option>
          </>
        )}
      </Select>
      {value.type === 'numeric' && (
        <div className={css.actions}>
          <label>
            指标
            <Select
              value={value.metric}
              onChange={(e) => change({ ...value, metric: e.target.value })}
            >
              {metrics.map((m) => (
                <option key={m} value={m}>
                  {metricNames[m]}
                </option>
              ))}
            </Select>
          </label>
          <label>
            比较
            <Select
              value={value.operator}
              onChange={(e) => change({ ...value, operator: e.target.value })}
            >
              {['>=', '>', '<=', '<', '==', '!='].map((op) => (
                <option key={op}>{op}</option>
              ))}
            </Select>
          </label>
          <label>
            阈值
            <input
              type="number"
              step="any"
              required
              value={value.threshold}
              onChange={(e) => change({ ...value, threshold: e.target.valueAsNumber })}
            />
          </label>
        </div>
      )}
      {'conditions' in value && (
        <>
          {value.conditions.map((child, i) => (
            <div key={i}>
              <ConditionEditor
                value={child}
                metrics={metrics}
                depth={depth + 1}
                change={(v) =>
                  change({
                    ...value,
                    conditions: value.conditions.map((c, n) => (n === i ? v : c)),
                  })
                }
              />
              {value.conditions.length > 1 && (
                <button
                  type="button"
                  onClick={() =>
                    change({ ...value, conditions: value.conditions.filter((_, n) => n !== i) })
                  }
                >
                  移除此条件
                </button>
              )}
            </div>
          ))}
          {value.conditions.length < 8 && (
            <button
              type="button"
              onClick={() =>
                change({ ...value, conditions: [...value.conditions, semanticCondition] })
              }
            >
              添加条件
            </button>
          )}
        </>
      )}
    </fieldset>
  )
}
export function ContactRuleEditor({
  value,
  change,
  operation,
}: {
  value: ContactRule
  change: (v: ContactRule) => void
  operation: string
}) {
  const metrics =
    operation === 'market_quote'
      ? ['price', 'pct_change', 'volume_ratio', 'turnover', 'amount_yi']
      : operation === 'market_technical'
        ? ['rsi_14', 'macd_hist']
        : []
  const conditional = ['condition', 'periodic_check'].includes(value.mode)
  return (
    <>
      <label>
        联系方式
        <Select
          value={value.mode}
          onChange={(e) => {
            const mode = e.target.value as ContactRule['mode']
            change({
              mode,
              ...(['condition', 'periodic_check'].includes(mode)
                ? { condition: value.condition || semanticCondition }
                : {}),
              ...(mode === 'condition'
                ? {}
                : {
                    time: value.time || '15:30',
                    trading_days_only: value.trading_days_only ?? true,
                  }),
              notify_on: value.notify_on || 'transition',
              cooldown_minutes: value.cooldown_minutes ?? 60,
            })
          }}
        >
          <option value="condition">条件满足时联系</option>
          <option value="periodic_check">按时检查，满足条件才联系</option>
          <option value="scheduled_delivery">按时交付研究结果</option>
          <option value="due_reminder">到时直接提醒</option>
        </Select>
      </label>
      {conditional && (
        <ConditionEditor
          value={value.condition || semanticCondition}
          metrics={metrics}
          change={(condition) => change({ ...value, condition })}
        />
      )}
      {value.mode !== 'condition' && (
        <div className={css.actions}>
          <label>
            每日时间（北京时间）
            <input
              required
              type="time"
              value={value.time || '15:30'}
              onChange={(e) => change({ ...value, time: e.target.value })}
            />
          </label>
          <label className={css.checkLabel}>
            <input
              type="checkbox"
              checked={value.trading_days_only || false}
              onChange={(e) => change({ ...value, trading_days_only: e.target.checked })}
            />
            仅交易日（日历未知时等待）
          </label>
        </div>
      )}
      {conditional && (
        <div className={css.actions}>
          <label>
            提醒时机
            <Select
              value={value.notify_on || 'transition'}
              onChange={(e) => change({ ...value, notify_on: e.target.value })}
            >
              <option value="transition">从不满足变为满足时</option>
              <option value="first_entry">仅首次满足</option>
              <option value="reentry">再次满足时</option>
              <option value="level">满足期间按间隔提醒</option>
            </Select>
          </label>
          <label>
            最短联系间隔（分钟）
            <input
              type="number"
              min="0"
              max="43200"
              value={value.cooldown_minutes ?? 60}
              onChange={(e) => change({ ...value, cooldown_minutes: e.target.valueAsNumber })}
            />
          </label>
        </div>
      )}
      <p className={css.note}>
        缺少资料时保留“未知”，不触发条件提醒；不自动追加模型重试。定时交付会产生研究调用，到时直接提醒不进行研究。
      </p>
    </>
  )
}
