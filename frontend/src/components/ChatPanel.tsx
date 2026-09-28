import { AlertTriangle, AudioLines, Bot, History, LoaderCircle, Mic, MicOff, RotateCcw, Send, Sparkles, Square, UserRound, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { actionLabel, translate } from '../i18n'
import type { Clarification, Observation, PendingConfirmation, PendingOfferPublication, SessionLanguage, TimelineMessage, TrainingRewindStatus, UiLanguage } from '../types'
import { ProtocolNotice } from './ProtocolNotice'
import { RoleBriefContent } from './RoleBriefContent'
import { useSpeechRecognition, useSpeechSynthesis } from './useWebSpeech'

interface ChatPanelProps {
  language: UiLanguage
  sessionLanguage: SessionLanguage
  messages: TimelineMessage[]
  roleBrief?: Observation['role_brief']
  contextItems?: Observation['context']
  scenarioTitle?: string
  ownParticipantId: string
  ownRoleId: string
  isMyTurn: boolean
  /** A message is being sent (or a failed attempt still holds the composer). */
  busy: boolean
  /** Another mutation (a hint request) is in flight, so the composer waits without a "sending" label. */
  locked?: boolean
  /** The service is still preparing the counterpart reply; the same message is retried automatically. */
  waiting?: boolean
  terminal: boolean
  currency?: string
  clarification?: Clarification
  confirmation?: PendingConfirmation
  publication?: PendingOfferPublication
  error?: string
  /** Text of the attempt that failed; it returns to the composer when the attempt is discarded. */
  failedText?: string
  currentRevision?: number
  rewind?: TrainingRewindStatus
  rewindingRevision?: number
  assisting?: boolean
  onSend: (message: string) => void
  onRewind?: (revision: number) => void
  onAnswerForMe?: () => void
  onRetry?: () => void
  onDiscard?: () => void
}

function isOwnMessage(message: TimelineMessage, ownParticipantId: string, ownRoleId: string): boolean {
  if (message.participantId && message.participantId === ownParticipantId) return true
  const normalizedRole = message.role.toLowerCase()
  return normalizedRole === ownRoleId.toLowerCase()
    || normalizedRole === 'human'
    || normalizedRole === 'player'
    || normalizedRole === `participant_${ownRoleId.toLowerCase()}`
}

function messageTime(timestamp: string | undefined, locale: string): string | undefined {
  if (!timestamp) return undefined
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return undefined
  return new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit' }).format(date)
}

export function ChatPanel({
  language,
  sessionLanguage,
  messages,
  roleBrief,
  contextItems,
  scenarioTitle,
  ownParticipantId,
  ownRoleId,
  isMyTurn,
  busy,
  locked = false,
  waiting = false,
  terminal,
  currency,
  clarification,
  confirmation,
  publication,
  error,
  failedText,
  currentRevision,
  rewind,
  rewindingRevision,
  assisting = false,
  onSend,
  onRewind,
  onAnswerForMe,
  onRetry,
  onDiscard,
}: ChatPanelProps) {
  const t = (key: string) => translate(language, key)
  const [draft, setDraft] = useState('')
  const [confirmingExit, setConfirmingExit] = useState(false)
  const timelineRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const wasActive = useRef(false)
  const locale = language === 'ru' ? 'ru-RU' : 'en-US'
  const activity = busy || locked
  const inputDisabled = !isMyTurn || activity
  const eligibleRevisions = useMemo(
    () => new Set(rewind?.eligible_source_revisions ?? []),
    [rewind?.eligible_source_revisions],
  )

  const onTranscript = useCallback((text: string) => setDraft(text), [])
  const recognition = useSpeechRecognition(sessionLanguage, onTranscript)
  const synthesis = useSpeechSynthesis(sessionLanguage)

  const latestCounterpart = useMemo(
    () => [...messages].reverse().find((message) => !isOwnMessage(message, ownParticipantId, ownRoleId)),
    [messages, ownParticipantId, ownRoleId],
  )

  useEffect(() => {
    const timeline = timelineRef.current
    // Keep the opening brief in view until the player starts the conversation.
    if ((roleBrief || contextItems?.length) && !messages.some((message) => isOwnMessage(message, ownParticipantId, ownRoleId))) return
    if (timeline) timeline.scrollTop = timeline.scrollHeight
  }, [messages, clarification, confirmation, publication, roleBrief, contextItems, ownParticipantId, ownRoleId])

  // Return focus to the composer after a send or hint request completes.
  useEffect(() => {
    if (wasActive.current && !activity && !terminal && isMyTurn) textareaRef.current?.focus()
    wasActive.current = activity
  }, [activity, isMyTurn, terminal])

  const submit = () => {
    const value = draft.trim()
    if (!value || inputDisabled || terminal) return
    onSend(value)
    setDraft('')
  }

  const discard = () => {
    onDiscard?.()
    if (failedText && !draft.trim()) setDraft(failedText)
  }

  const confirmText = publication
    ? sessionLanguage === 'ru' ? 'Подтверждаю окончательное предложение' : 'I confirm the final offer'
    : sessionLanguage === 'ru' ? 'Подтверждаю принятие полного предложения без дополнительных условий.' : 'I confirm acceptance of the complete offer without additional conditions.'
  const cancelText = publication
    ? sessionLanguage === 'ru' ? 'Отменяю подтверждение' : 'I cancel confirmation'
    : sessionLanguage === 'ru' ? 'Не подтверждаю принятие предложения.' : 'I do not confirm acceptance of the offer.'
  const exitText = sessionLanguage === 'ru' ? 'Прекращаю переговоры.' : 'I walk away.'

  return (
    <section className="chat-panel panel-card" aria-labelledby="conversation-title">
      <header className="chat-heading">
        <div>
          <p className="panel-kicker">{t('liveKicker')}</p>
          <h2 id="conversation-title">{t('conversation')}</h2>
        </div>
        <div className="chat-heading-actions">
          {latestCounterpart && synthesis.supported && (
            <button
              className={synthesis.speaking ? 'icon-button speech-button active' : 'icon-button speech-button'}
              type="button"
              onClick={() => synthesis.speak(latestCounterpart.text)}
              aria-label={synthesis.speaking ? t('stopReading') : t('readLastReply')}
              title={synthesis.speaking ? t('stopReading') : t('readLastReply')}
            >
              {synthesis.speaking ? <Square size={15} aria-hidden="true" /> : <AudioLines size={17} aria-hidden="true" />}
            </button>
          )}
          <span className={isMyTurn && !terminal ? 'turn-pill active' : 'turn-pill'}>
            <span aria-hidden="true" />
            {terminal ? t('terminalTitle') : isMyTurn ? t('yourTurn') : t('counterpartTurn')}
          </span>
        </div>
      </header>

      <div className="chat-timeline" ref={timelineRef} aria-live="polite">
        {(roleBrief || Boolean(contextItems?.length)) && (
          <article className="chat-brief" aria-label={t('yourBrief')}>
            <header className="chat-brief-heading">
              <h3>{t('yourBrief')}</h3>
              <span>{t('briefPrivate')}</span>
            </header>
            {scenarioTitle && <p className="chat-brief-scenario">{scenarioTitle}</p>}
            <RoleBriefContent language={language} brief={roleBrief} currency={currency} contextItems={contextItems} />
          </article>
        )}
        {messages.length === 0 ? (
          <div className="chat-empty">
            <span className="chat-empty-mark"><Bot size={26} aria-hidden="true" /></span>
            <p>{t('conversationEmpty')}</p>
          </div>
        ) : messages.map((message) => {
          const own = isOwnMessage(message, ownParticipantId, ownRoleId)
          const system = message.role.toLowerCase() === 'system'
          const label = system ? t('system') : own ? t('you') : t('counterpart')
          const rewindEligible = !own
            && !system
            && message.revision !== undefined
            && currentRevision !== undefined
            && message.revision < currentRevision
            && eligibleRevisions.has(message.revision)
          return (
            <article
              className={`chat-message ${own ? 'own' : 'counterpart'} ${system ? 'system-message' : ''} ${message.pending ? 'pending' : ''} ${message.failed ? 'failed' : ''}`}
              key={message.id}
            >
              <span className="message-avatar" aria-hidden="true">
                {system ? <Bot size={16} aria-hidden="true" /> : own ? <UserRound size={16} aria-hidden="true" /> : <Bot size={16} aria-hidden="true" />}
              </span>
              <div className="message-stack">
                <div className="message-meta">
                  <strong>{label}</strong>
                  {message.action && <span>{actionLabel(language, message.action)}</span>}
                  {message.failed && (
                    <span className="message-failed-flag">
                      <AlertTriangle size={12} aria-hidden="true" /> {t('messageFailed')}
                    </span>
                  )}
                  {messageTime(message.timestamp, locale) && <time>{messageTime(message.timestamp, locale)}</time>}
                </div>
                <div className="message-bubble">
                  <p>{message.text}</p>
                  {message.pending && <LoaderCircle className="spin message-spinner" size={14} aria-hidden="true" />}
                </div>
                {rewindEligible && (
                  <button
                    className="message-rewind-button"
                    type="button"
                    onClick={() => onRewind?.(message.revision as number)}
                    disabled={activity || !rewind?.available || !onRewind}
                    title={`${t('rewindRemaining')}: ${rewind?.remaining ?? 0}`}
                  >
                    {rewindingRevision === message.revision
                      ? <LoaderCircle className="spin" size={13} aria-hidden="true" />
                      : <History size={13} aria-hidden="true" />}
                    <span>{rewind?.remaining === 0
                      ? t('rewindExhausted')
                      : rewindingRevision === message.revision
                        ? t('rewinding')
                        : t('rewindHere')}</span>
                    <b aria-label={`${t('rewindRemaining')}: ${rewind?.remaining ?? 0}`}>{rewind?.remaining ?? 0}</b>
                  </button>
                )}
              </div>
            </article>
          )
        })}
      </div>

      <div className="chat-controls">
        <ProtocolNotice
          language={language}
          clarification={clarification}
          confirmation={confirmation}
          publication={publication}
          currency={currency}
          busy={inputDisabled || terminal}
          onConfirm={() => onSend(confirmText)}
          onCancel={() => onSend(cancelText)}
        />

        {error && (
          <div className="chat-error" role="alert">
            <AlertTriangle size={18} aria-hidden="true" />
            <span><strong>{t('apiError')}</strong>{error}</span>
            {onRetry && <button type="button" onClick={onRetry}><RotateCcw size={14} aria-hidden="true" /> {t('retry')}</button>}
            {onDiscard && <button type="button" onClick={discard}><X size={14} aria-hidden="true" /> {t('discardAttempt')}</button>}
          </div>
        )}

        {waiting && !error && (
          <div className="chat-notice" role="status">
            <LoaderCircle className="spin" size={16} aria-hidden="true" />
            <span>{t('waitingForCounterpart')}</span>
          </div>
        )}

        {!terminal && (
          <div className={recognition.listening ? 'composer listening' : 'composer'}>
            <textarea
              ref={textareaRef}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  submit()
                }
              }}
              rows={2}
              placeholder={recognition.listening ? t('listening') : isMyTurn ? t('messagePlaceholder') : t('counterpartTurn')}
              disabled={inputDisabled}
              aria-label={t('messagePlaceholder')}
            />
            <div className="composer-footer">
              <div className="composer-tools">
                {recognition.supported && (
                  <button
                    className={recognition.listening ? 'icon-button mic-button active' : 'icon-button mic-button'}
                    type="button"
                    onClick={recognition.toggle}
                    disabled={inputDisabled}
                    aria-label={recognition.listening ? t('stopDictation') : t('startDictation')}
                    title={recognition.listening ? t('stopDictation') : t('startDictation')}
                  >
                    {recognition.listening ? <MicOff size={18} aria-hidden="true" /> : <Mic size={18} aria-hidden="true" />}
                  </button>
                )}
                {onAnswerForMe && (
                  <button
                    className="assist-reply-button"
                    type="button"
                    onClick={onAnswerForMe}
                    disabled={inputDisabled}
                  >
                    {assisting
                      ? <LoaderCircle className="spin" size={15} aria-hidden="true" />
                      : <Sparkles size={15} aria-hidden="true" />}
                    <span>{assisting ? t('answeringForMe') : t('answerForMe')}</span>
                  </button>
                )}
                <small>{recognition.listening ? t('listening') : t('composerHint')}</small>
              </div>
              <button
                className="send-button"
                type="button"
                onClick={submit}
                disabled={!draft.trim() || inputDisabled}
                aria-label={busy ? t('sending') : t('send')}
              >
                {busy ? <LoaderCircle className="spin" size={18} aria-hidden="true" /> : <Send size={18} aria-hidden="true" />}
                <span>{busy ? t('sending') : t('send')}</span>
              </button>
            </div>
            <div className="exit-controls">
              {confirmingExit ? (
                <div className="exit-confirmation" role="alertdialog" aria-label={t('endNegotiationConfirm')}>
                  <span>{t('endNegotiationConfirm')}</span>
                  <button type="button" className="button button-secondary" onClick={() => setConfirmingExit(false)} disabled={inputDisabled}>
                    {t('keepNegotiating')}
                  </button>
                  <button type="button" className="button button-danger" onClick={() => { setConfirmingExit(false); onSend(exitText) }} disabled={inputDisabled}>
                    {t('endNegotiation')}
                  </button>
                </div>
              ) : (
                <button type="button" className="end-negotiation-button" onClick={() => setConfirmingExit(true)} disabled={inputDisabled}>
                  {t('endNegotiation')}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </section>
  )
}
