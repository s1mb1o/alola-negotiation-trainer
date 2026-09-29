import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AppHeader } from '../components/AppHeader'

describe('AppHeader preferences', () => {
  it('exposes Russian and English UI controls and all theme modes', async () => {
    const user = userEvent.setup()
    const onLanguageChange = vi.fn()
    const onThemeChange = vi.fn()
    const onViewChange = vi.fn()

    render(
      <AppHeader
        language="ru"
        theme="system"
        activeView="training"
        hasSession={false}
        onLanguageChange={onLanguageChange}
        onThemeChange={onThemeChange}
        onViewChange={onViewChange}
        onNewSession={vi.fn()}
      />,
    )

    await user.click(screen.getByRole('button', { name: 'EN' }))
    await user.click(screen.getByRole('link', { name: 'Прогресс' }))
    await user.selectOptions(screen.getByRole('combobox', { name: 'Тема: Системная' }), 'dark')

    expect(onLanguageChange).toHaveBeenCalledWith('en')
    expect(screen.getByRole('link', { name: 'Тренировка' })).toHaveAttribute('href', '/app/training')
    expect(screen.getByRole('link', { name: 'Прогресс' })).toHaveAttribute('href', '/app/progress')
    expect(screen.getByRole('link', { name: 'Сессии' })).toHaveAttribute('href', '/app/inspector')
    expect(screen.getByRole('link', { name: 'Настройка NPC' })).toHaveAttribute('href', '/app/admin')
    expect(onViewChange).toHaveBeenCalledWith('stats')
    expect(onThemeChange).toHaveBeenCalledWith('dark')
    expect(screen.getByRole('option', { name: 'Светлая' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Тёмная' })).toBeInTheDocument()
  })
})
