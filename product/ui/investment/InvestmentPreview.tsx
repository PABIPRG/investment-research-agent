import { money, securityName } from '../business-model.js'
import css from '../Form.module.css'
import type { InvestmentDraft } from './editor-model.js'
import type { EditTarget, Preview } from './types.js'
import { fmt, quantityUnit } from './types.js'
export function InvestmentPreview({
  preview,
  target,
  draft,
}: {
  preview: Preview
  target: EditTarget
  draft: InvestmentDraft
}) {
  const code = draft.security?.code
  const before = preview.before.holdings.find((p) => p.ticker === code),
    after = preview.after.holdings.find((p) => p.ticker === code)
  const watch =
    preview.after.watchlist.find((p) => p.ticker === code) ||
    preview.before.watchlist.find((p) => p.ticker === code)
  return (
    <section aria-label="保存前预览" className={css.form}>
      <div className={css.security}>
        <small>即将保存</small>
        <strong>
          {securityName(
            code || '',
            preview.impact.entry?.name,
            after?.name,
            after?.display_name,
            watch?.name,
            before?.name,
          )}
        </strong>
        <span>{code}</span>
      </div>
      {['trade', 'revision'].includes(target.kind) && (
        <dl className={css.summary}>
          <dt>本次操作</dt>
          <dd>
            {target.kind === 'revision'
              ? draft.revisionOp === 'void'
                ? '撤销成交记录'
                : '更正成交记录'
              : '记录已发生成交'}
          </dd>
          {draft.revisionOp !== 'void' && (
            <>
              <dt>方向 / 数量</dt>
              <dd>
                {draft.side === 'buy' ? '买入' : '卖出'} · {fmt(Number(draft.quantity))}{' '}
                {quantityUnit(draft.security)}
              </dd>
              <dt>价格 / 费用</dt>
              <dd>
                {money(Number(draft.price))} 元/{quantityUnit(draft.security)} ·{' '}
                {money(Number(draft.fees))} 元
              </dd>
              <dt>发生时间</dt>
              <dd>{draft.at.replace('T', ' ')}（本机时区）</dd>
            </>
          )}
          <dt>持仓处理</dt>
          <dd>{draft.affects ? '同步更新持仓' : '只补记录，不调整持仓'}</dd>
        </dl>
      )}
      {draft.reason && <p>记录原因：{draft.reason}</p>}
      {['watchlist', 'remove'].includes(target.kind) ? (
        <p>
          {target.kind === 'remove'
            ? '从自选中移除；持仓和已有委托保留。'
            : '加入自选；不会创建研究委托或开启通知。'}
        </p>
      ) : (
        <dl className={css.summary}>
          <dt>持仓数量</dt>
          <dd>
            {fmt(before?.quantity ?? 0)} →{' '}
            <strong>
              {fmt(after?.quantity ?? 0)} {quantityUnit(after || before || draft.security)}
            </strong>
          </dd>
          <dt>单位成本</dt>
          <dd>
            {money(before?.cost_price)} → <strong>{money(after?.cost_price)} 元</strong>
          </dd>
        </dl>
      )}
      <small>
        基于事实版本 {preview.fact_version}，确认保存后生效。
        {target.kind === 'holding' ? '校正不计作成交。' : ''}
      </small>
      {preview.impact.gaps?.map((gap, i) => (
        <p role="status" className={css.error} key={i}>
          {gap.detail}
        </p>
      ))}
    </section>
  )
}
