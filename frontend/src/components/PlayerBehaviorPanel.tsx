import type { BehaviorAssessment, BehaviorCriterion, PlayerBehaviorReview, UiLanguage } from '../types'

function practiceContent(language: UiLanguage) {
  const text = (ru: string, en: string) => language === 'ru' ? ru : en
  const criteria: Record<BehaviorCriterion, string> = {
    rapport: text('Установление контакта', 'Rapport'),
    listening: text('Вопросы и слушание', 'Questions and listening'),
    interest_discovery: text('Выяснение интересов', 'Interest discovery'),
    argumentation: text('Аргументация', 'Argumentation'),
    conditional_trading: text('Обмен уступками', 'Conditional trading'),
    clarity: text('Ясность договорённостей', 'Clarity'),
    plan_adherence: text('Следование личному плану', 'Plan adherence'),
  }
  // Authored practice guidance is not a model finding about the recorded dialogue.
  const practice: Record<BehaviorCriterion, { action: string; phrase: string }> = {
    rapport: {
      action: text('Начните с короткого приветствия и согласуйте повестку. Общая тема уместна, только если она вам известна; личный вопрос не обязателен.', 'Start with a brief greeting and agree on the agenda. Use a shared topic only if you know it. A personal question is optional.'),
      phrase: text('Добрый день. Что для вас важно обсудить в первую очередь?', 'Hello. What would you like to discuss first?'),
    },
    listening: {
      action: text('Задайте открытый вопрос, дождитесь ответа и кратко перескажите услышанное. Попросите собеседника подтвердить или поправить ваше понимание.', 'Ask an open question, wait for the answer, and summarize what you heard. Ask the other person to confirm or correct your understanding.'),
      phrase: text('Правильно ли я понял: для вас главное — [приоритет из ответа]? Что я упустил?', 'Have I understood correctly that your main priority is [priority from the answer]? What have I missed?'),
    },
    interest_discovery: {
      action: text('Уточните, почему собеседнику важно заявленное условие и какие ограничения за ним стоят. Используйте ответ при обсуждении вариантов.', 'Ask why the stated condition matters and which constraints explain it. Use the answer when discussing options.'),
      phrase: text('Почему для вас важно именно это условие? Какие ограничения нам нужно учесть?', 'Why does this condition matter to you? Which constraints do we need to consider?'),
    },
    argumentation: {
      action: text('Свяжите просьбу с реальной задачей или проверяемым фактом. Предложите общий критерий сравнения. Не придумывайте цифры или источники.', 'Connect your request to a real need or a verifiable fact. Suggest a shared comparison criterion. Do not invent figures or sources.'),
      phrase: text('Для нас важно [условие], потому что [проверяемая причина]. Можем опереться на [источник или критерий]?', 'We need [condition] because [verifiable reason]. Could we use [source or criterion] as a reference?'),
    },
    conditional_trading: {
      action: text('Назовите уступку, которую действительно можете сделать, и встречное изменение. Обсуждайте их одним пакетом, а не как одностороннюю уступку.', 'Name a concession you can actually make and the change you want in return. Discuss them as one package, not as a unilateral concession.'),
      phrase: text('Если мы [наша уступка], готовы ли вы [встречное изменение]?', 'If we [our concession], would you be willing to [reciprocal change]?'),
    },
    clarity: {
      action: text('Подведите итог: что согласовано, что ещё открыто и какие условия связаны между собой. Попросите собеседника проверить формулировки.', 'Summarize the agreed terms, open questions, and linked conditions. Ask the other person to check the wording.'),
      phrase: text('Верно ли я зафиксировал: [условия]? По [открытый вопрос] ещё нужно договориться.', 'Have I recorded this correctly: [terms]? We still need to agree on [open question].'),
    },
    plan_adherence: {
      action: text('Перед повтором заполните личный план: цель, ограничения, возможные уступки и вопросы. Затем сопоставьте с ним свои действия. Приватные пределы не нужно раскрывать NPC.', 'Before the retry, record your goal, constraints, possible trades, and questions in your private plan. Then compare your actions with that plan. You do not need to disclose private limits to the NPC.'),
      phrase: text('Мне важно [приоритет, которым вы готовы поделиться]. Какой вариант поможет учесть его и ваши ограничения?', 'I need [priority you are willing to share]. Which option could address that priority and your constraints?'),
    },
  }
  return { criteria, practice }
}

export function BehaviorPracticePanel({ language }: { language: UiLanguage }) {
  const text = (ru: string, en: string) => language === 'ru' ? ru : en
  const { criteria, practice } = practiceContent(language)
  return <section className="review-section" aria-labelledby="behavior-practice-title">
    <h3 id="behavior-practice-title">{text('Практика без AI-оценки', 'Practice without AI assessment')}</h3>
    <p>{text(
      'Это общие упражнения тренажёра, не оценка вашей переписки. Выберите одно действие для следующей попытки. Подсказки работают без AI. Замените текст в скобках реальными данными.',
      'These are general practice exercises, not an assessment of your transcript. Choose one action for your next attempt. The guidance works without AI. Replace bracketed text with real information.',
    )}</p>
    {(Object.keys(criteria) as BehaviorCriterion[]).map(criterion => <details className="behavior-practice" key={criterion}>
      <summary>{criteria[criterion]}</summary>
      <p>{practice[criterion].action}</p>
      <p><strong>{text('Пример реплики — не из переписки', 'Example phrase — not from the transcript')}: </strong>{practice[criterion].phrase}</p>
    </details>)}
  </section>
}

