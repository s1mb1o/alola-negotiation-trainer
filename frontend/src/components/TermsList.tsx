import { identifierLabel } from '../i18n'
import { formatTermValueForKey } from '../utils'
import type { JsonRecord } from '../types'
import { SupplyTermValue, supplyTermLabel } from './SupplyTermValue'

interface TermsListProps {
  terms: JsonRecord
  locale: string
  currency?: string
  compact?: boolean
}

export function TermsList({ terms, locale, currency, compact = false }: TermsListProps) {
  const entries = Object.entries(terms)
  const language = locale.toLowerCase().startsWith('ru') ? 'ru' : 'en'
  const hasCompositeTerms = entries.some(([key]) => ['delivery_lots', 'payment_schedule', 'reserve_policy'].includes(key))

  if (entries.length === 0) return <span className="empty-dash">—</span>

  return (
    <dl className={compact && !hasCompositeTerms ? 'terms-list compact' : 'terms-list'}>
      {entries.map(([key, value]) => (
        <div className="term-row" key={key}>
          <dt>{supplyTermLabel(key, language) ?? identifierLabel(language, key)}</dt>
          <dd>{['base_price', 'delivery_lots', 'payment_schedule', 'delivery_basis', 'reserve_policy'].includes(key)
            ? <SupplyTermValue term={key} value={value} locale={locale} />
            : formatTermValueForKey(key, value, locale, currency)}</dd>
        </div>
      ))}
    </dl>
  )
}
