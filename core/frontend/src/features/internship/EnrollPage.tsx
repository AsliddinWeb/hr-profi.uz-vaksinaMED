import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import type { Enrollment, Program } from './api'

interface Emp {
  id: number
  name: string
  phone: string | null
  has_account: boolean
}

/** /internship/enrollments/new: xodimni stajirovka dasturiga biriktirish. */
export function EnrollPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [sp] = useSearchParams()
  const [programId, setProgramId] = useState(sp.get('program_id') ?? '')
  const [emp, setEmp] = useState<Emp | null>(null)
  const [text, setText] = useState('')
  const [mentor, setMentor] = useState('')
  const [due, setDue] = useState('')
  const [note, setNote] = useState('')
  const programs = useQuery({ queryKey: ['internship', 'programs'], queryFn: () => api<Program[]>('/api/v1/internship/programs') })
  const mentors = useQuery({ queryKey: ['internship', 'mentors'], queryFn: () => api<{ id: number; name: string }[]>('/api/v1/internship/mentors') })
  const found = useQuery({ queryKey: ['internship', 'employees', text], queryFn: () => api<Emp[]>(`/api/v1/internship/employees?q=${encodeURIComponent(text.trim())}`), enabled: !emp && text.trim().length >= 2 })
  const save = useMutation({
    mutationFn: () => send<Enrollment>('POST', '/api/v1/internship/enrollments', { program_id: Number(programId), employee_id: emp?.id, mentor_id: mentor ? Number(mentor) : null, due_date: due || null, note: note || null }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['internship'] })
      navigate(`/internship/enrollments/${r.id}`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('internship.enroll.add')} backTo="/internship" backLabel={t('internship.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('internship.enroll.who')}>
          <Field label={t('internship.enroll.program')}>
            {(id) => (
              <Select id={id} value={programId} onChange={(e) => setProgramId(e.target.value)} required>
                <option value="">—</option>
                {programs.data?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.steps})
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t('internship.enroll.intern')} hint={emp && !emp.has_account ? t('internship.enroll.noAccount') : t('internship.enroll.internHint')}>
            {(id) =>
              emp ? (
                <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-1 text-sm">
                  {emp.name}
                  <button type="button" onClick={() => setEmp(null)} aria-label={t('common.clear')} className="text-muted hover:text-text">
                    <X className="size-3.5" />
                  </button>
                </span>
              ) : (
                <div className="relative">
                  <Input id={id} value={text} onChange={(e) => setText(e.target.value)} placeholder={t('internship.enroll.search')} autoComplete="off" />
                  {found.data && found.data.length > 0 && (
                    <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-control border border-border bg-surface py-1 shadow-card" role="listbox">
                      {found.data.map((x) => (
                        <li key={x.id}>
                          <button type="button" role="option" aria-selected={false} className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-2" onClick={() => (setEmp(x), setText(''))}>
                            {x.name} <span className="text-muted">{x.phone}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )
            }
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('internship.enroll.mentor')}>
              {(id) => (
                <Select id={id} value={mentor} onChange={(e) => setMentor(e.target.value)}>
                  <option value="">—</option>
                  {mentors.data?.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('internship.enroll.due')}>{(id) => <Input id={id} type="date" value={due} onChange={(e) => setDue(e.target.value)} />}</Field>
          </div>
          <Field label={t('recruit.candidate.note')}>{(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/internship')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !programId || !emp}>
            {t('internship.enroll.submit')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
