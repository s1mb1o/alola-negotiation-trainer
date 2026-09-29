import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { ApiError } from '../api'
import type { ScenarioSummary, SessionEnvelope } from '../types'

const apiMocks = vi.hoisted(() => ({
  createSession: vi.fn(),
  getAggregateStats: vi.fn(),
  getReview: vi.fn(),
  getSession: vi.fn(),
  listScenarios: vi.fn(),
  makeIdempotencyKey: vi.fn((prefix: string) => `${prefix}-stable-key`),
  requestHint: vi.fn(),
  sendMessage: vi.fn(),
}))

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  ...apiMocks,
}))

// The automatic NPC-render retry pauses through `wait`; the tests control that pause directly.
const utilMocks = vi.hoisted(() => ({
  wait: vi.fn(),
}))

vi.mock('../utils', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../utils')>()),
  wait: utilMocks.wait,
}))

const scenario: ScenarioSummary = {
  scenario_id: 'freight_contract_ru',
  version: 1,
  title: 'Контракт на перевозку',
  languages: ['ru'],
  roles: [
    { role_id: 'buyer', title: 'Заказчик' },
    { role_id: 'seller', title: 'Перевозчик' },
  ],
}

const createdSession: SessionEnvelope = {
  session_id: 'sess_retry_test',
  revision: 0,
  status: 'active',
  next_actor: 'participant_buyer',
  language: 'ru',
  observation: { conversation: [] },
  participant_token: 'participant-token',
  participants: [
    { participant_id: 'participant_buyer', role: 'buyer' },
    { participant_id: 'participant_seller', role: 'seller' },
  ],
}

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  window.history.replaceState({}, '', '/app/training')
  vi.clearAllMocks()
  // Drop queued one-time results so a failing test cannot leak them into the next one.
  for (const mock of [apiMocks.createSession, apiMocks.getReview, apiMocks.getSession, apiMocks.requestHint, apiMocks.sendMessage]) {
    mock.mockReset()
  }
  utilMocks.wait.mockReset().mockResolvedValue(undefined)
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  apiMocks.listScenarios.mockResolvedValue([scenario])
  apiMocks.getAggregateStats.mockResolvedValue({ sessions: 0 })
})

afterEach(cleanup)

const sessionAfterPendingRender: SessionEnvelope = {
  ...createdSession,
  revision: 4,
  observation: {
    conversation: [
      {
        id: 'message-player-after-pending',
        participant_id: 'participant_buyer',
        role: 'buyer',
        message: 'привет',
      },
      {
        id: 'message-npc-after-pending',
        participant_id: 'participant_seller',
        role: 'seller',
        message: 'Добрый день. Продолжим обсуждение.',
      },
    ],
  },
}

