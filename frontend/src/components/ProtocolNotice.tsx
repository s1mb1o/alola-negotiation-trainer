import { AlertCircle, ArrowRight, CheckCircle2, ShieldAlert, XCircle } from 'lucide-react'
import { identifierLabel, translate } from '../i18n'
import type { Clarification, PendingConfirmation, PendingOfferPublication, UiLanguage } from '../types'
import { TermsList } from './TermsList'

interface ProtocolNoticeProps {
  language: UiLanguage
  clarification?: Clarification
  confirmation?: PendingConfirmation
  publication?: PendingOfferPublication
  currency?: string
  busy: boolean
  onConfirm: () => void
  onCancel: () => void
}

export function ProtocolNotice({
  language,
  clarification,
  confirmation,
  publication,
  currency,
  busy,
  onConfirm,
  onCancel,
}: ProtocolNoticeProps) {
  const t = (key: string) => translate(language, key)

  if (clarification) {
    return (
      <section className="protocol-notice clarification-notice" aria-labelledby="clarification-title" role="status">
        <span className="protocol-notice-icon"><AlertCircle size={21} aria-hidden="true" /></span>
        <div className="protocol-notice-content">
          <p className="notice-kicker">{t('clarificationTitle')}</p>
          <h3 id="clarification-title">{clarification.question}</h3>
          <p>{t('clarificationLead')}</p>
          {Boolean(clarification.candidate_interpretations?.length) && (
            <div className="interpretation-list" aria-label={t('candidateInterpretations')}>
              {clarification.candidate_interpretations?.map((candidate) => (
                <span key={candidate}><ArrowRight size={13} aria-hidden="true" /> {identifierLabel(language, candidate)}</span>
              ))}
            </div>
          )}
          {clarification.recovery && (
            <div className="clarification-recovery">
              <strong>{t('clarificationRecovery')}</strong>
              <p>{clarification.recovery.example}</p>
              <small>{t('clarificationOrEnd')} «{clarification.recovery.end_session_message}»</small>
            </div>
          )}
        </div>
      </section>
    )
  }

  if (publication) {
    const incomplete = publication.unresolved_required_terms.length > 0
    return (
      <section className="protocol-notice confirmation-notice publication-notice" aria-labelledby="publication-title">
        <div className="confirmation-heading">
          <span className="protocol-notice-icon"><ShieldAlert size={21} aria-hidden="true" /></span>
          <div>
            <p className="notice-kicker">{t('publicationTitle')}</p>
            <h3 id="publication-title">{t('publicationLead')}</h3>
          </div>
          <span className="confirmation-ref">{t('revision')} {publication.proposal_revision}</span>
        </div>
        <TermsList terms={publication.terms} locale={language === 'ru' ? 'ru-RU' : 'en-US'} currency={currency} />
        <details className="proposal-sources">
          <summary>{t('snapshotReference')}</summary>
          <code>{publication.proposal_id} · {publication.snapshot_digest}</code>
        </details>
        {incomplete && <p role="alert">{t('publicationIncomplete')}</p>}
        <div className="confirmation-actions">
          <button className="button button-secondary" type="button" onClick={onCancel} disabled={busy}>
            <XCircle size={17} aria-hidden="true" /> {t('publicationCancel')}
          </button>
          <button className="button button-confirm" type="button" onClick={onConfirm} disabled={busy || incomplete}>
            <CheckCircle2 size={17} aria-hidden="true" /> {t('publicationConfirm')}
          </button>
        </div>
      </section>
    )
  }

  if (confirmation) {
    return (
      <section className="protocol-notice confirmation-notice" aria-labelledby="confirmation-title">
        <div className="confirmation-heading">
          <span className="protocol-notice-icon"><ShieldAlert size={21} aria-hidden="true" /></span>
          <div>
            <p className="notice-kicker">{t('confirmationTitle')}</p>
            <h3 id="confirmation-title">{t('confirmationLead')}</h3>
          </div>
          <span className="confirmation-ref">{t('revision')} {confirmation.offer_revision}</span>
        </div>
        <TermsList terms={confirmation.terms} locale={language === 'ru' ? 'ru-RU' : 'en-US'} currency={currency} compact />
        <div className="confirmation-actions">
          <button className="button button-secondary" type="button" onClick={onCancel} disabled={busy}>
            <XCircle size={17} aria-hidden="true" /> {t('cancel')}
          </button>
          <button className="button button-confirm" type="button" onClick={onConfirm} disabled={busy || Boolean(confirmation.unresolved_required_terms?.length)}>
            <CheckCircle2 size={17} aria-hidden="true" /> {t('confirm')}
          </button>
        </div>
      </section>
    )
  }

  return null
}
