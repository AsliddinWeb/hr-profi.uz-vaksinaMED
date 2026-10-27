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
import type { Application, CandidateDetail, CandidateRow, Page, VacancyPage } from './api'

/** /recruit/applications/new?vacancy_id=&candidate_id=: nomzodni vakansiyaga yozish. */
export function ApplicationNewPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [sp] = useSearchParams()
  const [vacancyId, setVacancyId] = useState(sp.get('vacancy_id') ?? '')
  const [candidateId, setCandidateId] = useState(sp.get('candidate_id') ?? '')
  const [text, setText] = useState('')
  const [note, setNote] = useState('')
  const vacancies = useQuery({ queryKey: ['recruit', 'vacancies', 'open'], queryFn: () => api<VacancyPage>('/api/v1/recruit/vacancies?status=open&size=100') })
  const chosen = useQuery({ queryKey: ['recruit', 'candidate', Number(candidateId)], queryFn: () => api<CandidateDetail>(`/api/v1/recruit/candidates/${candidateId}`), enabled: !!candidateId })
  const found = useQuery({
    queryKey: ['recruit', 'candidates', 'pick', text],
    queryFn: () => api<Page<CandidateRow>>(`/api/v1/recruit/candidates?size=8&q=${encodeURIComponent(text.trim())}`),
    enabled: !candidateId && text.trim().length >= 2,
  })
  const save = useMutation({
    mutationFn: () => send<Application>('POST', '/api/v1/recruit/applications', { vacancy_id: Number(vacancyId), candidate_id: Number(candidateId), note: note || null }),
    onSuccess: (a) => {
      void qc.invalidateQueries({ queryKey: ['recruit'] })
      navigate(`/recruit/applications/${a.id}`, { replace: true })
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('recruit.application.add')} backTo="/recruit/applications" backLabel={t('recruit.tabs.applications')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('recruit.application.who')}>
          <Field label={t('recruit.application.vacancy')}>
            {(id) => (
              <Select id={id} value={vacancyId} onChange={(e) => setVacancyId(e.target.value)} required>
                <option value="">—</option>
                {vacancies.data?.items.map((v) => (
                  <option key={v.id} value={v.id}>
                    {v.title}
                    {v.branch ? ` · ${v.branch.name}` : ''}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <Field label={t('recruit.tabs.candidates')} hint={candidateId ? undefined : t('recruit.application.pickHint')}>
            {(id) =>
              candidateId ? (
                <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-surface-2 px-2.5 py-1 text-sm">
                  {chosen.data?.full_name ?? '…'}
                  <button type="button" onClick={() => setCandidateId('')} aria-label={t('common.clear')} className="text-muted hover:text-text">
                    <X className="size-3.5" />
                  </button>
                </span>
              ) : (
                <div className="relative">
                  <Input id={id} value={text} onChange={(e) => setText(e.target.value)} placeholder={t('recruit.candidate.search')} autoComplete="off" />
                  {found.data && found.data.items.length > 0 && (
                    <ul className="absolute z-20 mt-1 max-h-56 w-full overflow-auto rounded-control border border-border bg-surface py-1 shadow-card" role="listbox">
                      {found.data.items.map((c) => (
                        <li key={c.id}>
                          <button type="button" role="option" aria-selected={false} className="block w-full px-3 py-2 text-left text-sm hover:bg-surface-2" onClick={() => (setCandidateId(String(c.id)), setText(''))}>
                            {c.full_name} <span className="text-muted">{c.phone}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )
            }
          </Field>
          <Field label={t('recruit.candidate.note')}>{(id) => <Input id={id} value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000} />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(-1)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !vacancyId || !candidateId}>
            {t('recruit.application.submit')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
