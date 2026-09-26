import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { ComponentProps } from 'react'
import { ContextPanel } from '../components/ContextPanel'
import { RoleBriefContent } from '../components/RoleBriefContent'

afterEach(cleanup)

function BriefAndSupport(props: ComponentProps<typeof ContextPanel>) {
  return <>
    <RoleBriefContent language={props.language} brief={props.observation.role_brief}
      currency={props.observation.currency} contextItems={props.observation.context} />
    <ContextPanel {...props} />
  </>
}


describe('Role brief and training support', () => {
  it.each([
    ['ru', 'Максимальная сумма к оплате по договору', 'Минимальная цена основной партии', 'Цена основной партии', 'Партии и сроки поставки', 'Оплата по партиям', 'Резерв для замены'],
    ['en', 'Maximum total contractual payment', 'Minimum main order price', 'Main order price', 'Delivery lots and dates', 'Payment by lot', 'Replacement reserve'],
  ] as const)('localizes supply limits and priorities across the %s brief and assistance', (language, limit, floor, price, delivery, payment, reserve) => {
    const priorities = ['base_price', 'delivery_lots', 'payment_schedule', 'reserve_policy']
    const { container } = render(<BriefAndSupport language={language} hintsEnabled requestingHint={false} onRequestHint={vi.fn()}
      observation={{ currency: 'EUR', negotiation_contract_version: 'supply-package-v1',
        role_brief: { constraints: { maximum_total_liability: 115000, minimum_base_price: 103000 }, priorities },
        assistance: { own_priorities: priorities },
      }} />)
    expect(screen.getByText(limit)).toBeInTheDocument()
    expect(screen.getByText(floor)).toBeInTheDocument()
    expect(screen.getByText(language === 'ru' ? /115.*000.*€/ : '€115,000')).toBeInTheDocument()
    expect(screen.getByText(language === 'ru' ? /103.*000.*€/ : '€103,000')).toBeInTheDocument()
    for (const label of [price, delivery, payment, reserve]) expect(screen.getAllByText(label)).toHaveLength(2)
    expect(container.textContent).not.toMatch(/maximum_total_liability|minimum_base_price|base_price|payment_schedule|delivery_lots|reserve_policy/)
    expect(container.textContent).not.toMatch(/Maximum Total Liability|Base Price|Delivery Lots|Reserve Policy|Payment Schedule/)
  })

  it('renders backend coaching, signals, and persisted hints', () => {
    render(
      <BriefAndSupport
        language="ru"
        hintsEnabled
        requestingHint={false}
        onRequestHint={vi.fn()}
        observation={{
          role_brief: 'Контекст роли',
          assistance: {
            coaching: 'Проверьте интерес вопросом.',
            detected_signals: ['price_terms_repeated'],
            own_priorities: ['delivery_weeks'],
            probable_interests: ['payment_terms'],
          },
          context: [{ id: 'expert-1', type: 'distractor', content: 'Рыночный слух без подтверждения.' }],
          hints: [{ id: 'hint-1', text: 'Сформулируйте условный обмен.' }],
        }}
      />,
    )

    expect(screen.getByText('Проверьте интерес вопросом.')).toBeInTheDocument()
    expect(screen.getByText('Цена упоминается повторно')).toBeInTheDocument()
    expect(screen.getByText('Сформулируйте условный обмен.')).toBeInTheDocument()
    expect(screen.getByText('Срок поставки')).toBeInTheDocument()
    expect(screen.getByText('Условия оплаты')).toBeInTheDocument()
    expect(screen.getByText('Рыночный слух без подтверждения.')).toBeInTheDocument()
  })

  it('renders a structured Russian role brief as localized sections', () => {
    render(
      <BriefAndSupport
        language="ru"
        hintsEnabled={false}
        requestingHint={false}
        onRequestHint={vi.fn()}
        observation={{
          currency: 'RUB',
          role_brief: {
            summary: 'Вы представляете компанию АО Городские Пространства.',
            objectives: ['Сдать свободный офис в аренду на год по приемлемой ставке.'],
            context: 'Пока офис пустует, компания теряет арендный доход. Предоплата снижает риск задержки платежей.',
            batna: 'Продолжить поиск арендатора в следующем квартале.',
            constraints: { minimum_annual_rent: 2_100_000 },
            priorities: ['annual_rent', 'prepayment_fraction', 'office_readiness_weeks'],
          },
        }}
      />,
    )

    expect(screen.getByText('Цель')).toBeInTheDocument()
    expect(screen.getByText('Исходная ситуация')).toBeInTheDocument()
    expect(screen.getByText('Альтернатива без сделки (BATNA)')).toBeInTheDocument()
    expect(screen.getByText('Границы сделки')).toBeInTheDocument()
    expect(screen.getByText('Минимальная годовая арендная плата')).toBeInTheDocument()
    expect(screen.getByText(/2.*100.*000.*₽/)).toBeInTheDocument()
    expect(screen.getByText('Приоритеты по убыванию')).toBeInTheDocument()
    expect(screen.getByText('Годовая арендная плата')).toBeInTheDocument()
    expect(screen.getByText('Доля предоплаты')).toBeInTheDocument()
    expect(screen.getByText('Срок готовности офиса к въезду')).toBeInTheDocument()
  })

  it('renders the structured role brief in English', () => {
    render(
      <BriefAndSupport
        language="en"
        hintsEnabled={false}
        requestingHint={false}
        onRequestHint={vi.fn()}
        observation={{
          currency: 'RUB',
          role_brief: {
            summary: 'You represent Urban Spaces JSC.',
            objectives: ['Lease the vacant office at a sustainable annual rate.'],
            context: 'Vacancy is expensive.',
            batna: 'Continue the tenant search next quarter.',
            constraints: { minimum_annual_rent: 2_100_000 },
            priorities: ['annual_rent'],
          },
        }}
      />,
    )

    expect(screen.getByText('Objective')).toBeInTheDocument()
    expect(screen.getByText('Starting situation')).toBeInTheDocument()
    expect(screen.getByText('No-deal alternative (BATNA)')).toBeInTheDocument()
    expect(screen.getByText('Deal limits')).toBeInTheDocument()
    expect(screen.getByText('Minimum annual rent')).toBeInTheDocument()
    expect(screen.getByText(/RUB.*2,100,000/)).toBeInTheDocument()
    expect(screen.getByText('Priorities, highest first')).toBeInTheDocument()
  })

  it('converts the legacy Russian role brief into human-readable sections', () => {
    const legacy = 'Вы представляете компанию АО Городские Пространства. '
      + 'Ваша цель: Сдать свободный офис на год. '
      + 'Ваш контекст: Пустующий офис приносит убытки. '
      + 'Ваша BATNA: Продолжить поиск арендатора. '
      + 'Ваши ограничения: {"minimum_price": 2100000} '
      + 'Ваши приоритеты по убыванию: price, prepayment_fraction, delivery_weeks.'
    const { container } = render(
      <BriefAndSupport
        language="ru"
        hintsEnabled={false}
        requestingHint={false}
        onRequestHint={vi.fn()}
        observation={{ currency: 'RUB', role_brief: legacy }}
      />,
    )

    expect(screen.getByText('Цель')).toBeInTheDocument()
    expect(screen.getByText('Минимальная годовая арендная плата')).toBeInTheDocument()
    expect(screen.getByText(/2.*100.*000.*₽/)).toBeInTheDocument()
    expect(screen.getByText('Годовая арендная плата')).toBeInTheDocument()
    expect(screen.getByText('Срок готовности офиса к въезду')).toBeInTheDocument()
    expect(container.textContent).not.toContain('Срок поставки')
    expect(container.textContent).not.toContain('{')
    expect(container.textContent).not.toContain('minimum_price')
    expect(container.textContent).not.toContain('prepayment_fraction')
    expect(container.textContent).not.toContain('delivery_weeks')
  })
})
