import { safeSource, time, type Evidence } from '../model.js'
import { sourceReason } from '../mandates/model.js'
import { evidenceTitle, sourceName } from './evidence-display.js'
import { marketQuoteRows } from './market-evidence.js'
import css from '../Query.module.css'
export function EvidenceCard({ row, context }: { row: Evidence; context?: string }) {
  const source = safeSource(row.source_url)
  const synthetic =
    row.source_url?.includes('example.invalid') ||
    row.raw?.source?.includes('合成') ||
    row.limitations?.some((x) => x.includes('合成'))
  const metric = row.values?.metric
  const period = row.values?.period
  const quotes = marketQuoteRows(row)
  return (
    <article className={css.evidence}>
      <strong>{evidenceTitle(row)}</strong>
      {context && <p className={css.note}>{context}</p>}
      <p className={css.note}>
        {sourceName(row.raw?.source || row.source)} · 采集于 {time(row.observed_at)}
      </p>
      {synthetic && <p className={css.note}>合成验收资料，不代表真实披露或行情。</p>}
      {row.status !== 'ok' && (
        <p>
          {row.status === 'empty' ? '该来源未返回记录。' : '这份资料尚不可用。'}
          {row.reason && sourceReason(row.reason)}
        </p>
      )}
      {metric && (
        <>
          <p>
            摘要指标：{metric} ·{' '}
            {row.values?.unit === 'source_unspecified' || !row.values?.unit
              ? '单位未核验'
              : `来源单位：${row.values.unit}`}
          </p>
          {row.values?.records?.map((r, i) => (
            <p key={i}>
              {String(r['指标'] || metric)}：{String(period ? (r[period] ?? '未提供') : '未提供')}
              （来源原值）
            </p>
          ))}
        </>
      )}
      {row.values?.price != null && (
        <>
          <dl className={css.quote}>
            <div>
              <dt>报价（元/股）</dt>
              <dd>{row.values.price}</dd>
            </div>
            <div>
              <dt>昨收（元/股）</dt>
              <dd>{row.values.previous_close ?? '—'}</dd>
            </div>
            <div>
              <dt>较昨收变化（%）</dt>
              <dd>{row.values.change_percent ?? '—'}</dd>
            </div>
          </dl>
          <p className={css.note}>
            报价时间：{time(row.data_as_of)}
            {!row.data_as_of && ' · 来源未提供时间，不能认定为实时行情'}
          </p>
        </>
      )}
      {quotes.map((quote, index) => (
        <section key={index} aria-label={`${quote.name}的行情资料`}>
          <strong>{quote.name}</strong>
          <dl className={css.quote}>
            {quote.facts.map((fact) => (
              <div key={fact.label}>
                <dt>{fact.label}</dt>
                <dd>{fact.value}</dd>
              </div>
            ))}
          </dl>
          <p className={css.note}>
            报价时间：{time(quote.asOf)}
            {!quote.asOf && ' · 来源未提供可核对的时间'}
            {quote.stale && ' · 时效尚未确认，请勿视为当前行情'}
          </p>
        </section>
      ))}
      {row.values?.profile?.map((r, i) => (
        <dl key={i}>
          {Object.entries(r).map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{String(v ?? '—')}</dd>
            </div>
          ))}
        </dl>
      ))}
      {row.limitations?.map((x, i) => (
        <p className={css.note} key={i}>
          {x}
        </p>
      ))}
      {source ? (
        <a href={source} target="_blank" rel="noreferrer noopener">
          打开资料来源 ↗
        </a>
      ) : (
        <p className={css.note}>未提供可打开的来源地址；以上是已留存资料。</p>
      )}
      <details className={css.meta}>
        <summary>排查信息（可选）</summary>
        <p>资料编号：{row.evidence_id}</p>
        <p>采集批次：{row.attempt_id}</p>
      </details>
    </article>
  )
}
