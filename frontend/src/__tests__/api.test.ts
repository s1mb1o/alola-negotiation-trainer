import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, getAdminSession, isResumableRequestError, listAdminSessions, listScenarios, requestPlayerAssist, rewindSession } from '../api'

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { 'content-type': 'application/json' },
  })
}

describe('listScenarios', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('requests scenarios in the selected UI language', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ items: [] }))
    vi.stubGlobal('fetch', fetchMock)

    await listScenarios('en')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/scenarios?language=en',
      expect.objectContaining({ headers: expect.objectContaining({ Accept: 'application/json' }) }),
    )
  })

  it('normalizes an items envelope and role company labels', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      items: [{
        id: 'supplier_001',
        latest_version: 3,
        name: 'Supplier negotiation',
        opening_kind: 'opening_position',
        roles: [
          { role: 'buyer', company: 'Nord Systems' },
          { role: 'seller', company: 'Atlas Supply' },
        ],
      }],
    })))

    const result = await listScenarios()

    expect(result).toHaveLength(1)
    expect(result[0]).toMatchObject({
      scenario_id: 'supplier_001',
      version: 3,
      opening_kind: 'opening_position',
    })
    expect(result[0].roles).toEqual([
      { role_id: 'buyer', title: 'Nord Systems', description: undefined },
      { role_id: 'seller', title: 'Atlas Supply', description: undefined },
    ])
  })

  it('accepts a scenarios envelope and object role map', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({
      scenarios: [{
        scenario_id: 'contract_01',
        version: 1,
        title: 'Contract',
        roles: {
          client: { company: 'Client Co' },
          vendor: { title: 'Vendor' },
        },
      }],
    })))

    const result = await listScenarios()

    expect(result[0].roles?.map((role) => role.role_id)).toEqual(['client', 'vendor'])
    expect(result[0].roles?.map((role) => role.title)).toEqual(['Client Co', 'Vendor'])
  })
})

describe('Admin Inspector API', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('sends filters and the administrator credential only to the admin list endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({
      items: [],
      total: 0,
      limit: 25,
      offset: 0,
    }))
    vi.stubGlobal('fetch', fetchMock)

    await listAdminSessions({
      status: 'active',
      scenario_id: 'freight_contract_ru',
      language: 'ru',
      run_mode: 'training',
      limit: 25,
      offset: 0,
    }, 'admin-secret')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/admin/sessions?status=active&scenario_id=freight_contract_ru&language=ru&run_mode=training&limit=25&offset=0',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer admin-secret' }),
      }),
    )
  })

  it('encodes the selected session ID for the admin detail endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ session_id: 'session/value' }))
    vi.stubGlobal('fetch', fetchMock)

    await getAdminSession('session/value', 'admin-secret')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/v1/admin/sessions/session%2Fvalue',
      expect.objectContaining({
        headers: expect.objectContaining({ Authorization: 'Bearer admin-secret' }),
      }),
    )
  })
})

describe('request retry safety', () => {
  it('retains the idempotency envelope for uncertain and pending results', () => {
    expect(isResumableRequestError(new TypeError('network unavailable'))).toBe(true)
    expect(isResumableRequestError(new ApiError(503, { error: 'service_unavailable' }))).toBe(true)
    expect(isResumableRequestError(new ApiError(409, { error: 'npc_render_pending' }))).toBe(true)
  })

  it('treats ordinary protocol errors as final results', () => {
    expect(isResumableRequestError(new ApiError(409, { error: 'revision_conflict' }))).toBe(false)
    expect(isResumableRequestError(new ApiError(422, { error: 'offer_not_bindable' }))).toBe(false)
  })
})

describe('training action API', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('sends the selected checkpoint and expected revision to authenticated endpoints', async () => {
    const fetchMock = vi.fn().mockImplementation(
      () => Promise.resolve(jsonResponse({ session_id: 'child' })),
    )
    vi.stubGlobal('fetch', fetchMock)

    await rewindSession('session/value', 6, 'rewind-key', 'participant-token')
    await requestPlayerAssist('session/value', 9, 'assist-key', 'participant-token')

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      '/api/v1/sessions/session%2Fvalue/rewind',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ source_revision: 6, idempotency_key: 'rewind-key' }),
        headers: expect.objectContaining({ Authorization: 'Bearer participant-token' }),
      }),
    )
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      '/api/v1/sessions/session%2Fvalue/player-assist',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ expected_revision: 9, idempotency_key: 'assist-key' }),
        headers: expect.objectContaining({ Authorization: 'Bearer participant-token' }),
      }),
    )
  })
})
