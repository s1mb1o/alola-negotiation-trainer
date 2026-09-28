import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ProtocolNotice } from '../components/ProtocolNotice'

afterEach(cleanup)

describe('ProtocolNotice', () => {
  it('shows an explicit clarification result', () => {
    render(
      <ProtocolNotice
        language="ru"
        clarification={{ question: 'Вы принимаете всё предложение?' }}
        busy={false}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByText('Нужно уточнение')).toBeInTheDocument()
    expect(screen.getByText('Вы принимаете всё предложение?')).toBeInTheDocument()
  })

  it('shows the bounded training recovery format', () => {
    render(
      <ProtocolNotice
        language="ru"
        clarification={{
          question: 'Уточните условия.',
          recovery: {
            version: 'training-clarification-v1',
            example: 'Например: «Предлагаю цену 110 000 EUR».',
            end_session_message: 'Прекращаю переговоры.',
          },
        }}
        busy={false}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByText('Поддерживаемый формат')).toBeInTheDocument()
    expect(screen.getByText('Например: «Предлагаю цену 110 000 EUR».')).toBeInTheDocument()
    expect(screen.getByText(/Прекращаю переговоры/)).toBeInTheDocument()
  })

  it('requires an explicit confirmation callback', async () => {
    const user = userEvent.setup()
    const onConfirm = vi.fn()
    render(
      <ProtocolNotice
        language="en"
        confirmation={{ offer_id: 'offer_1', offer_revision: 2, terms: { price: 100_000 } }}
        busy={false}
        onConfirm={onConfirm}
        onCancel={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'I fully confirm' }))
    expect(onConfirm).toHaveBeenCalledOnce()
    expect(screen.getByText('Revision 2')).toBeInTheDocument()
    expect(screen.queryByText(/offer_1/)).not.toBeInTheDocument()
  })

  it('shows the binding terms with the session currency and explicit zero shares', () => {
    render(
      <ProtocolNotice
        language="ru"
        currency="EUR"
        confirmation={{
          offer_id: 'offer_3',
          offer_revision: 4,
          terms: { price: 109_500, prepayment_fraction: 0, delivery_weeks: 3 },
        }}
        busy={false}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByText(/109.*500.*€/)).toBeInTheDocument()
    expect(screen.getByText('0%')).toBeInTheDocument()
    expect(screen.getByText('Редакция 4')).toBeInTheDocument()
    expect(screen.queryByText(/offer_3/)).not.toBeInTheDocument()
  })

  it('localizes structured offer terms in Russian', () => {
    render(
      <ProtocolNotice
        language="ru"
        confirmation={{ offer_id: 'offer_2', offer_revision: 1, terms: { price: 100_000, delivery_weeks: 3 } }}
        busy={false}
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
      />,
    )

    expect(screen.getByText('Цена')).toBeInTheDocument()
    expect(screen.getByText('Срок поставки')).toBeInTheDocument()
    expect(screen.getByText('3 недели')).toBeInTheDocument()
  })
})
