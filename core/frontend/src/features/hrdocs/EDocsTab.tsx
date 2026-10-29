import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate } from '../../lib/format'
import { useTranslation } from 'react-i18next'

interface FeedItem {
  type: 'application' | 'order' | 'letter' | 'penalty'
  id: number
  number: string | null
  title: string
  date: string
  status: string
  link: string
}

/** Xodim kartochkasidagi «Elektron hujjatlar»: ariza, buyruq, tushuntirish xati va jarimalar bitta lentada. */
export function EDocsTab({ empId, lang }: { empId: number; lang: string }) {
  const { t } = useTranslation()
  const q = useQuery({ queryKey: ['staffdocs', 'feed', empId], queryFn: () => api<{ items: FeedItem[] }>(`/api/v1/staffdocs/employee/${empId}/feed`), retry: false })
  if (!q.data) return <Skeleton className="h-32" />
  if (q.data.items.length === 0) return <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>
  return (
    <div className="flex flex-col gap-2">
      {q.data.items.map((it) => (
        <Link key={`${it.type}-${it.id}`} to={it.link}>
          <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
            <div>
              <div className="font-medium">
                {it.title} {it.number && <span className="text-xs font-normal text-muted">{it.number}</span>}
              </div>
              <div className="text-sm text-muted">
                {t(`staffdocs.feed.${it.type}`)} · {formatDate(it.date, lang)}
              </div>
            </div>
            <Badge>{it.status}</Badge>
          </Card>
        </Link>
      ))}
    </div>
  )
}