export function PlayerBehaviorPanel({ language, behavior, truncated }: {
  language: UiLanguage
  behavior?: PlayerBehaviorReview | null
  truncated?: boolean
}) {
  const text = (ru: string, en: string) => language === 'ru' ? ru : en
  const { criteria, practice } = practiceContent(language)
  const assessments: Record<BehaviorAssessment, string> = {
    effective: text('Удачно', 'Effective'),
    needs_improvement: text('Есть что улучшить', 'Needs improvement'),
    mixed: text('Смешанный результат', 'Mixed'),
    insufficient_evidence: text('Недостаточно данных', 'Insufficient evidence'),
  }
  return <section className="review-section player-behavior" aria-labelledby="player-behavior-title">
    <h3 id="player-behavior-title">{text('Поведение игрока', 'Player behavior')}</h3>
    <p className="field-note">{text(
      'Оценка действий в этой сессии, не личности. Выгодная сделка не доказывает хорошее поведение, а отсутствие сделки — плохое. Общий балл не рассчитывается.',
      'This assesses actions in this session, not personality. A favorable deal does not prove effective behavior, and no deal does not prove ineffective behavior. No total score is calculated.',
    )}</p>
    {behavior ? <>
      <p>{behavior.summary}</p>
      {behavior.criteria.some(item => item.assessment === 'insufficient_evidence') && <p className="field-note">{text(
        'Для пунктов без оценки показаны общие подсказки тренажёра. Это идеи для следующего диалога, а не утверждение, что вы чего-то не сделали. Замените текст в скобках реальными данными.',
        'Unrated criteria include general practice guidance from the trainer. These are ideas for the next dialogue, not claims that you omitted an action. Replace bracketed text with real information.',
      )}</p>}
      {truncated && <p className="field-note">{text(
        'История сокращена. Оценки относятся только к переданным фрагментам.',
        'The history is shortened. Assessments apply only to the supplied excerpts.',
      )}</p>}
      {behavior.criteria.map(item => <article className="coaching-card behavior-card" key={item.criterion}>
        <div className="behavior-card-heading">
          <h4>{criteria[item.criterion]}</h4>
          <span className="behavior-assessment">{assessments[item.assessment]}</span>
        </div>
        <p>{item.observation}</p>
        {item.assessment === 'insufficient_evidence'
          ? <>
            <p className="field-note">{text('Недостаток данных — не ошибка игрока и не низкая оценка навыка.', 'Missing evidence is not a player error or a low skill rating.')}</p>
            <div className="behavior-practice">
              <p><strong>{text('Что попробовать в следующем диалоге', 'What to try in the next dialogue')}: </strong>{practice[item.criterion].action}</p>
              <p><strong>{text('Пример реплики — не из переписки', 'Example phrase — not from the transcript')}: </strong>{practice[item.criterion].phrase}</p>
            </div>
          </>
          : <>
            {item.strength && <p><strong>{text('Что удалось', 'Strength')}: </strong>{item.strength}</p>}
            {item.improvement && <p><strong>{text('Что изменить', 'Improvement')}: </strong>{item.improvement}</p>}
          </>}
        {item.evidence.length > 0 && <details className="behavior-evidence">
          <summary>{text('Реплики-основания', 'Source messages')} ({item.evidence.length})</summary>
          {item.evidence.map(source => <blockquote key={source.ref}>
            <p>{source.text}{source.excerpt_truncated ? '…' : ''}</p>
            <cite>{source.is_player ? text('Игрок', 'Player') : 'NPC'} · {text('Ход', 'Turn')} {source.source_revision} · {source.ref}</cite>
          </blockquote>)}
        </details>}
        {item.assessment !== 'insufficient_evidence' && <>
          {item.alternative_phrase && <p><strong>{text('Возможная реплика · гипотеза', 'Possible alternative · hypothesis')}: </strong>{item.alternative_phrase}</p>}
          {item.next_practice && <p><strong>{text('Следующая практика', 'Next practice')}: </strong>{item.next_practice}</p>}
        </>}
      </article>)}
      <p className="field-note">{text('Это AI-разбор по доступным репликам, не валидированная оценка компетентности. Эффект предложенных реплик не гарантирован.', 'This is an AI review of the available messages, not a validated competence assessment. Suggested alternatives have no guaranteed effect.')}</p>
    </> : <p>{text('В этой версии сохранённого разбора отдельная оценка поведения отсутствует. Старый разбор не изменён.', 'This saved review version has no separate behavior assessment. The original review is unchanged.')}</p>}
  </section>
}
