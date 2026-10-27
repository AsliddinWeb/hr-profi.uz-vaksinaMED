import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import type { SearchResult } from './api'

/** /search?q=...: global qidiruv (xodimlar, nomzodlar, topshiriqlar, ticketlar, mehmonlar, mashinalar va h.k.), faqat ruxsat etilganlar. */
export function SearchPage() {
  const { t } = useTranslation()
  const [sp] = useSearchParams()
  const q = (sp.get('q') ?? '').trim()
  const res = useQuery({ queryKey: ['search', q], queryFn: () => api<SearchResult>(`/api/v1/search?q=${encodeURIComponent(q)}`), enabled: q.length >= 2, placeholderData: (p) => p })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('search.title')} subtitle={q ? t('search.for', { q }) : t('search.hint')} />
      {q.length < 2 ? (
        <p className="text-sm text-muted">{t('search.tooShort')}</p>
      ) : !res.data ? (
        <Skeleton className="h-48" />
      ) : res.data.groups.length === 0 ? (
        <Card className="p-10 text-center text-muted">{t('search.none')}</Card>
      ) : (
        res.data.groups.map((g) => (
          <Card key={g.type} className="overflow-hidden">
            <h2 className="px-5 pt-4 text-sm font-semibold text-muted">{t(`search.type.${g.type}`)}</h2>
            <ul className="mt-2 divide-y divide-border">
              {g.items.map((i) => (
                <li key={i.id}>
                  <Link to={i.link} className="block px-5 py-2.5 hover:bg-surface-2">
                    <span className="font-medium">{i.title}</span>
                    {i.subtitle && <span className="ml-2 text-xs text-muted">{i.subtitle}</span>}
                  </Link>
                </li>
              ))}
            </ul>
          </Card>
        ))
      )}
    </div>
  )
}
