import { describe, expect, it } from 'vitest'
import { providerFeaturesEnabled } from '../features'

describe('provider feature flag', () => {
  it('defaults to off and enables only an explicit true value', () => {
    expect(providerFeaturesEnabled(undefined)).toBe(false)
    expect(providerFeaturesEnabled('false')).toBe(false)
    expect(providerFeaturesEnabled('true')).toBe(true)
    expect(providerFeaturesEnabled(true)).toBe(true)
  })
})
