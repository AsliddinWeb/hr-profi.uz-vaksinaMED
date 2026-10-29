import clsx from 'clsx'
import { useTranslation } from 'react-i18next'

import { relativeTime } from '../../lib/format'
import { catKey, catLabel, pick, type NotificationItem } from './api'

const dot = {
  info: 'bg-info',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
}

export function NotificationItemRow({ n, onOpen }: { n: NotificationItem; onOpen: (n: NotificationItem) => void }) {
  const { t, i18n } = useTranslation()
  const body = pick(n.body, i18n.language)
  return (
    <button
      onClick={() => onOpen(n)}
      className={clsx(
        'flex w-full items-start gap-3 rounded-control px-3 py-3 text-left transition-colors hover:bg-surface-2',
        !n.read && 'bg-primary/5',
      )}
    >
      <span className={clsx('mt-1.5 size-2.5 shrink-0 rounded-full', n.read ? 'bg-border' : dot[n.severity])} />
      <span className="min-w-0 flex-1">
        <span className={clsx('block text-sm', n.read ? 'font-normal' : 'font-semibold')}>{pick(n.title, i18n.language)}</span>
        {body && <span className="mt-0.5 line-clamp-2 block text-sm text-muted">{body}</span>}
        <span className="mt-1 flex items-center gap-2 text-xs text-muted">
          <span className="rounded-full bg-surface-2 px-2 py-0.5">{catLabel(t, catKey(n.kind))}</span>
          {relativeTime(n.created_at, i18n.language)}
          {n.link && <span aria-hidden>›</span>}
        </span>
      </span>
    </button>
  )
}
