import type {
  ApiErrorPayload,
  AdminSessionDetail,
  AdminSessionFilters,
  AdminSessionListResponse,
  AggregateStatsResponse,
  CreateSessionRequest,
  HintView,
  Observation,
  ScenarioSummary,
  SessionEnvelope,
  SessionReview,
  UiLanguage,
} from './types'

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1'

export class ApiError extends Error {
  readonly status: number
  readonly payload: ApiErrorPayload

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.detail ?? payload.message ?? payload.code ?? `HTTP ${status}`)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

export function apiErrorCode(error: unknown): string | undefined {
  if (!(error instanceof ApiError)) return undefined
  return typeof error.payload.error === 'string'
    ? error.payload.error
    : error.payload.code
}

export function isNpcRenderPending(error: unknown): boolean {
  return apiErrorCode(error) === 'npc_render_pending'
}

export function isResumableRequestError(error: unknown): boolean {
  if (!(error instanceof ApiError)) return true
  return isNpcRenderPending(error)
    || error.status === 408
    || error.status === 429
    || error.status >= 500
}

interface ApiRequestOptions extends RequestInit {
  token?: string
}

async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const { token, headers, ...requestOptions } = options
  const response = await fetch(`${API_BASE}${path}`, {
    ...requestOptions,
    headers: {
      Accept: 'application/json',
      ...(requestOptions.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  })

  const contentType = response.headers.get('content-type') ?? ''
  const body = contentType.includes('application/json')
    ? ((await response.json()) as unknown)
    : { detail: (await response.text()) || response.statusText }

  if (!response.ok) {
    throw new ApiError(response.status, (body ?? {}) as ApiErrorPayload)
  }

  return body as T
}

function normalizeScenario(raw: Record<string, unknown>): ScenarioSummary {
  const scenarioId = String(raw.scenario_id ?? raw.id ?? '')
  const rawLanguages = Array.isArray(raw.languages) ? raw.languages : raw.language ? [raw.language] : ['ru']
  const rawRoles = Array.isArray(raw.roles)
    ? raw.roles
    : typeof raw.roles === 'object' && raw.roles !== null
      ? Object.entries(raw.roles).map(([roleId, value]) =>
          typeof value === 'object' && value !== null ? { role_id: roleId, ...value } : { role_id: roleId, title: value },
        )
      : []
  return {
    scenario_id: scenarioId,
    version: Number(raw.version ?? raw.latest_version ?? 1),
    title: String(raw.title ?? raw.name ?? scenarioId),
    opening_kind: raw.opening_kind === 'opening_offer' || raw.opening_kind === 'opening_position'
      ? raw.opening_kind
      : undefined,
    currency: typeof raw.currency === 'string' ? raw.currency : undefined,
    description: typeof raw.description === 'string' ? raw.description : undefined,
    languages: rawLanguages.filter((value): value is 'ru' | 'en' => value === 'ru' || value === 'en'),
    duration_minutes: typeof raw.duration_minutes === 'number' ? raw.duration_minutes : undefined,
    role_label: typeof raw.role_label === 'string' ? raw.role_label : undefined,
    counterpart_label: typeof raw.counterpart_label === 'string' ? raw.counterpart_label : undefined,
    roles: rawRoles
      .filter((role): role is Record<string, unknown> => typeof role === 'object' && role !== null)
      .map((role) => {
        const roleId = String(role.role_id ?? role.id ?? role.role ?? '')
        return {
          role_id: roleId,
          title: String(role.title ?? role.name ?? role.label ?? role.company ?? roleId),
          description: typeof role.description === 'string' ? role.description : undefined,
        }
      })
      .filter((role) => role.role_id.length > 0),
  }
}

export async function listScenarios(language?: UiLanguage, token?: string): Promise<ScenarioSummary[]> {
  const query = language ? `?language=${encodeURIComponent(language)}` : ''
  const payload = await apiRequest<unknown>(`/scenarios${query}`, { token })
  const records = Array.isArray(payload)
    ? payload
    : typeof payload === 'object' && payload !== null && Array.isArray((payload as { items?: unknown[] }).items)
      ? (payload as { items: unknown[] }).items
      : typeof payload === 'object' && payload !== null && Array.isArray((payload as { scenarios?: unknown[] }).scenarios)
        ? (payload as { scenarios: unknown[] }).scenarios
      : []
  return records
    .filter((record): record is Record<string, unknown> => typeof record === 'object' && record !== null)
    .map(normalizeScenario)
    .filter((scenario) => scenario.scenario_id.length > 0)
}

export function createSession(payload: CreateSessionRequest, token?: string): Promise<SessionEnvelope> {
  return apiRequest<SessionEnvelope>('/sessions', {
    method: 'POST',
    token,
    body: JSON.stringify(payload),
  })
}

export function getSession(sessionId: string, token: string): Promise<SessionEnvelope> {
  return apiRequest<SessionEnvelope>(`/sessions/${encodeURIComponent(sessionId)}`, { token })
}

export function getObservation(sessionId: string, token: string): Promise<SessionEnvelope | Observation> {
  return apiRequest<SessionEnvelope | Observation>(`/sessions/${encodeURIComponent(sessionId)}/observation`, { token })
}

export function sendMessage(
  sessionId: string,
  message: string,
  expectedRevision: number,
  idempotencyKey: string,
  token: string,
): Promise<SessionEnvelope> {
  return apiRequest<SessionEnvelope>(`/sessions/${encodeURIComponent(sessionId)}/messages`, {
    method: 'POST',
    token,
    body: JSON.stringify({
      message,
      idempotency_key: idempotencyKey,
      expected_revision: expectedRevision,
    }),
  })
}

export function requestHint(
  sessionId: string,
  expectedRevision: number,
  idempotencyKey: string,
  token: string,
): Promise<{ revision?: number; hint?: HintView; observation?: Observation }> {
  return apiRequest(`/sessions/${encodeURIComponent(sessionId)}/hints`, {
    method: 'POST',
    token,
    body: JSON.stringify({
      idempotency_key: idempotencyKey,
      expected_revision: expectedRevision,
    }),
  })
}

export function getReview(sessionId: string, token: string): Promise<SessionReview> {
  return apiRequest<SessionReview>(`/sessions/${encodeURIComponent(sessionId)}/review`, { token })
}

export function getAggregateStats(token?: string): Promise<AggregateStatsResponse> {
  return apiRequest<AggregateStatsResponse>('/stats', { token })
}

export function listAdminSessions(
  filters: AdminSessionFilters,
  adminToken: string,
): Promise<AdminSessionListResponse> {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  const suffix = query.size > 0 ? `?${query.toString()}` : ''
  return apiRequest<AdminSessionListResponse>(`/admin/sessions${suffix}`, {
    token: adminToken,
  })
}

export function getAdminSession(
  sessionId: string,
  adminToken: string,
): Promise<AdminSessionDetail> {
  return apiRequest<AdminSessionDetail>(
    `/admin/sessions/${encodeURIComponent(sessionId)}`,
    { token: adminToken },
  )
}

export function makeIdempotencyKey(prefix = 'web'): string {
  const random = typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `${prefix}_${random}`
}
