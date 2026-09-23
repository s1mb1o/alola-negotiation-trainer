import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useState } from 'react'
import { TrainingSetupFields, defaultTraining } from '../components/TrainingSetupFields'
import { TrainingReviewPanel } from '../components/TrainingReviewPanel'
import { storeReview } from '../utils'
import type { TrainingReview } from '../types'

afterEach(cleanup)

const data: TrainingReview = {
  preparation: { ...defaultTraining().preparation, target: 'Приватная цель' },
  goal_comparison: [{ term_id: 'price', operator: 'lte', value: 100, actual: null, gap: null, status: 'unknown' }],
  initial_social: { rapport: 45 }, final_social: { rapport: 48 }, offer_history: [],
  evidence: [{ ref: 'message:1', source_revision: 1, text: 'Первый вопрос', role: 'buyer', is_player: true }],
  checkpoints: [{ source_revision: 0 }, { source_revision: 2 }], informed_practice: false, skill_scores_validated: false,
  coaching: { status: 'not_requested' },
}

describe('training loop', () => {
  it('keeps shared background and private goals in separate setup fields', async () => {
    const user = userEvent.setup()
    const changed = vi.fn()
    function Form() {
      const [value, setValue] = useState(defaultTraining)
      return <TrainingSetupFields language="ru" value={value} onChange={next => { changed(next); setValue(next) }} />
    }
    render(<Form />)
    await user.type(screen.getByRole('textbox', { name: /Что собеседник знает/ }), 'Общая история')
    await user.click(screen.getByText('Мой план переговоров'))
    await user.type(screen.getByRole('textbox', { name: 'Моя цель' }), 'Скрытая цель')
    expect(changed.mock.lastCall?.[0]).toMatchObject({ shared_background: 'Общая история', preparation: { target: 'Скрытая цель' } })
  })

  it('requests coaching only on click and retries the selected checkpoint', async () => {
    const user = userEvent.setup(), coach = vi.fn(), fork = vi.fn()
    render(<TrainingReviewPanel language="ru" data={data} onCoaching={coach} onFork={fork} />)
    expect(coach).not.toHaveBeenCalled()
    expect(screen.getByText('Нет соглашения')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Получить разбор' }))
    expect(coach).toHaveBeenCalledTimes(1)
    await user.selectOptions(screen.getByRole('combobox', { name: 'Ход для повтора' }), '2')
    await user.click(screen.getByRole('button', { name: 'Начать повтор' }))
    expect(fork).toHaveBeenCalledWith(2)
  })

  it('retains goals and retry when coaching fails', () => {
    render(<TrainingReviewPanel language="en" data={{ ...data, coaching: { status: 'unavailable' } }} />)
    expect(screen.getByText('Приватная цель')).toBeInTheDocument()
    expect(screen.getByText(/LLM coaching is unavailable/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Start retry' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Get coaching' })).not.toBeInTheDocument()
  })

  it('does not persist private plan or transcript in local progress history', () => {
    localStorage.clear()
    storeReview('session', 'Scenario', { outcome: { agreement: false }, training: data })
    expect(JSON.stringify(localStorage)).not.toContain('Приватная цель')
    expect(JSON.stringify(localStorage)).not.toContain('Первый вопрос')
  })

  it('renders exact source evidence as text, including hostile markup', () => {
    render(<TrainingReviewPanel language="ru" data={{ ...data, coaching: {
      status: 'complete', summary: 'Итог', goal_assessment: 'Проверка цели', cards: [{
        observation: 'Наблюдение', recommendation: 'Рекомендация', alternative_phrase: 'Альтернатива', next_practice: 'Практика',
        alternative_is_hypothesis: true, evidence: [{ ...data.evidence[0], text: '<script>alert(1)</script>' }],
      }],
    } }} />)
    expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument()
    expect(document.querySelector('script')).toBeNull()
  })
})
