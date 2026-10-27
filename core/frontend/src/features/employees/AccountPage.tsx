import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { UserPicker, type PickedUser } from '../../components/UserPicker'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { roleName, type RoleOption } from '../users/api'
import type { Employee } from './api'

/** /employees/:id/account: tizimga kirish hisobi (yaratish, mavjudni ulash, uzish). */
export function AccountPage() {
  const empId = Number(useParams().id)
  const emp = useQuery({ queryKey: ['employees', 'one', empId], queryFn: () => api<Employee>(`/api/v1/employees/${empId}`), retry: false })
  if (emp.isLoading) return <Skeleton className="mx-auto h-80 max-w-3xl" />
  if (emp.error instanceof ApiError && emp.error.status === 404) return <NotFound />
  return emp.data ? <AccountForm emp={emp.data} /> : null
}

function AccountForm({ emp }: { emp: Employee }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const can = useCan()
  const [roleKey, setRoleKey] = useState('')
  const [picked, setPicked] = useState<PickedUser | null>(null)
  const back = `/employees/${emp.id}`

  const roles = useQuery({ queryKey: ['assignable-roles'], queryFn: () => api<RoleOption[]>('/api/v1/users/assignable-roles'), enabled: !emp.user })
  const done = () => qc.invalidateQueries({ queryKey: ['employees'] })

  const create = useMutation({
    mutationFn: () => send<{ login: string; temp_password: string }>('POST', `/api/v1/employees/${emp.id}/account`, { role_key: roleKey }),
    onSuccess: async (r) => {
      await done()
      navigate('/users/credentials', { replace: true, state: { login: r.login, name: emp.full_name, password: r.temp_password, backTo: back, backLabel: t('employees.toCard') } })
    },
  })
  const link = useMutation({
    mutationFn: () => send('POST', `/api/v1/employees/${emp.id}/account`, { user_id: picked?.id }),
    onSuccess: async () => {
      await done()
      toast.push({ title: t('employees.accountLinked'), tone: 'success' })
      navigate(back)
    },
  })
  const unlink = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/employees/${emp.id}/account`),
    onSuccess: async () => {
      await done()
      toast.push({ title: t('employees.accountUnlinked'), tone: 'success' })
      navigate(back)
    },
  })

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t('employees.account')} subtitle={emp.full_name} backTo={back} backLabel={t('employees.toCard')} />

      {emp.user ? (
        <FormSection title={t('employees.accountExists')}>
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="font-mono font-medium">{emp.user.login}</span>
            {emp.user.is_active ? <Badge tone="success">{t('users.active')}</Badge> : <Badge tone="danger">{t('users.blocked')}</Badge>}
            {can('users.update') && (
              <Link to={`/users/${emp.user.id}/edit`} className="font-medium text-primary hover:underline">
                {t('employees.manageUser')}
              </Link>
            )}
          </div>
          <div>
            <Button
              variant="outline"
              className="text-danger"
              disabled={unlink.isPending}
              onClick={async () => {
                if (await confirm({ title: t('employees.unlinkAccount'), body: t('employees.unlinkHint'), danger: true, confirmLabel: t('employees.unlink') })) unlink.mutate()
              }}
            >
              {t('employees.unlinkAccount')}
            </Button>
          </div>
          {unlink.isError && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, unlink.error)}
            </p>
          )}
        </FormSection>
      ) : emp.status !== 'active' ? (
        <FormSection title={t('employees.account')}>
          <p className="text-sm text-muted">{t('employees.dismissedNoAccount')}</p>
        </FormSection>
      ) : (
        <>
          <FormSection title={t('employees.createAccount')} description={t('employees.createAccountHint')}>
            <Field label={t('users.role')}>
              {(id) => (
                <Select id={id} value={roleKey} onChange={(e) => setRoleKey(e.target.value)}>
                  <option value="">{t('users.chooseRole')}</option>
                  {roles.data?.map((r) => (
                    <option key={r.key} value={r.key} disabled={!r.assignable}>
                      {roleName(r, i18n.language)}
                      {!r.assignable ? ` — ${t('users.noRight')}` : ''}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <div>
              <Button onClick={() => create.mutate()} disabled={!roleKey || create.isPending}>
                {t('employees.createAccount')}
              </Button>
            </div>
            {create.isError && (
              <p role="alert" className="text-sm text-danger">
                {errorText(t, create.error)}
              </p>
            )}
          </FormSection>
          <FormSection title={t('employees.linkAccount')} description={t('employees.linkAccountHint')}>
            <Field label={t('users.fullName')}>{(id) => <UserPicker id={id} value={picked} onChange={setPicked} />}</Field>
            <div>
              <Button variant="outline" onClick={() => link.mutate()} disabled={!picked || link.isPending}>
                {t('employees.linkAccount')}
              </Button>
            </div>
            {link.isError && (
              <p role="alert" className="text-sm text-danger">
                {errorText(t, link.error)}
              </p>
            )}
          </FormSection>
        </>
      )}
      <FormFooter>
        <Button variant="outline" onClick={() => navigate(back)}>
          {t('employees.toCard')}
        </Button>
      </FormFooter>
    </div>
  )
}
