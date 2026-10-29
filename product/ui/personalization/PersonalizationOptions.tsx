import { Select } from '../shared/Select.js'
import type { Personalized } from './model.js'
import ui from '../investment/Sections.module.css'
export function PersonalizationOptions({
  data,
  busy,
  prepare,
  days,
  setDays,
}: {
  data: Personalized
  busy: boolean
  prepare: (payload: Record<string, unknown>) => Promise<void>
  days: number
  setDays: (days: number) => void
}) {
  return (
    <>
      <details className={ui.disclosure}>
        <summary>
          策略匹配 ·{' '}
          {data.matches.items.length ? `${data.matches.items.length} 项` : '暂无合格策略'}
        </summary>
        <div>
          {!data.matches.items.length && (
            <p className={ui.muted}>已有策略通过验证后，可在这里查看匹配理由。不会自动启用策略。</p>
          )}
          {data.matches.items.map((item) => (
            <details key={item.strategy_id} className={ui.record}>
              <summary>
                {item.name} · 匹配 {item.match_score} 分
              </summary>
              <p>{item.match_reasons?.map((r) => r.text).join('；')}</p>
              <dl className={ui.facts}>
                {Object.entries(item.breakdown || {}).map(([dim, b]) => (
                  <div key={dim}>
                    <dt>
                      {(
                        {
                          affinity: '标的关联',
                          profile_fit: '偏好契合',
                          shadow: '影子验证',
                          quality: '验证质量',
                          diversification: '分散化',
                        } as Record<string, string>
                      )[dim] || dim}
                    </dt>
                    <dd>
                      {b.score} · {b.notes?.join('；')}
                    </dd>
                  </div>
                ))}
              </dl>
              {item.caution && <p className={ui.muted}>{item.caution}</p>}
            </details>
          ))}
        </div>
      </details>
      <details className={ui.disclosure}>
        <summary>研究兴趣复盘</summary>
        <div>
          <div className={ui.filter}>
            <label>
              复盘窗口
              <Select value={days} onChange={(e) => setDays(Number(e.target.value))}>
                <option value={7}>近 7 天</option>
                <option value={30}>近 30 天</option>
                <option value={90}>近 90 天</option>
              </Select>
            </label>
          </div>
          <p className={ui.muted}>反映研究兴趣和使用信号，不代表投资收益或风险承受能力。</p>
          <p>
            {data.review.data_note ||
              `有效信号 ${data.review.overview.signal_count} 个，覆盖 ${data.review.overview.active_days} 天；可信度 ${data.review.overview.confidence}`}
          </p>
          {data.review.overview.signal_count > 0 && (
            <dl className={ui.metrics}>
              {(
                [
                  ['看到', data.review.funnel.impressions],
                  ['打开', data.review.funnel.opens],
                  ['带入分析', data.review.funnel.analyses],
                  ['反馈', data.review.funnel.feedback],
                ] as const
              ).map(([label, value]) => (
                <div key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </div>
              ))}
            </dl>
          )}
          {data.review.insights.map((i) => (
            <div key={i.id}>
              <strong>{i.title}</strong>
              <p>
                {i.explanation}（{i.evidence_count} 条证据）
              </p>
            </div>
          ))}
          {!!data.review.recent_activity.length && (
            <details>
              <summary>查看最近学习记录</summary>
              {data.review.recent_activity.map((a, i) => (
                <p key={i}>
                  {a.occurred_at} · {a.label}
                </p>
              ))}
            </details>
          )}
        </div>
      </details>
      <details className={ui.disclosure}>
        <summary>学习与隐私 · {data.learning.enabled ? '已启用' : '已暂停'}</summary>
        <div>
          <p className={ui.muted}>{data.notice}</p>
          <p>
            {data.learning.record_count} 条记录 · 最长保留 {data.learning.retention_days} 天、最多{' '}
            {data.learning.event_cap} 条。
          </p>
          <div className={ui.actions}>
            <button
              disabled={busy}
              onClick={() => void prepare({ action: 'learning', enabled: !data.learning.enabled })}
            >
              {data.learning.enabled ? '暂停本机学习' : '启用本机学习'}
            </button>
            <button
              data-variant="danger"
              disabled={busy || !data.learning.record_count}
              onClick={() => void prepare({ action: 'clear' })}
            >
              清除本机学习记录
            </button>
          </div>
          {!data.profile_is_explicit && (
            <p className={ui.muted}>
              风险偏好尚未填写，匹配暂按默认稳健档示例计算；这不是你的已确认画像。
            </p>
          )}
        </div>
      </details>
    </>
  )
}
