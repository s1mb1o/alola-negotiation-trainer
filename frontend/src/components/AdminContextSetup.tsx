import { useEffect, useState, type FormEvent } from 'react'
import { ApiError, listAdminTrainingPresets } from '../api'
import { translate } from '../i18n'
import type { AdminTrainingPreset, Difficulty, TrainingSetup, UiLanguage } from '../types'
import type { SessionSetupValue } from './SessionSetup'
import { defaultTraining } from './TrainingSetupFields'

const TOKEN_KEY = 'negotiation.admin-token'

/** Explicit allowlist: never hand the privileged objective or credential to a player. */
export function playerSetupFromPreset(preset: AdminTrainingPreset, difficulty: Difficulty,
  profile: TrainingSetup['profile']): SessionSetupValue {
  const roleId = preset.scenario.roles?.find(role => role.role_id !== preset.npc_role)?.role_id
  const sessionLanguage = preset.scenario.languages?.[0]
  if (!roleId || !sessionLanguage) throw new Error('Invalid authored preset')
  return {
    scenario: preset.scenario, sessionLanguage, roleId, difficulty,
    participantToken: '', hintsEnabled: difficulty !== 'expert',
    training: { ...defaultTraining(), profile, authored_tone: true, relationship: 'first_meeting' },
  }
}

