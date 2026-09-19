let demoMode = false

const ID_KEY_RE = /(^id$|_id$|_ids$|Id$)/

export function setDemoMode(value: boolean) {
  demoMode = Boolean(value)
}

export function isDemoMode() {
  return demoMode
}

export function demoDealTitle(dealId: string | number) {
  return `Сделка ${String(dealId).trim()}`
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

export function maskDealTitleInText(
  text: string | null | undefined,
  dealId?: string | number | null,
  realTitle?: string | null,
) {
  const source = text == null ? '' : String(text)
  if (!demoMode) return source
  const title = String(realTitle || '').trim()
  if (!title || !source.includes(title)) return source
  const id = String(dealId ?? '').trim()
  return source.split(title).join(id ? demoDealTitle(id) : 'Сделка')
}

export function maskDealTitleInValue<T>(
  value: T,
  dealId?: string | number | null,
  realTitle?: string | null,
): T {
  if (!demoMode) return value
  if (typeof value === 'string') return maskDealTitleInText(value, dealId, realTitle) as T
  if (Array.isArray(value)) {
    return value.map((item) => maskDealTitleInValue(item, dealId, realTitle)) as T
  }
  if (value && typeof value === 'object') {
    const next: Record<string, unknown> = {}
    for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
      next[key] = ID_KEY_RE.test(key) ? item : maskDealTitleInValue(item, dealId, realTitle)
    }
    return next as T
  }
  return value
}
