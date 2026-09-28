import { BarChart3, Bot, CalendarDays, CheckCircle2, ChevronRight, Languages, Laptop, Layers3, LoaderCircle, Route, Server, Target, Trophy } from 'lucide-react'
import { identifierLabel, translate } from '../i18n'
import type { AggregateStats, AggregateStatsResponse, UiLanguage } from '../types'
import { formatNumber, formatPercent } from '../utils'

interface StatsViewProps {
  language: UiLanguage
  localStats: AggregateStats
  remoteStats?: AggregateStatsResponse
  loading: boolean
  error?: string
  onStartTraining: () => void
}

interface GroupRow {
  label: string
  sessions?: number
  agreementRate?: number
  outcome?: number
  skill?: number
}

function numeric(record: Record<string, unknown>, ...keys: string[]): number | undefined {
  for (const key of keys) {
    if (typeof record[key] === 'number') return record[key] as number
  }
  return undefined
}

function normalizeGroup(value: unknown, labelKeys: string[]): GroupRow[] {
  const entries: Array<[string | undefined, unknown]> = Array.isArray(value)
    ? value.map((item) => [undefined, item])
    : typeof value === 'object' && value !== null
      ? Object.entries(value)
      : []

  return entries.flatMap(([entryKey, item]) => {
    if (typeof item !== 'object' || item === null) return []
    const record = item as Record<string, unknown>
    const labelValue = labelKeys.map((key) => record[key]).find((candidate) => typeof candidate === 'string')
    return [{
      label: String(labelValue ?? entryKey ?? '—'),
      sessions: numeric(record, 'sessions', 'session_count', 'total_sessions', 'count'),
      agreementRate: numeric(record, 'agreement_rate', 'agreements_rate', 'agreement_ratio'),
      outcome: numeric(record, 'average_outcome_score', 'avg_outcome_score', 'outcome_score', 'average_outcome'),
      skill: numeric(record, 'average_skill_score', 'avg_skill_score', 'skill_score', 'average_skill'),
    }]
  })
}

function metricScore(value: number | undefined): number | undefined {
  if (value === undefined) return undefined
  return value <= 1 ? value * 100 : value
}

