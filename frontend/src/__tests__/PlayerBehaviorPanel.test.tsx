import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it } from 'vitest'
import { PlayerBehaviorPanel } from '../components/PlayerBehaviorPanel'
import { TrainingReviewPanel } from '../components/TrainingReviewPanel'
import { defaultTraining } from '../components/TrainingSetupFields'
import type { BehaviorCriterion, PlayerBehaviorReview, TrainingReview } from '../types'

afterEach(cleanup)

function fixture(): PlayerBehaviorReview {
  const criteria: BehaviorCriterion[] = ['rapport', 'listening', 'interest_discovery', 'argumentation', 'conditional_trading', 'clarity', 'plan_adherence']
  return {
    version: 'player-behavior-v1', summary: 'О действиях, не о выгоде сделки.',
    criteria: criteria.map((criterion, index) => ({
      criterion, assessment: index === 6 ? 'insufficient_evidence' : 'mixed',
      evidence_refs: index === 6 ? [] : ['message:1', 'message:2'], observation: `Наблюдение ${criterion}`,
      strength: index === 6 ? null : 'Понятный вопрос', improvement: index === 6 ? null : 'Уточнить ответ',
      alternative_phrase: index === 6 ? null : 'Что для вас важнее?', next_practice: index === 6 ? null : 'Задайте один вопрос',
      evidence: index === 6 ? [] : [
        { ref: 'message:1', source_revision: 3, text: '<script>player</script>', role: 'buyer', is_player: true },
        { ref: 'message:2', source_revision: 4, text: 'Ответ NPC', role: 'seller', is_player: false },
      ], alternative_is_hypothesis: true,
    })),
  }
}

