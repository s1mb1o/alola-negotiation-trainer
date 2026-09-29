import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, type MockInstance, vi } from 'vitest'
import App from '../App'
import { ApiError } from '../api'
import type { HintView, ScenarioSummary, SessionEnvelope, SessionReview } from '../types'
import { defaultTraining } from '../components/TrainingSetupFields'
import { supplyProposal, supplyPublication } from './supplyFixtures'

const apiMocks = vi.hoisted(() => ({
  createSession: vi.fn(),
  getAggregateStats: vi.fn(),
  getReview: vi.fn(),
  getSession: vi.fn(),
  listScenarios: vi.fn(),
  makeIdempotencyKey: vi.fn((prefix: string) => `${prefix}-stable-key`),
  requestHint: vi.fn(),
  sendMessage: vi.fn(),
  requestCoaching: vi.fn(),
  forkSession: vi.fn(),
  rewindSession: vi.fn(),
  requestPlayerAssist: vi.fn(),
  getComparison: vi.fn(),
}))

vi.mock('../api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api')>()),
  ...apiMocks,
}))

const ACTIVE_SESSION_KEY = 'negotiation.active-session.v1'
const TOKEN_KEY = 'negotiation.participant-token'
const NEW_SESSION_CONFIRM = 'Текущие переговоры ещё не завершены. Начать новую сессию? Эта вкладка выйдет из текущей сессии.'

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
  session_id: 'sess_session_test',
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

const restoredSession: SessionEnvelope = {
  session_id: 'sess_restored',
  revision: 3,
  status: 'active',
  next_actor: 'participant_buyer',
  language: 'ru',
  observation: {
    participant_id: 'participant_buyer',
    role: 'buyer',
    conversation: [{
      id: 'restored-1',
      participant_id: 'participant_seller',
      role: 'seller',
      message: 'Восстановленная реплика оппонента.',
    }],
  },
}

let confirmSpy: MockInstance<(message?: string) => boolean>

beforeEach(() => {
  localStorage.clear()
  sessionStorage.clear()
  window.history.replaceState({}, '', '/app/training')
  vi.clearAllMocks()
  confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
  apiMocks.listScenarios.mockResolvedValue([scenario])
  apiMocks.getAggregateStats.mockResolvedValue({ sessions: 0 })
})

afterEach(cleanup)

async function startSession(user: ReturnType<typeof userEvent.setup>): Promise<void> {
  await screen.findByRole('option', { name: 'Контракт на перевозку' })
  await user.click(screen.getByRole('button', { name: 'Начать переговоры' }))
}

