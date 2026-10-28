import type { Facts } from './types.js'
import { securityName } from '../business-model.js'
/** Warm the existing directory for missing stock labels; never submit an investment command. */
export async function hydrateDisplayNames(
  facts: Facts,
  lookup: (code: string) => Promise<unknown>,
  onBatch: () => Promise<void> = async () => {},
) {
  const codes = [
    ...new Set(
      [...facts.holdings, ...facts.trades, ...facts.watchlist]
        .filter(
          (r) =>
            securityName(r.ticker, r.display_name, r.name) === '名称待补充' &&
            /^(?:60[0135]|68[89]|00[0123]|30[01])\d{3}$/.test(r.ticker),
        )
        .map((r) => r.ticker),
    ),
  ]
  for (let offset = 0; offset < codes.length; offset += 4) {
    const results = await Promise.allSettled(codes.slice(offset, offset + 4).map(lookup))
    if (results.some((r) => r.status === 'fulfilled')) await onBatch()
  }
}