describe('separate player behavior review', () => {
  it.each(['ru', 'en'] as const)('renders all seven criteria with qualitative labels in %s', language => {
    render(<PlayerBehaviorPanel language={language} behavior={fixture()} truncated />)
    expect(screen.getByRole('heading', { name: language === 'ru' ? 'Поведение игрока' : 'Player behavior' })).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 4 })).toHaveLength(7)
    expect(screen.getAllByText(language === 'ru' ? 'Смешанный результат' : 'Mixed')).toHaveLength(6)
    expect(screen.getByText(language === 'ru' ? 'Недостаточно данных' : 'Insufficient evidence')).toBeInTheDocument()
    expect(screen.getByText(language === 'ru' ? /Общий балл не рассчитывается/ : /No total score is calculated/)).toBeInTheDocument()
    expect(screen.getByText(language === 'ru' ? /История сокращена/ : /history is shortened/)).toBeInTheDocument()
    expect(screen.getByText(language === 'ru' ? /не ошибка игрока/ : /not a player error/)).toBeInTheDocument()
    const last = screen.getAllByRole('article')[6]
    expect(within(last).queryByText(/Что изменить|Improvement/)).not.toBeInTheDocument()
    expect(within(last).getByText(language === 'ru' ? /Что попробовать в следующем диалоге/ : /What to try in the next dialogue/)).toBeInTheDocument()
    expect(within(last).queryByText(/Возможная реплика · гипотеза|Possible alternative · hypothesis/)).not.toBeInTheDocument()
  })

  it.each(['ru', 'en'] as const)('adds distinct authored practice for every insufficient-evidence criterion in %s', language => {
    const data = fixture()
    data.criteria = data.criteria.map(item => ({
      ...item, assessment: 'insufficient_evidence' as const, evidence_refs: [], evidence: [],
      strength: null, improvement: null, alternative_phrase: null, next_practice: null,
    }))
    const original = structuredClone(data)
    render(<PlayerBehaviorPanel language={language} behavior={data} />)
    expect(screen.getAllByText(language === 'ru' ? 'Недостаточно данных' : 'Insufficient evidence')).toHaveLength(7)
    expect(screen.getAllByText(language === 'ru' ? /Что попробовать в следующем диалоге/ : /What to try in the next dialogue/)).toHaveLength(7)
    expect(screen.getAllByText(language === 'ru' ? /Пример реплики — не из переписки/ : /Example phrase — not from the transcript/)).toHaveLength(7)
    expect(screen.getByText(language === 'ru' ? /общие подсказки тренажёра/ : /general practice guidance/)).toBeInTheDocument()
    const cards = screen.getAllByRole('article')
    expect(within(cards[1]).getByText(language === 'ru' ? /дождитесь ответа/ : /wait for the answer/)).toBeInTheDocument()
    expect(within(cards[2]).getByText(language === 'ru' ? /Почему для вас важно именно это условие/ : /Why does this condition matter/)).toBeInTheDocument()
    expect(within(cards[3]).getByText(language === 'ru' ? /Не придумывайте цифры/ : /Do not invent figures/)).toBeInTheDocument()
    expect(within(cards[4]).getByText(language === 'ru' ? /Если мы \[наша уступка\]/ : /If we \[our concession\]/)).toBeInTheDocument()
    expect(within(cards[6]).getByText(language === 'ru' ? /Приватные пределы не нужно раскрывать NPC/ : /do not need to disclose private limits/)).toBeInTheDocument()
    expect(screen.queryByText(/Что удалось|Strength/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Что изменить|Improvement/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Реплики-основания|Source messages/)).not.toBeInTheDocument()
    expect(data).toEqual(original)
  })

  it('keeps authored practice out of supported assessments', () => {
    render(<PlayerBehaviorPanel language="ru" behavior={fixture()} />)
    const cards = screen.getAllByRole('article')
    expect(within(cards[0]).queryByText(/Что попробовать в следующем диалоге/)).not.toBeInTheDocument()
    expect(within(cards[0]).getByText('Понятный вопрос')).toBeInTheDocument()
    expect(within(cards[6]).getByText(/Что попробовать в следующем диалоге/)).toBeInTheDocument()
  })

  it('shows player and NPC evidence as escaped text in keyboard-accessible disclosures', async () => {
    render(<PlayerBehaviorPanel language="ru" behavior={fixture()} />)
    const first = screen.getAllByRole('article')[0]
    const disclosure = within(first).getByText('Реплики-основания (2)')
    await userEvent.click(disclosure)
    expect(disclosure.closest('details')).toHaveAttribute('open')
    expect(within(first).getByText('<script>player</script>')).toBeVisible()
    expect(within(first).getByText('Игрок · Ход 3 · message:1')).toBeInTheDocument()
    expect(within(first).getByText('NPC · Ход 4 · message:2')).toBeInTheDocument()
    expect(document.querySelector('script')).toBeNull()
  })

  it.each(['ru', 'en'] as const)('explains the missing section for historical cached results in %s', language => {
    render(<PlayerBehaviorPanel language={language} />)
    expect(screen.getByText(language === 'ru' ? /Старый разбор не изменён/ : /original review is unchanged/)).toBeInTheDocument()
    expect(screen.queryByRole('article')).not.toBeInTheDocument()
  })

  it('keeps behavior separate from the coaching cards and hidden in template mode', () => {
    const data: TrainingReview = {
      preparation: defaultTraining().preparation, goal_comparison: [], initial_social: {}, final_social: {},
      offer_history: [], evidence: [], checkpoints: [], informed_practice: false, skill_scores_validated: false,
      coaching: { status: 'complete', summary: 'Общий разбор', behavior: fixture() },
    }
    const { rerender } = render(<TrainingReviewPanel language="ru" data={data} providerFeatures />)
    const behaviorSection = screen.getByRole('region', { name: 'Поведение игрока' })
    expect(behaviorSection).not.toContainElement(screen.getByText('Общий разбор'))
    rerender(<TrainingReviewPanel language="ru" data={data} providerFeatures={false} />)
    expect(screen.queryByRole('region', { name: 'Поведение игрока' })).not.toBeInTheDocument()
  })

  it('does not invent ratings when coaching is unavailable', () => {
    const data: TrainingReview = {
      preparation: defaultTraining().preparation, goal_comparison: [], initial_social: {}, final_social: {},
      offer_history: [], evidence: [], checkpoints: [], informed_practice: false, skill_scores_validated: false,
      coaching: { status: 'unavailable' },
    }
    render(<TrainingReviewPanel language="ru" data={data} providerFeatures />)
    expect(screen.queryByRole('region', { name: 'Поведение игрока' })).not.toBeInTheDocument()
    expect(screen.getByText(/LLM-разбор недоступен/)).toBeInTheDocument()
  })

  it.each(['ru', 'en'] as const)('provides unassessed practice in every fallback state in %s', async language => {
    const data: TrainingReview = {
      preparation: defaultTraining().preparation, goal_comparison: [], initial_social: {}, final_social: {},
      offer_history: [], evidence: [], checkpoints: [{ source_revision: 0 }], informed_practice: false,
      skill_scores_validated: false, coaching: { status: 'not_requested' },
    }
    const { rerender } = render(<TrainingReviewPanel language={language} data={data} providerFeatures />)
    const heading = language === 'ru' ? 'Практика без AI-оценки' : 'Practice without AI assessment'
    for (const status of ['not_requested', 'pending', 'unavailable', 'complete'] as const) {
      rerender(<TrainingReviewPanel language={language} data={{ ...data, coaching: { status } }} providerFeatures />)
      const practice = screen.getByRole('region', { name: heading })
      expect(practice.querySelectorAll('details')).toHaveLength(7)
      expect(within(practice).queryByText(/Недостаточно данных|Insufficient evidence/)).not.toBeInTheDocument()
      expect(practice.querySelector('.behavior-assessment')).toBeNull()
      expect(within(practice).getByText(language === 'ru' ? /не оценка вашей переписки/ : /not an assessment of your transcript/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: language === 'ru' ? 'Начать повтор' : 'Start retry' })).toBeInTheDocument()
    }
    rerender(<TrainingReviewPanel language={language} data={{ ...data, coaching: { status: 'complete', behavior: fixture() } }} providerFeatures={false} />)
    const practice = screen.getByRole('region', { name: heading })
    expect(screen.queryByRole('region', { name: language === 'ru' ? 'Поведение игрока' : 'Player behavior' })).not.toBeInTheDocument()
    const disclosure = within(practice).getByText(language === 'ru' ? 'Вопросы и слушание' : 'Questions and listening')
    await userEvent.click(disclosure)
    expect(disclosure.closest('details')).toHaveAttribute('open')
    expect(within(practice).getByText(language === 'ru' ? /Приватные пределы не нужно раскрывать NPC/ : /do not need to disclose private limits/)).toBeInTheDocument()
    rerender(<TrainingReviewPanel language={language} data={{ ...data, coaching: { status: 'complete', behavior: fixture() } }} providerFeatures />)
    expect(screen.queryByRole('region', { name: heading })).not.toBeInTheDocument()
  })
})
