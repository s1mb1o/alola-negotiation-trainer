import { translate } from './i18n'
import type { ThemePreference, UiLanguage } from './types'

export const UI_LANGUAGE_KEY = 'negotiation.ui-language'
export const THEME_KEY = 'negotiation.theme'

function storedValue(key: string): string | null {
  try {
    return localStorage.getItem(key)
  } catch {
    return null
  }
}

function storeValue(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // The UI remains usable when browser storage is unavailable.
  }
}

export function initialUiLanguage(): UiLanguage {
  return storedValue(UI_LANGUAGE_KEY) === 'en' ? 'en' : 'ru'
}

export function initialTheme(): ThemePreference {
  const stored = storedValue(THEME_KEY)
  return stored === 'light' || stored === 'dark' ? stored : 'system'
}

export function systemUsesDarkTheme(): boolean {
  return typeof window !== 'undefined'
    && typeof window.matchMedia === 'function'
    && window.matchMedia('(prefers-color-scheme: dark)').matches
}

export function applyUiLanguage(language: UiLanguage): void {
  document.documentElement.lang = language
  document.title = translate(language, 'documentTitle')
  document
    .querySelector<HTMLMetaElement>('meta[name="description"]')
    ?.setAttribute('content', translate(language, 'documentDescription'))
  storeValue(UI_LANGUAGE_KEY, language)
}

export function applyTheme(theme: ThemePreference): void {
  if (theme === 'system') delete document.documentElement.dataset.theme
  else document.documentElement.dataset.theme = theme

  const resolvedTheme = theme === 'system'
    ? systemUsesDarkTheme() ? 'dark' : 'light'
    : theme
  document.documentElement.style.colorScheme = resolvedTheme
  document
    .querySelector<HTMLMetaElement>('meta[name="theme-color"]')
    ?.setAttribute('content', resolvedTheme === 'dark' ? '#10140f' : '#f3f5ef')
  storeValue(THEME_KEY, theme)
}
