import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { roleName, type RoleOption } from '../users/api'
import { AssignmentFields } from './AssignmentFields'
import { assignmentParams, type Assignment } from './assignment'
import type { WorkGroup } from '../schedule/api'
import { DISMISS_REASONS, today, type BulkResult } from './api'

const ACTIONS = ['transfer', 'dismiss', 'reinstate', 'create_accounts', 'assign_group'] as const
type Action = (typeof ACTIONS)[number]

/** /employees/bulk/:action: tanlangan xodimlarga ommaviy amal (ro'yxat sahifasidan keladi). */
export function BulkPage() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const action = useParams().action as Action
  const state = useLocation().state as { ids: number[]; names: string[] } | null

  const [assignment, setAssignment] = useState<Assignment>({ departmentId: '', positionId: '', branchId: '' })
  const [date, setDate] = useState(today())
  const [note, setNote] = useState('')
  const [reason, setReason] = useState<string>('own_will')
  const [block, setBlock] = useState(true)
  const [reactivate, setReactivate] = useState(true)
  const [roleKey, setRoleKey] = useState('')
  const [groupId, setGroupId] = useState('')

  const roles = useQuery({ queryKey: ['assignable-roles'], queryFn: () => api<RoleOption[]>('/api/v1/users/assignable-roles'), enabled: action === 'create_accounts' })

  const groups = useQuery({ queryKey: ['schedule', 'groups'], queryFn: () => api<WorkGroup[]>('/api/v1/schedule/groups'), enabled: action === 'assign_group' })

  const run = useMutation({
    mutationFn: () => {
      let params: Record<string, unknown>
      if (action === 'transfer') params = { ...assignmentParams(assignment), effective_date: date, note: note || null }
      else if (action === 'dismiss') params = { date, reason, note: note || null, block_account: block }
      else if (action === 'reinstate') params = { date, note: note || null, reactivate_account: reactivate }
      else if (action === 'assign_group') params = { work_group_id: groupId ? Number(groupId) : null }
      else params = { role_key: roleKey }
      return send<BulkResult>('POST', '/api/v1/employees/bulk', { ids: state?.ids, action, params })
    },
    onSuccess: async (result) => {
      await qc.invalidateQueries({ queryKey: ['employees'] })
      navigate('/employees/bulk-result', { replace: true, state: { result } })
    },
  })

  if (!state?.ids?.length || !ACTIONS.includes(action)) return <Navigate to="/employees" replace />
  const submit = (e: FormEvent) => {
    e.preventDefault()
    run.mutate()
  }
  const noChange = action === 'transfer' && Object.keys(assignmentParams(assignment)).length === 0
  const invalid = noChange || (action === 'create_accounts' && !roleKey) || (action === 'dismiss' && reason === 'other' && !note.trim())

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t(`employees.bulk.${action}`)} subtitle={t('employees.bulkSubtitle', { count: state.ids.length })} backTo="/employees" backLabel={t('employees.title')} />

      <FormSection title={t('employees.selectedEmployees')}>
        <div className="flex max-h-32 flex-wrap gap-1.5 overflow-auto">
          {state.names.map((n, i) => (
            <Badge key={state.ids[i]}>{n}</Badge>
          ))}
        </div>
      </FormSection>

      <form onSubmit={submit} className="flex flex-col gap-6">
        {action === 'transfer' && (
          <>
            <FormSection title={t('employees.newAssignment')} description={t('employees.bulkTransferHint')}>
              <AssignmentFields value={assignment} onChange={setAssignment} keepLabel={t('employees.keep')} />
            </FormSection>
            <FormSection title={t('employees.sectionDetails')}>
              <Field label={t('employees.effectiveDate')}>{(id) => <Input id={id} type="date" value={date} onChange={(e) => setDate(e.target.value)} required className="max-w-52" />}</Field>
              <NoteField value={note} onChange={setNote} />
            </FormSection>
          </>
        )}
        {action === 'dismiss' && (
          <FormSection title={t('employees.sectionDetails')} description={t('employees.dismissHint')}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t('employees.dismissalDate')}>{(id) => <Input id={id} type="date" value={date} max={today()} onChange={(e) => setDate(e.target.value)} required />}</Field>
              <Field label={t('employees.dismissalReason')}>
                {(id) => (
                  <Select id={id} value={reason} onChange={(e) => setReason(e.target.value)}>
                    {DISMISS_REASONS.map((r) => (
                      <option key={r} value={r}>
                        {t(`employees.reasons.${r}`)}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            </div>
            <NoteField value={note} onChange={setNote} />
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={block} onChange={(e) => setBlock(e.target.checked)} />
              {t('employees.blockAccounts')}
            </label>
          </FormSection>
        )}
        {action === 'reinstate' && (
          <FormSection title={t('employees.sectionDetails')} description={t('employees.reinstateHint')}>
            <Field label={t('employees.effectiveDate')}>{(id) => <Input id={id} type="date" value={date} onChange={(e) => setDate(e.target.value)} required className="max-w-52" />}</Field>
            <NoteField value={note} onChange={setNote} />
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={reactivate} onChange={(e) => setReactivate(e.target.checked)} />
              {t('employees.reactivateAccounts')}
            </label>
          </FormSection>
        )}
        {action === 'assign_group' && (
          <FormSection title={t('employees.workGroup')} description={t('employees.bulkGroupHint')}>
            <Field label={t('employees.workGroup')}>
              {(id) => (
                <Select id={id} value={groupId} onChange={(e) => setGroupId(e.target.value)}>
                  <option value="">{t('employees.defaultGroup')}</option>
                  {groups.data
                    ?.filter((g) => g.is_active)
                    .map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                </Select>
              )}
            </Field>
          </FormSection>
        )}
        {action === 'create_accounts' && (
          <FormSection title={t('employees.createAccount')} description={t('employees.bulkAccountsHint')}>
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
          </FormSection>
        )}

        <FormFooter error={run.isError ? errorText(t, run.error) : noChange ? t('employees.bulkNothing') : null}>
          <Button variant="outline" onClick={() => navigate('/employees')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={run.isPending || invalid} className={action === 'dismiss' ? 'bg-danger text-white hover:opacity-90' : undefined}>
            {t('employees.bulkRun', { count: state.ids.length })}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}

function NoteField({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const { t } = useTranslation()
  return (
    <Field label={t('employees.note')}>
      {(id) => <textarea id={id} value={value} onChange={(e) => onChange(e.target.value)} maxLength={500} rows={3} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
    </Field>
  )
}
