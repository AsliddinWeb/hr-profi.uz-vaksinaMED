import { useQuery } from '@tanstack/react-query'
import { CheckCircle2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { branchTitle, type Quality } from './api'

/** /pharmacy/quality: tarmoq ma'lumotlari to'liqligi (qaysi filialda mudir, koordinator, joylashuv, me'yor, ish vaqti yo'q). */
export function QualityPage() {
  const { t } = useTranslation()
  const q = useQuery({ queryKey: ['pharmacy', 'quality'], queryFn: () => api<Quality>('/api/v1/pharmacy/quality') })
  const d = q.data
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('pharmacy.quality.title')} subtitle={t('pharmacy.quality.subtitle')} backTo="/pharmacy" backLabel={t('pharmacy.title')} />
      {!d ? (
        <Skeleton className="h-72" />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Card tint="lilac" className="p-5">
              <div className="text-sm text-muted">{t('pharmacy.quality.total')}</div>
              <div className="mt-2 text-3xl font-semibold tabular-nums">{d.branches}</div>
              <div className="text-xs text-muted">{t('pharmacy.quality.active', { count: d.active })}</div>
            </Card>
            <Card tint="mint" className="p-5">
              <div className="text-sm text-muted">{t('pharmacy.quality.complete')}</div>
              <div className="mt-2 text-3xl font-semibold tabular-nums">{d.complete}</div>
              <div className="text-xs text-muted">{d.branches ? Math.round((d.complete / d.branches) * 100) : 0}%</div>
            </Card>
            <Card tint="sand" className="p-5">
              <div className="text-sm text-muted">{t('pharmacy.quality.withIssues')}</div>
              <div className="mt-2 text-3xl font-semibold tabular-nums">{d.branches - d.complete}</div>
            </Card>
          </div>
          {d.issues.length === 0 && (
            <Card className="flex items-center gap-3 p-6">
              <CheckCircle2 className="size-6 text-success" />
              {t('pharmacy.quality.allGood')}
            </Card>
          )}
          {d.issues.map((i) => (
            <Card key={i.code} className="p-5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="font-semibold">{t(`pharmacy.quality.codes.${i.code}`)}</h2>
                <Badge tone="warning">{i.count}</Badge>
              </div>
              <p className="text-xs text-muted">{t(`pharmacy.quality.hints.${i.code}`)}</p>
              <ul className="mt-3 flex flex-wrap gap-1.5">
                {i.branches.slice(0, 60).map((b) => (
                  <li key={b.id}>
                    <Link to={`/pharmacy/${b.id}`} className="inline-block rounded-full bg-surface-2 px-2.5 py-1 text-xs hover:bg-border">
                      {branchTitle(b)}
                    </Link>
                  </li>
                ))}
                {i.branches.length > 60 && <li className="px-1 py-1 text-xs text-muted">+{i.branches.length - 60}</li>}
              </ul>
            </Card>
          ))}
        </>
      )}
    </div>
  )
}