function storeIdentity(overrides: Record<string, unknown> = {}): void {
  sessionStorage.setItem(TOKEN_KEY, 'stored-token')
  sessionStorage.setItem(ACTIVE_SESSION_KEY, JSON.stringify({
    session_id: 'sess_restored',
    role_id: 'buyer',
    session_language: 'ru',
    scenario,
    difficulty: 'normal',
    hints_enabled: true,
    revision: 3,
    ...overrides,
  }))
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

describe('session persistence', () => {
  it('coaches only on request and switches to a retry with fresh participant credentials', async () => {
    const user = userEvent.setup()
    const report: SessionReview = { outcome: { agreement: false }, training: {
      preparation: defaultTraining().preparation, goal_comparison: [], initial_social: { rapport: 45 }, final_social: { rapport: 45 },
      offer_history: [], evidence: [], checkpoints: [{ source_revision: 0 }], informed_practice: false,
      skill_scores_validated: false, coaching: { status: 'not_requested' },
    } }
    apiMocks.createSession.mockResolvedValue({ ...createdSession, status: 'walked_away', next_actor: null })
    apiMocks.getReview.mockResolvedValue(report)
    apiMocks.requestCoaching.mockResolvedValue({ status: 'complete' })
    apiMocks.forkSession.mockResolvedValue({ ...createdSession, session_id: 'sess_child', participant_token: 'fresh-child-token',
      observation: { participant_id: 'child-buyer', role: 'buyer', conversation: [] }, next_actor: 'child-buyer' })
    render(<App />)
    await startSession(user)
    await screen.findByRole('button', { name: 'Получить разбор' })
    expect(apiMocks.requestCoaching).not.toHaveBeenCalled()
    expect(apiMocks.createSession.mock.calls[0][0].training).toMatchObject({ relationship: 'successful_history' })
    await user.click(screen.getByRole('button', { name: 'Получить разбор' }))
    await waitFor(() => expect(apiMocks.requestCoaching).toHaveBeenCalledWith('sess_session_test', 'participant-token'))
    await user.click(screen.getByRole('button', { name: 'Начать повтор' }))
    await screen.findByText('sess_child')
    expect(apiMocks.forkSession).toHaveBeenCalledWith('sess_session_test', 0, 'fork-stable-key', 'participant-token')
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('fresh-child-token')
    expect(JSON.parse(sessionStorage.getItem(ACTIVE_SESSION_KEY) ?? '{}').session_id).toBe('sess_child')
    expect(screen.queryByRole('button', { name: 'Получить разбор' })).not.toBeInTheDocument()
  })

  it('stores the session identity in sessionStorage after creation', async () => {
    const user = userEvent.setup()
    apiMocks.createSession.mockResolvedValue(createdSession)

    render(<App />)
    await startSession(user)
    await screen.findByText('sess_session_test')

    const stored = JSON.parse(sessionStorage.getItem(ACTIVE_SESSION_KEY) ?? 'null') as Record<string, unknown>
    expect(stored).toMatchObject({
      session_id: 'sess_session_test',
      role_id: 'buyer',
      session_language: 'ru',
      difficulty: 'normal',
      hints_enabled: true,
      revision: 0,
    })
    expect((stored.scenario as ScenarioSummary).scenario_id).toBe('freight_contract_ru')
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('participant-token')
  })

  it('restores the active session from sessionStorage after a reload', async () => {
    storeIdentity()
    apiMocks.getSession.mockResolvedValue(restoredSession)

    render(<App />)
    expect(screen.getByRole('status')).toHaveTextContent('Восстанавливаем сессию…')

    await screen.findByText('Восстановленная реплика оппонента.')
    expect(apiMocks.getSession).toHaveBeenCalledWith('sess_restored', 'stored-token')
    expect(apiMocks.createSession).not.toHaveBeenCalled()
    expect(screen.getByText('sess_restored')).toBeInTheDocument()
    expect(screen.getByText('Контракт на перевозку')).toBeInTheDocument()
    expect(screen.getByText('r3')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Сформулируйте следующий ход…' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Новая сессия' })).toBeInTheDocument()
    // Without `hints_enabled` in the payload the stored session-creation choice applies.
    expect(screen.getByRole('button', { name: 'Получить подсказку' })).toBeInTheDocument()
    expect(screen.queryByText('Подтвердите полное согласие')).not.toBeInTheDocument()
    expect(screen.queryByText('Нужно уточнение')).not.toBeInTheDocument()
  })

  it('restores a pending confirmation card and the server hint setting', async () => {
    storeIdentity({ revision: 5, hints_enabled: true })
    apiMocks.getSession.mockResolvedValue({
      ...restoredSession,
      revision: 5,
      hints_enabled: false,
      clarification: null,
      pending_confirmation: {
        offer_id: 'offer_01',
        offer_revision: 4,
        terms: { price: 109_500, prepayment_fraction: 0.5, delivery_weeks: 6 },
        unresolved_required_terms: [],
      },
      observation: { ...restoredSession.observation, currency: 'EUR' },
    })

    render(<App />)

    await screen.findByText('Восстановленная реплика оппонента.')
    expect(screen.getByText('Подтвердите полное согласие')).toBeInTheDocument()
    expect(screen.getByText('Редакция 4')).toBeInTheDocument()
    expect(screen.getByText(/109.*500.*€/)).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Подтверждаю полностью' })).toBeEnabled()
    expect(screen.getByRole('button', { name: 'Не подтверждаю' })).toBeEnabled()
    expect(screen.queryByText('Нужно уточнение')).not.toBeInTheDocument()
    // `hints_enabled: false` from the service overrides the stored `true`.
    expect(screen.queryByRole('button', { name: 'Получить подсказку' })).not.toBeInTheDocument()
  })

  it.each([
    ['active session', null],
    ['pending confirmation', {
      offer_id: 'offer_01',
      offer_revision: 4,
      terms: { price: 109_500, prepayment_fraction: 0.5, delivery_weeks: 6 },
      unresolved_required_terms: [],
    }],
  ])('ends an %s through the Player API after confirmation', async (_label, pendingConfirmation) => {
    storeIdentity()
    apiMocks.getSession.mockResolvedValue({
      ...restoredSession,
      pending_confirmation: pendingConfirmation,
    })
    apiMocks.sendMessage.mockResolvedValue({
      ...restoredSession,
      revision: 4,
      status: 'walked_away',
      next_actor: null,
    })
    apiMocks.getReview.mockResolvedValue({ outcome: { agreement: false, termination_reason: 'walked_away' } })
    const user = userEvent.setup()

    render(<App />)
    await screen.findByText('Восстановленная реплика оппонента.')
    await user.click(screen.getByRole('button', { name: 'Завершить переговоры' }))
    expect(screen.getByRole('alertdialog', { name: 'Завершить переговоры без соглашения?' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Завершить переговоры' }))

    expect(apiMocks.sendMessage).toHaveBeenCalledWith(
      'sess_restored', 'Прекращаю переговоры.', 3, 'message-stable-key', 'stored-token',
    )
  })

  it('restores the owner publication snapshot and submits its confirmation through the Player API', async () => {
    storeIdentity()
    apiMocks.getSession.mockResolvedValue({
      ...restoredSession, negotiation_contract_version: 'supply-package-v1',
      confirmation_kind: 'publish_offer', pending_offer_publication: supplyPublication,
      observation: { ...restoredSession.observation, negotiation_contract_version: 'supply-package-v1', preliminary_proposals: [supplyProposal] },
    })
    apiMocks.sendMessage.mockResolvedValue({ ...restoredSession, revision: 4, pending_offer_publication: null })
    const user = userEvent.setup()
    render(<App />)
    await screen.findByText('Подтвердите публикацию предложения')
    expect(screen.getByRole('heading', { name: 'Обсуждаемый пакет' })).toBeInTheDocument()
    expect(screen.queryByText('Подтвердите полное согласие')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Опубликовать окончательное предложение' }))
    expect(apiMocks.sendMessage).toHaveBeenCalledWith(
      'sess_restored', 'Подтверждаю окончательное предложение', 3, 'message-stable-key', 'stored-token',
    )
    await waitFor(() => expect(screen.queryByText('Подтвердите публикацию предложения')).not.toBeInTheDocument())
  })

  it('restores a pending clarification notice', async () => {
    storeIdentity()
    const question = 'Вы соглашаетесь только с условием поставки или со всем предложением?'
    apiMocks.getSession.mockResolvedValue({
      ...restoredSession,
      hints_enabled: true,
      pending_confirmation: null,
      clarification: {
        reason_code: 'ambiguous_agreement_scope',
        question,
        candidate_interpretations: ['agree_to_delivery_term', 'accept_complete_offer'],
      },
    })

    render(<App />)

    await screen.findByText('Восстановленная реплика оппонента.')
    expect(screen.getByText('Нужно уточнение')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: question })).toBeInTheDocument()
    expect(screen.getByText('Agree To Delivery Term')).toBeInTheDocument()
    expect(screen.queryByText('Подтвердите полное согласие')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Получить подсказку' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Сформулируйте следующий ход…' })).toBeEnabled()
  })

  it('restores a finished session straight into its review', async () => {
    storeIdentity({ revision: 9 })
    apiMocks.getSession.mockResolvedValue({
      ...restoredSession,
      revision: 9,
      status: 'agreement_reached',
      next_actor: null,
    })
    apiMocks.getReview.mockResolvedValue({
      outcome: { agreement: true, termination_reason: 'agreement_reached' },
      outcome_score: 80,
    })

    render(<App />)

    await screen.findByRole('heading', { name: 'Соглашение достигнуто' })
    expect(apiMocks.getReview).toHaveBeenCalledWith('sess_restored', 'stored-token')
    expect(screen.queryByRole('textbox', { name: 'Сформулируйте следующий ход…' })).not.toBeInTheDocument()
  })

  it('clears the stored identity when the session no longer exists', async () => {
    storeIdentity()
    apiMocks.getSession.mockRejectedValue(new ApiError(404, { error: 'not_found' }))

    render(<App />)

    await screen.findByRole('button', { name: 'Начать переговоры' })
    expect(sessionStorage.getItem(ACTIVE_SESSION_KEY)).toBeNull()
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('stored-token')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('clears the stored identity when the participant token is rejected', async () => {
    storeIdentity()
    apiMocks.getSession.mockRejectedValue(new ApiError(401, { error: 'participant_unauthorized' }))

    render(<App />)

    await screen.findByRole('button', { name: 'Начать переговоры' })
    expect(sessionStorage.getItem(ACTIVE_SESSION_KEY)).toBeNull()
  })

  it('keeps the stored identity after a transient restore failure', async () => {
    storeIdentity()
    apiMocks.getSession.mockRejectedValue(new TypeError('network unavailable'))

    render(<App />)

    await screen.findByText('Сервис пока недоступен. Проверьте, что API запущен.')
    expect(sessionStorage.getItem(ACTIVE_SESSION_KEY)).not.toBeNull()
  })
})

describe('new session confirmation', () => {
  it('asks for confirmation before leaving an unfinished session', async () => {
    const user = userEvent.setup()
    apiMocks.createSession.mockResolvedValue(createdSession)

    render(<App />)
    await startSession(user)
    await screen.findByText('sess_session_test')

    confirmSpy.mockReturnValueOnce(false)
    await user.click(screen.getByRole('button', { name: 'Новая сессия' }))
    expect(confirmSpy).toHaveBeenCalledWith(NEW_SESSION_CONFIRM)
    expect(screen.getByText('sess_session_test')).toBeInTheDocument()
    expect(sessionStorage.getItem(ACTIVE_SESSION_KEY)).not.toBeNull()

    await user.click(screen.getByRole('button', { name: 'Новая сессия' }))
    await screen.findByRole('button', { name: 'Начать переговоры' })
    expect(confirmSpy).toHaveBeenCalledTimes(2)
    expect(sessionStorage.getItem(ACTIVE_SESSION_KEY)).toBeNull()
  })

  it('does not ask when the session is already finished', async () => {
    const user = userEvent.setup()
    apiMocks.createSession.mockResolvedValue({ ...createdSession, status: 'agreement_reached', next_actor: null })
    apiMocks.getReview.mockResolvedValue({
      outcome: { agreement: true, termination_reason: 'agreement_reached' },
      outcome_score: 75,
    })

    render(<App />)
    await startSession(user)
    await screen.findByRole('heading', { name: 'Соглашение достигнуто' })

    await user.click(screen.getByRole('button', { name: 'Новая сессия' }))
    await screen.findByRole('button', { name: 'Начать переговоры' })
    expect(confirmSpy).not.toHaveBeenCalled()
  })
})

describe('serialized mutations', () => {
  it('blocks message sending while a hint request is in flight', async () => {
    const user = userEvent.setup()
    const hint = deferred<{ revision?: number; hint?: HintView }>()
    apiMocks.createSession.mockResolvedValue(createdSession)
    apiMocks.requestHint.mockReturnValueOnce(hint.promise)

    render(<App />)
    await startSession(user)
    const composer = await screen.findByRole('textbox', { name: 'Сформулируйте следующий ход…' })
    await user.type(composer, 'привет')

    await user.click(screen.getByRole('button', { name: 'Получить подсказку' }))
    expect(composer).toBeDisabled()
    const sendButton = screen.getByRole('button', { name: 'Отправить' })
    expect(sendButton).toBeDisabled()
    await user.click(sendButton)
    expect(apiMocks.sendMessage).not.toHaveBeenCalled()

    await act(async () => hint.resolve({ revision: 1, hint: { id: 'hint-1', text: 'Спросите про сроки поставки.' } }))

    await screen.findByText('Спросите про сроки поставки.')
    expect(composer).toBeEnabled()
    expect(composer).toHaveValue('привет')
    expect(apiMocks.requestHint).toHaveBeenCalledWith('sess_session_test', 0, 'hint-stable-key', 'participant-token')
  })

  it('blocks hint requests while a message is in flight', async () => {
    const user = userEvent.setup()
    const message = deferred<SessionEnvelope>()
    apiMocks.createSession.mockResolvedValue(createdSession)
    apiMocks.sendMessage.mockReturnValueOnce(message.promise)

    render(<App />)
    await startSession(user)
    const composer = await screen.findByRole('textbox', { name: 'Сформулируйте следующий ход…' })
    await user.type(composer, 'привет')
    await user.click(screen.getByRole('button', { name: 'Отправить' }))

    const hintButton = screen.getByRole('button', { name: 'Получить подсказку' })
    expect(hintButton).toBeDisabled()
    await user.click(hintButton)
    expect(apiMocks.requestHint).not.toHaveBeenCalled()

    await act(async () => message.resolve({
      ...createdSession,
      revision: 2,
      observation: {
        conversation: [
          { id: 'm-player', participant_id: 'participant_buyer', role: 'buyer', message: 'привет' },
          { id: 'm-npc', participant_id: 'participant_seller', role: 'seller', message: 'Здравствуйте.' },
        ],
      },
    }))

    await screen.findByText('Здравствуйте.')
    await waitFor(() => expect(hintButton).toBeEnabled())
    expect(composer).toHaveFocus()
  })
})

describe('bounded training actions', () => {
  const activeTrainingSession: SessionEnvelope = {
    ...createdSession,
    revision: 4,
    observation: {
      participant_id: 'participant_buyer',
      role: 'buyer',
      conversation: [
        {
          id: 'npc-opening',
          revision: 0,
          participant_id: 'participant_seller',
          role: 'seller',
          message: 'Рад снова вас видеть. С чего начнём?',
        },
        {
          id: 'player-one',
          revision: 1,
          participant_id: 'participant_buyer',
          role: 'buyer',
          message: 'Начнём со сроков.',
        },
        {
          id: 'npc-two',
          revision: 2,
          participant_id: 'participant_seller',
          role: 'seller',
          message: 'Срок можно обсудить вместе с ценой.',
        },
      ],
      training: {
        ...defaultTraining(),
        version: 'training-v1',
        rewind: {
          limit: 3,
          used: 0,
          remaining: 3,
          available: true,
          eligible_source_revisions: [0, 2],
        },
      },
    },
  }

  it('returns to an eligible NPC message with a fresh child credential', async () => {
    const user = userEvent.setup()
    apiMocks.createSession.mockResolvedValue(activeTrainingSession)
    apiMocks.rewindSession.mockResolvedValue({
      ...activeTrainingSession,
      session_id: 'sess_rewind_child',
      revision: 0,
      participant_token: 'fresh-rewind-token',
      participant_credentials: [
        { participant_id: 'participant_child_buyer', role: 'buyer', token: 'fresh-rewind-token' },
      ],
      next_actor: 'participant_child_buyer',
      observation: {
        ...activeTrainingSession.observation,
        participant_id: 'participant_child_buyer',
        conversation: [activeTrainingSession.observation.conversation?.[0] ?? ''],
        training: {
          ...activeTrainingSession.observation.training!,
          rewind: {
            limit: 3,
            used: 1,
            remaining: 2,
            available: true,
            eligible_source_revisions: [0],
          },
        },
      },
    })

    render(<App />)
    await startSession(user)
    const rewindButtons = await screen.findAllByRole('button', { name: /Вернуться сюда/ })
    expect(rewindButtons).toHaveLength(2)
    expect(rewindButtons[0]).toHaveTextContent('3')
    await user.click(rewindButtons[0])

    await screen.findByText('sess_rewind_child')
    expect(apiMocks.rewindSession).toHaveBeenCalledWith(
      'sess_session_test', 0, 'rewind-stable-key', 'participant-token',
    )
    expect(sessionStorage.getItem(TOKEN_KEY)).toBe('fresh-rewind-token')
    expect(screen.queryByText('Начнём со сроков.')).not.toBeInTheDocument()
  })

  it('uses the player-side model and submits its text through the normal message API', async () => {
    const user = userEvent.setup()
    const generated = 'Предлагаю сначала согласовать срок и затем обсудить цену.'
    apiMocks.createSession.mockResolvedValue(activeTrainingSession)
    apiMocks.requestPlayerAssist.mockResolvedValue({
      session_id: activeTrainingSession.session_id,
      revision: activeTrainingSession.revision,
      message: generated,
      prompt_version: 'player-assist-v1',
      provider: 'qwen',
      model: 'Qwen3.8-Max',
    })
    apiMocks.sendMessage.mockResolvedValue({
      ...activeTrainingSession,
      revision: 6,
      observation: {
        ...activeTrainingSession.observation,
        conversation: [
          ...(activeTrainingSession.observation.conversation ?? []),
          {
            id: 'player-assisted',
            revision: 5,
            participant_id: 'participant_buyer',
            role: 'buyer',
            message: generated,
          },
        ],
      },
    })

    render(<App />)
    await startSession(user)
    await user.click(await screen.findByRole('button', { name: 'Ответь за меня' }))

    await waitFor(() => expect(apiMocks.requestPlayerAssist).toHaveBeenCalledWith(
      'sess_session_test', 4, 'player-assist-stable-key', 'participant-token',
    ))
    await waitFor(() => expect(apiMocks.sendMessage).toHaveBeenCalledWith(
      'sess_session_test', generated, 4, 'message-stable-key', 'participant-token',
    ))
    expect(await screen.findByText(generated)).toBeInTheDocument()
  })

  it('shows exhausted rewind actions as disabled', async () => {
    const user = userEvent.setup()
    apiMocks.createSession.mockResolvedValue({
      ...activeTrainingSession,
      observation: {
        ...activeTrainingSession.observation,
        training: {
          ...activeTrainingSession.observation.training!,
          rewind: {
            limit: 3,
            used: 3,
            remaining: 0,
            available: false,
            eligible_source_revisions: [0, 2],
          },
        },
      },
    })

    render(<App />)
    await startSession(user)
    const exhausted = await screen.findAllByRole('button', { name: /Возвраты закончились/ })
    expect(exhausted).toHaveLength(2)
    expect(exhausted.every((button) => button.hasAttribute('disabled'))).toBe(true)
  })
})

describe('role labels', () => {
  it('labels the counterpart turn by role instead of a raw participant identifier', async () => {
    const user = userEvent.setup()
    apiMocks.createSession.mockResolvedValue({ ...createdSession, next_actor: 'participant_seller' })

    render(<App />)
    await startSession(user)
    await screen.findByText('sess_session_test')

    expect(screen.getByText('Поставщик')).toBeInTheDocument()
    expect(screen.queryByText(/Participant Seller/i)).not.toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Сформулируйте следующий ход…' })).toBeDisabled()
  })
})
