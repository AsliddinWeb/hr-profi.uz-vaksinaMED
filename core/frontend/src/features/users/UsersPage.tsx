import { useQuery } from '@tanstack/react-query'
import { Plus, Search } from 'lucide-react'
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
import { formatDateTime, initials } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { roleName, type RoleOption, type UsersPage as Page } from './api'

const SIZE = 20

export function UsersPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const [q, setQ] = useState('')
  const [role, setRole] = useState('')
  const [active, setActive] = useState('')
  const [page, setPage] = useState(1)

  const roles = useQuery({ queryKey: ['assignable-roles'], queryFn: () => api<RoleOption[]>('/api/v1/users/assignable-roles') })

  const params = new URLSearchParams({ page: String(page), size: String(SIZE) })
  if (q.trim()) params.set('q', q.trim())
  if (role) params.set('role', role)
  if (active) params.set('active', active)
  const users = useQuery({
    queryKey: ['users', 'list', q, role, active, page],
    queryFn: () => api<Page>(`/api/v1/users?${params}`),
    placeholderData: (prev) => prev,
  })
  const data = users.data
  const editable = can('users.update')

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader
        title={t('users.title')}
        subtitle={t('users.subtitle')}
        actions={
          can('users.create') && (
            <Link to="/users/new">
              <Button>
                <Plus className="size-4" />
                {t('users.add')}
              </Button>
            </Link>
          )
        }
      />

      <Card className="flex flex-wrap items-center gap-3 p-4">
        <label className="relative min-w-36 max-w-64 flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
          <Input
            className="pl-9"
            placeholder={t('users.search')}
            value={q}
            onChange={(e) => {
              setQ(e.target.value)
              setPage(1)
            }}
            aria-label={t('users.search')}
          />
        </label>
        <Select
          className="w-auto"
          value={role}
          onChange={(e) => {
            setRole(e.target.value)
            setPage(1)
          }}
          aria-label={t('users.role')}
        >
          <option value="">{t('users.allRoles')}</option>
          {roles.data?.map((r) => (
            <option key={r.key} value={r.key}>
              {roleName(r, i18n.language)}
            </option>
          ))}
        </Select>
        <Select
          className="w-auto"
          value={active}
          onChange={(e) => {
            setActive(e.target.value)
            setPage(1)
          }}
          aria-label={t('users.status')}
        >
          <option value="">{t('users.allStatuses')}</option>
          <option value="true">{t('users.active')}</option>
          <option value="false">{t('users.blocked')}</option>
        </Select>
      </Card>

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                <th className="px-5 py-2.5 font-medium">{t('users.fullName')}</th>
                <th className="px-5 py-2.5 font-medium">{t('users.role')}</th>
                <th className="px-5 py-2.5 font-medium">{t('users.status')}</th>
                <th className="hidden px-5 py-2.5 font-medium md:table-cell">{t('users.lastLogin')}</th>
                <th className="px-5 py-2.5" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {users.isLoading &&
                Array.from({ length: 5 }, (_, i) => (
                  <tr key={i}>
                    <td colSpan={5} className="px-5 py-2.5">
                      <Skeleton className="h-8" />
                    </td>
                  </tr>
                ))}
              {data?.items.map((u) => (
                <tr key={u.id} className={u.is_active ? '' : 'opacity-60'}>
                  <td className="px-5 py-2.5">
                    <div className="flex items-center gap-3">
                      <span className="grid size-9 shrink-0 place-items-center rounded-full bg-surface-2 text-xs font-semibold">{initials(u.full_name)}</span>
                      <div className="min-w-0">
                        {editable ? (
                          <Link to={`/users/${u.id}/edit`} className="block truncate font-medium hover:text-primary hover:underline">
                            {u.full_name}
                          </Link>
                        ) : (
                          <div className="truncate font-medium">{u.full_name}</div>
                        )}
                        <div className="truncate text-xs text-muted">
                          {u.login}
                          {u.phone ? ` · ${u.phone}` : ''}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-2.5">{roleName({ name_uz: u.role_name_uz, name_ru: u.role_name_ru }, i18n.language)}</td>
                  <td className="px-5 py-2.5">
                    {u.is_active ? <Badge tone="success">{t('users.active')}</Badge> : <Badge tone="danger">{t('users.blocked')}</Badge>}
                    {u.must_change_password && (
                      <Badge tone="warning" className="ml-1">
                        {t('users.pending')}
                      </Badge>
                    )}
                  </td>
                  <td className="hidden px-5 py-2.5 text-muted md:table-cell">{formatDateTime(u.last_login_at, i18n.language)}</td>
                  <td className="px-5 py-2.5 text-right">
                    {editable && (
                      <Link to={`/users/${u.id}/edit`}>
                        <Button variant="ghost" className="h-8 px-2">
                          {t('common.edit')}
                        </Button>
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
              {data && data.items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-10 text-center text-muted">
                    {t('common.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        {data && (
          <div className="border-t border-border px-5 py-2.5">
            <Pagination page={page} size={SIZE} total={data.total} onPage={setPage} />
          </div>
        )}
      </Card>
    </div>
  )
}
