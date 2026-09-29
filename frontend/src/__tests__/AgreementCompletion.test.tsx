import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NegotiationWorkspace } from '../components/NegotiationWorkspace'
import type { SessionEnvelope, TimelineMessage, UiLanguage } from '../types'

const session: SessionEnvelope = {
  session_id: 'agreement-session', status: 'agreement_reached', revision: 4, language: 'ru',
  observation: { conversation: [] },
  committed_actions: [{ participant_id: 'npc', action: 'accept' }],
}
const messages: TimelineMessage[] = [{ id: 'final', participantId: 'npc', role: 'seller', action: 'accept',
  text: 'Принимаю полное предложение: годовая аренда 2 600 000 ₽, предоплата 60%, готовность через 4 недели.' }]
const onSend = vi.fn()

function workspace(current = session, language: UiLanguage = 'ru', transcript = messages) {
  return <NegotiationWorkspace language={language} session={current} messages={transcript} token="token"
    ownParticipantId="player" ownRoleId="buyer" scenarioTitle="Office lease" hintsEnabled={false}
    busy={false} requestingHint={false} reviewLoading={false} review={{ outcome: { agreement: current.status === 'agreement_reached' } }}
    onSend={onSend} onRequestHint={vi.fn()} onTokenChange={vi.fn()} onRetryReview={vi.fn()} onNewSession={vi.fn()} />
}

beforeEach(() => { sessionStorage.clear(); vi.clearAllMocks() })
afterEach(cleanup)

describe('agreement completion', () => {
  it('keeps the final message and opens analysis only on request', async () => {
    const user = userEvent.setup()
    const view = render(workspace())
    const dialog = screen.getByRole('dialog', { name: 'Контрагент принял ваши условия' })
    expect(screen.getByText(messages[0].text)).toBeInTheDocument()
    expect(screen.queryByText('Разбор результата')).not.toBeInTheDocument()
    expect(dialog).toHaveFocus()
    await user.click(within(dialog).getByRole('button', { name: 'Посмотреть договорённость' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText(messages[0].text)).toBeInTheDocument()
    view.rerender(workspace({ ...session, revision: 5 }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Перейти к разбору' }))
    expect(screen.getByText('Разбор результата')).toBeInTheDocument()
    expect(onSend).not.toHaveBeenCalled()
  })

  it('opens the review directly from the dialog and retains the transcript', async () => {
    const user = userEvent.setup()
    render(workspace())
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Перейти к разбору' }))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('Разбор результата')).toBeInTheDocument()
    expect(screen.getByText(messages[0].text)).toBeInTheDocument()
    expect(onSend).not.toHaveBeenCalled()
  })

  it('contains keyboard focus and Escape leaves the completed conversation visible', async () => {
    const user = userEvent.setup()
    render(workspace())
    const dialog = screen.getByRole('dialog')
    await user.tab({ shift: true })
    expect(within(dialog).getByRole('button', { name: 'Перейти к разбору' })).toHaveFocus()
    await user.tab()
    expect(within(dialog).getByRole('button', { name: 'Закрыть' })).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Перейти к разбору' })).toHaveFocus()
    expect(screen.queryByText('Разбор результата')).not.toBeInTheDocument()
  })

  it('remembers dismissal after remount but keeps a different session independent', async () => {
    const user = userEvent.setup()
    const view = render(workspace())
    await user.keyboard('{Escape}')
    view.unmount()
    const restored = render(workspace())
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    restored.rerender(workspace({ ...session, session_id: 'another-session' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('uses a neutral English title after player confirmation or restoration without acceptance evidence', () => {
    render(workspace({ ...session, committed_actions: [{ participant_id: 'player', action: 'accept' }] }, 'en', []))
    const dialog = screen.getByRole('dialog', { name: 'Agreement reached' })
    expect(within(dialog).getByRole('button', { name: 'View agreement' })).toBeInTheDocument()
    expect(screen.queryByText('The counterpart accepted your terms')).not.toBeInTheDocument()
  })

  it('does not announce acceptance for a walk-away', () => {
    render(workspace({ ...session, status: 'walked_away', committed_actions: [] }, 'ru', []))
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('Разбор результата')).toBeInTheDocument()
  })
})
