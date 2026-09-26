import {
  Brain,
  Lightbulb,
  LoaderCircle,
  Sparkles,
  Target,
} from 'lucide-react'
import { identifierLabel, translate } from '../i18n'
import type { AssistanceView, HintView, Observation, UiLanguage } from '../types'

interface ContextPanelProps {
  language: UiLanguage
  observation: Observation
  hintsEnabled: boolean
  requestingHint: boolean
  /** Another mutation (a message) is in flight, so a hint request must wait. */
  busy?: boolean
  onRequestHint: () => void
}

function collectHints(observation: Observation): HintView[] {
  const assistance = observation.assistance as AssistanceView | null | undefined
  return [...(assistance?.hints ?? []), ...(observation.hints ?? [])]
}

export function ContextPanel({
  language,
  observation,
  hintsEnabled,
  requestingHint,
  busy = false,
  onRequestHint,
}: ContextPanelProps) {
  const t = (key: string) => translate(language, key)
  const assistance = observation.assistance as AssistanceView | null | undefined
  const hints = collectHints(observation)
  const detectedSignals = assistance?.detected_signals
  const signals = assistance?.signals
    ?? (Array.isArray(detectedSignals) ? detectedSignals : [])
  const coaching = typeof assistance?.coaching === 'string' ? assistance.coaching : undefined
  const priorities = assistance?.own_priorities ?? []
  const probableInterests = assistance?.probable_interests ?? []
  const remainingHints = typeof assistance?.remaining_hints === 'number'
    ? assistance.remaining_hints
    : observation.remaining_hints
  const hintsAvailable = assistance?.available ?? observation.hints_available

  return (
    <>
      {observation.training?.preparation?.target && <section className="panel-card context-panel">
        <header className="panel-heading"><span className="panel-icon"><Target size={18} aria-hidden="true" /></span>
          <h2>{language === 'ru' ? 'Мой план' : 'My plan'}</h2>
        </header>
        <div className="panel-body"><p>{observation.training.preparation.target}</p>
          <p className="field-note">{language === 'ru' ? 'Виден только вам.' : 'Visible only to you.'}</p>
        </div>
      </section>}

      {hintsEnabled && (
        <section className="panel-card assistance-panel" aria-labelledby="assistance-title">
          <header className="panel-heading">
            <span className="panel-icon coach-icon"><Brain size={18} aria-hidden="true" /></span>
            <div>
              <p className="panel-kicker">{t('signalsKicker')}</p>
              <h2 id="assistance-title">{t('assistance')}</h2>
            </div>
            {typeof remainingHints === 'number' && (
              <span className="hint-balance">{remainingHints}</span>
            )}
          </header>

          <div className="assistance-body">
            {coaching && (
              <article className="hint-card coaching-card">
                <span><Sparkles size={15} aria-hidden="true" /></span>
                <div><p>{coaching}</p></div>
              </article>
            )}
            {signals.length > 0 && (
              <div className="signals-block">
                <strong>{t('signals')}</strong>
                {signals.map((signal, index) => {
                  const label = typeof signal === 'string' ? signal : signal.label ?? signal.text ?? ''
                  const confidence = typeof signal === 'object' ? signal.confidence : undefined
                  return (
                    <div className="signal-row" key={`${label}-${index}`}>
                      <span className="signal-pulse" aria-hidden="true" />
                      <span>{identifierLabel(language, label)}</span>
                      {confidence !== undefined && <small>{String(confidence)}</small>}
                    </div>
                  )
                })}
              </div>
            )}
            {priorities.length > 0 && (
              <div className="signals-block">
                <strong>{t('priorities')}</strong>
                {priorities.map((priority) => (
                  <div className="signal-row" key={priority}>
                    <span className="signal-pulse" aria-hidden="true" />
                    <span>{identifierLabel(language, priority)}</span>
                  </div>
                ))}
              </div>
            )}
            {probableInterests.length > 0 && (
              <div className="signals-block">
                <strong>{t('probableInterests')}</strong>
                {probableInterests.map((interest) => (
                  <div className="signal-row" key={interest}>
                    <span className="signal-pulse" aria-hidden="true" />
                    <span>{identifierLabel(language, interest)}</span>
                  </div>
                ))}
              </div>
            )}

            <div className="hint-list">
              {hints.length > 0 ? hints.map((hint, index) => (
                <article className="hint-card" key={hint.id ?? `${hint.title}-${index}`}>
                  <span><Lightbulb size={15} aria-hidden="true" /></span>
                  <div>
                    {hint.title && <strong>{hint.title}</strong>}
                    <p>{hint.text ?? hint.message}</p>
                  </div>
                </article>
              )) : (
                <div className="panel-empty compact-empty">
                  <Sparkles size={20} aria-hidden="true" />
                  <p>{t('noHints')}</p>
                </div>
              )}
            </div>

            <button
              className="button button-coach"
              type="button"
              onClick={onRequestHint}
              disabled={requestingHint || busy || hintsAvailable === false}
            >
              {requestingHint ? <LoaderCircle className="spin" size={16} aria-hidden="true" /> : <Lightbulb size={16} aria-hidden="true" />}
              {requestingHint ? t('requestingHint') : t('requestHint')}
            </button>
          </div>
        </section>
      )}
    </>
  )
}
