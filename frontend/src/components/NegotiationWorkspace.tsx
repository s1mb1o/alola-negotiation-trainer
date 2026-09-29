import { CheckCircle2, CircleDot, Copy, KeyRound, Layers3, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { identifierLabel, translate } from '../i18n'
import type { SessionEnvelope, SessionReview, TimelineMessage, UiLanguage } from '../types'
import { isTerminalStatus } from '../utils'
import { PROVIDER_FEATURES_ENABLED } from '../features'
import { ChatPanel } from './ChatPanel'
import { AgreementDialog } from './AgreementDialog'
import { ContextPanel } from './ContextPanel'
import { OfferPanel } from './OfferPanel'
import { ReviewPanel } from './ReviewPanel'
import { SocialIndicators } from './SocialIndicators'
import { TokenDialog } from './TokenDialog'
import { TermsList } from './TermsList'
import type { TrainingReviewActions } from './TrainingReviewPanel'

interface NegotiationWorkspaceProps extends TrainingReviewActions {
  language: UiLanguage
  session: SessionEnvelope
  messages: TimelineMessage[]
  token: string
  ownParticipantId: string
  ownRoleId: string
  scenarioTitle: string
  hintsEnabled: boolean
  /** A message is in flight or a failed attempt still holds the composer. */
  busy: boolean
  /** A hint request is in flight; the composer waits for it. */
  locked?: boolean
  /** The counterpart reply is still being prepared and the message is retried automatically. */
  waitingForCounterpart?: boolean
  requestingHint: boolean
  assisting?: boolean
  rewindingRevision?: number
  error?: string
  failedMessageText?: string
  review?: SessionReview
  reviewLoading: boolean
  reviewError?: string
  onSend: (message: string) => void
  onRewind?: (revision: number) => void
  onAnswerForMe?: () => void
  onRequestHint: () => void
  onTokenChange: (token: string) => void
  onRetryMessage?: () => void
  onDiscardMessage?: () => void
  onRetryReview: () => void
  onNewSession: () => void
}

export function NegotiationWorkspace({
  language,
  session,
  messages,
  token,
  ownParticipantId,
  ownRoleId,
  scenarioTitle,
  hintsEnabled,
  busy,
  locked = false,
  waitingForCounterpart = false,
  requestingHint,
  assisting = false,
  rewindingRevision,
  error,
  failedMessageText,
  review,
  reviewLoading,
  reviewError,
  onSend,
  onRewind,
  onAnswerForMe,
  onRequestHint,
  onTokenChange,
  onRetryMessage,
  onDiscardMessage,
  onRetryReview,
  onNewSession,
  providerFeatures = PROVIDER_FEATURES_ENABLED,
  ...trainingActions
}: NegotiationWorkspaceProps) {
  const t = (key: string) => translate(language, key)
  const [accessOpen, setAccessOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [agreementViews, setAgreementViews] = useState<Record<string, 'chat' | 'review'>>({})
  const terminal = isTerminalStatus(session.status)
  const agreement = session.status === 'agreement_reached'
  const agreementKey = `negotiation.agreement-view.${session.session_id}`
  let storedView: string | null = null
  try { storedView = sessionStorage.getItem(agreementKey) } catch { /* Storage can be disabled. */ }
  const agreementView = agreementViews[session.session_id] ?? storedView
  const showReview = terminal && (!agreement || agreementView === 'review')
  const setAgreementView = (view: 'chat' | 'review') => {
    setAgreementViews((current) => ({ ...current, [session.session_id]: view }))
    try { sessionStorage.setItem(agreementKey, view) } catch { /* Memory state remains sufficient for this mount. */ }
  }
  const counterpartAccepted = session.committed_actions?.some((action) => action.action === 'accept'
    && !!action.participant_id && action.participant_id !== ownParticipantId)
    || messages.some((message) => message.action === 'accept'
      && !!message.participantId && message.participantId !== ownParticipantId)
  const normalizedNextActor = session.next_actor?.toLowerCase() ?? ''
  const isMyTurn = !session.next_actor
    || normalizedNextActor === ownParticipantId.toLowerCase()
    || normalizedNextActor === ownRoleId.toLowerCase()
    || normalizedNextActor === `participant_${ownRoleId.toLowerCase()}`
  // The next actor is labelled by its role ("Поставщик"/"Supplier"), never by a raw participant identifier.
  const nextActorLabel = identifierLabel(language, session.next_actor ?? '')
  const accessLabel = token ? t('connected') : t('manageAccess')

  const copyId = async () => {
    await navigator.clipboard?.writeText(session.session_id)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1400)
  }

  return (
    <main className={terminal ? 'workspace terminal-workspace' : 'workspace'}>
      <section className="session-strip" aria-label={t('session')}>
        <div className="session-identity">
          <span className="session-scenario-mark"><Layers3 size={19} aria-hidden="true" /></span>
          <div>
            <strong>{scenarioTitle}</strong>
            <button
              type="button"
              onClick={copyId}
              title={t('copySessionId')}
              aria-label={`${t('copySessionId')}: ${session.session_id}`}
            >
              <span>{session.session_id}</span>
              {copied ? <CheckCircle2 size={13} aria-hidden="true" /> : <Copy size={13} aria-hidden="true" />}
            </button>
          </div>
        </div>

        <div className="session-facts">
          <div className="status-fact">
            <small>{t('statusKicker')}</small>
            <span className={`status-badge status-${session.status}`}>
              <CircleDot size={13} aria-hidden="true" /> {t(session.status)}
            </span>
          </div>
          {!terminal && (
            <div>
              <small>{t('nextActor').toUpperCase()}</small>
              <strong className={isMyTurn ? 'your-turn-text' : ''}>{isMyTurn ? t('yourTurn') : nextActorLabel}</strong>
            </div>
          )}
          <div>
            <small>{t('round').toUpperCase()}</small>
            <strong>{session.round ?? '—'}</strong>
          </div>
          <div>
            <small>{t('revision').toUpperCase()}</small>
            <strong>r{session.revision}</strong>
          </div>
          <button className="access-button" type="button" onClick={() => setAccessOpen(true)} aria-label={accessLabel}>
            {token ? <ShieldCheck size={16} aria-hidden="true" /> : <KeyRound size={16} aria-hidden="true" />}
            <span>{accessLabel}</span>
          </button>
        </div>
      </section>

      {agreement && !showReview && (
        <section className="panel-card agreement-notice">
          <div><h2>{t('agreement_reached')}</h2><p>{t('agreementDialogLead')}</p></div>
          <button data-open-agreement-review className="button button-primary" type="button"
            onClick={() => setAgreementView('review')}>{t('openAnalysis')}</button>
        </section>
      )}

      {showReview ? (
        <div className="terminal-layout">
          <ReviewPanel
            {...trainingActions}
            providerFeatures={providerFeatures}
            language={language}
            status={session.status}
            review={review}
            loading={reviewLoading}
            error={reviewError}
            onRetry={onRetryReview}
            onNewSession={onNewSession}
          />
          {session.status === 'agreement_reached' && session.negotiation_contract_version === 'supply-package-v1' && session.observation.current_public_terms && (
            <section className="panel-card agreement-package">
              <h2>{t('agreementPackage')}</h2>
              <TermsList terms={session.observation.current_public_terms} locale={language === 'ru' ? 'ru-RU' : 'en-US'} currency={session.observation.currency} />
            </section>
          )}
          <details className="terminal-transcript panel-card">
            <summary>{t('conversation')} <span>{messages.length}</span></summary>
            <ChatPanel
              key={session.session_id}
              language={language}
              sessionLanguage={session.language ?? 'ru'}
              messages={messages}
              roleBrief={session.observation.role_brief}
              contextItems={session.observation.context}
              scenarioTitle={scenarioTitle}
              currency={session.observation.currency}
              ownParticipantId={ownParticipantId}
              ownRoleId={ownRoleId}
              isMyTurn={false}
              busy={false}
              terminal
              onSend={onSend}
            />
          </details>
        </div>
      ) : (
        <div className="workspace-grid">
          <ChatPanel
            key={session.session_id}
            language={language}
            sessionLanguage={session.language ?? 'ru'}
            messages={messages}
            roleBrief={session.observation.role_brief}
            contextItems={session.observation.context}
            scenarioTitle={scenarioTitle}
            ownParticipantId={ownParticipantId}
            ownRoleId={ownRoleId}
            isMyTurn={!terminal && isMyTurn}
            busy={busy}
            locked={locked}
            waiting={waitingForCounterpart}
            terminal={terminal}
            currency={session.observation.currency}
            clarification={terminal ? undefined : session.clarification ?? undefined}
            confirmation={terminal ? undefined : session.pending_confirmation ?? undefined}
            publication={terminal ? undefined : session.pending_offer_publication ?? undefined}
            error={error}
            failedText={failedMessageText}
            currentRevision={session.revision}
            rewind={session.observation.training?.rewind}
            rewindingRevision={rewindingRevision}
            assisting={assisting}
            onSend={onSend}
            onRewind={onRewind}
            onAnswerForMe={onAnswerForMe}
            onRetry={onRetryMessage}
            onDiscard={onDiscardMessage}
          />
          <div className="workspace-sidebar">
            <OfferPanel
              language={language}
              offers={session.observation.active_offers ?? []}
              preliminaryProposals={session.observation.preliminary_proposals}
              financialSummary={session.observation.financial_summary}
              currentPublicTerms={session.observation.current_public_terms}
              currency={session.observation.currency}
            />
            <ContextPanel
              language={language}
              observation={session.observation}
              hintsEnabled={hintsEnabled}
              requestingHint={requestingHint}
              busy={terminal || busy || locked || assisting || rewindingRevision !== undefined}
              onRequestHint={onRequestHint}
            />
            {providerFeatures && (
              <SocialIndicators language={language} state={session.observation.training?.social_state} />
            )}
          </div>
        </div>
      )}

      {agreement && !agreementView && (
        <AgreementDialog key={session.session_id} language={language} counterpartAccepted={!!counterpartAccepted}
          onClose={() => setAgreementView('chat')} onReview={() => setAgreementView('review')} />
      )}

      <TokenDialog
        open={accessOpen}
        language={language}
        token={token}
        sessionId={session.session_id}
        onClose={() => setAccessOpen(false)}
        onSave={onTokenChange}
      />
    </main>
  )
}
