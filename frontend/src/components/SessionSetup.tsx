import { ArrowRight, BrainCircuit, Check, Clock3, KeyRound, Languages, LoaderCircle, MessagesSquare, ShieldCheck, Sparkles } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { translate } from '../i18n'
import type { Difficulty, ScenarioSummary, SessionLanguage, UiLanguage, TrainingSetup } from '../types'
import { TrainingSetupFields, defaultTraining } from './TrainingSetupFields'

export interface SessionSetupValue {
  scenario: ScenarioSummary
  sessionLanguage: SessionLanguage
  difficulty: Difficulty
  hintsEnabled: boolean
  participantToken: string
  roleId: string
  training?: TrainingSetup
}

interface SessionSetupProps {
  language: UiLanguage
  scenarios: ScenarioSummary[]
  loadingScenarios: boolean
  usingFallback: boolean
  creating: boolean
  error?: string
  onStart: (value: SessionSetupValue) => void
}

const difficultyOptions: Array<{ id: Difficulty; icon: typeof Sparkles }> = [
  { id: 'guided', icon: Sparkles },
  { id: 'easy', icon: ShieldCheck },
  { id: 'normal', icon: MessagesSquare },
  { id: 'expert', icon: BrainCircuit },
]

export function SessionSetup({
  language,
  scenarios,
  loadingScenarios,
  usingFallback,
  creating,
  error,
  onStart,
}: SessionSetupProps) {
  const t = (key: string) => translate(language, key)
  const [scenarioId, setScenarioId] = useState(
    () => scenarios.find((scenario) => scenario.languages?.includes(language))?.scenario_id
      ?? scenarios[0]?.scenario_id
      ?? '',
  )
  const [sessionLanguage, setSessionLanguage] = useState<SessionLanguage>('ru')
  const [difficulty, setDifficulty] = useState<Difficulty>('normal')
  const [hintsEnabled, setHintsEnabled] = useState(true)
  const [participantToken, setParticipantToken] = useState(() => sessionStorage.getItem('negotiation.participant-token') ?? '')
  const [roleId, setRoleId] = useState('buyer')
  const [training, setTraining] = useState<TrainingSetup>(defaultTraining)

  const selectedScenario = useMemo(
    () => scenarios.find((scenario) => scenario.scenario_id === scenarioId) ?? scenarios[0],
    [scenarioId, scenarios],
  )

  const roles = selectedScenario?.roles?.length
    ? selectedScenario.roles
    : [
        { role_id: 'buyer', title: t('roleBuyer') },
        { role_id: 'seller', title: t('roleSeller') },
      ]

  useEffect(() => {
    if (scenarios.some((scenario) => scenario.scenario_id === scenarioId)) return
    const preferred = scenarios.find((scenario) => scenario.languages?.includes(language)) ?? scenarios[0]
    if (preferred) setScenarioId(preferred.scenario_id)
  }, [language, scenarioId, scenarios])

  useEffect(() => {
    if (!roles.some((role) => role.role_id === roleId)) setRoleId(roles[0]?.role_id ?? 'buyer')
  }, [roleId, roles])

  useEffect(() => {
    const supported = selectedScenario?.languages
    if (supported?.length && !supported.includes(sessionLanguage)) setSessionLanguage(supported[0])
  }, [selectedScenario, sessionLanguage])

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!selectedScenario) return
    onStart({ scenario: selectedScenario, sessionLanguage, difficulty, hintsEnabled, participantToken, roleId, training })
  }

  return (
    <main className="setup-page">
      <section className="setup-story" aria-labelledby="setup-title">
        <div className="story-orbit orbit-one" aria-hidden="true" />
        <div className="story-orbit orbit-two" aria-hidden="true" />
        <div className="story-content">
          <p className="eyebrow">{t('setupEyebrow')}</p>
          <h1 id="setup-title">{t('setupTitle')}</h1>
          <p className="setup-lead">{t('setupLead')}</p>

          <div className="story-points">
            <article>
              <span className="story-icon"><MessagesSquare size={20} aria-hidden="true" /></span>
              <div>
                <h2>{t('setupPointOneTitle')}</h2>
                <p>{t('setupPointOneText')}</p>
              </div>
            </article>
            <article>
              <span className="story-icon"><ShieldCheck size={20} aria-hidden="true" /></span>
              <div>
                <h2>{t('setupPointTwoTitle')}</h2>
                <p>{t('setupPointTwoText')}</p>
              </div>
            </article>
            <article>
              <span className="story-icon"><BrainCircuit size={20} aria-hidden="true" /></span>
              <div>
                <h2>{t('setupPointThreeTitle')}</h2>
                <p>{t('setupPointThreeText')}</p>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section className="setup-form-wrap">
        <form className="setup-card" onSubmit={submit}>
          <div className="setup-card-heading">
            <div>
              <p className="eyebrow">01 / {t('setupStartKicker')}</p>
              <h2>{t('configure')}</h2>
              <p>{t('configureHint')}</p>
            </div>
            <span className="setup-step-mark"><Sparkles size={22} aria-hidden="true" /></span>
          </div>

          <div className="form-field">
            <label htmlFor="scenario">{t('scenario')}</label>
            <div className="scenario-select-wrap">
              <select
                id="scenario"
                value={selectedScenario?.scenario_id ?? ''}
                onChange={(event) => {
                  setScenarioId(event.target.value)
                  setTraining(value => ({ ...value, preparation: { ...value.preparation, targets: [] } }))
                }}
                disabled={loadingScenarios || scenarios.length === 0}
              >
                {loadingScenarios && <option>{t('scenarioLoading')}</option>}
                {scenarios.map((scenario) => (
                  <option key={scenario.scenario_id} value={scenario.scenario_id}>
                    {scenario.title}
                  </option>
                ))}
              </select>
                  {selectedScenario && (
                <div className="scenario-summary">
                  <div>
                    <strong>{selectedScenario.title}{selectedScenario.scenario_id === 'supplier_001' ? ` · ${t('mainCase')}` : ''}</strong>
                    <p>{selectedScenario.description}</p>
                  </div>
                  {selectedScenario.duration_minutes && (
                    <span><Clock3 size={15} aria-hidden="true" /> {selectedScenario.duration_minutes} {t('minuteShort')}</span>
                  )}
                </div>
              )}
            </div>
            {usingFallback && <p className="field-note warning-note">{t('fallbackScenarioNote')}</p>}
          </div>

          <TrainingSetupFields language={language} value={training} scenario={selectedScenario} onChange={setTraining} />

          <fieldset className="form-field fieldset-reset">
            <legend>{t('yourRole')}</legend>
            <div className="segmented-control role-segments">
              {roles.map((role) => (
                <button
                  key={role.role_id}
                  type="button"
                  className={roleId === role.role_id ? 'active' : ''}
                  onClick={() => setRoleId(role.role_id)}
                  aria-pressed={roleId === role.role_id}
                >
                  {roleId === role.role_id && <Check size={15} aria-hidden="true" />}
                  {role.title}
                </button>
              ))}
            </div>
          </fieldset>

          <div className="form-row two-columns">
            <fieldset className="form-field fieldset-reset">
              <legend><Languages size={15} aria-hidden="true" /> {t('language')}</legend>
              <div className="segmented-control">
                {(['ru', 'en'] as const).map((value) => (
                  <button
                    key={value}
                    type="button"
                    className={sessionLanguage === value ? 'active' : ''}
                    onClick={() => setSessionLanguage(value)}
                    disabled={Boolean(selectedScenario?.languages?.length && !selectedScenario.languages.includes(value))}
                    aria-pressed={sessionLanguage === value}
                  >
                    {value === 'ru' ? 'Русский' : 'English'}
                  </button>
                ))}
              </div>
            </fieldset>

            <div className="form-field token-field">
              <label htmlFor="participant-token"><KeyRound size={15} aria-hidden="true" /> {t('accessToken')}</label>
              <input
                id="participant-token"
                type="password"
                autoComplete="off"
                value={participantToken}
                onChange={(event) => setParticipantToken(event.target.value)}
                placeholder={t('accessTokenOptional')}
              />
              <small>{t('accessTokenHelp')}</small>
            </div>
          </div>

          <fieldset className="form-field fieldset-reset">
            <legend>{t('difficulty')}</legend>
            <div className="difficulty-grid">
              {difficultyOptions.map(({ id, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  className={difficulty === id ? 'difficulty-option active' : 'difficulty-option'}
                  onClick={() => setDifficulty(id)}
                  aria-pressed={difficulty === id}
                >
                  <span className="difficulty-icon"><Icon size={18} aria-hidden="true" /></span>
                  <span>
                    <strong>{t(`difficulty${id[0].toUpperCase()}${id.slice(1)}`)}</strong>
                    <small>{t(`difficulty${id[0].toUpperCase()}${id.slice(1)}Desc`)}</small>
                  </span>
                  <span className="radio-dot" aria-hidden="true" />
                </button>
              ))}
            </div>
          </fieldset>

          <label className="switch-row">
            <span className="switch-copy">
              <span className="switch-icon"><Sparkles size={17} aria-hidden="true" /></span>
              <span>
                <strong>{t('hints')}</strong>
                <small>{t('hintsEnabled')}</small>
              </span>
            </span>
            <input
              type="checkbox"
              checked={hintsEnabled}
              onChange={(event) => setHintsEnabled(event.target.checked)}
            />
            <span className="switch-track" aria-hidden="true"><span /></span>
          </label>

          {error && <div className="inline-error" role="alert">{error}</div>}

          <button className="button button-primary start-button" type="submit" disabled={!selectedScenario || creating}>
            {creating ? <LoaderCircle className="spin" size={19} aria-hidden="true" /> : <ArrowRight size={19} aria-hidden="true" />}
            {creating ? t('creating') : t('start')}
          </button>
        </form>
      </section>
    </main>
  )
}
