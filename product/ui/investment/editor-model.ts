import { localTime, type EditTarget, type Security } from './types.js'
import { securityName } from '../business-model.js'
export type InvestmentDraft = {
  security?: Security
  quantity: string
  price: string
  fees: string
  side: string
  at: string
  reason: string
  affects: boolean
  revisionOp: 'amend' | 'void'
}
export function initialDraft(target: EditTarget): InvestmentDraft {
  const row = target.trade || target.position || target.watch
  return {
    security: row
      ? {
          code: row.ticker,
          name: securityName(row.ticker, row.display_name, row.name, target.securityName),
        }
      : undefined,
    quantity: String(
      target.trade?.quantity ??
        (target.kind === 'holding' ? target.position?.quantity : undefined) ??
        '',
    ),
    price: String(
      target.trade?.price ??
        (target.kind === 'holding' ? target.position?.cost_price : undefined) ??
        '',
    ),
    fees: String(target.trade?.fees ?? 0),
    side: target.trade?.side || 'buy',
    at: localTime(target.trade?.traded_at),
    reason: '',
    affects: target.trade?.affects_holdings ?? true,
    revisionOp: 'amend',
  }
}
export function previewCommand(target: EditTarget, d: InvestmentDraft, requestId: string) {
  if (!d.security) throw Error('请先搜索并选择证券。')
  const ticker = d.security.code,
    name = d.security.name
  if (target.kind === 'remove')
    return {
      command: 'watchlist',
      payload: { ticker, name, reason: target.watch?.reason || '', remove: true },
    }
  if (target.kind === 'watchlist')
    return { command: 'watchlist', payload: { ticker, name, reason: d.reason, remove: false } }
  const at = new Date(d.at)
  if (!Number.isFinite(at.getTime())) throw Error('请选择有效的记录时间。')
  if (target.kind === 'holding')
    return {
      command: 'holding',
      payload: {
        ticker,
        name,
        quantity: Number(d.quantity),
        cost_price: d.price === '' ? null : Number(d.price),
        effective_at: at.toISOString(),
        reason: d.reason,
      },
    }
  const trade = {
    side: d.side,
    quantity: Number(d.quantity),
    price: Number(d.price),
    fees: Number(d.fees),
    traded_at: at.toISOString(),
  }
  if (target.kind === 'trade')
    return {
      command: 'trade',
      payload: {
        request_id: requestId,
        ticker,
        ...(name !== '名称待补充' ? { name } : {}),
        ...trade,
        affects_holdings: d.affects,
      },
    }
  return {
    command: 'revision',
    payload: {
      revision_id: requestId,
      trade_request_id: target.trade!.request_id,
      operation: d.revisionOp,
      ...(d.revisionOp === 'amend' ? trade : {}),
      affects_holdings: d.affects,
      reason: d.reason,
    },
  }
}
