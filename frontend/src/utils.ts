import type {
  AggregateStats,
  ConversationEntry,
  Observation,
  SessionEnvelope,
  SessionReview,
  StoredActiveSession,
  StoredSessionReview,
  TimelineMessage,
} from './types'

const REVIEW_HISTORY_KEY = 'negotiation-trainer.review-history.v1'
export const ACTIVE_SESSION_KEY = 'negotiation.active-session.v1'

export const terminalStatuses = new Set([
  'agreement_reached',
  'walked_away',
  'expired',
  'aborted',
  'technical_failure',
])

export function isTerminalStatus(status: string): boolean {
  return terminalStatuses.has(status)
}

export function wait(milliseconds: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, milliseconds)
  })
}

export function extractParticipantToken(response: SessionEnvelope, preferredRole = 'buyer'): string {
  if (response.participant_token) return response.participant_token
  if (response.access_token) return response.access_token

  const participant = response.participants?.find((item) => item.role === preferredRole) ?? response.participants?.[0]
  if (participant?.token) return participant.token
  if (participant?.access_token) return participant.access_token

  const credential = response.participant_credentials?.find((item) => item.role === preferredRole)
    ?? response.participant_credentials?.[0]
  if (credential?.token) return credential.token
  if (credential?.access_token) return credential.access_token

  if (response.next_actor && response.participant_tokens?.[response.next_actor]) {
    return response.participant_tokens[response.next_actor]
  }

  return Object.values(response.participant_tokens ?? {})[0] ?? ''
}

function normalizeEntry(entry: ConversationEntry | string, index: number): TimelineMessage | null {
  if (typeof entry === 'string') {
    return {
      id: `conversation-${index}-${entry}`,
      role: 'counterpart',
      text: entry,
    }
  }

  const text = entry.message ?? entry.text
  if (!text) return null

  return {
    id: entry.id ?? entry.event_id ?? `conversation-${index}-${entry.participant_id ?? entry.role ?? 'actor'}-${text}`,
    participantId: entry.participant_id,
    role: entry.role ?? entry.actor ?? 'counterpart',
    action: entry.action,
    text,
    timestamp: entry.occurred_at ?? entry.created_at,
  }
}

export function extractTimeline(response: SessionEnvelope): TimelineMessage[] {
  const conversation = response.observation?.conversation ?? []
  const normalizedConversation = conversation
    .map(normalizeEntry)
    .filter((entry): entry is TimelineMessage => entry !== null)

  if (normalizedConversation.length > 0) return normalizedConversation

  return (response.committed_actions ?? [])
    .filter((action) => Boolean(action.message))
    .map((action, index) => ({
      id: `${response.revision}-${index}-${action.participant_id ?? action.role ?? 'actor'}`,
      participantId: action.participant_id,
      role: action.role ?? action.participant_id ?? 'counterpart',
      action: action.action,
      text: action.message ?? '',
    }))
}

export function mergeTimeline(current: TimelineMessage[], incoming: TimelineMessage[]): TimelineMessage[] {
  const byId = new Map(current.filter((item) => !item.pending).map((item) => [item.id, item]))
  for (const item of incoming) byId.set(item.id, item)
  return [...byId.values()]
}

export function normalizeObservationResponse(
  response: SessionEnvelope | Observation,
  current: SessionEnvelope,
): SessionEnvelope {
  if ('session_id' in response && typeof response.session_id === 'string') return response as SessionEnvelope
  return { ...current, observation: response as Observation }
}

export function maskToken(token: string): string {
  if (!token) return ''
  if (token.length <= 10) return '••••••••'
  return `${token.slice(0, 4)}••••••${token.slice(-4)}`
}

export function formatNumber(value: number, locale: string, maximumFractionDigits = 0): string {
  return new Intl.NumberFormat(locale, { maximumFractionDigits }).format(value)
}

export function formatPercent(value: number | null | undefined, locale: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  const normalized = value <= 1 ? value * 100 : value
  return `${formatNumber(normalized, locale, 0)}%`
}

export function humanizeTermKey(key: string): string {
  return key
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
}

export function formatTermValue(value: unknown, locale: string): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? '✓' : '—'
  if (typeof value === 'number') {
    if (value > 0 && value < 1) return formatPercent(value, locale)
    return formatNumber(value, locale, 2)
  }
  if (typeof value === 'string') return value.replace(/_/g, ' ')
  if (Array.isArray(value)) return value.map((item) => formatTermValue(item, locale)).join(' · ')
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .map(([key, nested]) => `${humanizeTermKey(key)}: ${formatTermValue(nested, locale)}`)
      .join(' · ')
  }
  return String(value)
}

