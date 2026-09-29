import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AdminContextSetup } from '../components/AdminContextSetup'
import { ApiError, listAdminTrainingPresets } from '../api'
import type { AdminTrainingPreset } from '../types'

vi.mock('../api', async importOriginal => ({
  ...await importOriginal<typeof import('../api')>(), listAdminTrainingPresets: vi.fn(),
}))
const catalog: AdminTrainingPreset[] = ['equipment', 'software'].flatMap(domain =>
  ['buyer', 'seller'].flatMap(role => [1, 2].map(version => ({
    preset_id: `${domain}-${role}-${version}`, domain_id: domain, domain,
    topic_id: domain, topic: `${domain} topic`, npc_role: role,
    npc_goal: `Private ${domain} ${role} goal ${version}`,
    scenario: { scenario_id: `${domain}-${version}`, version, title: `Case ${version}`,
      languages: ['ru'], roles: [{ role_id: 'buyer', title: 'Buyer' }, { role_id: 'seller', title: 'Seller' }] },
  }))),
)
const props = { language: 'ru' as const, creating: false, hasActiveSession: false, onStart: vi.fn() }

beforeEach(() => {
  vi.clearAllMocks()
  sessionStorage.clear()
  vi.mocked(listAdminTrainingPresets).mockResolvedValue(catalog)
})
afterEach(cleanup)

describe('administrator context setup', () => {
  it('requires an explicit credential and localizes the login screen', async () => {
    const user = userEvent.setup()
    render(<AdminContextSetup {...props} language="en" />)
    expect(listAdminTrainingPresets).not.toHaveBeenCalled()
    await user.type(screen.getByLabelText('Administrator token'), 'admin-test-only')
    await user.click(screen.getByRole('button', { name: 'Connect' }))
    await screen.findByLabelText('Counterpart tone')
    expect(listAdminTrainingPresets).toHaveBeenCalledWith('en', 'admin-test-only')
    expect(screen.getAllByRole('combobox')).toHaveLength(6)
    expect(screen.getByLabelText('NPC goal — authored preset')).toBeInTheDocument()
  })

  it('selects a real bundle and clears privileged data before the player handoff', async () => {
    sessionStorage.setItem('negotiation.admin-token', 'admin-test-only')
    const onStart = vi.fn(setup => {
      expect(sessionStorage.getItem('negotiation.admin-token')).toBeNull()
      expect(JSON.stringify(setup)).not.toMatch(/Private|admin-test-only|npc_goal/)
    })
    const user = userEvent.setup()
    render(<AdminContextSetup {...props} onStart={onStart} />)
    await screen.findByLabelText('Сфера')
    await user.selectOptions(screen.getByLabelText('Сфера'), 'software')
    await user.selectOptions(screen.getByLabelText('Роль собеседника (NPC)'), 'buyer')
    await user.selectOptions(screen.getByLabelText('Цель NPC — готовый пресет'), 'software-buyer-2')
    await user.selectOptions(screen.getByLabelText('Сложность'), 'expert')
    await user.selectOptions(screen.getByLabelText('Тон собеседника'), 'sociable')
    await user.click(screen.getByRole('button', { name: 'Запустить тренировку игрока' }))
    expect(onStart).toHaveBeenCalledWith(expect.objectContaining({
      scenario: expect.objectContaining({ scenario_id: 'software-2', version: 2 }),
      roleId: 'seller', difficulty: 'expert', hintsEnabled: false, participantToken: '',
      training: expect.objectContaining({ profile: 'sociable', authored_tone: true }),
    }))
    expect(screen.queryByText('Private software buyer goal 2')).not.toBeInTheDocument()
  })

  it('does not abandon an active player session', async () => {
    sessionStorage.setItem('negotiation.admin-token', 'admin-test-only')
    render(<AdminContextSetup {...props} hasActiveSession />)
    expect(await screen.findByRole('button', { name: 'Запустить тренировку игрока' })).toBeDisabled()
    expect(props.onStart).not.toHaveBeenCalled()
  })

  it.each([401, 503])('fails closed for catalog HTTP %s', async status => {
    sessionStorage.setItem('negotiation.admin-token', 'admin-test-only')
    vi.mocked(listAdminTrainingPresets).mockRejectedValue(new ApiError(status, { error: 'unavailable' }))
    render(<AdminContextSetup {...props} />)
    await screen.findByRole('alert')
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(props.onStart).not.toHaveBeenCalled()
  })

  it('clears an old catalog when the language changes', async () => {
    sessionStorage.setItem('negotiation.admin-token', 'admin-test-only')
    const { rerender } = render(<AdminContextSetup {...props} />)
    await screen.findByLabelText('Сфера')
    vi.mocked(listAdminTrainingPresets).mockResolvedValue([])
    rerender(<AdminContextSetup {...props} language="en" />)
    await waitFor(() => expect(screen.queryByRole('combobox')).not.toBeInTheDocument())
    expect(await screen.findByText('No published presets for this language.')).toBeInTheDocument()
  })
})
