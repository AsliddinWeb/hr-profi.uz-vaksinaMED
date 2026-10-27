import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Trash2 } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send, upload } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText, fieldErrors } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { roleName, type RoleOption } from '../users/api'
import { Avatar } from './Avatar'
import { AssignmentFields } from './AssignmentFields'
import type { WorkGroup } from '../schedule/api'
import type { Assignment } from './assignment'
import { today, type DuplicateMatch, type Employee } from './api'

/** /employees/new va /employees/:id/edit */
export function EmployeeFormPage() {
  const { id } = useParams()
  const empId = id ? Number(id) : null
  const emp = useQuery({
    queryKey: ['employees', 'one', empId],
    queryFn: () => api<Employee>(`/api/v1/employees/${empId}`),
    enabled: empId !== null,
    retry: false,
  })
  if (empId === null) return <EmployeeForm emp={null} />
  if (emp.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (emp.error instanceof ApiError && emp.error.status === 404) return <NotFound />
  if (!emp.data) return null
  return <EmployeeForm key={emp.data.id} emp={emp.data} />
}

function EmployeeForm({ emp }: { emp: Employee | null }) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const can = useCan()
  const confirm = useConfirm()
  const sensitive = can('employees.sensitive')
  const back = emp ? `/employees/${emp.id}` : '/employees'

  const [lastName, setLastName] = useState(emp?.last_name ?? '')
  const [firstName, setFirstName] = useState(emp?.first_name ?? '')
  const [middleName, setMiddleName] = useState(emp?.middle_name ?? '')
  const [gender, setGender] = useState(emp?.gender ?? '')
  const [birthDate, setBirthDate] = useState(emp?.birth_date ?? '')
  const [phone, setPhone] = useState(emp?.phone ?? '')
  const [phone2, setPhone2] = useState(emp?.phone2 ?? '')
  const [email, setEmail] = useState(emp?.email ?? '')
  const [address, setAddress] = useState(emp?.address ?? '')
  const [passport, setPassport] = useState(sensitive ? (emp?.passport_no ?? '') : '')
  const [pinfl, setPinfl] = useState(sensitive ? (emp?.pinfl ?? '') : '')
  const [assignment, setAssignment] = useState<Assignment>({ departmentId: '', positionId: '', branchId: '' })
  const [hireDate, setHireDate] = useState(emp?.hire_date ?? today())
  const [createAccount, setCreateAccount] = useState(false)
  const [roleKey, setRoleKey] = useState('')
  const [photo, setPhoto] = useState<File | null>(null)
  const [photoV, setPhotoV] = useState(0)
  const [confirmDup, setConfirmDup] = useState(false)
  const [workGroupId, setWorkGroupId] = useState(emp?.work_group?.id?.toString() ?? '')
  const fileRef = useRef<HTMLInputElement>(null)

  const roles = useQuery({
    queryKey: ['assignable-roles'],
    queryFn: () => api<RoleOption[]>('/api/v1/users/assignable-roles'),
    enabled: createAccount && can('employees.accounts'),
  })

  const groups = useQuery({ queryKey: ['schedule', 'groups'], queryFn: () => api<WorkGroup[]>('/api/v1/schedule/groups'), enabled: can('schedule.read') })

  const refresh = () => qc.invalidateQueries({ queryKey: ['employees'] })

  const save = useMutation({
    mutationFn: async () => {
      const common = {
        last_name: lastName,
        first_name: firstName,
        middle_name: middleName || null,
        gender: gender || null,
        phone: phone || null,
        phone2: phone2 || null,
        email: email || null,
        ...(sensitive ? { birth_date: birthDate || null, address: address || null, passport_no: passport || null, pinfl: pinfl || null } : {}),
        work_group_id: workGroupId ? Number(workGroupId) : null,
        confirm_duplicate: confirmDup,
      }
      if (emp) return send<Employee>('PATCH', `/api/v1/employees/${emp.id}`, { ...common, hire_date: hireDate || null })
      return send<{ employee: Employee; temp_password: string | null; login: string | null }>('POST', '/api/v1/employees', {
        ...common,
        department_id: assignment.departmentId ? Number(assignment.departmentId) : null,
        position_id: assignment.positionId ? Number(assignment.positionId) : null,
        branch_id: assignment.branchId ? Number(assignment.branchId) : null,
        hire_date: hireDate || null,
        create_account: createAccount,
        role_key: createAccount ? roleKey : null,
      })
    },
    onSuccess: async (res) => {
      if (!emp) {
        const created = res as { employee: Employee; temp_password: string | null; login: string | null }
        if (photo) await upload('PUT', `/api/v1/employees/${created.employee.id}/photo`, photoForm(photo)).catch(() => {})
        await refresh()
        if (created.temp_password) {
          navigate('/users/credentials', {
            replace: true,
            state: { login: created.login, name: created.employee.full_name, password: created.temp_password, backTo: `/employees/${created.employee.id}`, backLabel: t('employees.toCard') },
          })
        } else {
          toast.push({ title: t('common.saved'), tone: 'success' })
          navigate(`/employees/${created.employee.id}`, { replace: true })
        }
      } else {
        await refresh()
        toast.push({ title: t('common.saved'), tone: 'success' })
        navigate(back)
      }
    },
  })

  const photoMutation = useMutation({
    mutationFn: (file: File) => upload('PUT', `/api/v1/employees/${emp?.id}/photo`, photoForm(file)),
    onSuccess: async () => {
      setPhotoV(Date.now())
      await refresh()
    },
  })
  const photoDelete = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/employees/${emp?.id}/photo`),
    onSuccess: async () => {
      setPhotoV(Date.now())
      await refresh()
    },
  })

  const err = save.error
  const fe = fieldErrors(t, err)
  const dup = err instanceof ApiError && (err.code === 'possible_duplicate' || err.code === 'duplicate_identifier') ? err : null
  const matches = (dup?.extra.matches ?? []) as DuplicateMatch[]
  const lang = i18n.language

  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const accountInvalid = createAccount && !roleKey

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader
        title={emp ? t('employees.edit') : t('employees.add')}
        subtitle={emp ? `№${emp.employee_no} · ${emp.full_name}` : t('employees.addHint')}
        backTo={back}
        backLabel={emp ? t('employees.toCard') : t('employees.title')}
      />

      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('employees.sectionPhoto')}>
          <div className="flex items-center gap-4">
            <Avatar id={emp?.id ?? 0} name={`${lastName} ${firstName}`.trim() || '?'} hasPhoto={!!emp?.has_photo && (emp?.has_photo ?? false)} size={72} v={photoV} />
            {!photo || emp ? null : <span className="text-sm text-muted">{photo.name}</span>}
            <div className="flex flex-wrap gap-2">
              <input
                ref={fileRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="sr-only"
                onChange={(e) => {
                  const f = e.target.files?.[0]
                  if (!f) return
                  if (emp && can('employees.update')) photoMutation.mutate(f)
                  else setPhoto(f)
                  e.target.value = ''
                }}
              />
              <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={photoMutation.isPending}>
                <Camera className="size-4" />
                {t('employees.choosePhoto')}
              </Button>
              {emp?.has_photo && (
                <Button
                  variant="ghost"
                  className="text-danger"
                  onClick={async () => {
                    if (await confirm({ title: t('employees.deletePhoto'), danger: true, confirmLabel: t('common.delete') })) photoDelete.mutate()
                  }}
                >
                  <Trash2 className="size-4" />
                  {t('common.delete')}
                </Button>
              )}
            </div>
          </div>
          {(photoMutation.isError || photoDelete.isError) && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, photoMutation.error ?? photoDelete.error)}
            </p>
          )}
          <p className="text-xs text-muted">{t('employees.photoHint')}</p>
        </FormSection>

        <FormSection title={t('employees.sectionPersonal')}>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('employees.lastName')} error={fe.last_name}>
              {(id) => <Input id={id} value={lastName} onChange={(e) => setLastName(e.target.value)} required maxLength={80} autoFocus />}
            </Field>
            <Field label={t('employees.firstName')} error={fe.first_name}>
              {(id) => <Input id={id} value={firstName} onChange={(e) => setFirstName(e.target.value)} required maxLength={80} />}
            </Field>
            <Field label={t('employees.middleName')}>
              {(id) => <Input id={id} value={middleName} onChange={(e) => setMiddleName(e.target.value)} maxLength={80} />}
            </Field>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('employees.gender')}>
              {(id) => (
                <Select id={id} value={gender} onChange={(e) => setGender(e.target.value as 'm' | 'f' | '')}>
                  <option value="">—</option>
                  <option value="m">{t('employees.male')}</option>
                  <option value="f">{t('employees.female')}</option>
                </Select>
              )}
            </Field>
            {sensitive && (
              <Field label={t('employees.birthDate')} error={fe.birth_date}>
                {(id) => <Input id={id} type="date" value={birthDate} onChange={(e) => setBirthDate(e.target.value)} max={today()} />}
              </Field>
            )}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('employees.phone')} error={fe.phone} hint={t('employees.phoneHint')}>
              {(id) => <Input id={id} value={phone} onChange={(e) => setPhone(e.target.value)} inputMode="tel" placeholder="+998 90 123 45 67" />}
            </Field>
            <Field label={t('employees.phone2')} error={fe.phone2}>
              {(id) => <Input id={id} value={phone2} onChange={(e) => setPhone2(e.target.value)} inputMode="tel" />}
            </Field>
          </div>
          <Field label={t('employees.email')} error={fe.email}>
            {(id) => <Input id={id} type="email" value={email} onChange={(e) => setEmail(e.target.value)} maxLength={120} />}
          </Field>
          {sensitive && (
            <Field label={t('employees.address')}>{(id) => <Input id={id} value={address} onChange={(e) => setAddress(e.target.value)} maxLength={300} />}</Field>
          )}
        </FormSection>

        {sensitive && (
          <FormSection title={t('employees.sectionIdentity')} description={t('employees.identityHint')}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t('employees.passport')} error={fe.passport_no} hint="AA1234567">
                {(id) => <Input id={id} value={passport} onChange={(e) => setPassport(e.target.value.toUpperCase())} maxLength={12} />}
              </Field>
              <Field label={t('employees.pinfl')} error={fe.pinfl} hint={t('employees.pinflHint')}>
                {(id) => <Input id={id} value={pinfl} onChange={(e) => setPinfl(e.target.value)} inputMode="numeric" maxLength={14} />}
              </Field>
            </div>
          </FormSection>
        )}

        <FormSection
          title={t('employees.sectionJob')}
          description={emp ? t('employees.jobEditHint') : t('employees.jobCreateHint')}
        >
          {emp ? (
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
              <span>
                <span className="text-muted">{t('employees.department')}: </span>
                {emp.department?.name ?? '—'}
              </span>
              <span>
                <span className="text-muted">{t('employees.position')}: </span>
                {emp.position?.name ?? '—'}
              </span>
              <span>
                <span className="text-muted">{t('employees.branch')}: </span>
                {emp.branch?.name ?? '—'}
              </span>
              {can('employees.transfer') && emp.status === 'active' && (
                <Link to={`/employees/${emp.id}/transfer`} className="font-medium text-primary hover:underline">
                  {t('employees.transfer')}
                </Link>
              )}
            </div>
          ) : (
            <AssignmentFields value={assignment} onChange={setAssignment} errors={fe} />
          )}
          {can('schedule.read') && (
            <Field label={t('employees.workGroup')} hint={t('employees.workGroupHint')} error={fe.work_group_id}>
              {(id) => (
                <Select id={id} value={workGroupId} onChange={(e) => setWorkGroupId(e.target.value)}>
                  <option value="">{t('employees.defaultGroup')}</option>
                  {groups.data
                    ?.filter((g) => g.is_active || String(g.id) === workGroupId)
                    .map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                </Select>
              )}
            </Field>
          )}
          <Field label={t('employees.hireDate')} error={fe.hire_date}>
            {(id) => <Input id={id} type="date" value={hireDate} onChange={(e) => setHireDate(e.target.value)} className="max-w-52" />}
          </Field>
        </FormSection>

        {!emp && can('employees.accounts') && (
          <FormSection title={t('employees.sectionAccount')} description={t('employees.accountHint')}>
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={createAccount} onChange={(e) => setCreateAccount(e.target.checked)} />
              {t('employees.createAccount')}
            </label>
            {createAccount && (
              <Field label={t('users.role')}>
                {(id) => (
                  <Select id={id} value={roleKey} onChange={(e) => setRoleKey(e.target.value)}>
                    <option value="">{t('users.chooseRole')}</option>
                    {roles.data?.filter((r) => r.assignable).map((r) => (
                      <option key={r.key} value={r.key}>
                        {roleName(r, lang)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
          </FormSection>
        )}

        {dup && (
          <div role="alert" className="rounded-card border border-warning/40 bg-warning/10 p-5">
            <p className="font-medium">{dup.code === 'duplicate_identifier' ? t('employees.dupIdentifier') : t('employees.dupPossible')}</p>
            <ul className="mt-3 flex flex-col gap-1.5 text-sm">
              {matches.map((m) => (
                <li key={m.id}>
                  <Link to={`/employees/${m.id}`} target="_blank" className="font-medium text-primary hover:underline">
                    №{m.employee_no} {m.full_name}
                  </Link>{' '}
                  <span className="text-muted">({m.reasons.map((r) => t(`employees.reason.${r}`)).join(', ')})</span>
                </li>
              ))}
            </ul>
            {dup.code === 'possible_duplicate' && (
              <Button
                className="mt-4"
                variant="outline"
                onClick={() => {
                  setConfirmDup(true)
                  setTimeout(() => save.mutate(), 0)
                }}
              >
                {t('employees.saveAnyway')}
              </Button>
            )}
          </div>
        )}

        <FormFooter error={err && !dup && Object.keys(fe).length === 0 ? errorText(t, err) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !lastName.trim() || !firstName.trim() || accountInvalid}>
            {emp ? t('common.save') : t('employees.create')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

function photoForm(file: File): FormData {
  const f = new FormData()
  f.append('file', file)
  return f
}
