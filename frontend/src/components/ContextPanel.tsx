import type { ReactNode } from 'react'
import {
  BookOpenText,
  Brain,
  Compass,
  Lightbulb,
  ListOrdered,
  LoaderCircle,
  Route,
  ShieldCheck,
  Sparkles,
  Target,
} from 'lucide-react'
import { identifierLabel, translate } from '../i18n'
import type { AssistanceView, HintView, JsonRecord, Observation, UiLanguage } from '../types'
import { formatTermValueForKey } from '../utils'

interface ContextPanelProps {
  language: UiLanguage
  observation: Observation
  hintsEnabled: boolean
  requestingHint: boolean
  /** Another mutation (a message) is in flight, so a hint request must wait. */
  busy?: boolean
  onRequestHint: () => void
}

function roleBriefContent(roleBrief: Observation['role_brief']): {
  title?: string
  summary?: string
  objectives: string[]
  context: string[]
  batna?: string
  constraints: JsonRecord
  priorities: string[]
} {
  if (typeof roleBrief === 'string') {
    return parseLegacyRoleBrief(roleBrief)
  }
  if (!roleBrief) return { objectives: [], context: [], constraints: {}, priorities: [] }
  return {
    title: roleBrief.title,
    summary: roleBrief.summary ?? roleBrief.content,
    objectives: roleBrief.objectives ?? [],
    context: Array.isArray(roleBrief.context)
      ? roleBrief.context
      : roleBrief.context ? [roleBrief.context] : [],
    batna: roleBrief.batna,
    constraints: roleBrief.constraints ?? {},
    priorities: roleBrief.priorities ?? [],
  }
}

function parseLegacyRoleBrief(roleBrief: string): {
  summary?: string
  objectives: string[]
  context: string[]
  batna?: string
  constraints: JsonRecord
  priorities: string[]
} {
  const patterns = [
    /^(?<summary>.+?)\s+Ваша цель:\s*(?<objective>.+?)\s+Ваш контекст:\s*(?<context>.+?)\s+Ваша BATNA:\s*(?<batna>.+?)\s+Ваши ограничения:\s*(?<constraints>\{.*\})\s+Ваши приоритеты по убыванию:\s*(?<priorities>[^.]+)\.?$/u,
    /^(?<summary>.+?)\s+Your (?:goal|objective):\s*(?<objective>.+?)\s+Your context:\s*(?<context>.+?)\s+Your BATNA:\s*(?<batna>.+?)\s+Your constraints:\s*(?<constraints>\{.*\})\s+Your priorities(?: in descending order)?:\s*(?<priorities>[^.]+)\.?$/iu,
  ]
  const groups = patterns.map((pattern) => pattern.exec(roleBrief)?.groups).find(Boolean)
  if (!groups) {
    return { summary: roleBrief, objectives: [], context: [], constraints: {}, priorities: [] }
  }
  let constraints: JsonRecord = {}
  try {
    const parsed = JSON.parse(groups.constraints ?? '') as unknown
    if (typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)) {
      constraints = parsed as JsonRecord
    }
  } catch {
    constraints = {}
  }
  let priorities = (groups.priorities ?? '')
    .split(',')
    .map((value) => value.trim())
    .filter((value) => /^[a-z0-9_.-]+$/i.test(value))
  const isOfficeLease = /(?:офис|office)/iu.test(
    `${groups.objective ?? ''} ${groups.context ?? ''}`,
  )
  if (isOfficeLease) {
    const officeConstraintKeys: Record<string, string> = {
      minimum_price: 'minimum_annual_rent',
      maximum_price: 'maximum_annual_rent',
    }
    constraints = Object.fromEntries(
      Object.entries(constraints).map(([key, value]) => [officeConstraintKeys[key] ?? key, value]),
    )
    const officePriorityKeys: Record<string, string> = {
      price: 'annual_rent',
      delivery_weeks: 'office_readiness_weeks',
    }
    priorities = priorities.map((key) => officePriorityKeys[key] ?? key)
  }
  return {
    summary: groups.summary,
    objectives: groups.objective ? [groups.objective] : [],
    context: groups.context ? [groups.context] : [],
    batna: groups.batna,
    constraints,
    priorities,
  }
}

