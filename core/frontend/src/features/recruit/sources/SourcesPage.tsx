import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../../components/layout/PageHeader'
import { Card } from '../../../components/ui/Card'
import { Skeleton } from '../../../components/ui/Skeleton'
import { api } from '../../../lib/api'
import { RecruitTabs } from '../RecruitTabs'
import type { SourcesReport } from './api'

/** /recruit/sources: nomzod manbalari: kanal va link egasi bo'yicha ariza, ishga olingan va linkni ochganlar. */
export function SourcesPage() {
  const { t } = useTranslation()
  const q = useQuery({ queryKey: ['recruit', 'sources'], queryFn: () => api<SourcesReport>('/api/v1/recruit/sources') })
  const r = q.data
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('recruit.title')} subtitle={t('recruitSources.reportHint')} />
      <RecruitTabs />
      {!r ? (
        <Skeleton className="h-48" />
      ) : (
        <>
          <Card className="overflow-hidden">
            <h2 className="px-5 pt-5 font-semibold">{t('recruitSources.byChannel')} ({r.total})</h2>
            <table className="mt-3 w-full text-left text-sm">
              <thead className="border-y border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('recruitSources.channelLabel')}</th>
                  <th className="px-3 py-2.5 font-medium">{t('recruitSources.clicks')}</th>
                  <th className="px-3 py-2.5 font-medium">{t('recruitSources.applications')}</th>
                  <th className="px-3 py-2.5 font-medium">{t('recruitSources.hired')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {r.by_channel.map((c) => (
                  <tr key={c.channel}>
                    <td className="px-5 py-2.5">{t(`recruitSources.channel.${c.channel}`, { defaultValue: c.channel })}</td>
                    <td className="px-3 py-2.5 tabular-nums">{c.clicks}</td>
                    <td className="px-3 py-2.5 tabular-nums">{c.applications}</td>
                    <td className="px-3 py-2.5 tabular-nums">{c.hired}</td>
                  </tr>
                ))}
                {r.by_channel.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-5 py-8 text-center text-muted">{t('common.empty')}</td>
                  </tr>
                )}
              </tbody>
            </table>
          </Card>
          <Card className="overflow-hidden">
            <h2 className="px-5 pt-5 font-semibold">{t('recruitSources.byOwner')}</h2>
            <table className="mt-3 w-full text-left text-sm">
              <tbody className="divide-y divide-border">
                {r.by_owner.map((o, i) => (
                  <tr key={i}>
                    <td className="px-5 py-2.5">{o.owner ?? t('recruitSources.noOwner')}</td>
                    <td className="px-3 py-2.5 tabular-nums">{o.applications}</td>
                    <td className="px-3 py-2.5 tabular-nums">{o.hired}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        </>
      )}
    </div>
  )
}
