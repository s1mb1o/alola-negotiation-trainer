import type { FinancialSummaryView, UiLanguage } from '../types'

const labels: Record<UiLanguage, Record<string, string>> = {
  ru: {
    title: 'Финансовая сводка', base_price_minor: 'Основная партия', maximum_liability_minor: 'Максимум к оплате по пакету',
    advance_minor: 'Общий аванс', balance_minor: 'Остаток за основную партию', weighted_advance_fraction: 'Доля аванса по всей партии',
    delayed_balance_fraction: 'Доля оплаты с отсрочкой', reserve_unit_price_minor: 'Цена одного резервного устройства',
    reserve_quantity: 'Резервных устройств', maximum_reserve_liability_minor: 'Максимальная доплата за резерв',
    help: 'Расчёт сервиса по текущим условиям. Максимум включает оплату всего резерва, если она потребуется. Этот расчёт не подтверждает заключение сделки.',
    details: 'Резерв и распределение оплаты', main: 'Основная партия', early: 'Первая партия', remaining: 'Оставшаяся партия',
    lot: 'Партия', units: 'шт.', price: 'Стоимость', advance: 'Аванс', balance: 'Остаток', missingCurrency: 'валюта не указана',
  },
  en: {
    title: 'Financial summary', base_price_minor: 'Main order', maximum_liability_minor: 'Maximum payable for the package',
    advance_minor: 'Total advance', balance_minor: 'Main order balance', weighted_advance_fraction: 'Advance share across all lots',
    delayed_balance_fraction: 'Deferred payment share', reserve_unit_price_minor: 'Reserve unit price',
    reserve_quantity: 'Reserve units', maximum_reserve_liability_minor: 'Maximum extra reserve payment',
    help: 'Service calculation for the current terms. The maximum includes all reserves if payment becomes due. This calculation does not confirm an agreement.',
    details: 'Reserve and payment allocation', main: 'Main lot', early: 'First lot', remaining: 'Remaining lot',
    lot: 'Lot', units: 'units', price: 'Price', advance: 'Advance', balance: 'Balance', missingCurrency: 'currency not specified',
  },
}

export function FinancialSummary({ summary, language, currency }: { summary?: FinancialSummaryView | null; language: UiLanguage; currency?: string }) {
  if (!summary) return null
  const t = labels[language]
  const locale = language === 'ru' ? 'ru-RU' : 'en-US'
  const unitCurrency = summary.currency ?? currency
  const amount = (value: number) => {
    if (unitCurrency && /^[A-Z]{3}$/.test(unitCurrency)) {
      return new Intl.NumberFormat(locale, { style: 'currency', currency: unitCurrency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value / 100)
    }
    return `${new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value / 100)} (${t.missingCurrency})`
  }
  const display = (key: string, value: number) => key.endsWith('_minor') ? amount(value)
    : key.endsWith('_fraction') ? new Intl.NumberFormat(locale, { style: 'percent', maximumFractionDigits: 2 }).format(value)
      : new Intl.NumberFormat(locale).format(value)
  const primaryKeys = ['base_price_minor', 'maximum_liability_minor', 'advance_minor', 'balance_minor', 'weighted_advance_fraction'] as const
  const detailKeys = ['reserve_quantity', 'reserve_unit_price_minor', 'maximum_reserve_liability_minor', 'delayed_balance_fraction'] as const
  const rows = (keys: ReadonlyArray<keyof FinancialSummaryView>) => keys.map((key) => {
    const value = summary[key]
    return typeof value === 'number' && Number.isFinite(value)
      ? <div className="term-row" key={key}><dt>{t[key]}</dt><dd>{display(key, value)}</dd></div> : null
  })
  return <section className="financial-summary">
    <h3>{t.title}</h3>
    <dl className="terms-list">{rows(primaryKeys)}</dl>
    <p className="explanatory-copy">{t.help}</p>
    <details>
      <summary>{t.details}</summary>
      <dl className="terms-list">{rows(detailKeys)}</dl>
      {summary.lots && <ul className="supply-term-items">{summary.lots.map((lot) => <li key={lot.lot_id}>
        <strong>{t[lot.lot_id] ?? t.lot} · {lot.quantity} {t.units}</strong>
        <span>{t.price}: {amount(lot.price_minor)}</span><span>{t.advance}: {amount(lot.advance_minor)}</span><span>{t.balance}: {amount(lot.balance_minor)}</span>
      </li>)}</ul>}
    </details>
  </section>
}
