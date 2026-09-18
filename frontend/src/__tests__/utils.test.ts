import { beforeEach, describe, expect, it } from 'vitest'
import type { SessionEnvelope, SessionReview } from '../types'
import {
  ACTIVE_SESSION_KEY,
  aggregateReviewHistory,
  clearActiveSession,
  extractParticipantToken,
  extractTimeline,
  formatTermValueForKey,
  readActiveSession,
  storeActiveSession,
  storeReview,
} from '../utils'

describe('term formatting', () => {
  it('renders explicit zero and full prepayment shares as percentages', () => {
    expect(formatTermValueForKey('prepayment_fraction', 0, 'ru-RU')).toBe('0%')
    expect(formatTermValueForKey('prepayment_fraction', 1, 'ru-RU')).toBe('100%')
    expect(formatTermValueForKey('prepayment_fraction', 0.5, 'en-US')).toBe('50%')
    expect(formatTermValueForKey('price', 109_500, 'ru-RU', 'EUR')).toMatch(/109.*500.*€/)
  })
})

describe('active session persistence', () => {
  beforeEach(() => sessionStorage.clear())

  it('round-trips the stored session identity and clears it', () => {
    storeActiveSession({
      session_id: 'sess_1',
      role_id: 'buyer',
      session_language: 'ru',
      scenario: { scenario_id: 'supplier_001', version: 3, title: 'Поставка' },
      difficulty: 'normal',
      hints_enabled: true,
      revision: 4,
    })

    expect(readActiveSession()).toMatchObject({ session_id: 'sess_1', role_id: 'buyer', revision: 4 })
    clearActiveSession()
    expect(readActiveSession()).toBeUndefined()
    expect(sessionStorage.getItem(ACTIVE_SESSION_KEY)).toBeNull()
  })

  it('ignores a malformed stored identity', () => {
    sessionStorage.setItem(ACTIVE_SESSION_KEY, '{"session_id": 1}')
    expect(readActiveSession()).toBeUndefined()
    sessionStorage.setItem(ACTIVE_SESSION_KEY, 'not json')
    expect(readActiveSession()).toBeUndefined()
  })
})

describe('participant credentials', () => {
  it('selects the preferred role token', () => {
    const response = {
      session_id: 's1',
      revision: 0,
      status: 'active',
      observation: {},
      participants: [
        { role: 'seller', token: 'seller-token' },
        { role: 'buyer', access_token: 'buyer-token' },
      ],
    } satisfies SessionEnvelope

    expect(extractParticipantToken(response, 'buyer')).toBe('buyer-token')
  })

  it('reads the one-time participant credential envelope', () => {
    const response = {
      session_id: 's2',
      revision: 0,
      status: 'active',
      observation: {},
      participant_credentials: [
        { role: 'seller', token: 'seller-token' },
        { role: 'buyer', token: 'buyer-token' },
      ],
    } satisfies SessionEnvelope

    expect(extractParticipantToken(response, 'buyer')).toBe('buyer-token')
  })
})

describe('session timeline', () => {
  it('renders an Easy revision-zero opponent opening without a fake committed turn', () => {
    const response = {
      session_id: 's-easy',
      revision: 0,
      status: 'active',
      next_actor: 'participant_buyer',
      substantive_turn_count: 0,
      committed_actions: [],
      observation: {
        conversation: [{
          revision: 0,
          participant_id: 'participant_seller',
          role: 'seller',
          message: 'Добрый день. Моё начальное предложение: цена 120 000 EUR.',
        }],
      },
    } satisfies SessionEnvelope

    expect(extractTimeline(response)).toEqual([expect.objectContaining({
      participantId: 'participant_seller',
      role: 'seller',
      text: 'Добрый день. Моё начальное предложение: цена 120 000 EUR.',
    })])
  })
})

describe('local review aggregation', () => {
  beforeEach(() => localStorage.clear())

  it('aggregates stored outcomes and normalized skill values', () => {
    const review: SessionReview = {
      outcome: { agreement: true, termination_reason: 'agreement_reached', pareto_efficiency: 0.8 },
      outcome_score: 82,
      skills: { probing: 0.7, value_creation: 0.9 },
    }
    storeReview('s1', 'Supplier', review)

    const stats = aggregateReviewHistory()

    expect(stats.sessions).toBe(1)
    expect(stats.agreements).toBe(1)
    expect(stats.average_outcome).toBe(82)
    expect(stats.average_skills.probing).toBe(0.7)
  })
})
