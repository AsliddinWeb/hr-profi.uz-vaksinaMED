import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { Fragment, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'

interface Entry {
  id: number
  created_at: string
  actor_login: string | null
  action: string
  entity: string | null
  entity_id: string | null
  ip: string | null
  data: Record<string, unknown> | null
}

interface AuditPage {
  total: number
  items: Entry[]
}

const SIZE = 50
const GROUPS = ['auth.', 'user.', 'role.', 'profile.']

export function AuditPage() {
  const { t, i18n } = useTranslation()
  const [action, setAction] = useState('')
  const [login, setLogin] = useState('')
  const [page, setPage] = useState(1)
  const [open, setOpen] = useState<number | null>(null)

  const params = new URLSearchParams({ page: String(page), size: String(SIZE) })
  if (action) params.set('action', action)
  const query = useQuery({
    queryKey: ['audit', action, page],
    queryFn: () => api<AuditPage>(`/api/v1/audit?${params}`),
    placeholderData: (prev) => prev,
  })

  // Aktor bo'yicha tezkor filtr (joriy sahifa ichida)
  const items = (query.data?.items ?? []).filter((e) => !login.trim() || (e.actor_login ?? '').includes(login.trim().toLowerCase()))
  const tone = (a: string) => (a.includes('failed') || a.includes('blocked') || a.includes('reuse') ? 'danger' : a.startsWith('auth.') ? 'neutral' : 'success')

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('audit.title')}</h1>
        <p className="mt-1 text-sm text-muted">{t('audit.subtitle')}</p>
      </div>

      <Card className="flex flex-wrap gap-3 p-4">
        <Select
          className="w-auto"
          value={action}
          onChange={(e) => {
            setAction(e.target.value)
            setPage(1)
          }}
          aria-label={t('audit.action')}
        >
          <option value="">{t('audit.allActions')}</option>
          {GROUPS.map((g) => (
            <option key={g} value={g}>
              {t(`audit.groups.${g.replace('.', '')}`)}
            </option>
          ))}
        </Select>
        <Input className="max-w-56" placeholder={t('audit.actor')} value={login} onChange={(e) => setLogin(e.target.value)} aria-label={t('audit.actor')} />
      </Card>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="w-8 px-3 py-3" />
                <th className="px-3 py-3 font-medium">{t('audit.time')}</th>
                <th className="px-3 py-3 font-medium">{t('audit.actor')}</th>
                <th className="px-3 py-3 font-medium">{t('audit.action')}</th>
                <th className="hidden px-3 py-3 font-medium md:table-cell">{t('audit.object')}</th>
                <th className="hidden px-3 py-3 font-medium lg:table-cell">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {query.isLoading && (
                <tr>
                  <td colSpan={6} className="px-5 py-2.5">
                    <Skeleton className="h-24" />
                  </td>
                </tr>
              )}
              {items.map((e) => (
                <Fragment key={e.id}>
                  <tr className="cursor-pointer hover:bg-surface-2" onClick={() => setOpen(open === e.id ? null : e.id)}>
                    <td className="px-3 py-3 text-muted">{e.data ? open === e.id ? <ChevronDown className="size-4" /> : <ChevronRight className="size-4" /> : null}</td>
                    <td className="whitespace-nowrap px-3 py-3 text-muted">{formatDateTime(e.created_at, i18n.language)}</td>
                    <td className="px-3 py-3 font-medium">{e.actor_login ?? '—'}</td>
                    <td className="px-3 py-3">
                      <Badge tone={tone(e.action)}>{e.action}</Badge>
                    </td>
                    <td className="hidden px-3 py-3 text-muted md:table-cell">{e.entity ? `${e.entity}${e.entity_id ? ` #${e.entity_id}` : ''}` : '—'}</td>
                    <td className="hidden px-3 py-3 text-muted lg:table-cell">{e.ip ?? '—'}</td>
                  </tr>
                  {open === e.id && e.data && (
                    <tr className="bg-surface-2">
                      <td />
                      <td colSpan={5} className="px-3 py-3">
                        <pre className="overflow-x-auto font-mono text-xs">{JSON.stringify(e.data, null, 2)}</pre>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
              {query.data && items.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-5 py-10 text-center text-muted">
                    {t('common.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {query.data && (
          <div className="border-t border-border px-5 py-2.5">
            <Pagination page={page} size={SIZE} total={query.data.total} onPage={setPage} />
          </div>
        )}
      </Card>
    </div>
  )
}
