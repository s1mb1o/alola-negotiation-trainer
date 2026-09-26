import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SocialIndicators } from '../components/SocialIndicators'

const state = {
  values: { rapport: 42, credibility: 65, tension: 18, patience: 77 },
  delta: { rapport: -3, credibility: 2, tension: -4, patience: 0 },
  source_revision: 3,
}

describe('SocialIndicators', () => {
  it('shows all axes, current meter values, and signed latest deltas in Russian', () => {
    render(<SocialIndicators language="ru" state={state} />)

    expect(screen.getByRole('heading', { name: 'Состояние контакта' })).toBeInTheDocument()
    expect(screen.getByRole('meter', { name: 'Контакт' })).toHaveAttribute('aria-valuenow', '42')
    expect(screen.getByRole('meter', { name: 'Доверие к словам' })).toHaveAttribute('aria-valuenow', '65')
    expect(screen.getByRole('meter', { name: 'Напряжение' })).toHaveAttribute('aria-valuenow', '18')
    expect(screen.getByRole('meter', { name: 'Терпение' })).toHaveAttribute('aria-valuenow', '77')
    expect(screen.getByLabelText('Контакт: текущее значение 42')).toHaveTextContent('42')
    expect(screen.getByLabelText('Доверие к словам: текущее значение 65')).toHaveTextContent('65')
    expect(screen.getByLabelText('Контакт: изменение −3')).toHaveTextContent('Δ −3')
    expect(screen.getByLabelText('Доверие к словам: изменение +2')).toHaveTextContent('Δ +2')
    expect(screen.getByLabelText('Напряжение: изменение −4')).toHaveClass('social-axis-delta-beneficial')
    expect(screen.getByLabelText('Терпение: изменение 0')).toHaveTextContent('Δ 0')
  })

  it('uses English labels and stays absent without an owner projection', () => {
    const { rerender } = render(<SocialIndicators language="en" state={state} />)
    expect(screen.getByRole('heading', { name: 'Counterpart state' })).toBeInTheDocument()
    expect(screen.getByRole('meter', { name: 'Credibility' })).toBeInTheDocument()
    rerender(<SocialIndicators language="en" />)
    expect(screen.queryByRole('heading', { name: 'Counterpart state' })).not.toBeInTheDocument()
  })
})
