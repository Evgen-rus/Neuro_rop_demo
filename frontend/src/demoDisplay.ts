let demoMode = false

const ID_KEY_RE = /(^id$|_id$|_ids$|Id$)/

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
  return maskManagerNameInText(next, source?.manager_id, source?.manager_name)
}

export function maskDemoValue<T>(value: T, source?: DemoMaskSource | null): T {
  const next = maskDealTitleInValue(value, source?.deal_id, source?.title)
  return maskManagerNameInValue(next, source?.manager_id, source?.manager_name)
}
