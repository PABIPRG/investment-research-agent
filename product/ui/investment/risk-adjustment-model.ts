import type { RiskProfile } from './types.js'

export const toleranceOptions = [
  { value: 0, label: '保守', description: '更重视控制波动，愿意少一些收益机会。' },
  { value: 0.5, label: '稳健', description: '兼顾收益与风险，可以接受一定波动。' },
  { value: 1, label: '进取', description: '追求更高的潜在收益，可以接受较大波动与回撤。' },
] as const

/** Display the existing round(2 * risk) bands; never rewrite a stored value. */
export function toleranceLabel(value: number): string {
  return value <= 0.25 ? '保守' : value < 0.75 ? '稳健' : '进取'
}
export function adjustmentDefaults(profile?: RiskProfile | null) {
  return {
    risk:
      profile?.manual_adjust?.risk_tolerance ??
      { conservative: 0, balanced: 0.5, aggressive: 1 }[profile?.profile ?? ''] ??
      0.5,
    years: profile?.manual_adjust ? String(profile.manual_adjust.horizon_years) : '',
  }
}
export function validHorizon(value: string): boolean {
  return /^\d+$/.test(value) && Number(value) >= 1 && Number(value) <= 30
}
