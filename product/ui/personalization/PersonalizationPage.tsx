import { useEffect, useState } from 'react'
import { request, errorText } from '../shared/api.js'
import { FieldGroup } from '../shared/FieldGroup.js'
import { PersonalizationConfirm } from './PersonalizationConfirm.js'
import type { Personalized, PersonalPreview, Card } from './model.js'
import form from '../Form.module.css'
import business from '../Business.module.css'
const buckets: Record<string, string> = {
  holdings: '持仓相关',
  watchlist: '自选相关',
  strategy: '策略相关',
  fresh: '其他资讯',
}
export function PersonalizationPage() {
  const [data, setData] = useState<Personalized>(),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false)
  const [generation, setGeneration] = useState(0),
    [offset, setOffset] = useState(0),
    [days, setDays] = useState(7)
  const [preview, setPreview] = useState<PersonalPreview>()
  const refresh = () => {
    setGeneration((n) => n + 1)
  }
  useEffect(() => {
    const abort = new AbortController()
    setError('')
    void request<Personalized>('personalization', { operation: 'read', offset, days }, abort.signal)
      .then((r) => {
        if (!abort.signal.aborted) setData(r)
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(errorText(e))
      })
    return () => abort.abort()
  }, [generation, offset, days])
  const prepare = async (payload: Record<string, unknown>) => {
    setBusy(true)
    setError('')
    try {
      setPreview(await request('personalization', { operation: 'preview', ...payload }))
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  const fetchSources = async () => {
    setBusy(true)
    setError('')
    try {
      const result = await request<{ status: string; notice: string }>('personalization', {
        operation: 'refresh',
      })
      if (result.status !== 'ok') setError(result.notice)
      refresh()
    } catch (e) {
      setError(errorText(e))
    } finally {
      setBusy(false)
    }
  }
  const reading = (card: Card, action: 'open' | 'analyze') => {
    if (!data?.learning.enabled) return
    void request('personalization', {
      operation: 'record',
      request_key: crypto.randomUUID(),
      card_id: card.card_id,
      action,
    }).catch((e) => setError(errorText(e)))
  }
  return (
    <section aria-label="为我关注" className={form.form}>
      <div className={business.tools}>
        <button onClick={refresh}>刷新本机记录</button>
        <button disabled={busy} onClick={() => void fetchSources()}>
          获取当前持仓与自选资讯
        </button>
      </div>
      {error && (
        <p role="alert">
          {error} 内容可能未更新。<button onClick={refresh}>重试读取</button>
        </p>
      )}
      {!data ? (
        <p role="status">正在读取个性化研究…</p>
      ) : (
        <>
          <FieldGroup title="本机学习" hint={data.notice}>
            <p>
              {data.learning.enabled ? '已启用' : '已暂停'} · {data.learning.record_count} 条记录 ·
              最长保留 {data.learning.retention_days} 天、最多 {data.learning.event_cap} 条。
            </p>
            <button
              disabled={busy}
              onClick={() => void prepare({ action: 'learning', enabled: !data.learning.enabled })}
            >
              {data.learning.enabled ? '暂停本机学习' : '启用本机学习'}
            </button>
            <button
              disabled={busy || !data.learning.record_count}
              onClick={() => void prepare({ action: 'clear' })}
            >
              清除本机学习记录
            </button>
            {!data.profile_is_explicit && (
              <p>风险偏好尚未填写，匹配暂按默认稳健档计算；这不代表你已被评定为稳健型。</p>
            )}
          </FieldGroup>
          <FieldGroup
            title="为你关注的资讯"
            hint="按持仓、自选、策略关联和研究兴趣排序。相关性和风险标签可继续向火火核查。"
          >
            {!data.cards.total && <p>当前没有保存的资讯。获取资讯后可在这里查看、反馈和复盘。</p>}
            {data.cards.cards.map((card) => (
              <article key={card.card_id}>
                <small>
                  {buckets[card.bucket]} · 相关度 {card.relevance_score} · {card.source}
                </small>
                <h3>{card.title}</h3>
                <p>{card.reasons.join('；')}</p>
                <details
                  onToggle={(e) => {
                    if (e.currentTarget.open) reading(card, 'open')
                  }}
                >
                  <summary>阅读详情</summary>
                  <p>{card.summary}</p>
                  <p>{card.time}</p>
                  {card.url && /^https?:\/\//.test(card.url) && (
                    <a href={card.url} target="_blank" rel="noreferrer">
                      查看来源
                    </a>
                  )}
                </details>
                <div className={business.tools}>
                  <button
                    disabled={busy || !data.learning.enabled}
                    aria-pressed={card.feedback_sentiment === 'useful'}
                    onClick={() =>
                      void prepare({
                        action: 'feedback',
                        card_id: card.card_id,
                        sentiment: 'useful',
                      })
                    }
                  >
                    值得关注
                  </button>
                  <button
                    disabled={busy || !data.learning.enabled}
                    aria-pressed={card.feedback_sentiment === 'useless'}
                    onClick={() =>
                      void prepare({
                        action: 'feedback',
                        card_id: card.card_id,
                        sentiment: 'useless',
                      })
                    }
                  >
                    减少此类
                  </button>
                  {card.feedback_sentiment && (
                    <button
                      disabled={busy}
                      onClick={() =>
                        void prepare({
                          action: 'feedback',
                          card_id: card.card_id,
                          sentiment: 'neutral',
                        })
                      }
                    >
                      撤销反馈
                    </button>
                  )}
                </div>
              </article>
            ))}
            <div className={business.tools}>
              <button disabled={!offset} onClick={() => setOffset((n) => Math.max(0, n - 20))}>
                上一页
              </button>
              <button
                disabled={!data.cards.page_info.has_more}
                onClick={() => setOffset(data.cards.page_info.next_offset)}
              >
                下一页
              </button>
            </div>
          </FieldGroup>
          <FieldGroup title="与你匹配的策略" hint="只对已有合格策略评分，不自动启用策略。">
            {!data.matches.items.length && <p>暂无已通过验证、可用于匹配的策略。</p>}
            {data.matches.items.map((item) => (
              <details key={item.strategy_id}>
                <summary>
                  {item.name} · 匹配 {item.match_score} 分
                </summary>
                <p>{item.match_reasons?.map((r) => r.text).join('；')}</p>
                {Object.entries(item.breakdown || {}).map(([dim, b]) => (
                  <p key={dim}>
                    {(
                      {
                        affinity: '标的关联',
                        profile_fit: '偏好契合',
                        shadow: '影子验证',
                        quality: '验证质量',
                        diversification: '分散化',
                      } as Record<string, string>
                    )[dim] || dim}
                    ：{b.score} · {b.notes?.join('；')}
                  </p>
                ))}
              </details>
            ))}
          </FieldGroup>
          <FieldGroup
            title="偏好复盘与效果归因"
            hint="展示研究兴趣和使用信号；不代表投资收益或风险承受能力。"
          >
            <label>
              复盘窗口
              <select value={days} onChange={(e) => setDays(Number(e.target.value))}>
                <option value={7}>近 7 天</option>
                <option value={30}>近 30 天</option>
                <option value={90}>近 90 天</option>
              </select>
            </label>
            <p>
              {data.review.data_note ||
                `有效信号 ${data.review.overview.signal_count} 个，覆盖 ${data.review.overview.active_days} 天；可信度 ${data.review.overview.confidence}`}
            </p>
            <p>
              看到 {data.review.funnel.impressions} · 打开 {data.review.funnel.opens} · 带入分析{' '}
              {data.review.funnel.analyses} · 反馈 {data.review.funnel.feedback}
            </p>
            {data.review.insights.map((i) => (
              <p key={i.id}>
                <strong>{i.title}</strong> · {i.explanation}（{i.evidence_count} 条证据）
              </p>
            ))}
            <details>
              <summary>查看最近学习记录</summary>
              {data.review.recent_activity.map((a, i) => (
                <p key={i}>
                  {a.occurred_at} · {a.label}
                </p>
              ))}
            </details>
          </FieldGroup>
        </>
      )}
      {preview && (
        <PersonalizationConfirm
          preview={preview}
          close={() => setPreview(undefined)}
          saved={() => {
            setPreview(undefined)
            refresh()
          }}
        />
      )}
    </section>
  )
}
