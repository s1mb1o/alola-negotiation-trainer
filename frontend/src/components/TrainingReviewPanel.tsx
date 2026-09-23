import { useState } from 'react'
import { identifierLabel } from '../i18n'
import type { TrainingComparison, TrainingReview, UiLanguage } from '../types'
import { TermsList } from './TermsList'

export interface TrainingReviewActions {
  onCoaching?: () => void
  onFork?: (revision: number) => void
  trainingBusy?: boolean
  trainingError?: string
  comparison?: TrainingComparison
}

export function TrainingReviewPanel({ language, data, onCoaching, onFork, trainingBusy, trainingError, comparison }: {
  language: UiLanguage; data: TrainingReview
} & TrainingReviewActions) {
  const text = (ru: string, en: string) => language === 'ru' ? ru : en
  const [selected, setSelected] = useState(data.checkpoints[0]?.source_revision ?? 0)
  const coaching = data.coaching
  const format = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString(language === 'ru' ? 'ru-RU' : 'en-US')
  const axes: Record<string, string> = {
    rapport: text('Контакт', 'Rapport'), credibility: text('Доверие к словам', 'Credibility'),
    tension: text('Напряжение', 'Tension'), patience: text('Терпение', 'Patience'),
  }
  return <div className="training-review">
    <section className="review-section">
      <h3>{text('Цель и результат', 'Goal and outcome')}</h3>
      <p>{data.preparation.target || text('Личная цель не задана.', 'No personal goal was specified.')}</p>
      {Boolean(data.goal_comparison.length) && <div className="training-table-wrap"><table>
        <thead><tr>{[text('Условие', 'Term'), text('Цель', 'Target'), text('Результат', 'Actual'), text('Разрыв', 'Gap')].map(label => <th key={label}>{label}</th>)}</tr></thead>
        <tbody>{data.goal_comparison.map(goal => <tr key={goal.term_id}>
          <td>{identifierLabel(language, goal.term_id)}</td><td>{{ lte: '≤', gte: '≥', eq: '=' }[goal.operator]} {format(goal.value)}</td>
          <td>{format(goal.actual)}</td><td>{goal.status === 'unknown' ? text('Нет соглашения', 'No agreement') : format(goal.gap)}</td>
        </tr>)}</tbody>
      </table></div>}
      <p className="field-note">{text('Числовые цели проверяет движок по заключённой сделке. Для свободного текста процент достижения не рассчитывается.', 'The engine checks numeric goals against the agreed deal. Free-text goals have no computed achievement percentage.')}</p>
      <details><summary>{text('Мой исходный план', 'My original plan')}</summary>
        <dl>{([
          ['unacceptable_result', text('Неприемлемый результат', 'Unacceptable outcome')],
          ['available_trades', text('Возможные обмены', 'Possible trades')],
          ['information_to_discover', text('Что выяснить', 'What to discover')],
        ] as const).map(([key, label]) => <div key={key}><dt>{label}</dt><dd>{data.preparation[key] || '—'}</dd></div>)}</dl>
      </details>
    </section>
    <section className="review-section" aria-busy={trainingBusy}>
      <h3>{text('Разбор с тренером', 'Coaching review')}</h3>
      {coaching.evidence_truncated && <p className="field-note">{text('Разбор использует сокращённую историю. Выводы относятся только к приведённым фрагментам.', 'This review uses a shortened history. Conclusions apply only to the included excerpts.')}</p>}
      {coaching.status === 'complete' ? <>
        <p>{coaching.summary}</p><p>{coaching.goal_assessment}</p>
        {coaching.cards?.map((card, index) => <article className="coaching-card" key={index}>
          <h4>{card.observation}</h4>
          {card.evidence.map(source => <blockquote key={source.ref}>
            <p>{source.text}{source.excerpt_truncated ? '…' : ''}</p><cite>{text('Ход', 'Turn')} {source.source_revision} · {identifierLabel(language, source.role)}</cite>
          </blockquote>)}
          <p>{card.recommendation}</p>
          <p><strong>{text('Возможная реплика', 'Possible alternative')}: </strong>{card.alternative_phrase}</p>
          <p><strong>{text('Следующая практика', 'Next practice')}: </strong>{card.next_practice}</p>
        </article>)}
        <p className="field-note">{text('Альтернативные реплики — гипотезы. Их эффект проверяется в повторе.', 'Alternative phrases are hypotheses. Test their effect in a retry.')}</p>
      </> : <>
        <p>{coaching.status === 'unavailable'
          ? text('LLM-разбор недоступен. Расчёты результата и история сохранены.', 'LLM coaching is unavailable. Outcome calculations and history remain available.')
          : coaching.status === 'pending' ? text('Разбор готовится. Обновите его через некоторое время.', 'Analysis is in progress. Refresh it shortly.')
          : text('Тренер сопоставит ваш план с результатом и предложит другие реплики на основе истории.', 'The coach will compare your plan with the outcome and suggest evidence-based alternatives.')}</p>
        {coaching.status !== 'unavailable' && <button type="button" className="button button-primary" disabled={trainingBusy || !onCoaching} onClick={onCoaching}>
          {trainingBusy ? text('Готовим разбор…', 'Preparing review…') : coaching.status === 'pending' ? text('Обновить разбор', 'Refresh review') : text('Получить разбор', 'Get coaching')}
        </button>}
      </>}
      {trainingError && <p role="alert" className="review-error-detail">{trainingError}</p>}
    </section>
    <section className="review-section">
      <h3>{text('Повторить решение', 'Retry a decision')}</h3>
      <p>{text('Выберите состояние перед вашим ходом. Повтор сохранит предысторию и условия на этот момент.', 'Select the state before your turn. The retry preserves history and conditions at that point.')}</p>
      {data.checkpoints.length ? <div className="training-retry-controls">
        <select aria-label={text('Ход для повтора', 'Retry checkpoint')} value={selected} disabled={trainingBusy} onChange={event => setSelected(Number(event.target.value))}>
          {data.checkpoints.map(checkpoint => {
            const nextMessage = data.evidence.find(item => item.is_player && item.source_revision > checkpoint.source_revision)
            return <option key={checkpoint.source_revision} value={checkpoint.source_revision}>
              {text('Перед ходом', 'Before turn')} {checkpoint.source_revision + 1}{nextMessage ? ` · ${nextMessage.text.slice(0, 65)}` : ''}
            </option>
          })}
        </select>
        <button type="button" className="button button-primary" disabled={trainingBusy || !onFork} onClick={() => onFork?.(selected)}>{text('Начать повтор', 'Start retry')}</button>
      </div> : <p>{text('Для этой сессии нет сохранённых точек повтора.', 'This session has no saved checkpoints.')}</p>}
      <p className="field-note">{text('Повтор после обратной связи — практика с дополнительной информацией. Он не доказывает улучшение навыка.', 'A retry after feedback is informed practice. It does not prove a skill improvement.')}</p>
      {comparison && <div className="training-comparison" role="status">
        <h4>{text('Сравнение попыток', 'Attempt comparison')}</h4>
        <p>{text('Полезность результата', 'Outcome utility')}: {format(comparison.before.participant_utility)} → {format(comparison.after.participant_utility)} ({comparison.utility_delta > 0 ? '+' : ''}{format(comparison.utility_delta)})</p>
        <p>{text('Соглашение', 'Agreement')}: {comparison.before.agreement ? text('да', 'yes') : text('нет', 'no')} → {comparison.after.agreement ? text('да', 'yes') : text('нет', 'no')}</p>
        <p className="field-note">{text('Одинаковая версия сценария и состояние в выбранной точке. Разница относится только к этим попыткам.', 'The same scenario version and checkpoint state were used. The difference describes these attempts only.')}</p>
      </div>}
    </section>
    <details className="review-section">
      <summary>{text('История предложений', 'Offer history')}</summary>
      {data.offer_history.map(offer => <article className="coaching-card" key={offer.event_id}>
        <h4>{text('Ход', 'Turn')} {offer.source_revision} · {identifierLabel(language, offer.type)}</h4>
        <TermsList terms={offer.terms} locale={language === 'ru' ? 'ru-RU' : 'en-US'} />
      </article>)}
    </details>
    <details className="review-section">
      <summary>{text('Динамика отношений', 'Relationship changes')}</summary>
      <p className="field-note">{text('Параметры симуляции от 0 до 100. Это не психологическая оценка.', 'Simulation parameters from 0 to 100. These are not psychological assessments.')}</p>
      <div className="training-table-wrap"><table><thead><tr><th>{text('Параметр', 'Parameter')}</th><th>{text('Начало', 'Initial')}</th><th>{text('Конец', 'Final')}</th></tr></thead>
        <tbody>{Object.keys(data.initial_social).map(axis => <tr key={axis}><td>{axes[axis] ?? axis}</td><td>{data.initial_social[axis]}</td><td>{data.final_social[axis]}</td></tr>)}</tbody>
      </table></div>
    </details>
  </div>
}
