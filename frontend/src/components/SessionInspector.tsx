import { type FormEvent, useEffect, useMemo, useState } from 'react'
import {
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Database,
  Handshake,
  ListTree,
  LoaderCircle,
  LogOut,
  MessagesSquare,
  RefreshCw,
  Search,
  ShieldCheck,
  Users,
} from 'lucide-react'
import { ApiError, getAdminSession, listAdminSessions } from '../api'
import { identifierLabel, translate } from '../i18n'
import { DialogueQualityCard } from './DialogueQualityCard'
import { TermsList } from './TermsList'
import { FinancialSummary } from './FinancialSummary'
import type {
  AdminSessionDetail,
  AdminSessionEvent,
  AdminSessionFilters,
  AdminSessionSummary,
  FinancialSummaryView,
  JsonRecord,
  UiLanguage,
} from '../types'

const ADMIN_TOKEN_KEY = 'negotiation.admin-token'
const PAGE_SIZE = 25

type InspectorTab = 'overview' | 'messages' | 'events' | 'offers' | 'review'

interface SessionInspectorProps {
  language: UiLanguage
}

function formatDate(value: string, language: UiLanguage): string {
  const date = new Date(value.includes('T') ? value : `${value.replace(' ', 'T')}Z`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat(language === 'ru' ? 'ru-RU' : 'en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function errorText(error: unknown, language: UiLanguage): string {
  if (error instanceof ApiError) {
    const code = error.payload.error ?? error.payload.code
    if (code === 'administrator_unauthorized') return translate(language, 'inspectorUnauthorized')
    if (code === 'administrative_access_disabled') return translate(language, 'inspectorDisabled')
  }
  return translate(language, 'inspectorLoadError')
}

function JsonPayload({ value }: { value: JsonRecord }) {
  return <pre className="inspector-json">{JSON.stringify(value, null, 2)}</pre>
}

function preliminaryFromEvent(event: AdminSessionEvent): JsonRecord | undefined {
  const nested = event.payload.proposal
  const proposal = nested && typeof nested === 'object' && !Array.isArray(nested) ? nested as JsonRecord : event.payload
  return typeof proposal.proposal_id === 'string' && typeof proposal.proposal_revision === 'number'
    && proposal.terms && typeof proposal.terms === 'object' && !Array.isArray(proposal.terms)
    ? proposal : undefined
}

function PreliminaryEventCard({ event, language, currency }: { event: AdminSessionEvent; language: UiLanguage; currency?: string | null }) {
  const proposal = preliminaryFromEvent(event)
  if (!proposal) return null
  const sources = Array.isArray(proposal.source_event_ids) ? proposal.source_event_ids.filter((id): id is string => typeof id === 'string') : []
  return <article className="inspector-preliminary-card">
    <header>
      <div><strong>{translate(language, 'preliminaryProposal')} · {translate(language, 'revision')} {String(proposal.proposal_revision)}</strong><code>{String(proposal.proposal_id)}</code></div>
      <span>{translate(language, 'preliminaryNonBinding')}</span>
    </header>
    <TermsList terms={proposal.terms as JsonRecord} locale={language === 'ru' ? 'ru-RU' : 'en-US'} currency={currency ?? undefined} />
    <footer><code>{event.event_id}</code> · r{event.session_revision}</footer>
    {sources.length > 0 && <details className="proposal-sources"><summary>{translate(language, 'proposalSources')}</summary><ul>{sources.map((id) => <li key={id}><code>{id}</code></li>)}</ul></details>}
  </article>
}

function StatusBadge({ session, language }: { session: AdminSessionSummary; language: UiLanguage }) {
  return (
    <span className={`inspector-status status-${session.status}`}>
      {translate(language, session.status, session.status)}
    </span>
  )
}

function SessionListItem({
  session,
  language,
  selected,
  onSelect,
}: {
  session: AdminSessionSummary
  language: UiLanguage
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      className={selected ? 'inspector-session-item selected' : 'inspector-session-item'}
      onClick={onSelect}
      aria-pressed={selected}
      aria-label={`${session.scenario_title} · ${session.session_id} · ${translate(language, session.status, session.status)}`}
    >
      <span className="inspector-session-title-row">
        <strong>{session.scenario_title}</strong>
        <StatusBadge session={session} language={language} />
      </span>
      <code>{session.session_id}</code>
      <span className="inspector-session-meta">
        <span>{session.language.toUpperCase()}</span>
        <span>{translate(language, `inspectorMode_${session.run_mode}`, session.run_mode)}</span>
        <span>r{session.revision}</span>
        <span>{formatDate(session.updated_at, language)}</span>
      </span>
    </button>
  )
}

function OverviewTab({ detail, language }: { detail: AdminSessionDetail; language: UiLanguage }) {
  return (
    <div className="inspector-tab-panel">
      <dl className="inspector-facts">
        <div><dt>{translate(language, 'scenarioLabel')}</dt><dd>{detail.scenario_title}</dd></div>
        <div><dt>{translate(language, 'inspectorScenarioVersion')}</dt><dd>{detail.scenario_id}@{detail.scenario_version}</dd></div>
        <div><dt>{translate(language, 'result')}</dt><dd><StatusBadge session={detail} language={language} /></dd></div>
        <div><dt>{translate(language, 'revision')}</dt><dd>{detail.revision}</dd></div>
        <div><dt>{translate(language, 'round')}</dt><dd>{detail.round}</dd></div>
        <div><dt>{translate(language, 'inspectorTurns')}</dt><dd>{detail.substantive_turn_count}</dd></div>
        <div><dt>{translate(language, 'language')}</dt><dd>{detail.language.toUpperCase()}</dd></div>
        <div><dt>{translate(language, 'difficulty')}</dt><dd>{identifierLabel(language, detail.difficulty)}</dd></div>
        <div><dt>{translate(language, 'inspectorRunMode')}</dt><dd>{translate(language, `inspectorMode_${detail.run_mode}`)}</dd></div>
        <div><dt>{translate(language, 'nextActor')}</dt><dd><code>{detail.next_actor ?? '—'}</code></dd></div>
        <div><dt>{translate(language, 'inspectorCreated')}</dt><dd>{formatDate(detail.created_at, language)}</dd></div>
        <div><dt>{translate(language, 'inspectorUpdated')}</dt><dd>{formatDate(detail.updated_at, language)}</dd></div>
      </dl>

      <DialogueQualityCard quality={detail.dialogue_quality} language={language} />

      <section className="inspector-subsection">
        <div className="inspector-subsection-title"><Users size={18} aria-hidden="true" /><h3>{translate(language, 'inspectorParticipants')}</h3></div>
        <div className="inspector-participant-grid">
          {detail.participants.map((participant) => (
            <article key={participant.participant_id} className="inspector-participant-card">
              <header>
                <strong><code>{participant.role}</code></strong>
                <span>{translate(language, `inspectorController_${participant.controller}`, participant.controller)}</span>
              </header>
              <code>{participant.participant_id}</code>
              {(participant.provider || participant.model) && (
                <p>{[participant.provider, participant.model].filter(Boolean).join(' / ')}</p>
              )}
              {participant.prompt_version && <small>{participant.prompt_version}</small>}
            </article>
          ))}
        </div>
      </section>

      {Object.keys(detail.run_metadata).length > 0 && (
        <section className="inspector-subsection">
          <div className="inspector-subsection-title"><Database size={18} aria-hidden="true" /><h3>{translate(language, 'inspectorRunMetadata')}</h3></div>
          <JsonPayload value={detail.run_metadata as JsonRecord} />
        </section>
      )}
    </div>
  )
}

function MessagesTab({ detail, language }: { detail: AdminSessionDetail; language: UiLanguage }) {
  if (detail.messages.length === 0) return <p className="inspector-empty-panel">{translate(language, 'inspectorNoMessages')}</p>
  return (
    <ol className="inspector-timeline inspector-tab-panel">
      {detail.messages.map((message, index) => (
        <li key={`${message.session_revision}-${message.participant_id}-${index}`}>
          <header>
            <strong><code>{message.role}</code></strong>
            <span>r{message.session_revision} · {formatDate(message.created_at, language)}</span>
          </header>
          <p>{message.content}</p>
        </li>
      ))}
    </ol>
  )
}

function EventsTab({ detail, language }: { detail: AdminSessionDetail; language: UiLanguage }) {
  if (detail.events.length === 0) return <p className="inspector-empty-panel">{translate(language, 'inspectorNoEvents')}</p>
  return (
    <div className="inspector-event-list inspector-tab-panel">
      {detail.events.map((event) => (
        <details key={event.event_id}>
          <summary>
            <span><strong>{event.type}</strong><code>{event.event_id}</code></span>
            <small>r{event.session_revision} · {formatDate(event.created_at, language)}</small>
          </summary>
          {preliminaryFromEvent(event) ? <>
            <PreliminaryEventCard event={event} language={language} currency={detail.currency} />
            <details><summary>{translate(language, 'inspectorTechnicalData')}</summary><JsonPayload value={event.payload} /></details>
          </> : <JsonPayload value={event.payload} />}
        </details>
      ))}
    </div>
  )
}

function OffersTab({ detail, language }: { detail: AdminSessionDetail; language: UiLanguage }) {
  const preliminaryEvents = detail.events.filter((event) => preliminaryFromEvent(event))
  if (detail.offers.length === 0 && preliminaryEvents.length === 0) return <p className="inspector-empty-panel">{translate(language, 'inspectorNoOffers')}</p>
  return (
    <div className="inspector-offer-list inspector-tab-panel">
      {preliminaryEvents.map((event) => <PreliminaryEventCard key={event.event_id} event={event} language={language} currency={detail.currency} />)}
      {detail.offers.map((offer) => (
        <article key={`${offer.offer_id}-${offer.offer_revision}`}>
          <header>
            <div>
              <strong>{translate(language, 'inspectorOffer')} #{offer.offer_revision}</strong>
              <code>{offer.offer_id}</code>
            </div>
            <span>{offer.status}</span>
          </header>
          <TermsList terms={offer.terms} locale={language === 'ru' ? 'ru-RU' : 'en-US'} currency={detail.currency ?? undefined} />
          <footer>
            {translate(language, 'inspectorProposer')}: <code>{offer.proposer_participant_id}</code> · r{offer.created_session_revision}
          </footer>
        </article>
      ))}
    </div>
  )
}

function ReviewTab({ detail, language }: { detail: AdminSessionDetail; language: UiLanguage }) {
  if (detail.review_state === 'sealed') {
    return (
      <div className="inspector-review-state sealed inspector-tab-panel">
        <ShieldCheck size={28} aria-hidden="true" />
        <div><h3>{translate(language, 'inspectorReviewSealed')}</h3><p>{translate(language, 'inspectorReviewSealedText')}</p></div>
      </div>
    )
  }
  if (detail.review_state !== 'available' || !detail.review) {
    return (
      <div className="inspector-review-state inspector-tab-panel">
        <ClipboardList size={28} aria-hidden="true" />
        <div><h3>{translate(language, 'inspectorReviewNotReady')}</h3><p>{translate(language, 'inspectorReviewNotReadyText')}</p></div>
      </div>
    )
  }
  const outcome = typeof detail.review.outcome === 'object' && detail.review.outcome !== null
    ? detail.review.outcome as JsonRecord
    : {}
  const moments = Array.isArray(detail.review.key_moments)
    ? detail.review.key_moments.filter((item): item is JsonRecord => typeof item === 'object' && item !== null)
    : []
  const terms = typeof outcome.agreement_terms === 'object' && outcome.agreement_terms !== null
    ? outcome.agreement_terms as JsonRecord
    : undefined
  return (
    <div className="inspector-tab-panel inspector-review">
      <div className="inspector-review-summary">
        <div><small>{translate(language, 'result')}</small><strong>{translate(language, String(outcome.termination_reason ?? detail.status), String(outcome.termination_reason ?? detail.status))}</strong></div>
        <div><small>{translate(language, 'agreement')}</small><strong>{outcome.agreement === true ? translate(language, 'inspectorYes') : translate(language, 'inspectorNo')}</strong></div>
        <div><small>{translate(language, 'inspectorReviewRevision')}</small><strong>r{String(detail.review.revision ?? detail.revision)}</strong></div>
      </div>
      {terms && (
        <section className="inspector-subsection">
          <div className="inspector-subsection-title"><Handshake size={18} aria-hidden="true" /><h3>{translate(language, 'terms')}</h3></div>
          <TermsList terms={terms} locale={language === 'ru' ? 'ru-RU' : 'en-US'} currency={detail.currency ?? undefined} />
        </section>
      )}
      <FinancialSummary summary={outcome.financial_summary && typeof outcome.financial_summary === 'object'
        ? outcome.financial_summary as FinancialSummaryView : undefined} language={language} currency={detail.currency ?? undefined} />
      <section className="inspector-subsection">
        <div className="inspector-subsection-title"><ListTree size={18} aria-hidden="true" /><h3>{translate(language, 'keyMoments')}</h3></div>
        {moments.length > 0 ? (
          <div className="inspector-moments">
            {moments.map((moment, index) => (
              <article key={String(moment.event_id ?? index)}>
                <strong>{String(moment.title ?? moment.type ?? translate(language, 'inspectorMoment'))}</strong>
                {moment.summary !== undefined && moment.summary !== null && (
                  <p>{String(moment.summary)}</p>
                )}
              </article>
            ))}
          </div>
        ) : <p className="inspector-empty-panel">{translate(language, 'noKeyMoments')}</p>}
      </section>
    </div>
  )
}

function SessionDetailView({ detail, language }: { detail: AdminSessionDetail; language: UiLanguage }) {
  const [tab, setTab] = useState<InspectorTab>('overview')
  useEffect(() => setTab('overview'), [detail.session_id])
  const tabs: Array<{ id: InspectorTab; label: string; count?: number }> = [
    { id: 'overview', label: translate(language, 'inspectorOverview') },
    { id: 'messages', label: translate(language, 'inspectorMessages'), count: detail.messages.length },
    { id: 'events', label: translate(language, 'inspectorEvents'), count: detail.events.length },
    { id: 'offers', label: translate(language, 'inspectorOffers'), count: detail.offers.length + detail.events.filter((event) => preliminaryFromEvent(event)).length },
    { id: 'review', label: translate(language, 'inspectorReview') },
  ]
  return (
    <section className="inspector-detail panel-card">
      <header className="inspector-detail-heading">
        <div><p className="eyebrow">{translate(language, 'inspectorSessionDetail')}</p><h2>{detail.scenario_title}</h2><code>{detail.session_id}</code></div>
        <StatusBadge session={detail} language={language} />
      </header>
      <div className="inspector-tabs" role="tablist" aria-label={translate(language, 'inspectorSections')}>
        {tabs.map((item) => (
          <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)}>
            {item.label}{typeof item.count === 'number' && <span>{item.count}</span>}
          </button>
        ))}
      </div>
      {tab === 'overview' && <OverviewTab detail={detail} language={language} />}
      {tab === 'messages' && <MessagesTab detail={detail} language={language} />}
      {tab === 'events' && <EventsTab detail={detail} language={language} />}
      {tab === 'offers' && <OffersTab detail={detail} language={language} />}
      {tab === 'review' && <ReviewTab detail={detail} language={language} />}
    </section>
  )
}