export function AdminContextSetup({ language, creating, error, hasActiveSession, onStart }: {
  language: UiLanguage
  creating: boolean
  error?: string
  hasActiveSession: boolean
  onStart: (setup: SessionSetupValue) => void
}) {
  const text = (ru: string, en: string) => language === 'ru' ? ru : en
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) ?? '')
  const [draft, setDraft] = useState('')
  const [presets, setPresets] = useState<AdminTrainingPreset[]>([])
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')
  const [reload, setReload] = useState(0)
  const [domainId, setDomainId] = useState('equipment')
  const [topicId, setTopicId] = useState('')
  const [npcRole, setNpcRole] = useState('seller')
  const [presetId, setPresetId] = useState('')
  const [difficulty, setDifficulty] = useState<Difficulty>('normal')
  const [profile, setProfile] = useState<TrainingSetup['profile']>('concise_skeptical')

  useEffect(() => {
    setPresets([])
    setLoadError('')
    if (!token) return
    let active = true
    setLoading(true)
    listAdminTrainingPresets(language, token).then(items => {
      if (active) setPresets(items)
    }).catch(cause => {
      if (!active) return
      const key = cause instanceof ApiError && cause.status === 503 ? 'inspectorDisabled'
        : cause instanceof ApiError && cause.status === 401 ? 'inspectorUnauthorized' : 'inspectorLoadError'
      setLoadError(translate(language, key))
    }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [language, token, reload])

  const domains = [...new Map(presets.map(p => [p.domain_id, p.domain])).entries()]
  const domain = domains.some(([id]) => id === domainId) ? domainId : domains[0]?.[0]
  const inDomain = presets.filter(p => p.domain_id === domain)
  const topics = [...new Map(inDomain.map(p => [p.topic_id, p.topic])).entries()]
  const topic = topics.some(([id]) => id === topicId) ? topicId : topics[0]?.[0]
  const inTopic = inDomain.filter(p => p.topic_id === topic)
  const roles = [...new Set(inTopic.map(p => p.npc_role))]
  const role = roles.includes(npcRole) ? npcRole : roles[0]
  const goals = inTopic.filter(p => p.npc_role === role)
  const selected = goals.find(p => p.preset_id === presetId) ?? goals[0]
  const disconnect = () => {
    sessionStorage.removeItem(TOKEN_KEY)
    setToken(''); setDraft(''); setPresets([]); setLoadError('')
  }
  const connect = (event: FormEvent) => {
    event.preventDefault()
    const credential = draft.trim()
    if (!credential) return
    sessionStorage.setItem(TOKEN_KEY, credential)
    setToken(credential); setDraft(''); setReload(value => value + 1)
  }
  const submit = (event: FormEvent) => {
    event.preventDefault()
    if (!selected || creating || hasActiveSession) return
    const setup = playerSetupFromPreset(selected, difficulty, profile)
    disconnect()
    onStart(setup)
  }

  return <main className="admin-context-page">
    <header><p className="eyebrow">{text('Администратор', 'Administrator')}</p>
      <h1>{text('Настройка контекста тренировки', 'Training context setup')}</h1>
      <p>{text('Выберите готовый контекст и цель собеседника. Затем передайте тренировку игроку.',
        'Select an authored context and counterpart goal. Then hand the training session to the player.')}</p>
    </header>
    {error && <p className="inline-error" role="alert">{error}</p>}
    {creating && <p role="status">{text('Создаём тренировку…', 'Creating training session…')}</p>}
    {!token ? <section className="panel-card admin-context-card">
      <h2>{translate(language, 'inspectorAccessTitle')}</h2>
      <p>{translate(language, 'inspectorAccessLead')}</p>
      <form onSubmit={connect}>
        <label className="form-field">{translate(language, 'inspectorAdminToken')}
          <input type="password" autoComplete="off" required value={draft} onChange={e => setDraft(e.target.value)} />
        </label>
        <button className="button button-primary" disabled={creating}>{translate(language, 'inspectorConnect')}</button>
      </form>
    </section> : <section className="panel-card admin-context-card">
      <div className="admin-context-actions">
        <button className="button button-secondary" onClick={disconnect}>{translate(language, 'inspectorDisconnect')}</button>
        <button className="button button-secondary" onClick={() => setReload(value => value + 1)} disabled={loading}>{translate(language, 'inspectorRefresh')}</button>
      </div>
      {loading && <p role="status">{text('Загружаем готовые контексты…', 'Loading authored contexts…')}</p>}
      {loadError && <p className="inline-error" role="alert">{loadError}</p>}
      {!loading && !loadError && !selected && <p>{text('Нет опубликованных пресетов для этого языка.', 'No published presets for this language.')}</p>}
      {!loading && selected && <form onSubmit={submit}>
        <div className="admin-context-grid">
          <label className="form-field">{text('Сфера', 'Domain')}
            <select value={domain} onChange={e => { setDomainId(e.target.value); setTopicId(''); setPresetId('') }}>
              {domains.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
          </label>
          <label className="form-field">{text('Тема переговоров', 'Negotiation topic')}
            <select value={topic} onChange={e => { setTopicId(e.target.value); setPresetId('') }}>
              {topics.map(([id, label]) => <option key={id} value={id}>{label}</option>)}
            </select>
          </label>
          <label className="form-field">{text('Роль собеседника (NPC)', 'Counterpart role (NPC)')}
            <select value={role} onChange={e => { setNpcRole(e.target.value); setPresetId('') }}>
              {roles.map(id => <option key={id} value={id}>{id === 'buyer' ? text('Покупатель / заказчик', 'Buyer / client') : id === 'seller' ? text('Поставщик / исполнитель', 'Supplier / provider') : id}</option>)}
            </select>
          </label>
          <label className="form-field">{text('Цель NPC — готовый пресет', 'NPC goal — authored preset')}
            <select value={selected.preset_id} onChange={e => setPresetId(e.target.value)}>
              {goals.map(p => <option key={p.preset_id} value={p.preset_id}>{p.npc_goal} — {p.scenario.title}</option>)}
            </select>
          </label>
          <label className="form-field">{text('Сложность', 'Difficulty')}
            <select value={difficulty} onChange={e => setDifficulty(e.target.value as Difficulty)}>
              {(['guided', 'easy', 'normal', 'expert'] as const).map(id => <option key={id} value={id}>{translate(language, `difficulty${id[0].toUpperCase()}${id.slice(1)}`)}</option>)}
            </select>
          </label>
          <label className="form-field">{text('Тон собеседника', 'Counterpart tone')}
            <select value={profile} onChange={e => setProfile(e.target.value as TrainingSetup['profile'])}>
              <option value="concise_skeptical">{text('Краткий деловой', 'Concise business tone')}</option>
              <option value="sociable">{text('Доброжелательный', 'Warm tone')}</option>
            </select>
          </label>
        </div>
        <aside className="admin-preset-summary">
          <h2>{selected.scenario.title}</h2><p>{selected.npc_goal}</p>
          <p><code>{selected.scenario.scenario_id}@{selected.scenario.version}</code></p>
          <p>{text('Цель связана с готовым сценарием и ролью. Другой пресет выбирает соответствующие правила. Экономика не редактируется. Тон работает и без AI.',
            'The goal belongs to an authored scenario and role. Another preset selects its rules. Economics are not editable. Tone also works without AI.')}</p>
        </aside>
        <p className="field-note">{text('При запуске доступ администратора в этой вкладке будет сброшен. Цель NPC и токен администратора не передаются в интерфейс игрока.',
          'Starting clears administrator access in this tab. The NPC objective and administrator token are not passed to the player interface.')}</p>
        {hasActiveSession && <p role="status">{text('Сначала завершите текущую тренировку или нажмите «Новая сессия».', 'First finish the current training session or choose New session.')}</p>}
        <button className="button button-primary" disabled={creating || hasActiveSession}>{text('Запустить тренировку игрока', 'Start player training')}</button>
      </form>}
    </section>}
  </main>
}
