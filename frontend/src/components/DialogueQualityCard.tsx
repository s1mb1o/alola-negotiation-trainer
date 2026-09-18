import { MessageSquareText } from 'lucide-react'
import { translate } from '../i18n'
import type { DialogueQuality, UiLanguage } from '../types'

export function DialogueQualityCard({ quality, language }: { quality?: DialogueQuality | null; language: UiLanguage }) {
  const t = (key: string) => translate(language, key)
  const missing = t('dialogueQualityMissing')
  const number = (value: number | null | undefined) => value == null ? missing
    : new Intl.NumberFormat(language === 'ru' ? 'ru-RU' : 'en-GB', { maximumFractionDigits: 1 }).format(value)
  const percent = (value: number | null | undefined) => value == null ? missing
    : new Intl.NumberFormat(language === 'ru' ? 'ru-RU' : 'en-GB', { style: 'percent', maximumFractionDigits: 1 }).format(value)
  const duration = (value: number | null | undefined) => value == null ? missing : `${number(value)} ${t('dialogueQualityMilliseconds')}`
  const failureLabel = (code: string) => translate(language, `dialogueFailure_${code}`, t('dialogueFailure_other'))
  return (
    <section className="inspector-subsection" aria-label={t('dialogueQualityTitle')}>
      <div className="inspector-subsection-title"><MessageSquareText size={18} aria-hidden="true" /><h3>{t('dialogueQualityTitle')}</h3></div>
      <p>{t('dialogueQualityHeuristic')}</p>
      {!quality ? <p>{missing}</p> : <>
        <dl className="inspector-facts">
          <div><dt>{t('dialogueQualityNpcTurns')}</dt><dd>{number(quality.turns.npc)}</dd></div>
          <div><dt>{t('dialogueQualityExactRepeats')}</dt><dd>{number(quality.repetition.exact_repeat_count)}</dd></div>
          <div><dt>{t('dialogueQualityQuestionRepeats')}</dt><dd>{number(quality.repetition.question_repeat_count)}</dd></div>
          <div><dt>{t('dialogueQualityFallback')}</dt><dd>{percent(quality.rendering.fallback_rate)}</dd></div>
          <div><dt>{t('dialogueQualityLatencyAverage')}</dt><dd>{duration(quality.rendering.latency_ms.average)}</dd></div>
          <div><dt>{t('dialogueQualityLatencyP95')}</dt><dd>{duration(quality.rendering.latency_ms.p95)}</dd></div>
          <div><dt>{t('dialogueQualityTelemetryCoverage')}</dt><dd>{number(quality.rendering.telemetry_turns)} / {number(quality.rendering.delivered_turns)}</dd></div>
          <div><dt>{t('dialogueQualityLatencySamples')}</dt><dd>{number(quality.rendering.latency_ms.samples)}</dd></div>
          <div><dt>{t('dialogueQualityFallbackSamples')}</dt><dd>{number(quality.rendering.fallback_observations)} / {number(quality.rendering.generation_attempts)}</dd></div>
        </dl>
        <p>{t('dialogueQualityCanonical')}</p>
        {(Object.keys(quality.rendering.failure_counts).length > 0 || Object.keys(quality.rendering.validation_failures).length > 0) && <>
          <h4>{t('dialogueQualityFailures')}</h4>
          <ul>
            {Object.entries(quality.rendering.failure_counts).map(([code, count]) => <li key={`failure-${code}`}>{failureLabel(code)}: {number(count)}</li>)}
            {Object.entries(quality.rendering.validation_failures).map(([code, count]) => <li key={`validation-${code}`}>{t('dialogueQualityValidation')}: {failureLabel(code)}: {number(count)}</li>)}
          </ul>
        </>}
        {quality.repetition.flags.length > 0 && <details>
          <summary>{t('dialogueQualitySources')}</summary>
          <ul>{quality.repetition.flags.map((flag, index) => <li key={`${flag.source_message_id}-${index}`}>
            {t(flag.kind === 'question_repeat' ? 'dialogueQualityQuestionRepeats' : 'dialogueQualityExactRepeats')}: <code>{flag.source_message_id}</code> → <code>{flag.repeats_source_message_id}</code>
          </li>)}</ul>
          {quality.repetition.flags_truncated && <p>{t('dialogueQualitySourcesTruncated')}</p>}
        </details>}
        <h4>{t('dialogueQualityHumanTitle')}</h4>
        <p>{t('dialogueQualityHumanHelp')}</p>
        <dl className="inspector-facts">
          {Object.entries(quality.human_review.dimensions).map(([dimension, rating]) => <div key={dimension}>
            <dt>{t(`dialogueQualityDimension_${dimension}`)}</dt>
            <dd>{rating == null ? t('dialogueQualityUnrated') : `${number(rating)} / 4`}</dd>
          </div>)}
        </dl>
        <small>{t('dialogueQualityHumanCoverage')}: {quality.human_review.coverage.rated_turns} / {quality.human_review.coverage.eligible_turns} · {quality.human_review.rubric_version}</small>
      </>}
    </section>
  )
}