async function startSession(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await screen.findByRole('option', { name: 'Контракт на перевозку' })
  await user.click(screen.getByRole('button', { name: 'Начать переговоры' }))
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

describe('request idempotency retries', () => {
  it('shows one revision-zero opponent opener and keeps the player composer enabled', async () => {
    const user = userEvent.setup()
    const opener = 'Добрый день. Моё начальное предложение: цена 440 000 ₽.'
    apiMocks.createSession.mockResolvedValue({
      ...createdSession,
      committed_actions: [],
      observation: {
        conversation: [{
          revision: 0,
          participant_id: 'participant_seller',
          role: 'seller',
          message: opener,
        }],
      },
    })

    render(<App />)
    await startSession(user)

    await screen.findByText('sess_retry_test')
    const renderedOpeners = await screen.findAllByText((_, element) => (
      element?.tagName === 'P' && element.textContent === opener
    ))
    expect(renderedOpeners).toHaveLength(1)
    expect(screen.getByRole('textbox', { name: 'Сформулируйте следующий ход…' })).toBeEnabled()
  })

  it('reuses the create-session key after an uncertain network result', async () => {
    const user = userEvent.setup()
    apiMocks.createSession
      .mockRejectedValueOnce(new TypeError('network unavailable'))
      .mockResolvedValueOnce(createdSession)

    render(<App />)
    await startSession(user)
    await screen.findByText('Сервис пока недоступен. Проверьте, что API запущен.')
    await user.click(screen.getByRole('button', { name: 'Начать переговоры' }))

    await screen.findByText('sess_retry_test')
    await waitFor(() => expect(apiMocks.createSession).toHaveBeenCalledTimes(2))
    expect(apiMocks.createSession.mock.calls[0][0].idempotency_key).toBe('create-stable-key')
    expect(apiMocks.createSession.mock.calls[1][0].idempotency_key).toBe('create-stable-key')
  })

  it('reuses one message envelope and one optimistic message after a network loss', async () => {
    const user = userEvent.setup()
    apiMocks.createSession.mockResolvedValue(createdSession)
    apiMocks.sendMessage
      .mockRejectedValueOnce(new TypeError('network unavailable'))
      .mockResolvedValueOnce({
        ...createdSession,
        revision: 2,
        observation: {
          conversation: [
            {
              id: 'message-player',
              participant_id: 'participant_buyer',
              role: 'buyer',
              message: 'привет',
            },
            {
              id: 'message-npc',
              participant_id: 'participant_seller',
              role: 'seller',
              message: 'Здравствуйте. Давайте обсудим условия.',
            },
          ],
        },
      })

    render(<App />)
    await startSession(user)

    const composer = await screen.findByRole('textbox', { name: 'Сформулируйте следующий ход…' })
    await user.type(composer, 'привет')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))
    await screen.findByText('Сервис пока недоступен. Проверьте, что API запущен.')
    expect(screen.getAllByText('привет')).toHaveLength(1)

    await user.click(screen.getByRole('button', { name: 'Повторить' }))
    await screen.findByText('Здравствуйте. Давайте обсудим условия.')

    expect(apiMocks.sendMessage).toHaveBeenCalledTimes(2)
    expect(apiMocks.sendMessage.mock.calls[0].slice(1, 4)).toEqual([
      'привет',
      0,
      'message-stable-key',
    ])
    expect(apiMocks.sendMessage.mock.calls[1].slice(1, 4)).toEqual([
      'привет',
      0,
      'message-stable-key',
    ])
    expect(screen.getAllByText('привет')).toHaveLength(1)
  })

  it('auto-retries a pending NPC render with the exact original envelope behind a neutral notice', async () => {
    const user = userEvent.setup()
    const pause = deferred<void>()
    utilMocks.wait.mockReturnValueOnce(pause.promise)
    apiMocks.createSession.mockResolvedValue(createdSession)
    apiMocks.sendMessage
      .mockRejectedValueOnce(new ApiError(409, {
        error: 'npc_render_pending',
        revision: 2,
      }))
      .mockImplementationOnce((_sessionId, message, expectedRevision, idempotencyKey) => {
        if (JSON.stringify({ message, expectedRevision, idempotencyKey }) !== JSON.stringify({
          message: 'привет',
          expectedRevision: 0,
          idempotencyKey: 'message-stable-key',
        })) {
          return Promise.reject(new ApiError(409, { error: 'idempotency_key_reused' }))
        }
        return Promise.resolve(sessionAfterPendingRender)
      })

    render(<App />)
    await startSession(user)

    const composer = await screen.findByRole('textbox', { name: 'Сформулируйте следующий ход…' })
    await user.type(composer, 'привет')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    const notice = await screen.findByRole('status')
    expect(notice).toHaveTextContent('Ждём ответ оппонента…')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(composer).toBeDisabled()
    expect(apiMocks.sendMessage).toHaveBeenCalledTimes(1)
    expect(utilMocks.wait).toHaveBeenCalledWith(1000)

    await act(async () => pause.resolve(undefined))

    await screen.findByText('Добрый день. Продолжим обсуждение.')
    expect(apiMocks.sendMessage).toHaveBeenCalledTimes(2)
    for (const call of apiMocks.sendMessage.mock.calls) {
      expect(call.slice(1, 4)).toEqual(['привет', 0, 'message-stable-key'])
    }
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(composer).toBeEnabled()
  })

  it('shows Retry and Discard only after the automatic NPC render retries are exhausted', async () => {
    const user = userEvent.setup()
    apiMocks.createSession.mockResolvedValue(createdSession)
    const pendingRender = () => new ApiError(409, { error: 'npc_render_pending', revision: 2 })
    apiMocks.sendMessage
      .mockRejectedValueOnce(pendingRender())
      .mockRejectedValueOnce(pendingRender())
      .mockRejectedValueOnce(pendingRender())
      .mockRejectedValueOnce(pendingRender())
      .mockResolvedValueOnce(sessionAfterPendingRender)

    render(<App />)
    await startSession(user)

    const composer = await screen.findByRole('textbox', { name: 'Сформулируйте следующий ход…' })
    await user.type(composer, 'привет')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(
      'Предыдущий ответ оппонента ещё формируется. Повторите попытку через несколько секунд.',
    )
    expect(apiMocks.sendMessage).toHaveBeenCalledTimes(4)
    expect(utilMocks.wait.mock.calls.map(([milliseconds]) => milliseconds)).toEqual([1000, 2000, 4000])
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Отменить отправку' })).toBeInTheDocument()
    expect(screen.getByText('Не отправлено')).toBeInTheDocument()
    expect(composer).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Повторить' }))
    await screen.findByText('Добрый день. Продолжим обсуждение.')

    expect(apiMocks.sendMessage).toHaveBeenCalledTimes(5)
    for (const call of apiMocks.sendMessage.mock.calls) {
      expect(call.slice(1, 4)).toEqual(['привет', 0, 'message-stable-key'])
    }
  })

  it('lets the player discard a failed attempt and keeps the draft text', async () => {
    const user = userEvent.setup()
    apiMocks.createSession.mockResolvedValue(createdSession)
    apiMocks.sendMessage.mockRejectedValueOnce(new TypeError('network unavailable'))

    render(<App />)
    await startSession(user)

    const composer = await screen.findByRole('textbox', { name: 'Сформулируйте следующий ход…' })
    await user.type(composer, 'привет')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))
    await screen.findByRole('alert')
    expect(composer).toBeDisabled()
    expect(screen.getByText('Не отправлено')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Отменить отправку' }))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(composer).toBeEnabled()
    expect(composer).toHaveValue('привет')
    expect(composer).toHaveFocus()
    expect(screen.queryAllByText((_, element) => (
      element?.tagName === 'P' && element.textContent === 'привет'
    ))).toHaveLength(0)
    expect(apiMocks.sendMessage).toHaveBeenCalledTimes(1)
  })
})

