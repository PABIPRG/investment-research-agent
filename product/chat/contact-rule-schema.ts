const numeric = {
  type: 'object',
  additionalProperties: false,
  properties: {
    type: { type: 'string', enum: ['numeric'] },
    metric: {
      type: 'string',
      enum: [
        'price',
        'change',
        'change_percent',
        'pct_change',
        'volume_ratio',
        'turnover',
        'amount_yi',
        'rsi_14',
        'macd_hist',
      ],
    },
    operator: { type: 'string', enum: ['>', '>=', '<', '<=', '==', '!='] },
    threshold: { type: 'number' },
  },
  required: ['type', 'metric', 'operator', 'threshold'],
}
const semantic = {
  type: 'object',
  additionalProperties: false,
  properties: {
    type: { type: 'string', enum: ['semantic'] },
    claim: {
      type: 'string',
      minLength: 1,
      maxLength: 80,
      description: '用户明确说出的单一变化，默认 notable_change；不要自行增加条件。',
    },
    expected: { type: 'string', enum: ['met', 'unmet'] },
    min_confidence: { type: 'number', minimum: 0, maximum: 1 },
  },
  required: ['type', 'claim'],
}
function condition(depth: number): any {
  const choices: any[] = [numeric, semantic]
  if (depth)
    choices.push({
      type: 'object',
      additionalProperties: false,
      properties: {
        type: { type: 'string', enum: ['all', 'any'] },
        conditions: { type: 'array', minItems: 1, maxItems: 8, items: condition(depth - 1) },
      },
      required: ['type', 'conditions'],
    })
  return { anyOf: choices }
}
export const contactRuleSchema = {
  type: 'object',
  additionalProperties: false,
  description:
    '程序可执行的联系规则。必须向用户用自然语言展示并确认，不从联系备注暗自推断阈值；数值仅支持 market_quote / market_technical 提供的对应指标。',
  properties: {
    mode: {
      type: 'string',
      enum: ['condition', 'scheduled_delivery', 'periodic_check', 'due_reminder'],
    },
    condition: condition(4),
    time: {
      type: 'string',
      pattern: '^(?:[01][0-9]|2[0-3]):[0-5][0-9]$',
      description: '北京时间，每日；仅用于有日程的模式。',
    },
    trading_days_only: {
      type: 'boolean',
      description: '仅可靠交易日历确认的交易日，未知时保留等待，不以工作日猜测。',
    },
    notify_on: { type: 'string', enum: ['transition', 'first_entry', 'reentry', 'level'] },
    cooldown_minutes: { type: 'integer', minimum: 0, maximum: 43200 },
  },
  required: ['mode'],
}
const metrics: Record<string, string> = {
  price: '价格（元/股）',
  change: '涨跌额（元）',
  change_percent: '涨跌幅（%）',
  pct_change: '涨跌幅（%）',
  volume_ratio: '量比',
  turnover: '换手率（%）',
  amount_yi: '成交额（亿元）',
  rsi_14: 'RSI(14)',
  macd_hist: 'MACD 柱',
}
export function describeContactRule(rule: any): string {
  if (!rule) return '有证据的重要变化时联系'
  const describe = (c: any): string =>
    c?.type === 'numeric'
      ? `${metrics[c.metric]} ${c.operator} ${c.threshold}`
      : c?.conditions
        ? c.conditions.map(describe).join(c.type === 'all' ? '，且 ' : '，或 ')
        : c?.claim && c.claim !== 'notable_change'
          ? (c.expected === 'unmet' ? '有依据证伪：' : '') + c.claim
          : '有证据的重要变化'
  const modes: Record<string, string> = {
    condition: '条件满足时联系',
    periodic_check: '按时检查，满足条件才联系',
    scheduled_delivery: '按时交付研究结果',
    due_reminder: '到时直接提醒',
  }
  return [
    modes[rule.mode],
    rule.condition && describe(rule.condition),
    rule.time && `每日 ${rule.time}（北京时间）`,
    rule.trading_days_only && '仅交易日',
    '未知不触发、不自动追加模型重试',
  ]
    .filter(Boolean)
    .join('；')
}