export function StatsView({ language, localStats, remoteStats, loading, error, onStartTraining }: StatsViewProps) {
  const t = (key: string) => translate(language, key)
  const locale = language === 'ru' ? 'ru-RU' : 'en-US'
  const totals = (remoteStats?.totals ?? remoteStats ?? {}) as Record<string, unknown>
  const remoteSessions = numeric(totals, 'total_sessions', 'sessions', 'session_count')
  // The summary cards show service-wide totals when the API returned them and local history otherwise.
  const hasRemoteTotals = remoteSessions !== undefined
  const totalsSourceLabel = hasRemoteTotals ? t('statsServiceTotals') : t('statsLocalTotals')
  const totalSessions = remoteSessions ?? localStats.sessions
  const completedSessions = numeric(totals, 'completed_sessions', 'completed_count') ?? totalSessions
  const totalAgreements = numeric(totals, 'agreements', 'agreement_count', 'total_agreements') ?? localStats.agreements
  const agreementRate = numeric(totals, 'agreement_rate', 'agreements_rate', 'agreement_ratio')
    ?? (completedSessions ? totalAgreements / completedSessions : undefined)
  const averageOutcome = numeric(totals, 'average_outcome_score', 'avg_outcome_score', 'average_outcome') ?? localStats.average_outcome ?? undefined

  const groups = [
    { key: 'by_model', title: t('byModel'), icon: Bot, rows: normalizeGroup(remoteStats?.by_model, ['model', 'model_id', 'name']) },
    { key: 'by_scenario', title: t('byScenario'), icon: Layers3, rows: normalizeGroup(remoteStats?.by_scenario, ['scenario', 'scenario_id', 'scenario_title', 'name']) },
    { key: 'by_language', title: t('byLanguage'), icon: Languages, rows: normalizeGroup(remoteStats?.by_language, ['language', 'language_code', 'name']) },
    { key: 'by_difficulty', title: t('byDifficulty'), icon: Route, rows: normalizeGroup(remoteStats?.by_difficulty, ['difficulty', 'level', 'name']) },
  ]

  const hasData = totalSessions > 0 || localStats.sessions > 0

  return (
    <main className="stats-page">
      <header className="stats-heading">
        <div>
          <p className="eyebrow">{t('statsEyebrow')}</p>
          <h1>{t('statsTitle')}</h1>
          <p>{t('statsLead')}</p>
        </div>
        <button className="button button-primary" type="button" onClick={onStartTraining}>
          {t('newSession')} <ChevronRight size={17} aria-hidden="true" />
        </button>
      </header>

      {loading && !remoteStats ? (
        <div className="stats-loading"><LoaderCircle className="spin" size={22} aria-hidden="true" /> {t('statsRefreshing')}</div>
      ) : error ? (
        <div className="stats-service-note"><BarChart3 size={18} aria-hidden="true" /><span>{t('statsServiceUnavailable')}</span></div>
      ) : null}

      {!hasData && !loading ? (
        <section className="stats-empty panel-card">
          <span><Trophy size={32} aria-hidden="true" /></span>
          <h2>{t('statsEmptyTitle')}</h2>
          <p>{t('statsEmptyText')}</p>
          <button className="button button-primary" type="button" onClick={onStartTraining}>{t('goToTraining')}</button>
        </section>
      ) : (
        <>
          <p className="stats-source-note">
            {hasRemoteTotals ? <Server size={15} aria-hidden="true" /> : <Laptop size={15} aria-hidden="true" />}
            <span>{totalsSourceLabel}</span>
          </p>
          <section className="stats-metrics" aria-label={totalsSourceLabel}>
            <article>
              <span className="metric-icon"><CalendarDays size={19} aria-hidden="true" /></span>
              <div><small>{t('totalSessions')}</small><strong>{formatNumber(totalSessions, locale)}</strong></div>
            </article>
            <article>
              <span className="metric-icon green"><CheckCircle2 size={19} aria-hidden="true" /></span>
              <div><small>{t('agreements')}</small><strong>{formatNumber(totalAgreements, locale)}</strong></div>
              <span className="metric-trend">{formatPercent(agreementRate, locale)}</span>
            </article>
            <article>
              <span className="metric-icon amber"><Target size={19} aria-hidden="true" /></span>
              <div><small>{t('averageOutcome')}</small><strong>{averageOutcome === undefined ? '—' : formatNumber(metricScore(averageOutcome) ?? 0, locale, 0)}</strong></div>
              <span className="metric-trend neutral">/ 100</span>
            </article>
          </section>

          {groups.some((group) => group.rows.length > 0) && (
            <section className="aggregate-section">
              <div className="section-title-row">
                <div><BarChart3 size={20} aria-hidden="true" /><h2>{t('aggregateBreakdown')}</h2></div>
              </div>
              <div className="aggregate-grid">
                {groups.map(({ key, title, icon: Icon, rows }) => (
                  <article className="aggregate-card" key={key}>
                    <header><span><Icon size={17} aria-hidden="true" /></span><h3>{title}</h3></header>
                    {rows.length ? (
                      <div className="aggregate-rows">
                        {rows.slice(0, 6).map((row) => (
                          <div className="aggregate-row" key={row.label}>
                            <div className="aggregate-row-title">
                              <strong>{identifierLabel(language, row.label)}</strong>
                              <small>{row.sessions ?? 0} {t('sessionsShort')}</small>
                            </div>
                            <div className="aggregate-row-values">
                              <span title={t('agreementRate')}>{formatPercent(row.agreementRate, locale)}</span>
                              <strong>{row.outcome === undefined ? '—' : Math.round(metricScore(row.outcome) ?? 0)}</strong>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : <p className="aggregate-empty">—</p>}
                  </article>
                ))}
              </div>
            </section>
          )}

          {localStats.recent.length > 0 && (
            <section className="stats-section recent-section">
              <div className="section-title-row">
                <div><CalendarDays size={20} aria-hidden="true" /><h2>{t('recentSessions')}</h2></div>
                <small className="stats-source-badge">{t('statsLocalTotals')}</small>
              </div>
              <div className="recent-table-wrap">
                <table className="recent-table">
                  <thead><tr><th>{t('date')}</th><th>{t('scenarioLabel')}</th><th>{t('result')}</th><th>{t('outcomeScore')}</th></tr></thead>
                  <tbody>
                    {localStats.recent.map((item) => (
                      <tr key={item.session_id}>
                        <td>{new Intl.DateTimeFormat(locale, { day: '2-digit', month: 'short', year: 'numeric' }).format(new Date(item.finished_at))}</td>
                        <td><strong>{item.scenario_title}</strong><small>{item.session_id}</small></td>
                        <td><span className={item.review.outcome.agreement ? 'table-result agreement' : 'table-result'}>{item.review.outcome.agreement ? t('agreement') : t('noAgreement')}</span></td>
                        <td><strong>{item.review.outcome_score === undefined ? '—' : Math.round(metricScore(item.review.outcome_score) ?? 0)}</strong></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}
        </>
      )}
    </main>
  )
}
