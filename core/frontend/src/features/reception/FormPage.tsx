import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { fromLocalInput, toLocalInput } from '../attendance/api'
import { errorText, fieldErrors } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { PURPOSES, type Visit, type VisitDetail } from './api'

/** /reception/new va /reception/:id/edit */
export function FormPage() {
  const { id } = useParams()
  const visitId = id ? Number(id) : null
  const q = useQuery({ queryKey: ['reception', 'one', visitId], queryFn: () => api<VisitDetail>(`/api/v1/reception/${visitId}`), enabled: visitId !== null, retry: false })
  if (visitId === null) return <VisitForm visit={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <VisitForm key={q.data.id} visit={q.data} />
}

function HostPicker({ id, value, onChange }: { id?: string; value: { id: number; name: string | null } | null; onChange: (v: { id: number; name: string | null } | null) => void }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  const found = useQuery({ queryKey: ['reception', 'hosts', q], queryFn: () => api<{ id: number; name: string }[]>(`/api/v1/reception/hosts?q=${encodeURIComponent(q.trim())}`) })
  if (value)
    return (
      <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-1 text-sm">
        {value.name}
        <button type="button" onClick={() => onChange(null)} aria-label={t('common.clear')} className="text-muted hover:text-text">
          <X className="size-3.5" />
        </button>
      </span>
    )
  return (
    <div className="relative">
      <Input id={id} value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)} placeholder={t('tasks.form.searchPerson')} autoComplete="off" />
      {open && found.data && found.data.length > 0 && (
        <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-control border border-border bg-surface py-1 shadow-card" role="listbox">
          {found.data.map((u) => (
            <li key={u.id} role="option" aria-selected={false}>
              <button type="button" onMouseDown={(e) => e.preventDefault()} onClick={() => (onChange({ id: u.id, name: u.name }), setQ(''), setOpen(false))} className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-2">
                {u.name}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function VisitForm({ visit }: { visit: VisitDetail | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const desk = useCan()('reception.desk')
  const [name, setName] = useState(visit?.visitor_name ?? '')
  const [phone, setPhone] = useState(visit?.visitor_phone ?? '')
  const [company, setCompany] = useState(visit?.company ?? '')
  const [purpose, setPurpose] = useState<string>(visit?.purpose ?? 'meeting')
  const [host, setHost] = useState(visit?.host ?? null)
  const [branchId, setBranchId] = useState(String(visit?.branch?.id ?? ''))
  const [expected, setExpected] = useState(toLocalInput(visit?.expected_at))
  const [doc, setDoc] = useState(visit?.doc_info ?? '')
  const [plate, setPlate] = useState(visit?.vehicle_plate ?? '')
  const [badge, setBadge] = useState(visit?.badge_no ?? '')
  const [note, setNote] = useState(visit?.note ?? '')
  const [walkIn, setWalkIn] = useState(false)
  const branches = useQuery({ queryKey: ['reception', 'branches'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/reception/branches') })
  const needExpected = !walkIn && (!visit || visit.status === 'expected')

  const save = useMutation({
    mutationFn: () => {
      const body = {
        visitor_name: name, visitor_phone: phone || null, company: company || null, purpose, host_id: host?.id ?? null, branch_id: branchId ? Number(branchId) : null,
        expected_at: needExpected || expected ? fromLocalInput(expected) : null, doc_info: doc || null, vehicle_plate: plate || null, badge_no: badge || null, note: note || null, arrive: walkIn,
      }
      return visit ? send<Visit>('PUT', `/api/v1/reception/${visit.id}`, body) : send<Visit>('POST', '/api/v1/reception', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['reception'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/reception/${r.id}`, { replace: true })
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={visit ? t('reception.edit') : t(desk ? 'reception.register' : 'reception.invite')} subtitle={visit?.visitor_name} backTo={visit ? `/reception/${visit.id}` : '/reception'} backLabel={visit ? visit.visitor_name : t('reception.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('reception.form.visitor')}>
          <Field label={t('reception.visitor')} error={fe.visitor_name}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={160} autoFocus />}</Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('reception.phone')}>{(id) => <Input id={id} value={phone} onChange={(e) => setPhone(e.target.value)} maxLength={32} inputMode="tel" />}</Field>
            <Field label={t('reception.company')}>{(id) => <Input id={id} value={company} onChange={(e) => setCompany(e.target.value)} maxLength={120} />}</Field>
          </div>
        </FormSection>
        <FormSection title={t('reception.form.visit')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('reception.purposeLabel')}>
              {(id) => (
                <Select id={id} value={purpose} onChange={(e) => setPurpose(e.target.value)}>
                  {PURPOSES.map((p) => (
                    <option key={p} value={p}>
                      {t(`reception.purpose.${p}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('reception.host')}>{(id) => <HostPicker id={id} value={host} onChange={setHost} />}</Field>
            <Field label={t('reception.branch')}>
              {(id) => (
                <Select id={id} value={branchId} onChange={(e) => setBranchId(e.target.value)}>
                  <option value="">—</option>
                  {branches.data?.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            {(!visit || visit.status === 'expected') && (
              <Field label={t('reception.expectedAt')} error={fe.expected_at}>{(id) => <Input id={id} type="datetime-local" value={expected} onChange={(e) => setExpected(e.target.value)} required={needExpected} disabled={walkIn} />}</Field>
            )}
          </div>
          {!visit && desk && (
            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" className="size-4" checked={walkIn} onChange={(e) => setWalkIn(e.target.checked)} />
              {t('reception.form.walkIn')}
            </label>
          )}
        </FormSection>
        <FormSection title={t('reception.form.extra')}>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('reception.doc')}>{(id) => <Input id={id} value={doc} onChange={(e) => setDoc(e.target.value)} maxLength={60} />}</Field>
            <Field label={t('reception.plate')}>{(id) => <Input id={id} value={plate} onChange={(e) => setPlate(e.target.value)} maxLength={16} />}</Field>
            {desk && <Field label={t('reception.badge')}>{(id) => <Input id={id} value={badge} onChange={(e) => setBadge(e.target.value)} maxLength={20} />}</Field>}
          </div>
          <Field label={t('reception.note')}>
            {(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={2000} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(visit ? `/reception/${visit.id}` : '/reception')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || name.trim().length < 2 || (needExpected && !expected)}>
            {visit ? t('common.save') : walkIn ? t('reception.form.registerArrived') : t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
