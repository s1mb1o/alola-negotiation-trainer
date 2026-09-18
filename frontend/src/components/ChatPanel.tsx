import { AlertTriangle, AudioLines, Bot, LoaderCircle, Mic, MicOff, RotateCcw, Send, Square, UserRound, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { actionLabel, translate } from '../i18n'
import type { Clarification, PendingConfirmation, PendingOfferPublication, SessionLanguage, TimelineMessage, UiLanguage } from '../types'
import { ProtocolNotice } from './ProtocolNotice'
import { useSpeechRecognition, useSpeechSynthesis } from './useWebSpeech'

interface ChatPanelProps {
  language: UiLanguage
  sessionLanguage: SessionLanguage
  messages: TimelineMessage[]
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
  onSend: (message: string) => void
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
  onSend,
  onRetry,
  onDiscard,
}: ChatPanelProps) {
  const t = (key: string) => translate(language, key)
  const [draft, setDraft] = useState('')
  const timelineRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const wasActive = useRef(false)
  const locale = language === 'ru' ? 'ru-RU' : 'en-US'
  const activity = busy || locked
  const inputDisabled = !isMyTurn || activity

  const onTranscript = useCallback((text: string) => setDraft(text), [])
  const recognition = useSpeechRecognition(sessionLanguage, onTranscript)
  const synthesis = useSpeechSynthesis(sessionLanguage)

  const latestCounterpart = useMemo(
    () => [...messages].reverse().find((message) => !isOwnMessage(message, ownParticipantId, ownRoleId)),
    [messages, ownParticipantId, ownRoleId],
  )

  useEffect(() => {
    const timeline = timelineRef.current
    if (timeline) timeline.scrollTop = timeline.scrollHeight
  }, [messages, clarification, confirmation, publication])

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
        {messages.length === 0 ? (
          <div className="chat-empty">
            <span className="chat-empty-mark"><Bot size={26} aria-hidden="true" /></span>
            <p>{t('conversationEmpty')}</p>
          </div>
        ) : messages.map((message) => {
          const own = isOwnMessage(message, ownParticipantId, ownRoleId)
          const system = message.role.toLowerCase() === 'system'
          const label = system ? t('system') : own ? t('you') : t('counterpart')
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
          </div>
        )}
      </div>
    </section>
  )
}
