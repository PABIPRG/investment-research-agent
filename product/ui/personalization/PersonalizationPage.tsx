import { useEffect, useState } from 'react'
import { request, errorText } from '../shared/api.js'
import ui from '../investment/Sections.module.css'
import { PersonalizationOptions } from './PersonalizationOptions.js'
import { PersonalizationConfirm } from './PersonalizationConfirm.js'
import type { Personalized, PersonalPreview, Card } from './model.js'
import business from '../Business.module.css'
const buckets: Record<string, string> = {
  holdings: '持仓相关',
  watchlist: '自选相关',
  strategy: '策略相关',
  fresh: '其他资讯',
}
export function PersonalizationPage({
  refreshKey = 0,
  hasSecurities = false,
}: {
  refreshKey?: number
  hasSecurities?: boolean
}) {
  const [data, setData] = useState<Personalized>(),
    [error, setError] = useState(''),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(true)
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
    setLoading(true)
    void request<Personalized>('personalization', { operation: 'read', offset, days }, abort.signal)
      .then((r) => {
        if (!abort.signal.aborted) setData(r)
      })
      .catch((e) => {
        if (!abort.signal.aborted) setError(errorText(e))
      })
      .finally(() => {
        if (!abort.signal.aborted) setLoading(false)
      })
    return () => abort.abort()
  }, [generation, offset, days, refreshKey])
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
      if (result.status !== 'ok') {
        setError(result.notice)
        return
      }
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
    <section aria-label="为我关注" className={ui.stack}>
      <header className={ui.heading}>
        <div>
          <h2>为你关注的资讯</h2>
          <p>按持仓、自选、策略关联与研究兴趣整理。阅读后可反馈，或带回对话继续核查。</p>
        </div>
        <div className={ui.actions}>
          <button
            data-variant="primary"
            disabled={busy || !hasSecurities}
            onClick={() => void fetchSources()}
          >
            {busy ? '处理中…' : '获取相关资讯'}
          </button>
        </div>
      </header>
      {error && (
        <p role="alert">
          {error} 内容可能未更新。<button onClick={refresh}>重试读取</button>
        </p>
      )}
      {!data ? (
        <p role={loading ? 'status' : undefined}>
          {loading ? '正在读取相关资讯…' : '暂时无法读取，请用顶部刷新重试。'}
        </p>
      ) : (
        <>
          <section aria-label="关注资讯" className={ui.section}>
            {!data.cards.total && (
              <p className={ui.empty}>
                {hasSecurities
                  ? '暂时没有已保存的相关资讯，点击“获取相关资讯”后可在这里阅读和反馈。'
                  : '先在“持仓”或“自选”录入证券，即可获取相关资讯。当前没有资讯不代表市场没有事件。'}
              </p>
            )}
            {data.cards.cards.map((card) => (
              <article key={card.card_id} className={ui.record}>
                <small>
                  {buckets[card.bucket]} · 相关度 {card.relevance_score} · {card.source}
                </small>
                <h3>{card.title}</h3>
                <p>{card.reasons.join('；')}</p>
                {card.risk && (
                  <small>
                    研究风险提示：
                    {(
                      { low: '低', medium: '中', high: '高', unknown: '待核对' } as Record<
                        string,
                        string
                      >
                    )[card.risk.level] || card.risk.level}
                    {card.risk.note ? ` · ${card.risk.note}` : ''}
                  </small>
                )}
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
                {!data.learning.enabled && (
                  <small>偏好学习已暂停，可在“学习与隐私”中启用反馈。</small>
                )}
              </article>
            ))}
            {(offset > 0 || data.cards.page_info.has_more) && (
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
            )}
          </section>
          <PersonalizationOptions
            data={data}
            busy={busy}
            prepare={prepare}
            days={days}
            setDays={setDays}
          />
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
