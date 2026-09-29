import type { MouseEvent } from 'react'
import { BarChart3, Database, MessageSquareText, MonitorCog, Moon, Plus, Settings2, Sun } from 'lucide-react'
import { translate } from '../i18n'
import { appViewPath, type AppView } from '../routing'
import type { ThemePreference, UiLanguage } from '../types'

interface AppHeaderProps {
  language: UiLanguage
  theme: ThemePreference
  activeView: AppView
  hasSession: boolean
  onLanguageChange: (language: UiLanguage) => void
  onThemeChange: (theme: ThemePreference) => void
  onViewChange: (view: AppView) => void
  onNewSession: () => void
}

export function AppHeader({
  language,
  theme,
  activeView,
  hasSession,
  onLanguageChange,
  onThemeChange,
  onViewChange,
  onNewSession,
}: AppHeaderProps) {
  const t = (key: string) => translate(language, key)
  const ThemeIcon = theme === 'dark' ? Moon : theme === 'light' ? Sun : MonitorCog
  const themeLabel = t(theme === 'dark' ? 'themeDark' : theme === 'light' ? 'themeLight' : 'themeSystem')
  const navigate = (event: MouseEvent<HTMLAnchorElement>, view: AppView) => {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
    event.preventDefault()
    onViewChange(view)
  }

  return (
    <header className="app-header">
      <a className="brand" href={appViewPath('training')} onClick={(event) => navigate(event, 'training')} aria-label={t('brand')}>
        <span className="brand-mark" aria-hidden="true">
          <span />
          <span />
        </span>
        <span className="brand-copy">
          <strong>{t('brand')}</strong>
          <small>{t('brandSubtitle')}</small>
        </span>
      </a>

      <nav className="primary-nav" aria-label={t('primaryNavigation')}>
        <a className={activeView === 'admin' ? 'nav-button active' : 'nav-button'}
          href={appViewPath('admin')} onClick={event => navigate(event, 'admin')}
          aria-label={t('navAdmin')}
          aria-current={activeView === 'admin' ? 'page' : undefined}>
          <Settings2 size={17} aria-hidden="true" /><span>{t('navAdmin')}</span>
        </a>
        <a
          className={activeView === 'training' ? 'nav-button active' : 'nav-button'}
          href={appViewPath('training')}
          onClick={(event) => navigate(event, 'training')}
          aria-current={activeView === 'training' ? 'page' : undefined}
          aria-label={t('navTraining')}
        >
          <MessageSquareText size={17} aria-hidden="true" strokeWidth={2} />
          <span>{t('navTraining')}</span>
        </a>
        <a
          className={activeView === 'stats' ? 'nav-button active' : 'nav-button'}
          href={appViewPath('stats')}
          onClick={(event) => navigate(event, 'stats')}
          aria-current={activeView === 'stats' ? 'page' : undefined}
          aria-label={t('navStats')}
        >
          <BarChart3 size={17} aria-hidden="true" strokeWidth={2} />
          <span>{t('navStats')}</span>
        </a>
        <a
          className={activeView === 'inspector' ? 'nav-button active' : 'nav-button'}
          href={appViewPath('inspector')}
          onClick={(event) => navigate(event, 'inspector')}
          aria-current={activeView === 'inspector' ? 'page' : undefined}
          aria-label={t('navInspector')}
        >
          <Database size={17} aria-hidden="true" strokeWidth={2} />
          <span>{t('navInspector')}</span>
        </a>
      </nav>

      <div className="header-actions">
        <div className="compact-control language-control" role="group" aria-label={t('uiLanguage')}>
          <button
            type="button"
            className={language === 'ru' ? 'active' : ''}
            onClick={() => onLanguageChange('ru')}
            aria-pressed={language === 'ru'}
          >
            RU
          </button>
          <button
            type="button"
            className={language === 'en' ? 'active' : ''}
            onClick={() => onLanguageChange('en')}
            aria-pressed={language === 'en'}
          >
            EN
          </button>
        </div>

        <label className="select-control theme-control" title={`${t('theme')}: ${themeLabel}`}>
          <ThemeIcon size={16} aria-hidden="true" />
          <select value={theme} onChange={(event) => onThemeChange(event.target.value as ThemePreference)} aria-label={`${t('theme')}: ${themeLabel}`}>
            <option value="system">{t('themeSystem')}</option>
            <option value="light">{t('themeLight')}</option>
            <option value="dark">{t('themeDark')}</option>
          </select>
        </label>

        {hasSession && (
          <button className="button button-secondary header-new-session" type="button" onClick={onNewSession} aria-label={t('newSession')}>
            <Plus size={17} aria-hidden="true" />
            <span>{t('newSession')}</span>
          </button>
        )}
      </div>
    </header>
  )
}
