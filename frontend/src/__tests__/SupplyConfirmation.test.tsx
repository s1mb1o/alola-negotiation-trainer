import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ChatPanel } from '../components/ChatPanel'
import { ProtocolNotice } from '../components/ProtocolNotice'
import type { SessionLanguage, UiLanguage } from '../types'
import { supplyPublication } from './supplyFixtures'

afterEach(cleanup)

describe('supply final publication', () => {
  it.each([
    ['en', 'ru', 'Publish final offer', 'Подтверждаю окончательное предложение', 'Cancel publication', 'Отменяю подтверждение'],
    ['ru', 'en', 'Опубликовать окончательное предложение', 'I confirm the final offer', 'Отменить публикацию', 'I cancel confirmation'],
  ])('uses the session language for publication with %s UI', async (language, sessionLanguage, confirmLabel, confirmMessage, cancelLabel, cancelMessage) => {
    const user = userEvent.setup()
    const onSend = vi.fn()
    render(<ChatPanel language={language as UiLanguage} sessionLanguage={sessionLanguage as SessionLanguage}
      messages={[]} ownParticipantId="participant_buyer" ownRoleId="buyer" isMyTurn busy={false} terminal={false}
      publication={supplyPublication} onSend={onSend} />)
    await user.click(screen.getByRole('button', { name: confirmLabel }))
    expect(onSend).toHaveBeenLastCalledWith(confirmMessage)
    await user.click(screen.getByRole('button', { name: cancelLabel }))
    expect(onSend).toHaveBeenLastCalledWith(cancelMessage)
  })

  it('shows the exact snapshot and disables incomplete publication', () => {
    render(<ProtocolNotice language="en" publication={{ ...supplyPublication, unresolved_required_terms: ['reserve_policy'] }}
      busy={false} onConfirm={vi.fn()} onCancel={vi.fn()} />)
    expect(screen.getByText('Revision 7')).toBeInTheDocument()
    expect(screen.getByText(/sha256:exact-snapshot/)).toBeInTheDocument()
    expect(screen.getByText('€109,500.00')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Publish final offer' })).toBeDisabled()
    expect(screen.queryByText('Confirm full acceptance')).not.toBeInTheDocument()
  })

  it('does not allow publication outside the participant turn', () => {
    render(<ChatPanel language="en" sessionLanguage="en" messages={[]} ownParticipantId="participant_buyer" ownRoleId="buyer"
      isMyTurn={false} busy={false} terminal={false} publication={supplyPublication} onSend={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Publish final offer' })).toBeDisabled()
  })
})
