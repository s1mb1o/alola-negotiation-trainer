import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { TermsList } from '../components/TermsList'
import { OfferPanel } from '../components/OfferPanel'
import { supplyProposal, supplyTerms } from './supplyFixtures'

afterEach(cleanup)

describe('supply package display', () => {
  it('keeps composite confirmation terms in a readable single column', () => {
    const { container } = render(<TermsList terms={supplyTerms} locale="en-US" compact />)
    expect(container.querySelector('.terms-list')).not.toHaveClass('compact')
  })

  it('renders exact money, lot windows, advances and reserve outcomes in Russian', () => {
    const { container } = render(<TermsList terms={supplyTerms} locale="ru-RU" />)
    expect(screen.getByText(/109.*500,00.*€/)).toBeInTheDocument()
    expect(screen.getByText('10 шт.')).toBeInTheDocument()
    expect(screen.getByText('90 шт.')).toBeInTheDocument()
    expect(screen.getByText(/5 ноября 2026.*7 ноября 2026/)).toBeInTheDocument()
    expect(screen.getByText('Предоплата: 100%')).toBeInTheDocument()
    expect(screen.getByText('Предоплата: 50%')).toBeInTheDocument()
    expect(screen.getByText('Остаток: через 30 дней после поставки партии')).toBeInTheDocument()
    expect(screen.getByText(/3 шт./)).toBeInTheDocument()
    expect(screen.getByText(/Неиспользованный резерв оплачивается 2 декабря 2026/)).toBeInTheDocument()
    expect(screen.getByText(/аппаратная неисправность или ремонт поставщиком/)).toBeInTheDocument()
    expect(screen.getByText(/без аппаратного дефекта: резерв оплачивается/)).toBeInTheDocument()
    expect(screen.getByText(/Неясный результат диагностики.*платёж не возникает/)).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/minor_units|advance_bps|diagnosis_policy_id|\{"/)
  })

  it('renders the English package and never mistakes reserve units for the main order', () => {
    const { container } = render(<TermsList terms={supplyTerms} locale="en-US" />)
    expect(screen.getByText('€109,500.00')).toBeInTheDocument()
    expect(screen.getByText('November 5, 2026 — November 7, 2026')).toBeInTheDocument()
    expect(screen.getByText(/3 units/)).toBeInTheDocument()
    expect(screen.getByText(/in addition to the main order/)).toBeInTheDocument()
    expect(screen.getByText(/A hardware defect takes precedence/)).toBeInTheDocument()
    expect(container.textContent).not.toContain('103 units')
    expect(container.textContent).not.toContain('vector_site')
  })

  it('keeps missing nested payments unknown and preserves a real zero advance', () => {
    render(<TermsList terms={{ payment_schedule: [{ lot_id: 'early' }, { lot_id: 'remaining', advance_bps: 0 }] }} locale="en-US" />)
    const lots = screen.getAllByRole('listitem')
    expect(within(lots[0]).getByText('Advance payment: Not specified')).toBeInTheDocument()
    expect(within(lots[0]).queryByText(/0%/)).not.toBeInTheDocument()
    expect(within(lots[1]).getByText('Advance payment: 0%')).toBeInTheDocument()
    expect(screen.getAllByText('Balance: Not specified')).toHaveLength(2)
    expect(screen.queryByText(/No additional reserve/)).not.toBeInTheDocument()
  })

  it('requires an explicit reserve mode and diagnostic policy', () => {
    const { rerender } = render(<TermsList terms={{ reserve_policy: {} }} locale="en-US" />)
    expect(screen.getByText('Not specified')).toBeInTheDocument()
    expect(screen.queryByText(/free replacement/)).not.toBeInTheDocument()
    rerender(<TermsList terms={{ reserve_policy: { mode: 'none' } }} locale="en-US" />)
    expect(screen.getByText('No additional reserve devices')).toBeInTheDocument()
  })

  it('renders complete preliminary packages as non-binding with no acceptance control', () => {
    render(<OfferPanel language="en" offers={[]} preliminaryProposals={[supplyProposal]} />)
    expect(screen.getByRole('heading', { name: 'Package under discussion' })).toBeInTheDocument()
    expect(screen.getByText('Not a final offer')).toBeInTheDocument()
    expect(screen.getByText(/Even a complete package remains under discussion/)).toHaveClass('explanatory-copy')
    expect(screen.getByText('Revision 7')).toBeInTheDocument()
    expect(screen.getByText('evt_split')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /accept|confirm|publish/i })).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Active offer' })).not.toBeInTheDocument()
  })

  it('renders nested unresolved paths as readable labels without creating values', () => {
    render(<OfferPanel language="ru" offers={[]} preliminaryProposals={[{
      ...supplyProposal, terms: { base_price: supplyTerms.base_price },
      unresolved_required_terms: ['payment_schedule.early.advance_bps', 'reserve_policy'],
    }]} />)
    expect(screen.getByText('Оплата по партиям · Первая партия · Предоплата')).toBeInTheDocument()
    expect(screen.getByText('Резерв для замены')).toBeInTheDocument()
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
    expect(screen.queryByText(/Без дополнительных/)).not.toBeInTheDocument()
  })
})
