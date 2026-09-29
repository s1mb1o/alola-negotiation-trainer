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
  it.each(['ru', 'en'] as const)('labels methodology dimensions and evidence limits in %s', language => {
    const cards = (['economics', 'process', 'communication'] as const).map(dimension => ({
      dimension, assessment: 'insufficient_evidence' as const,
      observation: dimension, recommendation: 'Practice', alternative_phrase: 'Question', next_practice: 'Next',
      alternative_is_hypothesis: true, evidence: data.evidence,
    }))
    render(<TrainingReviewPanel language={language} data={{ ...data,
      methodology: { version: 'harvard-batna-voss-v1', zopa: 'not_inferred', economics: {
        outcome: 'agreement', surplus_over_batna: 10, margin_over_reservation: -10, meets_reservation: false,
      } }, coaching: { status: 'complete', summary: 'Summary', cards },
    }} />)
    expect(screen.getByText(language === 'ru' ? 'Сравнение с лучшим вариантом без сделки' : 'Compared with your best option without a deal')).toBeInTheDocument()
    expect(screen.getByText('+10')).toBeInTheDocument()
    expect(screen.getByText('-10')).toBeInTheDocument()
    expect(screen.getByText(language === 'ru' ? 'Сделка хуже минимально приемлемого для вас результата.' : 'The deal is worse than your minimum acceptable result.')).toBeInTheDocument()
    expect(screen.getByText(language === 'ru' ? /не в деньгах и не в процентах/ : /not money or percentages/)).toBeInTheDocument()
    expect(screen.queryByText(/Запас до порога|Margin over reservation/)).not.toBeInTheDocument()
    expect(screen.getByText(/· Harvard/)).toBeInTheDocument()
    expect(screen.getByText(/· Voss/)).toBeInTheDocument()
    expect(screen.getAllByText(language === 'ru' ? /Недостаточно данных для вывода/ : /Insufficient evidence/)).toHaveLength(3)
  })

  it.each([
    ['ru', 20, '+20', 'Сделка лучше минимально приемлемого для вас результата.'],
    ['en', 20, '+20', 'The deal is better than your minimum acceptable result.'],
    ['ru', 0, '0', 'Сделка ровно на минимально приемлемом для вас уровне.'],
    ['en', 0, '0', 'The deal is exactly at your minimum acceptable level.'],
  ] as const)('explains a %s margin of %s without jargon', (language, margin, value, explanation) => {
    render(<TrainingReviewPanel language={language} data={{ ...data, methodology: {
      version: 'harvard-batna-voss-v1', zopa: 'not_inferred', economics: {
        outcome: 'agreement', surplus_over_batna: 5, margin_over_reservation: margin, meets_reservation: true,
      },
    } }} />)
    expect(screen.getByText(value)).toBeInTheDocument()
    expect(screen.getByText(explanation)).toBeInTheDocument()
    expect(screen.getByText(language === 'ru' ? /Это не цель из личного плана/ : /It is not your personal-plan target/)).toBeInTheDocument()
  })

  it('does not invent a minimum comparison when the value is missing', () => {
    render(<TrainingReviewPanel language="ru" data={{ ...data, methodology: {
      version: 'harvard-batna-voss-v1', zopa: 'not_inferred', economics: {
        outcome: 'agreement', surplus_over_batna: 5, margin_over_reservation: null, meets_reservation: null,
      },
    } }} />)
    expect(screen.queryByText(/Сделка (лучше|хуже|ровно)/)).not.toBeInTheDocument()
    expect(screen.getAllByText('—').length).toBeGreaterThan(0)
  })

  it('keeps absent deal margins distinct from zero when there is no agreement', () => {
    render(<TrainingReviewPanel language="en" data={{ ...data, methodology: {
      version: 'harvard-batna-voss-v1', zopa: 'not_inferred', economics: {
        outcome: 'no_agreement', surplus_over_batna: null, margin_over_reservation: null, meets_reservation: null,
      },
    } }} />)
    expect(screen.getByText(/Deal surplus is not calculated/)).toBeInTheDocument()
    expect(screen.queryByText('Compared with your best option without a deal')).not.toBeInTheDocument()
  })

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

  it('keeps deterministic review evidence and hides provider-only evidence in template mode', () => {
    render(<TrainingReviewPanel
      language="ru"
      providerFeatures={false}
      data={{ ...data, offer_history: [{
        source_revision: 2,
        event_id: 'event-2',
        type: 'offer.created',
        terms: { price: 105000 },
      }] }}
    />)
    expect(screen.getByText('История предложений')).toBeInTheDocument()
    expect(screen.getByText(/105\s000/)).toBeInTheDocument()
    expect(screen.queryByText('Разбор с тренером')).not.toBeInTheDocument()
    expect(screen.queryByText('Динамика отношений')).not.toBeInTheDocument()
  })

  it('hides provider wording controls without hiding shared training context', () => {
    render(<TrainingSetupFields
      language="ru"
      value={defaultTraining()}
      providerFeatures={false}
      onChange={vi.fn()}
    />)
    expect(screen.queryByText('Стиль реплик собеседника')).not.toBeInTheDocument()
    expect(screen.getByText('Общий опыт')).toBeInTheDocument()
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
