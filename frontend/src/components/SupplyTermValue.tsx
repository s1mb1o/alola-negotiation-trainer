import type { JsonRecord, UiLanguage } from '../types'

const labels: Record<UiLanguage, Record<string, string>> = {
  ru: {
    base_price: 'Цена основной партии', delivery_lots: 'Партии и сроки поставки',
    payment_schedule: 'Оплата по партиям', delivery_basis: 'Условия доставки', reserve_policy: 'Резерв для замены',
    main: 'Основная партия', early: 'Первая партия', remaining: 'Оставшаяся партия',
    advance_bps: 'Предоплата', balance_days: 'Срок оплаты остатка', quantity: 'Количество',
    window_start: 'Начало срока поставки', window_end: 'Окончание срока поставки',
    use_cutoff: 'Срок заявления о замене', unused_payable_on: 'Оплата неиспользованного резерва',
    diagnosis_policy_id: 'Правила диагностики', delivery_lot_id: 'Партия доставки резерва',
    unit_price_rule: 'Цена резервного устройства', currency: 'Валюта', minor_units: 'Сумма',
    basis: 'Базис доставки', destination_id: 'Место доставки', mode: 'Условия резерва',
  },
  en: {
    base_price: 'Main order price', delivery_lots: 'Delivery lots and dates',
    payment_schedule: 'Payment by lot', delivery_basis: 'Delivery basis', reserve_policy: 'Replacement reserve',
    main: 'Main lot', early: 'First lot', remaining: 'Remaining lot',
    advance_bps: 'Advance payment', balance_days: 'Balance payment timing', quantity: 'Quantity',
    window_start: 'Delivery window start', window_end: 'Delivery window end',
    use_cutoff: 'Replacement claim cutoff', unused_payable_on: 'Unused reserve payment date',
    diagnosis_policy_id: 'Diagnostic rules', delivery_lot_id: 'Reserve delivery lot',
    unit_price_rule: 'Reserve unit price', currency: 'Currency', minor_units: 'Amount',
    basis: 'Delivery basis', destination_id: 'Delivery destination', mode: 'Reserve terms',
  },
}

export function supplyTermLabel(path: string, language: UiLanguage): string | undefined {
  const parts = path.replace(/\[(\d+)\]/g, '.$1').split('.')
  if (!labels[language][parts[0]]) return undefined
  return parts.map((part) => labels[language][part] ?? (/^\d+$/.test(part) ? `#${Number(part) + 1}` : undefined))
    .filter(Boolean).join(' · ')
}

function record(value: unknown): JsonRecord {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as JsonRecord : {}
}

function dateText(value: unknown, locale: string, unspecified: string): string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return unspecified
  const date = new Date(`${value}T00:00:00Z`)
  if (Number.isNaN(date.getTime())) return unspecified
  return new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' }).format(date)
}

