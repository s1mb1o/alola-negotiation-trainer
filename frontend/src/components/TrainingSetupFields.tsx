import type { ScenarioSummary, TrainingSetup, UiLanguage } from '../types'

export const defaultTraining = (): TrainingSetup => ({
  profile: 'concise_skeptical', relationship: 'first_meeting', shared_background: '', personal_detail: false,
  preparation: { target: '', unacceptable_result: '', available_trades: '', information_to_discover: '', targets: [] },
})

export function TrainingSetupFields({ language, value, scenario, onChange }: {
  language: UiLanguage; value: TrainingSetup; scenario?: ScenarioSummary; onChange: (value: TrainingSetup) => void
}) {
  const text = (ru: string, en: string) => language === 'ru' ? ru : en
  const fields = [
    ['target', text('Моя цель', 'My goal')],
    ['unacceptable_result', text('Неприемлемый результат', 'Unacceptable outcome')],
    ['available_trades', text('Что я готов предложить в обмен', 'What I can trade')],
    ['information_to_discover', text('Что нужно выяснить', 'What I need to discover')],
  ] as const
  const numeric = value.preparation.targets[0]
  return <div className="training-setup">
    <details open>
      <summary>{text('Собеседник и предыстория', 'Counterpart and shared history')}</summary>
      <div className="form-row two-columns">
        <label className="form-field">{text('Характер собеседника', 'Counterpart style')}
          <select value={value.profile} onChange={event => onChange({ ...value, profile: event.target.value as TrainingSetup['profile'] })}>
            <option value="concise_skeptical">{text('Сдержанный, просит обоснования', 'Concise, asks for evidence')}</option>
            <option value="sociable">{text('Общительный, ценит отношения', 'Sociable, values relationships')}</option>
          </select>
        </label>
        <label className="form-field">{text('Общий опыт', 'Shared experience')}
          <select value={value.relationship} onChange={event => onChange({ ...value, relationship: event.target.value as TrainingSetup['relationship'] })}>
            <option value="first_meeting">{text('Первая встреча', 'First meeting')}</option>
            <option value="successful_history">{text('Успешные сделки в прошлом', 'Successful prior deals')}</option>
          </select>
        </label>
      </div>
      <label className="form-field">{text('Что собеседник знает обо мне', 'What the counterpart knows about me')}
        <textarea rows={2} maxLength={800} value={value.shared_background}
          onChange={event => onChange({ ...value, shared_background: event.target.value })} />
        <span className="field-note">{text('Только общая предыстория. Новые условия сделки обсуждаются в диалоге.', 'Shared history only. Negotiate new deal terms in the conversation.')}</span>
      </label>
      <label className="training-check"><input type="checkbox" checked={value.personal_detail}
        onChange={event => onChange({ ...value, personal_detail: event.target.checked })} />
        {text('Добавить личную деталь: собака Гуффи', 'Add a personal detail: Goofy the dog')}
      </label>
    </details>
    <details>
      <summary>{text('Мой план переговоров', 'My negotiation plan')}</summary>
      <p className="field-note">{text('Необязательно. План видите только вы и тренер после завершения. Собеседник его не получает.', 'Optional. Only you and the final coach can see this plan. It is not shared with the counterpart.')}</p>
      {fields.map(([key, label]) => <label className="form-field" key={key}>{label}
        <textarea rows={2} maxLength={1000} value={value.preparation[key]}
          onChange={event => onChange({ ...value, preparation: { ...value.preparation, [key]: event.target.value } })} />
      </label>)}
      {Boolean(scenario?.training_terms?.length) && <fieldset className="form-field fieldset-reset">
        <legend>{text('Измеримая цель по условию', 'Measurable term target')}</legend>
        <div className="training-target-fields">
          <select aria-label={text('Условие цели', 'Target term')} value={numeric?.term_id ?? ''}
            onChange={event => onChange({ ...value, preparation: { ...value.preparation, targets: event.target.value
              ? [{ term_id: event.target.value, operator: numeric?.operator ?? 'lte', value: numeric?.value ?? 0 }] : [] } })}>
            <option value="">{text('Без числовой цели', 'No numeric target')}</option>
            {scenario?.training_terms?.map(term => <option key={term.term_id} value={term.term_id}>{term.label}</option>)}
          </select>
          {numeric && <>
            <select aria-label={text('Сравнение', 'Comparison')} value={numeric.operator}
              onChange={event => onChange({ ...value, preparation: { ...value.preparation, targets: [{ ...numeric, operator: event.target.value as 'lte' | 'gte' | 'eq' }] } })}>
              <option value="lte">≤</option><option value="gte">≥</option><option value="eq">=</option>
            </select>
            <input aria-label={text('Значение цели', 'Target value')} type="number" step="any" required value={numeric.value}
              onChange={event => onChange({ ...value, preparation: { ...value.preparation, targets: [{ ...numeric, value: event.target.valueAsNumber }] } })} />
          </>}
        </div>
        <p className="field-note">{text('Используйте единицы условия; доли вводите от 0 до 1. Цель не меняет ограничения сценария.', 'Use the term units; enter fractions from 0 to 1. A target does not change scenario constraints.')}</p>
      </fieldset>}
    </details>
  </div>
}
