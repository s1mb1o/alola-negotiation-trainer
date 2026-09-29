import { CheckCircle2, X } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { translate } from '../i18n'
import type { UiLanguage } from '../types'

interface AgreementDialogProps {
  language: UiLanguage
  counterpartAccepted: boolean
  onClose: () => void
  onReview: () => void
}

export function AgreementDialog({ language, counterpartAccepted, onClose, onReview }: AgreementDialogProps) {
  const t = (key: string) => translate(language, key)
  const dialogRef = useRef<HTMLElement>(null)
  const closeRef = useRef(onClose)
  closeRef.current = onClose

  useEffect(() => {
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const dialog = dialogRef.current
    dialog?.focus()
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault()
        closeRef.current()
      }
      if (event.key === 'Tab' && dialog) {
        const buttons = [...dialog.querySelectorAll<HTMLButtonElement>('button')]
        const first = buttons[0]
        const last = buttons[buttons.length - 1]
        if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) {
          event.preventDefault()
          last?.focus()
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault()
          first?.focus()
        }
      }
    }
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('keydown', handleKey)
      if (previous?.isConnected && previous !== document.body) previous.focus()
      else document.querySelector<HTMLButtonElement>('[data-open-agreement-review]')?.focus()
    }
  }, [])

  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section ref={dialogRef} className="dialog-card agreement-dialog" role="dialog" aria-modal="true"
        aria-labelledby="agreement-dialog-title" aria-describedby="agreement-dialog-lead" tabIndex={-1}>
        <button className="icon-button dialog-close" type="button" onClick={onClose} aria-label={t('close')}>
          <X size={19} aria-hidden="true" />
        </button>
        <span className="dialog-icon"><CheckCircle2 size={22} aria-hidden="true" /></span>
        <h2 id="agreement-dialog-title">{t(counterpartAccepted ? 'counterpartAccepted' : 'agreement_reached')}</h2>
        <p id="agreement-dialog-lead">{t('agreementDialogLead')}</p>
        <div className="dialog-actions">
          <button className="button button-secondary" type="button" onClick={onClose}>{t('viewAgreement')}</button>
          <button className="button button-primary" type="button" onClick={onReview}>{t('openAnalysis')}</button>
        </div>
      </section>
    </div>
  )
}
