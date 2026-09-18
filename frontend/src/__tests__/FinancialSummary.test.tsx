import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { FinancialSummary } from '../components/FinancialSummary'
import { ReviewPanel } from '../components/ReviewPanel'
import type { FinancialSummaryView } from '../types'

afterEach(cleanup)

const summary: FinancialSummaryView = {
  currency: 'EUR', base_price_minor: 10_950_000, reserve_unit_price_minor: 109_500,
  reserve_quantity: 3, maximum_reserve_liability_minor: 328_500, maximum_liability_minor: 11_278_500,
  advance_minor: 6_022_500, balance_minor: 4_927_500, weighted_advance_fraction: 0.55,
  lots: [{ lot_id: 'early', quantity: 10, price_minor: 1_095_000, advance_minor: 1_095_000, balance_minor: 0, balance_days: 0 }],
}

describe('financial summary', () => {
  it('displays only the service supplied financial numbers in Russian', () => {
    render(<FinancialSummary language="ru" summary={summary} />)
    expect(screen.getByText('Максимум к оплате по пакету')).toBeInTheDocument()
    expect(screen.getByText(/112.*785,00.*€/)).toBeInTheDocument()
    expect(screen.getByText(/60.*225,00.*€/)).toBeInTheDocument()
    expect(screen.getByText('55 %')).toBeInTheDocument()
    expect(screen.getByText(/Максимум включает оплату всего резерва, если она потребуется/)).toBeInTheDocument()
    expect(screen.queryByText(/utility|maximum_liability_minor/)).not.toBeInTheDocument()
  })

  it('does not fabricate totals or zero advance for an incomplete summary', () => {
    render(<FinancialSummary language="en" summary={{ currency: 'EUR', base_price_minor: 10_950_000 }} />)
    expect(screen.getByText('€109,500.00')).toBeInTheDocument()
    expect(screen.queryByText('Total advance')).not.toBeInTheDocument()
    expect(screen.queryByText('Maximum payable for the package')).not.toBeInTheDocument()
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
  })

  it('does not show a financial card when the service omits it', () => {
    const { container } = render(<FinancialSummary language="en" />)
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the supplied financial summary in the final review', () => {
    render(<ReviewPanel language="en" status="agreement_reached" loading={false}
      review={{ outcome: { agreement: true, financial_summary: summary } }} onRetry={() => {}} onNewSession={() => {}} />)
    expect(screen.getByText('Financial summary')).toBeInTheDocument()
    expect(screen.getByText('€112,785.00')).toBeInTheDocument()
    expect(screen.getByText('55%')).toBeInTheDocument()
  })
})
