import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Lock } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { hasPermission, useCan, useMe } from '../auth/useAuth'
import { roleName, type RoleRow } from '../users/api'

interface Perm {
  key: string
  uz: string
  ru: string
}

export function RolesPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const can = useCan()
  const { data: me } = useMe()
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const canManage = can('roles.manage')

  const roles = useQuery({ queryKey: ['roles'], queryFn: () => api<RoleRow[]>('/api/v1/roles') })
  const catalog = useQuery({ queryKey: ['permissions'], queryFn: () => api<Perm[]>('/api/v1/permissions') })

  // Tahrirlanayotgan (saqlanmagan) holat: roleId -> Set<permission>
  const [draft, setDraft] = useState<Record<number, Set<string>>>({})
  const [savingId, setSavingId] = useState<number | null>(null)

  const save = useMutation({
    mutationFn: (role: RoleRow) =>
      send('PUT', `/api/v1/roles/${role.id}/permissions`, { permissions: [...(draft[role.id] ?? [])] }),
    onMutate: (role) => setSavingId(role.id),
    onSuccess: async (_d, role) => {
      setDraft(({ [role.id]: _gone, ...rest }) => rest)
      await qc.invalidateQueries({ queryKey: ['roles'] })
      await qc.invalidateQueries({ queryKey: ['me'] })
    },
    onSettled: () => setSavingId(null),
  })

  const groups = useMemo(() => {
    const map = new Map<string, Perm[]>()
    for (const p of catalog.data ?? []) {
      const g = p.key.split('.')[0]
      map.set(g, [...(map.get(g) ?? []), p])
    }
    return [...map.entries()]
  }, [catalog.data])

  const current = (r: RoleRow) => draft[r.id] ?? new Set(r.permissions)
  const granted = (r: RoleRow, key: string) => {
    const set = current(r)
    return set.has('*') || set.has(key) || hasPermission([...set], key)
  }
  const dirty = (r: RoleRow) => draft[r.id] !== undefined

  const toggle = (r: RoleRow, key: string) => {
    const next = new Set(current(r))
    if (next.has(key)) next.delete(key)
    else next.add(key)
    setDraft((d) => ({ ...d, [r.id]: next }))
  }

  const loading = roles.isLoading || catalog.isLoading

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">{t('roles.title')}</h1>
        <p className="mt-1 text-sm text-muted">{t('roles.subtitle')}</p>
      </div>

      {save.isError && (
        <p role="alert" className="rounded-control bg-danger/10 px-4 py-3 text-sm text-danger">
          {errorText(t, save.error)}
        </p>
      )}

      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border">
              <tr>
                <th className="sticky left-0 bg-surface px-5 py-4 text-xs font-medium text-muted">
                  {t('roles.permission')}
                </th>
                {roles.data?.map((r) => (
                  <th key={r.id} className="min-w-28 px-3 py-4 text-center align-bottom">
                    <div className="flex flex-col items-center gap-1">
                      <span className="text-sm font-semibold">{roleName(r, lang)}</span>
                      <span className="text-xs font-normal text-muted">
                        {r.users} {t('roles.users')}
                      </span>
                      {r.locked && (
                        <Badge>
                          <Lock className="size-3" /> {t('roles.locked')}
                        </Badge>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td className="px-5 py-4" colSpan={12}>
                    <Skeleton className="h-24" />
                  </td>
                </tr>
              )}
              {groups.map(([group, perms]) => (
                <GroupRows key={group} group={group} perms={perms} />
              ))}
            </tbody>
            {canManage && (
              <tfoot>
                <tr className="border-t border-border">
                  <td className="sticky left-0 bg-surface px-5 py-2.5" />
                  {roles.data?.map((r) => (
                    <td key={r.id} className="px-3 py-3 text-center">
                      {dirty(r) && (
                        <Button className="h-8 px-3" disabled={savingId === r.id} onClick={() => save.mutate(r)}>
                          {t('common.save')}
                        </Button>
                      )}
                    </td>
                  ))}
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      </Card>
    </div>
  )

  function GroupRows({ group, perms }: { group: string; perms: Perm[] }) {
    return (
      <>
        <tr className="bg-surface-2">
          <td colSpan={(roles.data?.length ?? 0) + 1} className="sticky left-0 px-5 py-2 text-xs font-semibold uppercase tracking-wide text-muted">
            {t(`roles.groups.${group}`, { defaultValue: group })}
          </td>
        </tr>
        {perms.map((p) => (
          <tr key={p.key} className="border-t border-border">
            <td className="sticky left-0 bg-surface px-5 py-2.5">
              <div className="font-medium">{p[lang]}</div>
              <div className="font-mono text-xs text-muted">{p.key}</div>
            </td>
            {roles.data?.map((r) => {
              const viaWildcard = granted(r, p.key) && !current(r).has(p.key)
              // Faqat o'zingizda bor ruxsatni o'zgartira olasiz (backend ham tekshiradi)
              const editable = canManage && !r.locked && hasPermission(me?.permissions, p.key)
              return (
                <td key={r.id} className="px-3 py-3 text-center">
                  <input
                    type="checkbox"
                    className="size-4 accent-[var(--primary)]"
                    checked={granted(r, p.key)}
                    disabled={!editable || viaWildcard}
                    onChange={() => toggle(r, p.key)}
                    aria-label={`${roleName(r, lang)}: ${p[lang]}`}
                    title={viaWildcard ? t('roles.viaWildcard') : undefined}
                  />
                </td>
              )
            })}
          </tr>
        ))}
      </>
    )
  }
}
