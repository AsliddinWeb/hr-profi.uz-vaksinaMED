import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { RecruitTabs } from './RecruitTabs'
import { STAGE_TONE, STAGES, type Application, type Page } from './api'

const SIZE = 25

/** /recruit/applications: barcha arizalar. */
export function ApplicationsPage() {
  const { t, i18n } = useTranslation()
  const manage = useCan()('recruit.manage')
  const [stage, setStage] = useState('open')
  const [text, setText] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), size: String(SIZE) })
  if (stage) params.set('stage', stage)
  if (text.trim()) params.set('q', text.trim())
  const q = useQuery({ queryKey: ['recruit', 'applications', params.toString()], queryFn: () => api<Page<Application>>(`/api/v1/recruit/applications?${params}`), placeholderData: (p) => p })

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('recruit.title')}
        subtitle={t('recruit.subtitle')}
        actions={
          manage && (
            <Link to="/recruit/applications/new">
              <Button>{t('recruit.application.add')}</Button>
            </Link>
          )
        }
      />
      <RecruitTabs />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Input className="w-56" value={text} onChange={(e) => (setText(e.target.value), setPage(1))} placeholder={t('recruit.candidate.search')} aria-label={t('recruit.candidate.search')} />
        <Select className="w-auto" value={stage} onChange={(e) => (setStage(e.target.value), setPage(1))} aria-label={t('recruit.application.stage')}>
          <option value="open">{t('recruit.application.inProcess')}</option>
          <option value="">{t('attendance.allStatuses')}</option>
          {STAGES.map((s) => (
            <option key={s} value={s}>
              {t(`recruit.stage.${s}`)}
            </option>
          ))}
        </Select>
      </div>
      {q.isLoading ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-border text-xs text-muted">
                <tr>
                  <th className="px-5 py-2.5 font-medium">{t('recruit.candidate.name')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('recruit.application.vacancy')}</th>
                  <th className="px-5 py-2.5 font-medium">{t('recruit.application.stage')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('recruit.vacancy.recruiter')}</th>
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('recruit.application.changed')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {q.data?.items.map((a) => (
                  <tr key={a.id}>
                    <td className="px-5 py-2.5">
                      <Link to={`/recruit/applications/${a.id}`} className="font-medium hover:text-primary hover:underline">
                        {a.candidate.full_name}
                      </Link>
                      <div className="text-xs text-muted tabular-nums">{a.candidate.phone}</div>
                    </td>
                    <td className="px-5 py-2.5">
                      <Link to={`/recruit/vacancies/${a.vacancy.id}`} className="hover:underline">
                        {a.vacancy.title}
                      </Link>
                    </td>
                    <td className="px-5 py-2.5">
                      <Badge tone={STAGE_TONE[a.stage]}>{t(`recruit.stage.${a.stage}`)}</Badge>
                      {a.rating && <span className="ml-1.5 text-xs text-warning">{'★'.repeat(a.rating)}</span>}
                    </td>
                    <td className="hidden px-5 py-2.5 text-muted md:table-cell">{a.recruiter?.name ?? '—'}</td>
                    <td className="hidden px-5 py-2.5 tabular-nums text-muted sm:table-cell">{formatDateTime(a.stage_changed_at, i18n.language)}</td>
                  </tr>
                ))}
                {q.data && q.data.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center text-muted">
                      {t('common.empty')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {q.data && q.data.total > SIZE && <Pagination page={page} size={SIZE} total={q.data.total} onPage={setPage} />}
    </div>
  )
}
