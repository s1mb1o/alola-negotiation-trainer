import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  applyTheme,
  applyUiLanguage,
  initialTheme,
  initialUiLanguage,
  THEME_KEY,
  UI_LANGUAGE_KEY,
} from '../preferences'

describe('UI preferences', () => {
  beforeEach(() => {
    localStorage.clear()
    delete document.documentElement.dataset.theme
    document.documentElement.style.colorScheme = ''
    document.head.innerHTML = '<meta name="description"><meta name="theme-color">'
  })

  afterEach(() => vi.unstubAllGlobals())

  it('applies and persists English document metadata', () => {
    applyUiLanguage('en')

    expect(document.documentElement.lang).toBe('en')
    expect(document.title).toBe('ALOLA — negotiation trainer')
    expect(document.querySelector('meta[name="description"]')).toHaveAttribute(
      'content',
      'A business negotiation trainer with controlled scenarios and evidence-based reviews.',
    )
    expect(localStorage.getItem(UI_LANGUAGE_KEY)).toBe('en')
    expect(initialUiLanguage()).toBe('en')
  })

  it('applies a manual dark theme and persists it', () => {
    applyTheme('dark')

    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(document.querySelector('meta[name="theme-color"]')).toHaveAttribute('content', '#10140f')
    expect(localStorage.getItem(THEME_KEY)).toBe('dark')
    expect(initialTheme()).toBe('dark')
  })

  it('follows the system theme without forcing a data attribute', () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true }))

    applyTheme('system')

    expect(document.documentElement).not.toHaveAttribute('data-theme')
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(localStorage.getItem(THEME_KEY)).toBe('system')
  })
})
