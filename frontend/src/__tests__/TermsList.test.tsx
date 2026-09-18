import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { TermsList } from '../components/TermsList'

afterEach(cleanup)

describe('TermsList', () => {
  it('formats the Russian office-lease terms for people', () => {
    render(
      <TermsList
        terms={{
          annual_rent: 2_400_000,
          prepayment_fraction: 0.5,
          office_readiness_weeks: 6,
        }}
        locale="ru-RU"
        currency="RUB"
      />,
    )

    expect(screen.getByText('Годовая арендная плата')).toBeInTheDocument()
    expect(screen.getByText(/2.*400.*000.*₽/)).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByText('6 недель')).toBeInTheDocument()
    expect(screen.getByText('Срок готовности офиса к въезду')).toBeInTheDocument()
  })

  it('formats the English office-lease terms for people', () => {
    render(
      <TermsList
        terms={{ annual_rent: 2_400_000, office_readiness_weeks: 1 }}
        locale="en-US"
        currency="RUB"
      />,
    )

    expect(screen.getByText('Annual rent')).toBeInTheDocument()
    expect(screen.getByText(/RUB.*2,400,000/)).toBeInTheDocument()
    expect(screen.getByText('1 week')).toBeInTheDocument()
    expect(screen.getByText('Office readiness for move-in')).toBeInTheDocument()
  })
})
