import type { ReactNode } from 'react'

import type { DailyControlStatus } from './api'
import { bitrixDealUrl } from './dealDisplay'

const STATUS_SYMBOL: Record<DailyControlStatus, string> = {
  red: '!',
  yellow: '?',
  green: '✓',
  neutral: '–',
}

export function BitrixDealLink({
  dealId,
  className,
  children,
}: {
  dealId: string
  className?: string
  children?: ReactNode
}) {
  const url = bitrixDealUrl(dealId)
  const content = children ?? `#${dealId}`
  if (!url) {
    return <span className={className}>{content}</span>
  }
  return (
    <a
      className={className}
      href={url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Открыть сделку #${dealId} в Bitrix`}
      title="Открыть в Bitrix"
      onClick={(event) => event.stopPropagation()}
    >
      {content}
    </a>
  )
}

export function BitrixDealIdLink({ dealId }: { dealId: string }) {
  return <BitrixDealLink className="dc-deal-id" dealId={dealId}>#{dealId}</BitrixDealLink>
}

export function DealStatusIndicator(props: {
  status: DailyControlStatus
  label: string
}) {
  return (
    <span
      className={`dc-deal-status-indicator ${props.status}`}
      aria-label={props.label}
      title={props.label}
    >
      {STATUS_SYMBOL[props.status]}
    </span>
  )
}