export function SupplyTermValue({ term, value, locale }: { term: string; value: unknown; locale: string }) {
  const language = locale.toLowerCase().startsWith('ru') ? 'ru' : 'en'
  const ru = language === 'ru'
  const unspecified = ru ? 'Не указано' : 'Not specified'
  const item = record(value)
  const lotLabel = (id: unknown) => typeof id === 'string' && ['main', 'early', 'remaining'].includes(id)
    ? labels[language][id] : ru ? 'Партия не указана' : 'Lot not specified'
  const units = (quantity: unknown) => typeof quantity === 'number'
    ? `${new Intl.NumberFormat(locale).format(quantity)} ${ru ? 'шт.' : 'units'}` : unspecified
  const date = (input: unknown) => dateText(input, locale, unspecified)

  if (term === 'base_price') {
    if (!Number.isSafeInteger(item.minor_units) || typeof item.currency !== 'string' || !/^[A-Z]{3}$/.test(item.currency)) return <>{unspecified}</>
    try {
      return <>{new Intl.NumberFormat(locale, { style: 'currency', currency: item.currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(item.minor_units) / 100)}</>
    } catch {
      return <>{unspecified}</>
    }
  }
  if (term === 'delivery_lots' || term === 'payment_schedule') {
    if (!Array.isArray(value) || value.length === 0) return <>{unspecified}</>
    return <ul className="supply-term-items">{value.map((entry, index) => {
      const lot = record(entry)
      return <li key={index}>
        <strong>{lotLabel(lot.lot_id)}</strong>
        {term === 'delivery_lots' ? <>
          <span>{units(lot.quantity)}</span>
          <span>{lot.window_start === lot.window_end ? date(lot.window_end) : `${date(lot.window_start)} — ${date(lot.window_end)}`}</span>
        </> : <>
          <span>{ru ? 'Предоплата' : 'Advance payment'}: {typeof lot.advance_bps === 'number' ? `${new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(lot.advance_bps / 100)}%` : unspecified}</span>
          <span>{ru ? 'Остаток' : 'Balance'}: {lot.balance_days === 0 ? ru ? 'при поставке партии' : 'on lot delivery' : lot.balance_days === 30 ? ru ? 'через 30 дней после поставки партии' : '30 days after lot delivery' : unspecified}</span>
        </>}
      </li>
    })}</ul>
  }
  if (term === 'delivery_basis') {
    return <>{item.basis === 'DDP' ? 'DDP' : unspecified} · {item.destination_id === 'vector_site' ? ru ? 'площадка покупателя Vector' : 'Vector buyer site' : unspecified}</>
  }
  if (term === 'reserve_policy') {
    if (item.mode === 'none') return <>{ru ? 'Без дополнительных резервных устройств' : 'No additional reserve devices'}</>
    if (item.mode !== 'contingent') return <>{unspecified}</>
    return <div className="supply-reserve-details">
      <p><strong>{units(item.quantity)}</strong> {ru ? 'дополнительно к основной партии' : 'in addition to the main order'}</p>
      <p>{ru ? 'Доставка вместе с партией' : 'Delivered with'}: {lotLabel(item.delivery_lot_id)}</p>
      <p>{ru ? 'Заявить о замене до конца' : 'Report replacement claims by the end of'} {date(item.use_cutoff)} ({ru ? 'московское время' : 'Moscow time'}).</p>
      <p>{ru ? 'Неиспользованный резерв оплачивается' : 'Unused reserve is payable on'} {date(item.unused_payable_on)}.</p>
      <p>{ru ? 'Цена за резервное устройство' : 'Reserve unit price'}: {item.unit_price_rule === 'base_unit_ceil'
        ? ru ? 'цена основной партии ÷ 100, с округлением вверх до евроцента' : 'main order price ÷ 100, rounded up to the next euro cent'
        : unspecified}.</p>
      {item.diagnosis_policy_id === 'hardware-replacement-v1' ? <>
        <ul>
          <li>{ru ? 'Подтверждённая аппаратная неисправность или ремонт поставщиком: замена бесплатна. Исходное устройство остаётся у поставщика, резервное — у покупателя.' : 'Verified hardware defect or supplier repair: free replacement. The supplier retains the original device; the buyer retains the reserve.'}</li>
          <li>{ru ? 'Подтверждённая проблема ПО, конфигурации или инфраструктуры покупателя без аппаратного дефекта: резерв оплачивается, исходное устройство возвращается покупателю.' : 'Verified buyer software, configuration, or infrastructure cause without a hardware defect: the reserve is payable, and the original device returns to the buyer.'}</li>
          <li>{ru ? 'Неясный результат диагностики: до истечения 10 календарных дней после получения исходного устройства поставщиком платёж не возникает. На это время исходное устройство находится у поставщика, резервное временно использует покупатель. По истечении срока замена бесплатна, исходное устройство остаётся у поставщика, резервное — у покупателя.' : 'Inconclusive diagnosis: no payment is due during the 10 calendar days after the supplier receives the original. The supplier holds the original while the buyer uses the reserve provisionally. At that deadline, replacement is free; the supplier retains the original and the buyer retains the reserve.'}</li>
        </ul>
        <p>{ru ? 'Аппаратный дефект имеет приоритет при смешанной причине. Своевременно использованный резерв не оплачивается как неиспользованный. Поздняя заявка не отменяет выкуп неиспользованного резерва.' : 'A hardware defect takes precedence with mixed causes. A timely used reserve is not also charged as unused. A late claim does not reverse the unused reserve purchase.'}</p>
      </> : <p>{ru ? 'Правила диагностики' : 'Diagnostic rules'}: {unspecified}</p>}
    </div>
  }
  return <>{unspecified}</>
}
