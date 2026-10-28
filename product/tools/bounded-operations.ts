export const boundedOperations = ['quote_snapshot', 'company_profile', 'financial_summary',
  'market_quote', 'market_technical', 'news', 'market_brief'] as const
export const boundedManifest = { version: 1, operations: boundedOperations }