function BriefSection({
  icon,
  title,
  children,
}: { icon: ReactNode; title: string; children: ReactNode }) {
  return (
    <section className="brief-section">
      <header className="brief-section-heading">
        <span aria-hidden="true">{icon}</span>
        <h3>{title}</h3>
      </header>
      <div className="brief-section-content">{children}</div>
    </section>
  )
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
  const locale = language === 'ru' ? 'ru-RU' : 'en-US'
  const roleBrief = roleBriefContent(observation.role_brief)
  const roleConstraints = Object.entries(roleBrief.constraints)
  const hasRoleBrief = Boolean(
    roleBrief.title
      || roleBrief.summary
      || roleBrief.objectives.length
      || roleBrief.context.length
      || roleBrief.batna
      || roleConstraints.length
      || roleBrief.priorities.length,
  )
  const assistance = observation.assistance as AssistanceView | null | undefined
  const hints = collectHints(observation)
  const detectedSignals = assistance?.detected_signals
  const signals = assistance?.signals
    ?? (Array.isArray(detectedSignals) ? detectedSignals : [])
  const coaching = typeof assistance?.coaching === 'string' ? assistance.coaching : undefined
  const priorities = assistance?.own_priorities ?? []
  const probableInterests = assistance?.probable_interests ?? []
  const contextItems = observation.context ?? []
  const remainingHints = typeof assistance?.remaining_hints === 'number'
    ? assistance.remaining_hints
    : observation.remaining_hints
  const hintsAvailable = assistance?.available ?? observation.hints_available

  return (
    <aside className="context-column">
      <section className="panel-card context-panel" aria-labelledby="context-title">
        <header className="panel-heading">
          <span className="panel-icon"><BookOpenText size={18} aria-hidden="true" /></span>
          <div>
            <p className="panel-kicker">{t('briefKicker')}</p>
            <h2 id="context-title">{t('context')}</h2>
          </div>
        </header>
        <div className="context-body">
          {roleBrief.title && <h3 className="brief-title">{roleBrief.title}</h3>}
          {roleBrief.summary && <p className="brief-summary">{roleBrief.summary}</p>}
          {!hasRoleBrief && <p className="brief-empty">{t('briefEmpty')}</p>}
          <div className="brief-sections">
            {roleBrief.objectives.length > 0 && (
              <BriefSection icon={<Target size={14} aria-hidden="true" />} title={t('roleObjective')}>
                <ul className="brief-copy-list">
                  {roleBrief.objectives.map((objective) => (
                    <li key={objective}>{objective}</li>
                  ))}
                </ul>
              </BriefSection>
            )}
            {roleBrief.context.length > 0 && (
              <BriefSection icon={<Compass size={14} aria-hidden="true" />} title={t('roleSituation')}>
                <ul className="brief-copy-list">
                  {roleBrief.context.map((item) => <li key={item}>{item}</li>)}
                </ul>
              </BriefSection>
            )}
            {roleBrief.batna && (
              <BriefSection icon={<Route size={14} aria-hidden="true" />} title={t('roleBatna')}>
                <p>{roleBrief.batna}</p>
              </BriefSection>
            )}
            {roleConstraints.length > 0 && (
              <BriefSection icon={<ShieldCheck size={14} aria-hidden="true" />} title={t('roleConstraints')}>
                <dl className="brief-facts">
                  {roleConstraints.map(([key, value]) => (
                    <div className="brief-fact-row" key={key}>
                      <dt>{identifierLabel(language, key)}</dt>
                      <dd>{formatTermValueForKey(key, value, locale, observation.currency)}</dd>
                    </div>
                  ))}
                </dl>
              </BriefSection>
            )}
            {roleBrief.priorities.length > 0 && (
              <BriefSection icon={<ListOrdered size={14} aria-hidden="true" />} title={t('rolePriorities')}>
                <ol className="brief-priority-list">
                  {roleBrief.priorities.map((priority, index) => (
                    <li key={priority}>
                      <span className="brief-priority-rank" aria-hidden="true">{index + 1}</span>
                      <span>{identifierLabel(language, priority)}</span>
                    </li>
                  ))}
                </ol>
              </BriefSection>
            )}
          </div>
          {contextItems.length > 0 && (
            <div className="objective-block">
              <strong>{t('additionalContext')}</strong>
              <ul>
                {contextItems.map((item, index) => (
                  <li key={item.id ?? `${item.type}-${index}`}>
                    <span><Sparkles size={13} aria-hidden="true" /></span>{item.content}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </section>

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
    </aside>
  )
}
