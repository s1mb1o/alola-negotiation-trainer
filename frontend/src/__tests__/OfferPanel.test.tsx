import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { OfferPanel } from '../components/OfferPanel'

afterEach(cleanup)

describe('OfferPanel', () => {
  it('shows a partial Russian opening position without invented values', () => {
    render(
      <OfferPanel
        language="ru"
        currency="EUR"
        offers={[{
          offer_id: 'offer_supplier',
          offer_revision: 1,
          proposer_role: 'seller',
          terms: { price: 120_000 },
          unresolved_required_terms: ['prepayment_fraction', 'delivery_weeks'],
        }]}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Начальная позиция' })).toBeInTheDocument()
    expect(screen.getByText(/Ещё не согласовано/)).toBeInTheDocument()
    expect(screen.getByText('Доля предоплаты')).toBeInTheDocument()
    expect(screen.getByText('Срок поставки')).toBeInTheDocument()
    expect(screen.getByText(/120.*000.*€/)).toBeInTheDocument()
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Активное предложение' })).not.toBeInTheDocument()
  })

  it('keeps a complete English offer labeled as an active offer', () => {
    render(
      <OfferPanel
        language="en"
        currency="RUB"
        offers={[{
          offer_id: 'offer_freight',
          offer_revision: 1,
          proposer_role: 'seller',
          terms: { price: 480_000, prepayment_fraction: 0.4, delivery_weeks: 6 },
          unresolved_required_terms: [],
        }]}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Active offer' })).toBeInTheDocument()
    expect(screen.queryByText('Not agreed yet')).not.toBeInTheDocument()
  })
})
