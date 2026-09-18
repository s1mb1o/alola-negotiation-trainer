import { CheckCircle2, CircleDot, Copy, KeyRound, Layers3, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { identifierLabel, translate } from '../i18n'
import type { SessionEnvelope, SessionReview, TimelineMessage, UiLanguage } from '../types'
import { isTerminalStatus } from '../utils'
import { ChatPanel } from './ChatPanel'
import { ContextPanel } from './ContextPanel'
import { OfferPanel } from './OfferPanel'
import { ReviewPanel } from './ReviewPanel'
import { TokenDialog } from './TokenDialog'
import { TermsList } from './TermsList'

interface NegotiationWorkspaceProps {
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
  error?: string
  failedMessageText?: string
  review?: SessionReview
  reviewLoading: boolean
  reviewError?: string
  onSend: (message: string) => void
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
  error,
  failedMessageText,
  review,
  reviewLoading,
  reviewError,
  onSend,
  onRequestHint,
  onTokenChange,
  onRetryMessage,
  onDiscardMessage,
  onRetryReview,
  onNewSession,
}: NegotiationWorkspaceProps) {
  const t = (key: string) => translate(language, key)
  const [accessOpen, setAccessOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const terminal = isTerminalStatus(session.status)
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

      {terminal ? (
        <div className="terminal-layout">
          <ReviewPanel
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
              language={language}
              sessionLanguage={session.language ?? 'ru'}
              messages={messages}
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
          <ContextPanel
            language={language}
            observation={session.observation}
            hintsEnabled={hintsEnabled}
            requestingHint={requestingHint}
            busy={busy}
            onRequestHint={onRequestHint}
          />
          <ChatPanel
            language={language}
            sessionLanguage={session.language ?? 'ru'}
            messages={messages}
            ownParticipantId={ownParticipantId}
            ownRoleId={ownRoleId}
            isMyTurn={isMyTurn}
            busy={busy}
            locked={locked}
            waiting={waitingForCounterpart}
            terminal={false}
            currency={session.observation.currency}
            clarification={session.clarification ?? undefined}
            confirmation={session.pending_confirmation ?? undefined}
            publication={session.pending_offer_publication ?? undefined}
            error={error}
            failedText={failedMessageText}
            onSend={onSend}
            onRetry={onRetryMessage}
            onDiscard={onDiscardMessage}
          />
          <OfferPanel
            language={language}
            offers={session.observation.active_offers ?? []}
            preliminaryProposals={session.observation.preliminary_proposals}
            financialSummary={session.observation.financial_summary}
            currentPublicTerms={session.observation.current_public_terms}
            currency={session.observation.currency}
          />
        </div>
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
