import assert from 'node:assert/strict'
import test from 'node:test'
import {
  adjustmentDefaults,
  toleranceLabel,
  validHorizon,
} from '../product/ui/investment/risk-adjustment-model.js'
import type { RiskProfile } from '../product/ui/investment/types.js'

const profile = (key: string, manual?: RiskProfile['manual_adjust']): RiskProfile => ({
  profile: key,
  label: '',
  tier: 'quick',
  score: 8,
  max_score: 15,
  answers: [],
  manual_adjust: manual,
})
test('editing starts from the effective profile and never invents a funding horizon', () => {
  assert.deepEqual(adjustmentDefaults(profile('conservative')), { risk: 0, years: '' })
  assert.deepEqual(adjustmentDefaults(profile('aggressive')), { risk: 1, years: '' })
  assert.deepEqual(adjustmentDefaults(profile('balanced')), { risk: 0.5, years: '' })
})
test('existing intermediate values and exact years survive opening the editor', () => {
  assert.deepEqual(
    adjustmentDefaults(profile('balanced', { risk_tolerance: 0.65, horizon_years: 7 })),
    { risk: 0.65, years: '7' },
  )
})
test('labels preserve the existing backend rounding boundaries', () => {
  assert.equal(toleranceLabel(0.25), '保守')
  assert.equal(toleranceLabel(0.25001), '稳健')
  assert.equal(toleranceLabel(0.74999), '稳健')
  assert.equal(toleranceLabel(0.75), '进取')
})
test('funding horizon requires explicit whole years in the supported range', () => {
  for (const value of ['', ' ', '0', '-1', '31', '1.5', '3e0', 'abc'])
    assert.equal(validHorizon(value), false, value)
  for (const value of ['1', '3', '5', '30']) assert.equal(validHorizon(value), true, value)
})