describe('stale session requests', () => {
  it('does not let a late reply from the prior session replace the new session', async () => {
    const user = userEvent.setup()
    const lateMessage = deferred<SessionEnvelope>()
    const nextSession: SessionEnvelope = {
      ...createdSession,
      session_id: 'sess_after_restart',
      participant_token: 'next-participant-token',
    }
    apiMocks.createSession
      .mockResolvedValueOnce(createdSession)
      .mockResolvedValueOnce(nextSession)
    apiMocks.sendMessage.mockReturnValueOnce(lateMessage.promise)

    render(<App />)
    await startSession(user)
    const composer = await screen.findByRole('textbox', { name: 'Сформулируйте следующий ход…' })
    await user.type(composer, 'старая реплика')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))
    expect(screen.getByText('старая реплика')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Новая сессия' }))
    expect(screen.queryByText('старая реплика')).not.toBeInTheDocument()
    await startSession(user)
    await screen.findByText('sess_after_restart')

    await act(async () => lateMessage.resolve({
      ...createdSession,
      revision: 2,
      observation: {
        conversation: [{
          id: 'late-old-message',
          participant_id: 'participant_seller',
          role: 'seller',
          message: 'Поздний ответ старой сессии',
        }],
      },
    }))

    expect(screen.getByText('sess_after_restart')).toBeInTheDocument()
    expect(screen.queryByText('Поздний ответ старой сессии')).not.toBeInTheDocument()
  })

  it('does not show a late prior-session error after starting over', async () => {
    const user = userEvent.setup()
    const lateMessage = deferred<SessionEnvelope>()
    apiMocks.createSession.mockResolvedValue(createdSession)
    apiMocks.sendMessage.mockReturnValueOnce(lateMessage.promise)

    render(<App />)
    await startSession(user)
    const composer = await screen.findByRole('textbox', { name: 'Сформулируйте следующий ход…' })
    await user.type(composer, 'старая реплика')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))
    await user.click(screen.getByRole('button', { name: 'Новая сессия' }))

    await act(async () => lateMessage.reject(new TypeError('private upstream failure detail')))

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText('старая реплика')).not.toBeInTheDocument()
  })
})
