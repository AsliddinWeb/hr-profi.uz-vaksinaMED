import { useQuery } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
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
import { LetterList } from './LetterList'
import { LETTER_STATUSES, type LetterPage } from './api'

const SIZE = 30
type Scope = 'mine' | 'issued' | 'all'

/** /letters: tushuntirish xatlari: menga yozilganlar, men so'ragan, hammasi. */
export function LettersPage() {
  const { t } = useTranslation()
  const can = useCan()
  const issuer = can('letters.issue') || can('letters.manage')
  const scopes: Scope[] = [...(can('letters.own') ? (['mine'] as const) : []), ...(issuer ? (['issued'] as const) : []), ...(can('letters.read') ? (['all'] as const) : [])]
  const [scope, setScope] = useState<Scope>(scopes[0] ?? 'mine')
  const [status, setStatus] = useState('')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ scope, page: String(page), size: String(SIZE) })
  if (status) params.set('status', status)
  if (q.trim()) params.set('q', q.trim())
  const list = useQuery({ queryKey: ['letters', 'list', params.toString()], queryFn: () => api<LetterPage>(`/api/v1/letters?${params}`), placeholderData: (p) => p, refetchInterval: 60_000 })

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('letters.title')}
        subtitle={t('letters.subtitle')}
        actions={
          issuer && (
            <Link to="/letters/new">
              <Button>
                <Plus className="size-4" />
                {t('letters.request')}
              </Button>
            </Link>
          )
        }
      />
      <Card className="flex flex-wrap items-center gap-3 p-4">
        {scopes.length > 1 && (
          <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]">
            {scopes.map((s) => (
              <button key={s} onClick={() => (setScope(s), setPage(1))} className={scope === s ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}>
                {t(`letters.scope.${s}`)}
              </button>
            ))}
          </div>
        )}
        <label className="relative min-w-36 max-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input className="pl-9" placeholder={t('letters.search')} value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} aria-label={t('letters.search')} />
        </label>
        <Select className="w-auto" value={status} onChange={(e) => (setStatus(e.target.value), setPage(1))} aria-label={t('attendance.statusLabel')}>
          <option value="">{t('attendance.allStatuses')}</option>
          <option value="open">{t('letters.openOnes')}</option>
          <option value="overdue">{t('letters.overdue')}</option>
          {LETTER_STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`letters.status.${s}`)}
            </option>
          ))}
        </Select>
      </Card>
      {list.isLoading ? <Skeleton className="h-40" /> : <LetterList items={list.data?.items ?? []} showEmployee={scope !== 'mine'} empty={t('common.empty')} />}
      {list.data && list.data.total > SIZE && <Pagination page={page} size={SIZE} total={list.data.total} onPage={setPage} />}
    </div>
  )
}
