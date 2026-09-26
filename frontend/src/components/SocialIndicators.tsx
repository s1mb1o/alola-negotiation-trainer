import { Activity } from 'lucide-react'
import type { CSSProperties } from 'react'
import type { TrainingSocialState, UiLanguage } from '../types'

interface SocialIndicatorsProps {
  language: UiLanguage
  state?: TrainingSocialState
}

const AXES = ['rapport', 'credibility', 'tension', 'patience'] as const

const LABELS = {
  ru: {
    kicker: 'ДИНАМИКА',
    title: 'Состояние контакта',
    note: 'Число — текущее значение. Δ — изменение после вашей последней реплики.',
    rapport: 'Контакт',
    credibility: 'Доверие к словам',
    tension: 'Напряжение',
    patience: 'Терпение',
    current: 'текущее значение',
    change: 'изменение',
  },
  en: {
    kicker: 'DYNAMICS',
    title: 'Counterpart state',
    note: 'The number is the current value. Δ is the change after your latest message.',
    rapport: 'Rapport',
    credibility: 'Credibility',
    tension: 'Tension',
    patience: 'Patience',
    current: 'current value',
    change: 'change',
  },
} as const

function signed(value: number) {
  if (value > 0) return `+${value}`
  if (value < 0) return `−${Math.abs(value)}`
  return '0'
}

function direction(axis: typeof AXES[number], value: number) {
  if (value === 0) return 'neutral'
  const beneficial = axis === 'tension' ? value < 0 : value > 0
  return beneficial ? 'beneficial' : 'adverse'
}

export function SocialIndicators({ language, state }: SocialIndicatorsProps) {
  if (!state) return null
  const copy = LABELS[language]

  return (
    <section className="panel-card social-indicators-panel" aria-labelledby="social-indicators-title">
      <div className="panel-heading">
        <span className="panel-icon social-indicators-icon"><Activity size={19} aria-hidden="true" /></span>
        <div>
          <div className="panel-kicker">{copy.kicker}</div>
          <h2 id="social-indicators-title">{copy.title}</h2>
        </div>
      </div>
      <div className="social-indicators-body">
        <div className="social-axis-list">
          {AXES.map(axis => {
            const value = Math.max(0, Math.min(100, state.values[axis]))
            const delta = state.delta[axis]
            const meterStyle = { '--axis-position': `${Math.max(2, Math.min(98, value))}%` } as CSSProperties
            return (
              <div className="social-axis" key={axis}>
                <div className="social-axis-copy">
                  <span>{copy[axis]}</span>
                  <span className="social-axis-values">
                    <output
                      className="social-axis-current"
                      aria-label={`${copy[axis]}: ${copy.current} ${value}`}
                    >
                      {value}
                    </output>
                    <output
                      className={`social-axis-delta social-axis-delta-${direction(axis, delta)}`}
                      aria-label={`${copy[axis]}: ${copy.change} ${signed(delta)}`}
                    >
                      Δ {signed(delta)}
                    </output>
                  </span>
                </div>
                <div
                  className="social-axis-meter"
                  role="meter"
                  aria-label={copy[axis]}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={value}
                  style={meterStyle}
                >
                  {Array.from({ length: 10 }, (_, index) => (
                    <span className="social-axis-segment" key={index} aria-hidden="true" />
                  ))}
                  <span className="social-axis-marker" aria-hidden="true">+</span>
                </div>
              </div>
            )
          })}
        </div>
        <p className="social-indicators-note">{copy.note}</p>
      </div>
    </section>
  )
}
