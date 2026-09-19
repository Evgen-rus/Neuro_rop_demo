let demoMode = false

const ID_KEY_RE = /(^id$|_id$|_ids$|Id$)/
const PHONE_VISIBLE_TAIL = 4
// Российские номера: +7/7/8 и 10 цифр, либо 10 цифр с 9. Разделители не ломают поиск.
const PHONE_CANDIDATE_RE = /(?<!\d)(?:(?:\+7|8|7)(?:[\s().-]*\d){10}|9(?:[\s().-]*\d){9})(?!\d)/g

export type DemoMaskSource = {
  deal_id?: string | number | null
  title?: string | null
  manager_id?: string | number | null
  manager_name?: string | null
}

export function setDemoMode(value: boolean) {
  demoMode = Boolean(value)
}

export function isDemoMode() {
  return demoMode
}

export function demoDealTitle(dealId: string | number) {
  return `Сделка ${String(dealId).trim()}`
}

export function demoManagerName(managerId: string | number) {
  return `Менеджер ${String(managerId).trim()}`
}

export function displayDealTitle(
  dealId?: string | number | null,
  title?: string | null,
  emptyFallback?: string | null,
) {
  const id = String(dealId ?? '').trim()
  if (demoMode) return id ? demoDealTitle(id) : 'Сделка'
  const real = String(title || '').trim()
  if (real) return real
  if (emptyFallback != null) return emptyFallback
  return id ? `Сделка #${id}` : ''
}

export function displayManagerName(
  managerId?: string | number | null,
  name?: string | null,
  emptyFallback?: string | null,
) {
  const id = String(managerId ?? '').trim()
  if (demoMode) return id ? demoManagerName(id) : 'Менеджер'
  const real = String(name || '').trim()
  if (real) return real
  if (emptyFallback != null) return emptyFallback
  return id ? `Ответственный #${id}` : ''
}

export function displayEntityTitle(
  entityType?: string | null,
  entityId?: string | number | null,
  title?: string | null,
  emptyFallback?: string | null,
) {
  if (String(entityType || '').trim().toLowerCase() === 'deal') {
    return displayDealTitle(entityId, title, emptyFallback)
  }
  const real = String(title || '').trim()
  if (real) return real
  return emptyFallback == null ? '' : emptyFallback
}

function replaceExact(source: string, needle: string, replacement: string) {
  if (!needle || !source.includes(needle)) return source
  return source.split(needle).join(replacement)
}

function maskPhoneDigits(raw: string) {
  const chars = Array.from(raw)
  const digitIndexes: number[] = []
  for (let index = 0; index < chars.length; index += 1) {
    if (chars[index] >= '0' && chars[index] <= '9') digitIndexes.push(index)
  }
  const hideUntil = Math.max(0, digitIndexes.length - PHONE_VISIBLE_TAIL)
  for (let index = 0; index < hideUntil; index += 1) {
    chars[digitIndexes[index]] = '*'
  }
  return chars.join('')
}

function isRuPhoneDigits(digits: string) {
  if (digits.length === 11) return digits[0] === '7' || digits[0] === '8'
  if (digits.length === 10) return digits[0] === '9'
  return false
}

export function maskPhonesInText(text: string | null | undefined) {
  const source = text == null ? '' : String(text)
  if (!demoMode || !source) return source
  return source.replace(PHONE_CANDIDATE_RE, (match) => {
    const digits = match.replace(/\D/g, '')
    return isRuPhoneDigits(digits) ? maskPhoneDigits(match) : match
  })
}

const PERSON_NAME_RE = /^[A-ZА-ЯЁ][a-zа-яё]+(?:[-\s]+[A-ZА-ЯЁ][a-zа-яё]+){1,3}$/u
const COMPANY_BRAND_RE = /praktik-?m|практик-?м/giu

export function isDemoPersonName(value: string | null | undefined) {
  if (!demoMode) return false
  return PERSON_NAME_RE.test(String(value || '').trim())
}

export function maskCompanyBrandInText(text: string | null | undefined) {
  const source = text == null ? '' : String(text)
  if (!demoMode || !source) return source
  return source.replace(COMPANY_BRAND_RE, (match) => '*'.repeat(match.length))
}

function maskSensitiveDisplayText(text: string) {
  return maskCompanyBrandInText(maskPhonesInText(text))
}

function maskPhonesInValue<T>(value: T): T {
  if (!demoMode) return value
  if (typeof value === 'string') return maskSensitiveDisplayText(value) as T
  if (Array.isArray(value)) return value.map((item) => maskPhonesInValue(item)) as T
  if (value && typeof value === 'object') {
    const next: Record<string, unknown> = {}
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      next[key] = ID_KEY_RE.test(key) ? item : maskPhonesInValue(item)
    }
    return next as T
  }
  return value
}

function maskExactInValue<T>(value: T, needle: string, replacement: string): T {
  if (!demoMode || !needle) return value
  if (typeof value === 'string') return replaceExact(value, needle, replacement) as T
  if (Array.isArray(value)) {
    return value.map((item) => maskExactInValue(item, needle, replacement)) as T
  }
  if (value && typeof value === 'object') {
    const next: Record<string, unknown> = {}
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      next[key] = ID_KEY_RE.test(key) ? item : maskExactInValue(item, needle, replacement)
    }
    return next as T
  }
  return value
}

export function maskDealTitleInText(
  text: string | null | undefined,
  dealId?: string | number | null,
  realTitle?: string | null,
) {
  const source = text == null ? '' : String(text)
  if (!demoMode) return source
  const title = String(realTitle || '').trim()
  const id = String(dealId ?? '').trim()
  return replaceExact(source, title, id ? demoDealTitle(id) : 'Сделка')
}

export function maskDealTitleInValue<T>(
  value: T,
  dealId?: string | number | null,
  realTitle?: string | null,
): T {
  if (!demoMode) return value
  const title = String(realTitle || '').trim()
  const id = String(dealId ?? '').trim()
  return maskExactInValue(value, title, id ? demoDealTitle(id) : 'Сделка')
}

export function maskManagerNameInText(
  text: string | null | undefined,
  managerId?: string | number | null,
  realName?: string | null,
) {
  const source = text == null ? '' : String(text)
  if (!demoMode) return source
  const name = String(realName || '').trim()
  const id = String(managerId ?? '').trim()
  return replaceExact(source, name, id ? demoManagerName(id) : 'Менеджер')
}

export function maskManagerNameInValue<T>(
  value: T,
  managerId?: string | number | null,
  realName?: string | null,
): T {
  if (!demoMode) return value
  const name = String(realName || '').trim()
  const id = String(managerId ?? '').trim()
  return maskExactInValue(value, name, id ? demoManagerName(id) : 'Менеджер')
}

export function maskDemoText(text: string | null | undefined, source?: DemoMaskSource | null) {
  const next = maskDealTitleInText(text, source?.deal_id, source?.title)
  return maskSensitiveDisplayText(maskManagerNameInText(next, source?.manager_id, source?.manager_name))
}

export function maskDemoValue<T>(value: T, source?: DemoMaskSource | null): T {
  const next = maskDealTitleInValue(value, source?.deal_id, source?.title)
  return maskPhonesInValue(maskManagerNameInValue(next, source?.manager_id, source?.manager_name))
}
