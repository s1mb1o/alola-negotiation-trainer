import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { TokenDialog } from '../components/TokenDialog'

afterEach(cleanup)

describe('TokenDialog', () => {
  it('moves focus into the dialog and closes on Escape', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    render(
      <TokenDialog
        open
        language="ru"
        token=""
        sessionId="sess_dialog"
        onClose={onClose}
        onSave={vi.fn()}
      />,
    )

    expect(screen.getByRole('dialog', { name: 'Доступ' })).toBeInTheDocument()
    expect(screen.getByPlaceholderText('Нет токена')).toHaveFocus()

    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('renders nothing while closed', () => {
    render(
      <TokenDialog
        open={false}
        language="en"
        token="secret"
        sessionId="sess_dialog"
        onClose={vi.fn()}
        onSave={vi.fn()}
      />,
    )

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
