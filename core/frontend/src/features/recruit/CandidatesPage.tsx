import { useQuery } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import { RecruitTabs } from './RecruitTabs'
import { SOURCES, type CandidateRow, type Page } from './api'

const SIZE = 25

/** /recruit/candidates: nomzodlar bazasi. */
export function CandidatesPage() {
  const { t } = useTranslation()
  const manage = useCan()('recruit.manage')
  const [text, setText] = useState('')
  const [source, setSource] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), size: String(SIZE) })
  if (text.trim()) params.set('q', text.trim())
  if (source) params.set('source', source)
  const q = useQuery({ queryKey: ['recruit', 'candidates', params.toString()], queryFn: () => api<Page<CandidateRow>>(`/api/v1/recruit/candidates?${params}`), placeholderData: (p) => p })

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-4">
      <PageHeader
        title={t('recruit.title')}
        subtitle={t('recruit.subtitle')}
        actions={
          manage && (
            <Link to="/recruit/candidates/new">
              <Button>
                <Plus className="size-4" />
                {t('recruit.candidate.add')}
              </Button>
            </Link>
          )
        }
      />
      <RecruitTabs />
      <div className="flex flex-wrap items-center gap-3 rounded-card bg-surface p-3 shadow-card">
        <Input className="w-64" value={text} onChange={(e) => (setText(e.target.value), setPage(1))} placeholder={t('recruit.candidate.search')} aria-label={t('recruit.candidate.search')} />
        <Select className="w-auto" value={source} onChange={(e) => (setSource(e.target.value), setPage(1))} aria-label={t('recruit.candidate.source')}>
          <option value="">{t('recruit.candidate.allSources')}</option>
          {SOURCES.map((s) => (
            <option key={s} value={s}>
              {t(`recruit.source.${s}`)}
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
                  <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('recruit.candidate.phone')}</th>
                  <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('recruit.candidate.source')}</th>
                  <th className="px-5 py-2.5 text-right font-medium">{t('recruit.tabs.applications')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {q.data?.items.map((c) => (
                  <tr key={c.id}>
                    <td className="px-5 py-2.5">
                      <Link to={`/recruit/candidates/${c.id}`} className="font-medium hover:text-primary hover:underline">
                        {c.full_name}
                      </Link>
                      {c.skills.length > 0 && <div className="mt-0.5 text-xs text-muted">{c.skills.slice(0, 4).join(' · ')}</div>}
                    </td>
                    <td className="hidden px-5 py-2.5 tabular-nums text-muted sm:table-cell">{c.phone ?? '—'}</td>
                    <td className="hidden px-5 py-2.5 text-muted md:table-cell">{c.source ? t(`recruit.source.${c.source}`) : '—'}</td>
                    <td className="px-5 py-2.5 text-right tabular-nums">{c.applications}</td>
                  </tr>
                ))}
                {q.data && q.data.items.length === 0 && (
                  <tr>
                    <td colSpan={4} className="px-5 py-10 text-center text-muted">
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