function formatCountedUnit(value: number, locale: string, unit: 'week'): string {
  const formatted = formatNumber(value, locale, 0)
  if (!locale.toLowerCase().startsWith('ru')) {
    return `${formatted} ${value === 1 ? unit : `${unit}s`}`
  }
  const form = new Intl.PluralRules('ru').select(value)
  const labels: Record<Intl.LDMLPluralRule, string> = {
    zero: 'недель',
    one: 'неделя',
    two: 'недели',
    few: 'недели',
    many: 'недель',
    other: 'недели',
  }
  return `${formatted} ${labels[form]}`
}

export function formatTermValueForKey(
  key: string,
  value: unknown,
  locale: string,
  currency?: string,
): string {
  const isMoney = key === 'price'
    || key.endsWith('_price')
    || key === 'maximum_total_liability'
    || key === 'annual_rent'
    || key.endsWith('_annual_rent')
  if (isMoney && typeof value === 'number' && currency) {
    return new Intl.NumberFormat(locale, {
      style: 'currency',
      currency,
      maximumFractionDigits: 0,
    }).format(value)
  }
  if (key.endsWith('_weeks') && typeof value === 'number') {
    return formatCountedUnit(value, locale, 'week')
  }
  // An explicit 0 or 1 share is a real term value: render "0%" and "100%".
  if (key.includes('fraction') && typeof value === 'number') {
    return formatPercent(value, locale)
  }
  return formatTermValue(value, locale)
}

export function readReviewHistory(): StoredSessionReview[] {
  try {
    const raw = localStorage.getItem(REVIEW_HISTORY_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? (parsed as StoredSessionReview[]) : []
  } catch {
    return []
  }
}

export function storeReview(sessionId: string, scenarioTitle: string, review: SessionReview): void {
  const history = readReviewHistory().filter((item) => item.session_id !== sessionId)
  history.unshift({
    session_id: sessionId,
    scenario_title: scenarioTitle,
    finished_at: new Date().toISOString(),
    review,
  })
  localStorage.setItem(REVIEW_HISTORY_KEY, JSON.stringify(history.slice(0, 50)))
}

export function readActiveSession(): StoredActiveSession | undefined {
  try {
    const raw = sessionStorage.getItem(ACTIVE_SESSION_KEY)
    if (!raw) return undefined
    const parsed = JSON.parse(raw) as Partial<StoredActiveSession> | null
    if (
      !parsed
      || typeof parsed.session_id !== 'string'
      || typeof parsed.role_id !== 'string'
      || typeof parsed.scenario !== 'object'
      || parsed.scenario === null
    ) return undefined
    return parsed as StoredActiveSession
  } catch {
    return undefined
  }
}

export function storeActiveSession(value: StoredActiveSession): void {
  try {
    sessionStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify(value))
  } catch {
    // The UI remains usable when browser storage is unavailable.
  }
}

export function clearActiveSession(): void {
  try {
    sessionStorage.removeItem(ACTIVE_SESSION_KEY)
  } catch {
    // Nothing to clear when browser storage is unavailable.
  }
}

function average(values: number[]): number | null {
  if (values.length === 0) return null
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

export function aggregateReviewHistory(history = readReviewHistory()): AggregateStats {
  const outcomes = history
    .map((item) => item.review.outcome_score)
    .filter((value): value is number => typeof value === 'number')
  const pareto = history
    .map((item) => item.review.outcome.pareto_efficiency)
    .filter((value): value is number => typeof value === 'number')
  const skillValues = new Map<string, number[]>()

  for (const item of history) {
    for (const [skill, value] of Object.entries(item.review.skills ?? {})) {
      if (typeof value !== 'number') continue
      skillValues.set(skill, [...(skillValues.get(skill) ?? []), value])
    }
  }

  return {
    sessions: history.length,
    agreements: history.filter((item) => item.review.outcome.agreement === true).length,
    walkaways: history.filter((item) => item.review.outcome.termination_reason === 'walked_away').length,
    average_outcome: average(outcomes),
    average_pareto: average(pareto),
    average_skills: Object.fromEntries(
      [...skillValues.entries()].map(([skill, values]) => [skill, average(values) ?? 0]),
    ),
    recent: history.slice(0, 8),
  }
}
