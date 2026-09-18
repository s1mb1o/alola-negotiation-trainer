import { describe, expect, it } from 'vitest'
import { appViewFromPathname, appViewPath } from '../routing'

describe('page routing', () => {
  it('maps application views to stable slugs', () => {
    expect(appViewPath('training')).toBe('/training')
    expect(appViewPath('stats')).toBe('/progress')
    expect(appViewPath('inspector')).toBe('/inspector')
  })

  it('restores the view from direct and trailing-slash paths', () => {
    expect(appViewFromPathname('/training')).toBe('training')
    expect(appViewFromPathname('/training/')).toBe('training')
    expect(appViewFromPathname('/progress')).toBe('stats')
    expect(appViewFromPathname('/progress/')).toBe('stats')
    expect(appViewFromPathname('/inspector')).toBe('inspector')
    expect(appViewFromPathname('/inspector/')).toBe('inspector')
  })

  it('routes the root and unknown paths to training', () => {
    expect(appViewFromPathname('/')).toBe('training')
    expect(appViewFromPathname('/unknown')).toBe('training')
  })
})
