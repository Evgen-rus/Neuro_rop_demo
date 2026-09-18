export const MOSCOW_TIME_ZONE = 'Europe/Moscow'

type DateTimeValue = string | number | Date

const DATE_ONLY_RE = /^\d{4}-\d{2}-\d{2}$/
const DATE_TIME_WITHOUT_ZONE_RE = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/

let businessNowOverride: Date | null = null

export function parseMoscowDateTime(value: DateTimeValue): Date {
  if (value instanceof Date || typeof value === 'number') return new Date(value)
  const normalized = DATE_ONLY_RE.test(value)
    ? `${value}T00:00:00+03:00`
    : DATE_TIME_WITHOUT_ZONE_RE.test(value)
      ? `${value.replace(' ', 'T')}+03:00`
      : value
  return new Date(normalized)
}

export function setBusinessNow(value?: DateTimeValue | null) {
  if (value == null || value === '') {
    businessNowOverride = null
    return
  }
  const parsed = parseMoscowDateTime(value)
  businessNowOverride = Number.isNaN(parsed.getTime()) ? null : parsed
}

export function businessNow(): Date {
  return businessNowOverride ? new Date(businessNowOverride.getTime()) : new Date()
}

export function formatMoscowDateTime(
  value: DateTimeValue,
  options: Intl.DateTimeFormatOptions,
): string | null {
  const parsed = parseMoscowDateTime(value)
  if (Number.isNaN(parsed.getTime())) return null
  return new Intl.DateTimeFormat('ru-RU', {
    ...options,
    timeZone: MOSCOW_TIME_ZONE,
  }).format(parsed)
}

export function moscowDateParts(value: DateTimeValue = businessNow()) {
  const parsed = parseMoscowDateTime(value)
  const parts = new Intl.DateTimeFormat('en-GB', {
    timeZone: MOSCOW_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(parsed)
  const mapped = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return {
    year: Number(mapped.year),
    month: Number(mapped.month),
    day: Number(mapped.day),
  }
}

export function moscowDateInputValue(value: DateTimeValue = businessNow()): string {
  const { year, month, day } = moscowDateParts(value)
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

export function formatMoscowReviewStamp(value: DateTimeValue, now: DateTimeValue = businessNow()): string | null {
  const date = formatMoscowDateTime(value, { day: 'numeric', month: 'long' })
  const time = formatMoscowDateTime(value, { hour: '2-digit', minute: '2-digit' })
  if (!date || !time) return null
  const valueYear = moscowDateParts(value).year
  const nowYear = moscowDateParts(now).year
  const yearPart = valueYear !== nowYear ? ` ${valueYear}` : ''
  return `${date}${yearPart}, ${time}`
}

export function moscowDateTimesOnSameDay(left: DateTimeValue, right: DateTimeValue = businessNow()): boolean {
  const a = moscowDateParts(left)
  const b = moscowDateParts(right)
  return a.year === b.year && a.month === b.month && a.day === b.day
}

export function isMoscowDateTimeOnOrAfter(value: DateTimeValue, reference: DateTimeValue): boolean {
  const left = parseMoscowDateTime(value).getTime()
  const right = parseMoscowDateTime(reference).getTime()
  if (Number.isNaN(left) || Number.isNaN(right)) return false
  return left >= right
}
