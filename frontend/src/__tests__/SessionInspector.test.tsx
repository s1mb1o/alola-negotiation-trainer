import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getAdminSession, listAdminSessions } from '../api'
import { SessionInspector } from '../components/SessionInspector'
import type { AdminSessionDetail, AdminSessionSummary } from '../types'
import { supplyProposal } from './supplyFixtures'

vi.mock('../api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../api')>()
  return {
    ...actual,
    listAdminSessions: vi.fn(),
    getAdminSession: vi.fn(),
  }
})

const summary: AdminSessionSummary = {
  session_id: 'sess_admin_001',
  scenario_id: 'office_lease_ru',
  scenario_version: 2,
  scenario_title: 'Годовая аренда офиса',
  currency: 'RUB',
  status: 'active',
  revision: 3,
  round: 2,
  substantive_turn_count: 3,
  next_actor: 'participant_buyer',
  difficulty: 'normal',
  language: 'ru',
  run_mode: 'training',
  hints_enabled: true,
  run_metadata: {},
  created_at: '2026-08-28 06:00:00',
  updated_at: '2026-08-28 06:05:00',
  message_count: 1,
  event_count: 1,
  offer_revision_count: 1,
  review_state: 'not_ready',
  participants: [
    {
      participant_id: 'participant_buyer',
      role: 'buyer',
      controller: 'human',
    },
    {
      participant_id: 'participant_seller',
      role: 'seller',
      controller: 'built_in_npc',
    },
  ],
}

const detail: AdminSessionDetail = {
  ...summary,
  messages: [{
    session_revision: 1,
    participant_id: 'participant_buyer',
    role: 'buyer',
    content: 'Предлагаю годовую аренду 2 400 000 рублей.',
    language: 'ru',
    created_at: '2026-08-28 06:01:00',
  }],
  events: [{
    event_id: 'evt_public_1',
    session_revision: 1,
    participant_id: 'participant_buyer',
    type: 'offer.created',
    payload: { offer_id: 'offer_1' },
    created_at: '2026-08-28 06:01:00',
  }],
  offers: [{
    offer_id: 'offer_1',
    offer_revision: 1,
    proposer_participant_id: 'participant_buyer',
    terms: {
      annual_rent: 2_400_000,
      prepayment_fraction: 0.25,
      office_readiness_weeks: 6,
    },
    status: 'active',
    created_session_revision: 1,
  }],
  review: null,
  benchmark_run: null,
}

describe('SessionInspector', () => {
  afterEach(() => {
    cleanup()
    sessionStorage.clear()
  })

  beforeEach(() => {
    sessionStorage.clear()
    vi.mocked(listAdminSessions).mockReset()
    vi.mocked(getAdminSession).mockReset()
    vi.mocked(listAdminSessions).mockResolvedValue({
      items: [summary],
      total: 1,
      limit: 25,
      offset: 0,
    })
    vi.mocked(getAdminSession).mockResolvedValue(detail)
  })

  it('stores the administrator token in session storage and renders safe session details', async () => {
    const user = userEvent.setup()
    render(<SessionInspector language="ru" />)

    await user.type(screen.getByLabelText('Токен администратора'), 'admin-secret')
    await user.click(screen.getByRole('button', { name: 'Подключиться' }))

    expect(await screen.findByRole('heading', { name: 'Годовая аренда офиса' })).toBeInTheDocument()
    expect(sessionStorage.getItem('negotiation.admin-token')).toBe('admin-secret')
    expect(listAdminSessions).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 25, offset: 0 }),
      'admin-secret',
    )
    expect(getAdminSession).toHaveBeenCalledWith('sess_admin_001', 'admin-secret')

    await user.click(screen.getByRole('tab', { name: /Сообщения/ }))
    expect(screen.getByText('Предлагаю годовую аренду 2 400 000 рублей.')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /События/ }))
    expect(screen.getByText('offer.created')).toBeInTheDocument()
    expect(screen.queryByText(/private_payload/)).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: /Предложения/ }))
    expect(screen.getByText('2 400 000 ₽')).toBeInTheDocument()
    expect(screen.getByText((_content, element) => element?.textContent?.replace(/\s/g, '') === '25%')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Разбор' }))
    expect(screen.getByText('Разбор ещё недоступен')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Инспектор сессий' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Годовая аренда офиса · sess_admin_001 · Идут переговоры' })).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Отключить/ }))
    expect(sessionStorage.getItem('negotiation.admin-token')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Подключите доступ администратора' })).toBeInTheDocument()
  })

  it('shows preliminary history with source revisions independently of formal offers', async () => {
    sessionStorage.setItem('negotiation.admin-token', 'admin-secret')
    vi.mocked(getAdminSession).mockResolvedValue({
      ...detail, offers: [], currency: 'EUR', events: [{
        event_id: 'evt_preliminary', session_revision: 8, participant_id: 'participant_buyer',
        type: 'proposal.revised', payload: { proposal: supplyProposal }, created_at: '2026-09-08 06:00:00',
      }],
    })
    const user = userEvent.setup()
    render(<SessionInspector language="en" />)
    await screen.findByRole('heading', { name: 'Годовая аренда офиса' })
    await user.click(screen.getByRole('tab', { name: /Offers/ }))
    expect(screen.getByText('Package under discussion · Revision 7')).toBeInTheDocument()
    expect(screen.getByText('Not a final offer')).toBeInTheDocument()
    expect(screen.getByText('€109,500.00')).toBeInTheDocument()
    expect(screen.getByText('evt_preliminary')).toBeInTheDocument()
    expect(screen.getByText('evt_split')).toBeInTheDocument()
    expect(screen.queryByText(/minor_units/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: /Events/ }))
    expect(screen.getByText('Technical event data')).toBeInTheDocument()
    expect(screen.getByText('Package under discussion · Revision 7')).toBeInTheDocument()
  })

  it('shows a sealed benchmark review without review content', async () => {
    sessionStorage.setItem('negotiation.admin-token', 'admin-secret')
    const sealedSummary: AdminSessionSummary = {
      ...summary,
      status: 'walked_away',
      run_mode: 'benchmark',
      review_state: 'sealed',
    }
    vi.mocked(listAdminSessions).mockResolvedValue({
      items: [sealedSummary],
      total: 1,
      limit: 25,
      offset: 0,
    })
    vi.mocked(getAdminSession).mockResolvedValue({
      ...detail,
      ...sealedSummary,
      review: null,
      benchmark_run: {
        benchmark_run_id: 'run_1',
        expected_trials: 2,
        session_count: 1,
        completed_count: 1,
        trial_count: 1,
        release_ready: false,
      },
    })
    const user = userEvent.setup()

    render(<SessionInspector language="en" />)
    expect(await screen.findByText('Administrator access active')).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Годовая аренда офиса' })).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Review' }))

    expect(screen.getByRole('heading', { name: 'Benchmark review sealed' })).toBeInTheDocument()
    expect(screen.queryByText('participant_scores')).not.toBeInTheDocument()
    await waitFor(() => expect(getAdminSession).toHaveBeenCalledTimes(1))
  })
})
