import { describe, expect, it } from 'vitest'
import { appViewFromPathname, appViewPath } from '../routing'

describe('page routing', () => {
  it('maps application views to stable slugs', () => {
    expect(appViewPath('training')).toBe('/app/training')
    expect(appViewPath('stats')).toBe('/app/progress')
    expect(appViewPath('inspector')).toBe('/app/inspector')
  })

  it('restores the view from direct and trailing-slash paths', () => {
    expect(appViewFromPathname('/app/training')).toBe('training')
    expect(appViewFromPathname('/app/training/')).toBe('training')
    expect(appViewFromPathname('/app/progress')).toBe('stats')
    expect(appViewFromPathname('/app/progress/')).toBe('stats')
    expect(appViewFromPathname('/app/inspector')).toBe('inspector')
    expect(appViewFromPathname('/app/inspector/')).toBe('inspector')
  })

  it('routes unknown application paths to training', () => {
    expect(appViewFromPathname('/app')).toBe('training')
    expect(appViewFromPathname('/app/unknown')).toBe('training')
  })
})
