import { FileCheck2, Layers3, UserRound } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { identifierLabel, translate } from '../i18n'
import type { FinancialSummaryView, JsonRecord, OfferView, PreliminaryProposal, UiLanguage } from '../types'
import { TermsList } from './TermsList'
import { supplyTermLabel } from './SupplyTermValue'
import { FinancialSummary } from './FinancialSummary'

interface OfferPanelProps {
  language: UiLanguage
  offers: OfferView[]
  preliminaryProposals?: PreliminaryProposal[]
  currentPublicTerms?: JsonRecord
  currency?: string
  financialSummary?: FinancialSummaryView | null
}

export function OfferPanel({ language, offers, preliminaryProposals = [], currentPublicTerms, currency, financialSummary }: OfferPanelProps) {
  const t = (key: string) => translate(language, key)
  const [selectedId, setSelectedId] = useState<string>()
  const locale = language === 'ru' ? 'ru-RU' : 'en-US'
  const activeOffers = useMemo(() => offers.filter((offer) => !offer.status || offer.status === 'active'), [offers])

  useEffect(() => {
    if (!activeOffers.some((offer) => `${offer.offer_id}:${offer.offer_revision}` === selectedId)) {
      const first = activeOffers[0]
      setSelectedId(first ? `${first.offer_id}:${first.offer_revision}` : undefined)
    }
  }, [activeOffers, selectedId])

  const selected = activeOffers.find((offer) => `${offer.offer_id}:${offer.offer_revision}` === selectedId) ?? activeOffers[0]
  const preliminary = preliminaryProposals.find((proposal) => proposal.status === 'active')
  const selectedIsPartial = Boolean(selected?.unresolved_required_terms?.length)
  const selectedIsOpeningPosition = selectedIsPartial && selected?.offer_revision === 1
  const singleOfferTitle = selectedIsOpeningPosition
    ? t('openingPosition')
    : selectedIsPartial
      ? t('incompleteOffer')
      : t('activeOffer')

  return (
    <aside className="offer-panel panel-card" aria-labelledby="offer-panel-title">
      <header className="panel-heading">
        <span className="panel-icon offer-icon"><FileCheck2 size={18} aria-hidden="true" /></span>
        <div>
          <p className="panel-kicker">{preliminary ? t('preliminaryKicker') : activeOffers.length > 1 ? t('mesoKicker') : selectedIsPartial ? t('positionKicker') : t('dealKicker')}</p>
          <h2 id="offer-panel-title">{preliminary ? t('preliminaryProposal') : activeOffers.length > 1 ? t('activeOffers') : singleOfferTitle}</h2>
        </div>
        {activeOffers.length > 0 && <span className="offer-count">{activeOffers.length}</span>}
      </header>

      {activeOffers.length > 1 && (
        <div className="offer-tabs" role="tablist" aria-label={t('activeOffers')}>
          {activeOffers.map((offer, index) => {
            const id = `${offer.offer_id}:${offer.offer_revision}`
            return (
              <button
                key={id}
                type="button"
                role="tab"
                aria-selected={id === selectedId}
                className={id === selectedId ? 'active' : ''}
                onClick={() => setSelectedId(id)}
              >
                {t('optionLabel')} {String.fromCharCode(65 + index)}
              </button>
            )
          })}
        </div>
      )}

      {preliminary ? (
        <div className="offer-content preliminary-content">
          <p className="preliminary-badge">{t('preliminaryNonBinding')}</p>
          <p className="explanatory-copy">{t('preliminaryLead')}</p>
          <div className="offer-meta">
            <span><Layers3 size={14} aria-hidden="true" /> {t('revision')} {preliminary.proposal_revision}</span>
            <span><UserRound size={14} aria-hidden="true" /> {t('proposedBy')}: {identifierLabel(language, preliminary.proposer_role)}</span>
          </div>
          <TermsList terms={preliminary.terms} locale={locale} currency={currency} />
          {preliminary.unresolved_required_terms.length > 0 && <div className="unresolved-block">
            <strong>{t('unresolvedTerms')}</strong>
            <ul>{preliminary.unresolved_required_terms.map((path) => <li key={path}>{supplyTermLabel(path, language)
              ?? preliminary.unresolved_term_details?.find((detail) => detail.path === path)?.label
              ?? identifierLabel(language, path)}</li>)}</ul>
          </div>}
          {preliminary.source_event_ids.length > 0 && <details className="proposal-sources">
            <summary>{t('proposalSources')} · {preliminary.source_event_ids.length}</summary>
            <ul>{preliminary.source_event_ids.map((id) => <li key={id}><code>{id}</code></li>)}</ul>
          </details>}
        </div>
      ) : selected ? (
        <div className="offer-content">
          <div className="offer-meta">
            <span><Layers3 size={14} aria-hidden="true" /> {t('offerRevision')} {selected.offer_revision}</span>
            {(selected.proposer_role || selected.proposer_participant_id) && (
              <span><UserRound size={14} aria-hidden="true" /> {t('proposedBy')}: {identifierLabel(language, selected.proposer_role ?? selected.proposer_participant_id ?? '')}</span>
            )}
          </div>
          <TermsList terms={selected.terms} locale={locale} currency={currency} />
          {Boolean(selected.unresolved_required_terms?.length) && (
            <div className="unresolved-block">
              <strong>{t('unresolvedTerms')}</strong>
              <ul>
                {selected.unresolved_required_terms?.map((term) => <li key={term}>{supplyTermLabel(term, language) ?? identifierLabel(language, term)}</li>)}
              </ul>
            </div>
          )}
        </div>
      ) : currentPublicTerms && Object.keys(currentPublicTerms).length > 0 ? (
        <div className="offer-content">
          <p className="section-caption">{t('publicTerms')}</p>
          <TermsList terms={currentPublicTerms} locale={locale} currency={currency} />
        </div>
      ) : (
        <div className="panel-empty offer-empty">
          <span className="empty-offer-shape" aria-hidden="true" />
          <p>{t('noOffer')}</p>
        </div>
      )}
      <FinancialSummary summary={financialSummary} language={language} currency={currency} />
    </aside>
  )
}
