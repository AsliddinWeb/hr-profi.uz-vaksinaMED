import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { addDays, todayLocal } from '../attendance/api'
import { errorText, fieldErrors } from '../auth/errorText'
import type { Employee } from '../employees/api'
import { EmployeePicker, type PickedEmployee } from './EmployeePicker'
import { INCIDENTS, type Letter, type LetterTemplate } from './api'

/** /letters/new: tushuntirish xati so'rash (kunlik davomat sahifasidan ?employee=&type=&date= bilan to'ldirilib keladi). */
export function IssueFormPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [params] = useSearchParams()
  const preEmployee = Number(params.get('employee')) || null
  const [today] = useState(todayLocal)

  const [employee, setEmployee] = useState<PickedEmployee | null>(null)
  const [type, setType] = useState<string>(INCIDENTS.includes(params.get('type') as never) ? (params.get('type') as string) : 'late')
  const [date, setDate] = useState(params.get('date') ?? today)
  const [note, setNote] = useState('')
  const [due, setDue] = useState(addDays(today, 3))
  const [templateId, setTemplateId] = useState('')

  useQuery({
    queryKey: ['employees', 'one', preEmployee],
    queryFn: async () => {
      const e = await api<Employee>(`/api/v1/employees/${preEmployee}`)
      setEmployee((cur) => cur ?? { id: e.id, name: e.full_name })
      return e
    },
    enabled: preEmployee !== null,
    retry: false,
  })
  const templates = useQuery({ queryKey: ['letters', 'templates'], queryFn: () => api<LetterTemplate[]>('/api/v1/letters/templates') })

  const save = useMutation({
    mutationFn: () => send<Letter>('POST', '/api/v1/letters', { employee_id: employee?.id, template_id: templateId ? Number(templateId) : null, incident_type: type, incident_date: date, incident_note: note || null, due_date: due || null }),
    onSuccess: (l) => {
      void qc.invalidateQueries({ queryKey: ['letters'] })
      toast.push({ title: t('letters.requested'), tone: 'success' })
      navigate(`/letters/${l.id}`, { replace: true })
    },
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const err = save.error instanceof ApiError && save.error.code !== 'validation' ? errorText(t, save.error) : null
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={t('letters.request')} subtitle={t('letters.form.subtitle')} backTo="/letters" backLabel={t('letters.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('letters.form.who')}>
          <Field label={t('employees.fullName')}>{(id) => <EmployeePicker id={id} value={employee} onChange={setEmployee} />}</Field>
        </FormSection>
        <FormSection title={t('letters.form.what')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('letters.incident')}>
              {(id) => (
                <Select id={id} value={type} onChange={(e) => setType(e.target.value)}>
                  {INCIDENTS.map((k) => (
                    <option key={k} value={k}>
                      {t(`letters.incidents.${k}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('letters.form.incidentDate')} error={fe.incident_date}>
              {(id) => <Input id={id} type="date" value={date} max={today} onChange={(e) => setDate(e.target.value)} required />}
            </Field>
          </div>
          <Field label={t('letters.form.note')} hint={t('letters.form.noteHint')}>
            {(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} rows={4} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}
          </Field>
        </FormSection>
        <FormSection title={t('letters.form.terms')}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('letters.due')}>{(id) => <Input id={id} type="date" value={due} min={today} onChange={(e) => setDue(e.target.value)} />}</Field>
            <Field label={t('letters.form.template')}>
              {(id) => (
                <Select id={id} value={templateId} onChange={(e) => setTemplateId(e.target.value)}>
                  <option value="">{t('letters.form.defaultTemplate')}</option>
                  {templates.data?.filter((x) => x.is_active).map((x) => (
                    <option key={x.id} value={x.id}>
                      {x.name}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
        </FormSection>
        <FormFooter error={err}>
          <Button variant="outline" onClick={() => navigate('/letters')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !employee || !date}>
            {t('letters.form.submit')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