export function SessionInspector({ language }: SessionInspectorProps) {
  const t = (key: string, fallback?: string) => translate(language, key, fallback)
  const storedToken = sessionStorage.getItem(ADMIN_TOKEN_KEY) ?? ''
  const [token, setToken] = useState(storedToken)
  const [tokenDraft, setTokenDraft] = useState(storedToken)
  const initialFilters = useMemo<AdminSessionFilters>(() => ({ limit: PAGE_SIZE, offset: 0 }), [])
  const [filterDraft, setFilterDraft] = useState<AdminSessionFilters>(initialFilters)
  const [filters, setFilters] = useState<AdminSessionFilters>(initialFilters)
  const [sessions, setSessions] = useState<AdminSessionSummary[]>([])
  const [total, setTotal] = useState(0)
  const [selectedSessionId, setSelectedSessionId] = useState<string>()
  const [detail, setDetail] = useState<AdminSessionDetail>()
  const [listLoading, setListLoading] = useState(false)
  const [detailLoading, setDetailLoading] = useState(false)
  const [error, setError] = useState<string>()
  const [refreshVersion, setRefreshVersion] = useState(0)

  useEffect(() => {
    if (!token) return
    let active = true
    setListLoading(true)
    setError(undefined)
    listAdminSessions(filters, token)
      .then((response) => {
        if (!active) return
        setSessions(response.items)
        setTotal(response.total)
        setSelectedSessionId((current) => (
          current && response.items.some((item) => item.session_id === current)
            ? current
            : response.items[0]?.session_id
        ))
        if (response.items.length === 0) setDetail(undefined)
      })
      .catch((requestError) => active && setError(errorText(requestError, language)))
      .finally(() => active && setListLoading(false))
    return () => { active = false }
  }, [filters, language, refreshVersion, token])

  useEffect(() => {
    if (!token || !selectedSessionId) return
    let active = true
    setDetailLoading(true)
    setError(undefined)
    getAdminSession(selectedSessionId, token)
      .then((response) => active && setDetail(response))
      .catch((requestError) => active && setError(errorText(requestError, language)))
      .finally(() => active && setDetailLoading(false))
    return () => { active = false }
  }, [language, refreshVersion, selectedSessionId, token])

  const connect = (event: FormEvent) => {
    event.preventDefault()
    const nextToken = tokenDraft.trim()
    if (!nextToken) return
    sessionStorage.setItem(ADMIN_TOKEN_KEY, nextToken)
    setToken(nextToken)
    setError(undefined)
  }

  const disconnect = () => {
    sessionStorage.removeItem(ADMIN_TOKEN_KEY)
    setToken('')
    setTokenDraft('')
    setSessions([])
    setDetail(undefined)
    setSelectedSessionId(undefined)
    setError(undefined)
  }

  const applyFilters = (event: FormEvent) => {
    event.preventDefault()
    setFilters({ ...filterDraft, limit: PAGE_SIZE, offset: 0 })
  }

  if (!token) {
    return (
      <main className="inspector-page inspector-access-page">
        <section className="inspector-access-card panel-card">
          <span className="inspector-access-icon"><ShieldCheck size={30} aria-hidden="true" /></span>
          <p className="eyebrow">{t('inspectorEyebrow')}</p>
          <h1>{t('inspectorAccessTitle')}</h1>
          <p>{t('inspectorAccessLead')}</p>
          <form onSubmit={connect}>
            <label htmlFor="admin-token">{t('inspectorAdminToken')}</label>
            <input id="admin-token" type="password" autoComplete="off" value={tokenDraft} onChange={(event) => setTokenDraft(event.target.value)} placeholder={t('inspectorTokenPlaceholder')} />
            <small>{t('inspectorTokenHelp')}</small>
            <button className="button button-primary" type="submit" disabled={!tokenDraft.trim()}>{t('inspectorConnect')}</button>
          </form>
        </section>
      </main>
    )
  }

  const offset = Number(filters.offset ?? 0)
  const rangeStart = total === 0 ? 0 : offset + 1
  const rangeEnd = Math.min(total, offset + PAGE_SIZE)
  return (
    <main className="inspector-page">
      <header className="inspector-hero">
        <div>
          <p className="eyebrow">{t('inspectorEyebrow')}</p>
          <h1>{t('inspectorTitle')}</h1>
          <p>{t('inspectorLead')}</p>
        </div>
        <div className="inspector-access-status">
          <span><ShieldCheck size={17} aria-hidden="true" />{t('inspectorConnected')}</span>
          <button type="button" className="button button-secondary" onClick={disconnect}><LogOut size={16} aria-hidden="true" />{t('inspectorDisconnect')}</button>
        </div>
      </header>

      <form className="inspector-filters panel-card" onSubmit={applyFilters}>
        <label><span>{t('result')}</span><select value={filterDraft.status ?? ''} onChange={(event) => setFilterDraft((current) => ({ ...current, status: event.target.value }))}>
          <option value="">{t('inspectorAllStatuses')}</option>
          {['active', 'agreement_reached', 'walked_away', 'expired', 'aborted', 'technical_failure'].map((status) => <option key={status} value={status}>{t(status, status)}</option>)}
        </select></label>
        <label><span>{t('scenarioLabel')}</span><input value={filterDraft.scenario_id ?? ''} onChange={(event) => setFilterDraft((current) => ({ ...current, scenario_id: event.target.value }))} placeholder={t('inspectorScenarioPlaceholder')} /></label>
        <label><span>{t('language')}</span><select value={filterDraft.language ?? ''} onChange={(event) => setFilterDraft((current) => ({ ...current, language: event.target.value as AdminSessionFilters['language'] }))}><option value="">{t('inspectorAllLanguages')}</option><option value="ru">RU</option><option value="en">EN</option></select></label>
        <label><span>{t('inspectorRunMode')}</span><select value={filterDraft.run_mode ?? ''} onChange={(event) => setFilterDraft((current) => ({ ...current, run_mode: event.target.value as AdminSessionFilters['run_mode'] }))}><option value="">{t('inspectorAllModes')}</option><option value="training">{t('inspectorMode_training')}</option><option value="benchmark">{t('inspectorMode_benchmark')}</option></select></label>
        <button className="button button-primary" type="submit"><Search size={16} aria-hidden="true" />{t('inspectorApply')}</button>
        <button className="button button-secondary" type="button" onClick={() => setRefreshVersion((value) => value + 1)} disabled={listLoading || detailLoading}><RefreshCw className={listLoading || detailLoading ? 'spin' : ''} size={16} aria-hidden="true" />{t('inspectorRefresh')}</button>
      </form>

      {error && <div className="inspector-error" role="alert">{error}</div>}

      <div className="inspector-workspace">
        <aside className="inspector-list panel-card">
          <header><div><Database size={18} aria-hidden="true" /><strong>{t('inspectorSessions')}</strong></div><span>{total}</span></header>
          {listLoading && sessions.length === 0 ? (
            <div className="inspector-loading"><LoaderCircle className="spin" size={22} aria-hidden="true" />{t('inspectorLoading')}</div>
          ) : sessions.length === 0 ? (
            <div className="inspector-list-empty"><Search size={25} aria-hidden="true" /><strong>{t('inspectorEmptyTitle')}</strong><p>{t('inspectorEmptyText')}</p></div>
          ) : (
            <div className="inspector-session-list">
              {sessions.map((session) => <SessionListItem key={session.session_id} session={session} language={language} selected={selectedSessionId === session.session_id} onSelect={() => setSelectedSessionId(session.session_id)} />)}
            </div>
          )}
          <footer className="inspector-pagination">
            <button type="button" aria-label={t('inspectorPrevious')} disabled={offset === 0 || listLoading} onClick={() => setFilters((current) => ({ ...current, offset: Math.max(0, offset - PAGE_SIZE) }))}><ChevronLeft size={17} aria-hidden="true" /></button>
            <span>{rangeStart}–{rangeEnd} {t('inspectorOf')} {total}</span>
            <button type="button" aria-label={t('inspectorNext')} disabled={offset + PAGE_SIZE >= total || listLoading} onClick={() => setFilters((current) => ({ ...current, offset: offset + PAGE_SIZE }))}><ChevronRight size={17} aria-hidden="true" /></button>
          </footer>
        </aside>

        {detailLoading && !detail ? (
          <section className="inspector-detail-loading panel-card"><LoaderCircle className="spin" size={26} aria-hidden="true" />{t('inspectorLoadingDetail')}</section>
        ) : detail ? (
          <SessionDetailView detail={detail} language={language} />
        ) : (
          <section className="inspector-detail-empty panel-card"><MessagesSquare size={30} aria-hidden="true" /><h2>{t('inspectorSelectTitle')}</h2><p>{t('inspectorSelectText')}</p></section>
        )}
      </div>
    </main>
  )
}
