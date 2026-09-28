import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ReviewPanel } from '../components/ReviewPanel'

afterEach(cleanup)

describe('ReviewPanel', () => {
  it('renders key-moment details and localized recommendations', () => {
    render(
      <ReviewPanel
        language="ru"
        status="agreement_reached"
        loading={false}
        onRetry={vi.fn()}
        onNewSession={vi.fn()}
        review={{
          outcome: { agreement: true, termination_reason: 'agreement_reached' },
          outcome_score: 82,
          skills: { clarity: 70 },
          key_moments: [{
            event_id: 'evt_1',
            type: 'offer.countered',
            summary: 'Вы предложили встречные условия.',
            detail: '«109 500 €, предоплата 50 %»',
          }],
          recommendations: [
            { skill: 'probing', text: 'Задавайте больше вопросов об интересах оппонента.' },
            { skill: 'custom_skill', text: 'Проверяйте допущения перед уступкой.' },
          ],
        }}
      />,
    )

    expect(screen.getByText('Вы предложили встречные условия.')).toBeInTheDocument()
    expect(screen.getByText('«109 500 €, предоплата 50 %»')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Рекомендации' })).toBeInTheDocument()
    expect(screen.getByText('Выявление интересов')).toBeInTheDocument()
    expect(screen.getByText('Задавайте больше вопросов об интересах оппонента.')).toBeInTheDocument()
    expect(screen.getByText('custom_skill')).toBeInTheDocument()
    expect(screen.getByText('Проверяйте допущения перед уступкой.')).toBeInTheDocument()
  })

  it('renders an older review payload without details or recommendations', () => {
    render(
      <ReviewPanel
        language="en"
        status="walked_away"
        loading={false}
        onRetry={vi.fn()}
        onNewSession={vi.fn()}
        review={{
          outcome: { agreement: false, termination_reason: 'walked_away' },
          key_moments: [{ event_id: 'evt_1', type: 'offer.created', summary: 'The session recorded offer.created.' }],
        }}
      />,
    )

    expect(screen.getByText('The session recorded offer.created.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Recommendations' })).not.toBeInTheDocument()
  })

  it('does not show an award for a deal below BATNA or reservation', () => {
    const { container } = render(
      <ReviewPanel
        language="en"
        status="agreement_reached"
        loading={false}
        onRetry={vi.fn()}
        onNewSession={vi.fn()}
        review={{
          outcome: { agreement: true, termination_reason: 'agreement_reached' },
          training: {
            preparation: { target: '', unacceptable_result: '', available_trades: '', information_to_discover: '', targets: [] },
            goal_comparison: [],
            initial_social: {},
            final_social: {},
            offer_history: [],
            evidence: [],
            checkpoints: [],
            informed_practice: false,
            skill_scores_validated: false,
            coaching: { status: 'unavailable' },
            methodology: {
              version: 'harvard-batna-voss-v1',
              economics: { outcome: 'agreement', surplus_over_batna: -4, margin_over_reservation: -2, meets_reservation: false },
              zopa: 'not_inferred',
            },
          },
        }}
      />,
    )

    expect(container.querySelector('.lucide-award')).not.toBeInTheDocument()
    expect(container.querySelector('.lucide-triangle-alert')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Heuristic diagnostics' })).not.toBeInTheDocument()
  })
})
