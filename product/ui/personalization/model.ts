export type Card = {
  card_id: string
  event_id: string
  title: string
  summary: string
  source: string
  time: string
  url?: string
  bucket: string
  business_view: string
  relevance_score: number
  reasons: string[]
  feedback_sentiment?: string
  tickers: { code: string; name?: string }[]
  risk: { level: string; note?: string }
}
export type Learning = {
  enabled: boolean
  record_count: number
  event_count: number
  feedback_count: number
  retention_days: number
  event_cap: number
}
export type Personalized = {
  version: number
  learning: Learning
  profile_is_explicit: boolean
  notice: string
  cards: { cards: Card[]; total: number; page_info: { has_more: boolean; next_offset: number } }
  matches: {
    items: {
      strategy_id: string
      name: string
      match_score: number
      fits_profile: boolean
      match_reasons: { dim: string; text: string; score: number }[]
      caution?: string
      breakdown: Record<string, { score: number; notes: string[] }>
    }[]
  }
  review: {
    data_note?: string
    overview: { signal_count: number; active_days: number; confidence: string }
    insights: { id: string; title: string; explanation: string; evidence_count: number }[]
    recent_activity: { label: string; occurred_at: string }[]
    funnel: { impressions: number; opens: number; analyses: number; feedback: number }
  }
}
export type PersonalPreview = {
  preview_id: string
  payload: { action: string; enabled?: boolean; card_id?: string; sentiment?: string }
  before: Personalized
  after: Personalized
}
