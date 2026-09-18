import { ArrowRight, Award, CheckCircle2, Gauge, Handshake, Lightbulb, LoaderCircle, RotateCcw, Sparkles, Target, TrendingUp } from 'lucide-react'
import { identifierLabel, translate } from '../i18n'
import type { SessionReview, SessionStatus, UiLanguage } from '../types'
import { formatNumber } from '../utils'
import { FinancialSummary } from './FinancialSummary'

interface ReviewPanelProps {
  language: UiLanguage
  status: SessionStatus
  review?: SessionReview
  loading: boolean
  error?: string
  onRetry: () => void
  onNewSession: () => void
}

function scoreValue(value: number | undefined): number | undefined {
  if (value === undefined) return undefined
  return value <= 1 ? value * 100 : value
}

export function ReviewPanel({
  language,
  status,
  review,
  loading,
  error,
  onRetry,
  onNewSession,
}: ReviewPanelProps) {
  const t = (key: string) => translate(language, key)
  const locale = language === 'ru' ? 'ru-RU' : 'en-US'

  if (loading && !review) {
    return (
      <section className="review-panel loading-review">
        <span className="review-loader"><LoaderCircle className="spin" size={28} aria-hidden="true" /></span>
        <h2>{t('reviewLoading')}</h2>
        <p>{t('terminalLead')}</p>
      </section>
    )
  }

  if (!review) {
    return (
      <section className="review-panel loading-review">
        <span className="review-loader warning"><RotateCcw size={26} aria-hidden="true" /></span>
        <h2>{t('reviewPending')}</h2>
        {error && <p className="review-error-detail">{error}</p>}
        <div className="review-empty-actions">
          <button className="button button-secondary" type="button" onClick={onRetry}><RotateCcw size={16} aria-hidden="true" /> {t('retry')}</button>
          <button className="button button-primary" type="button" onClick={onNewSession}>{t('startAgain')} <ArrowRight size={16} aria-hidden="true" /></button>
        </div>
      </section>
    )
  }

  const outcomeScore = scoreValue(review.outcome_score)
  const skillScore = scoreValue(review.skill_score)
  const skillEntries = Object.entries(review.skills ?? {}).filter((entry): entry is [string, number] => typeof entry[1] === 'number')
  const utilities = Object.entries(review.outcome.participant_utilities ?? {})
  if (utilities.length === 0 && typeof review.outcome.participant_utility === 'number') {
    utilities.push(['your_role', review.outcome.participant_utility])
  }
  const hintsUsed = typeof review.assistance_usage?.hints_used === 'number'
    ? review.assistance_usage.hints_used
    : 0

  return (
    <section className="review-panel" aria-labelledby="review-title">
      <header className="review-hero">
        <div className="review-hero-copy">
          <span className="review-hero-icon"><Award size={25} aria-hidden="true" /></span>
          <div>
            <p className="eyebrow">{t('reviewTitle')}</p>
            <h2 id="review-title">{t(status)}</h2>
            <p>{review.outcome.agreement ? t('agreement') : t('noAgreement')} · {identifierLabel(language, review.outcome.termination_reason ?? status)}</p>
          </div>
        </div>
        <button className="button button-primary" type="button" onClick={onNewSession}>
          {t('startAgain')} <ArrowRight size={17} aria-hidden="true" />
        </button>
      </header>

      <div className="review-score-grid">
        <article className="score-card primary-score">
          <span><Target size={19} aria-hidden="true" /></span>
          <small>{t('outcomeScore')}</small>
          <strong>{outcomeScore === undefined ? '—' : formatNumber(outcomeScore, locale, 0)}</strong>
          <div className="score-track"><span style={{ width: `${Math.min(100, outcomeScore ?? 0)}%` }} /></div>
        </article>
        <article className="score-card">
          <span><Sparkles size={19} aria-hidden="true" /></span>
          <small>{t('skillScore')}</small>
          <strong>{skillScore === undefined ? '—' : formatNumber(skillScore, locale, 0)}</strong>
          <div className="score-track"><span style={{ width: `${Math.min(100, skillScore ?? 0)}%` }} /></div>
        </article>
        <article className="score-card">
          <span><Lightbulb size={19} aria-hidden="true" /></span>
          <small>{t('hintsUsed')}</small>
          <strong>{formatNumber(hintsUsed, locale, 0)}</strong>
        </article>
        <article className="score-card">
          <span><Handshake size={19} aria-hidden="true" /></span>
          <small>{t('result')}</small>
          <strong className="result-word">{review.outcome.agreement ? t('agreement') : t('noAgreement')}</strong>
          <div className="score-result-note"><CheckCircle2 size={14} aria-hidden="true" /> {t(status)}</div>
        </article>
      </div>

      <FinancialSummary summary={review.outcome.financial_summary} language={language} />

      <div className="review-detail-grid">
        <section className="review-section skill-review">
          <header>
            <div><TrendingUp size={18} aria-hidden="true" /><h3>{t('skills')}</h3></div>
            <small>{t('scoreRange')}</small>
          </header>
          {skillEntries.length > 0 ? (
            <div className="skill-bars">
              {skillEntries.map(([skill, value]) => {
                const normalized = value <= 1 ? value * 100 : value
                return (
                  <div className="skill-row" key={skill}>
                    <div><span>{identifierLabel(language, skill)}</span><strong>{Math.round(normalized)}</strong></div>
                    <div className="skill-track"><span style={{ width: `${Math.min(100, normalized)}%` }} /></div>
                  </div>
                )
              })}
            </div>
          ) : <p className="empty-review-copy">—</p>}
        </section>

        <section className="review-section utility-review">
          <header><div><Gauge size={18} aria-hidden="true" /><h3>{t('utilities')}</h3></div></header>
          <div className="utility-list">
            {utilities.length > 0 ? utilities.map(([participant, utility]) => (
              <div key={participant}>
                <span>{identifierLabel(language, participant)}</span>
                <strong>{formatNumber(utility, locale, 1)}</strong>
              </div>
            )) : <p className="empty-review-copy">—</p>}
          </div>
        </section>

        <section className="review-section moments-review">
          <header><div><Sparkles size={18} aria-hidden="true" /><h3>{t('keyMoments')}</h3></div></header>
          {review.key_moments?.length ? (
            <div className="moments-list">
              {review.key_moments.map((moment, index) => (
                <article key={moment.event_id ?? `${moment.title}-${index}`}>
                  <span className={`moment-marker ${moment.impact ?? 'neutral'}`} />
                  <div>
                    {(moment.type || moment.title) && <strong>{moment.type ? identifierLabel(language, moment.type) : moment.title}</strong>}
                    <p>{moment.summary ?? moment.message ?? identifierLabel(language, moment.type ?? '')}</p>
                    {moment.detail && <p className="moment-detail">{moment.detail}</p>}
                  </div>
                </article>
              ))}
            </div>
          ) : <p className="empty-review-copy">{t('noKeyMoments')}</p>}
        </section>

        {Boolean(review.recommendations?.length) && (
          <section className="review-section recommendations-review">
            <header><div><Lightbulb size={18} aria-hidden="true" /><h3>{t('recommendations')}</h3></div></header>
            <div className="recommendation-list">
              {review.recommendations?.map((item, index) => (
                <article key={`${item.skill}-${index}`}>
                  <span className="moment-marker positive" />
                  <div>
                    <strong>{identifierLabel(language, item.skill, item.skill)}</strong>
                    <p>{item.text}</p>
                  </div>
                </article>
              ))}
            </div>
          </section>
        )}
      </div>
    </section>
  )
}
