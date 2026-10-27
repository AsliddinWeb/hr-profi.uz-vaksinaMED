import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
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
import { useCan } from '../auth/useAuth'
import { RecruitTabs } from './RecruitTabs'
import { salaryText, VSTATUS_TONE, type VacancyPage } from './api'

const SIZE = 20

/** /recruit/vacancies: ish o'rinlari ro'yxati. */
export function VacanciesPage() {
  const { t } = useTranslation()
  const manage = useCan()('recruit.manage')
  const [status, setStatus] = useState('active')
  const [text, setText] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), size: String(SIZE) })
  if (status) params.set('status', status)
  if (text.trim()) params.set('q', text.trim())
  const q = useQuery({ queryKey: ['recruit', 'vacancies', params.toString()], queryFn: () => api<VacancyPage>(`/api/v1/recruit/vacancies?${params}`), placeholderData: (p) => p })

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('recruit.title')}
        subtitle={t('recruit.subtitle')}
        actions={
          manage && (
            <Link to="/recruit/vacancies/new">
              <Button>
                <Plus className="size-4" />
                {t('recruit.vacancy.add')}
              </Button>
            </Link>
          )
        }
      />
      <RecruitTabs />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Input className="w-56" value={text} onChange={(e) => (setText(e.target.value), setPage(1))} placeholder={t('recruit.search')} aria-label={t('recruit.search')} />
        <Select className="w-auto" value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} aria-label={t('attendance.statusLabel')}>
          <option value="active">{t('recruit.vacancy.activeOnes')}</option>
          <option value="">{t('attendance.allStatuses')}</option>
          {(['draft', 'open', 'paused', 'closed'] as const).map((s) => (
            <option key={s} value={s}>
              {t(`recruit.vacancy.status.${s}`)}
            </option>
          ))}
        </Select>
      </div>
      {q.isLoading ? (
        <Skeleton className="h-48" />
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {q.data?.items.map((v) => {
            const f = v.funnel
            const open = f ? f.new + f.screening + f.interview + f.offer : 0
            return (
              <Link key={v.id} to={`/recruit/vacancies/${v.id}`} className="block">
                <Card className="flex h-full flex-col gap-3 p-5 transition-shadow hover:shadow-card">
                  <div className="flex items-start justify-between gap-3">
                    <h2 className="font-semibold">{v.title}</h2>
                    <Badge tone={VSTATUS_TONE[v.status]}>{t(`recruit.vacancy.status.${v.status}`)}</Badge>
                  </div>
                  <p className="text-sm text-muted">{[v.branch?.name, v.position?.name, salaryText(v.salary_from, v.salary_to)].filter((x) => x && x !== '—').join(' · ') || '—'}</p>
                  <div className="mt-auto flex flex-wrap gap-x-5 gap-y-1 text-sm tabular-nums">
                    <span>
                      <span className="text-muted">{t('recruit.vacancy.inProcess')}: </span>
                      {open}
                    </span>
                    <span>
                      <span className="text-muted">{t('recruit.vacancy.hired')}: </span>
                      {v.hired}/{v.openings}
                    </span>
                    {v.recruiter?.name && <span className="text-muted">{v.recruiter.name}</span>}
                  </div>
                </Card>
              </Link>
            )
          })}
          {q.data?.items.length === 0 && <p className="col-span-full py-10 text-center text-muted">{t('common.empty')}</p>}
        </div>
      )}
      {q.data && q.data.total > SIZE && <Pagination page={page} size={SIZE} total={q.data.total} onPage={setPage} />}
    </div>
  )
}
