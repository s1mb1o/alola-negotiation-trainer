import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { DialogueQualityCard } from '../components/DialogueQualityCard'
import type { DialogueQuality } from '../types'

const quality: DialogueQuality = {
  version: 1, heuristic_only: true,
  turns: { total: 6, player: 3, npc: 3 },
  repetition: { exact_repeat_count: 1, question_repeat_count: 1, flags: [{ kind: 'question_repeat', source_message_id: 'msg:npc:4:3', repeats_source_message_id: 'msg:npc:2:1' }], flags_truncated: false },
  rendering: { delivered_turns: 3, telemetry_turns: 3, generation_attempts: 2, fallback_observations: 2, fallback_count: 1, fallback_rate: 0.5,
    failure_counts: { output_invalid: 1 }, validation_failures: { numeric_reference: 1 }, latency_ms: { samples: 2, average: 150, p95: 200 } },
  human_review: { rubric_version: 'dialogue-human-v1', status: 'unrated', dimensions: { relevance: null, continuity: null, attribution: null, unsupported_claims: null }, coverage: { rated_turns: 0, eligible_turns: 3 } },
}

describe('DialogueQualityCard', () => {
  afterEach(cleanup)

  it.each(['ru', 'en'] as const)('renders localised technical diagnostics and unrated human dimensions in %s', (language) => {
    render(<DialogueQualityCard quality={quality} language={language} />)
    expect(screen.getByRole('heading', { name: language === 'ru' ? 'Диагностика диалога' : 'Dialogue diagnostics' })).toBeInTheDocument()
    expect(screen.getAllByText(language === 'ru' ? 'Не оценено' : 'Unrated')).toHaveLength(4)
    expect(screen.getByText(language === 'ru' ? '150 мс' : '150 ms')).toBeInTheDocument()
    expect(screen.getByText(language === 'ru' ? /Некорректная ссылка на число/ : /Invalid numeric reference/)).toBeInTheDocument()
    expect(screen.getByText('msg:npc:4:3')).toBeInTheDocument()
    expect(screen.getByText(language === 'ru' ? /не доказывают/ : /do not prove/)).toBeInTheDocument()
  })

  it('does not replace missing historical telemetry with zero', () => {
    render(<DialogueQualityCard quality={{ ...quality, rendering: { ...quality.rendering, fallback_rate: null, latency_ms: { samples: 0, average: null, p95: null } } }} language="en" />)
    expect(screen.getAllByText('No data')).toHaveLength(3)
    expect(screen.queryByText('0 ms')).not.toBeInTheDocument()
    expect(screen.queryByText('0%')).not.toBeInTheDocument()
  })

  it('supports old API responses without a diagnostic field', () => {
    render(<DialogueQualityCard language="ru" />)
    expect(screen.getByText('Нет данных')).toBeInTheDocument()
  })
})
