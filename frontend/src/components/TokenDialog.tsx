import { CheckCircle2, Copy, Eye, EyeOff, KeyRound, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { translate } from '../i18n'
import { maskToken } from '../utils'
import type { UiLanguage } from '../types'

interface TokenDialogProps {
  open: boolean
  language: UiLanguage
  token: string
  sessionId: string
  onClose: () => void
  onSave: (token: string) => void
}

export function TokenDialog({ open, language, token, sessionId, onClose, onSave }: TokenDialogProps) {
  const t = (key: string) => translate(language, key)
  const [value, setValue] = useState(token)
  const [visible, setVisible] = useState(false)
  const [copied, setCopied] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => setValue(token), [token])

  // Move focus into the dialog when it opens and close it on Escape.
  useEffect(() => {
    if (!open) return
    inputRef.current?.focus()
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        onCloseRef.current()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open])

  if (!open) return null

  const copySession = async () => {
    await navigator.clipboard?.writeText(sessionId)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section className="dialog-card" role="dialog" aria-modal="true" aria-labelledby="access-title">
        <button className="icon-button dialog-close" type="button" onClick={onClose} aria-label={t('close')}>
          <X size={19} aria-hidden="true" />
        </button>
        <span className="dialog-icon"><KeyRound size={22} aria-hidden="true" /></span>
        <h2 id="access-title">{t('manageAccess')}</h2>
        <p>{t('accessTokenHelp')}</p>

        <label className="dialog-field">
          <span>{t('accessToken')}</span>
          <span className="token-input-wrap">
            <input
              ref={inputRef}
              type={visible ? 'text' : 'password'}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              autoComplete="off"
              placeholder={maskToken(token) || t('disconnected')}
            />
            <button
              className="icon-button"
              type="button"
              onClick={() => setVisible((current) => !current)}
              aria-label={visible ? t('hideToken') : t('revealToken')}
            >
              {visible ? <EyeOff size={18} aria-hidden="true" /> : <Eye size={18} aria-hidden="true" />}
            </button>
          </span>
        </label>

        <div className="session-id-row">
          <span>
            <small>{t('session')}</small>
            <code>{sessionId}</code>
          </span>
          <button className="icon-button" type="button" onClick={copySession} aria-label={t('copySessionId')}>
            {copied ? <CheckCircle2 size={18} aria-hidden="true" /> : <Copy size={18} aria-hidden="true" />}
          </button>
        </div>

        <div className="dialog-actions">
          <button className="button button-secondary" type="button" onClick={onClose}>{t('close')}</button>
          <button
            className="button button-primary"
            type="button"
            onClick={() => {
              onSave(value.trim())
              onClose()
            }}
          >
            {t('save')}
          </button>
        </div>
      </section>
    </div>
  )
}
