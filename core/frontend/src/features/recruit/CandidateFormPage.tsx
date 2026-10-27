import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Sparkles, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText, fieldErrors } from '../auth/errorText'
import { SOURCES, type Candidate, type CandidateDetail } from './api'

const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'
interface Parsed {
  fields: Partial<Candidate>
  engine: string
  found: string[]
}

/** /recruit/candidates/new va /recruit/candidates/:id/edit */
export function CandidateFormPage() {
  const { id } = useParams()
  const cid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['recruit', 'candidate', cid], queryFn: () => api<CandidateDetail>(`/api/v1/recruit/candidates/${cid}`), enabled: cid !== null, retry: false })
  if (cid === null) return <CandidateForm c={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <CandidateForm key={q.data.id} c={q.data} />
}

function CandidateForm({ c }: { c: CandidateDetail | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const back = c ? `/recruit/candidates/${c.id}` : '/recruit/candidates'
  const [name, setName] = useState(c?.full_name ?? '')
  const [phone, setPhone] = useState(c?.phone ?? '')
  const [email, setEmail] = useState(c?.email ?? '')
  const [birth, setBirth] = useState(c?.birth_date ?? '')
  const [address, setAddress] = useState(c?.address ?? '')
  const [source, setSource] = useState(c?.source ?? '')
  const [skills, setSkills] = useState((c?.skills ?? []).join(', '))
  const [note, setNote] = useState(c?.note ?? '')
  const [resume, setResume] = useState(c?.resume_text ?? '')
  const [parsedInfo, setParsedInfo] = useState<string | null>(null)
  const [deleteError, setDeleteError] = useState<string | null>(null)

  const parse = useMutation({
    mutationFn: () => send<Parsed>('POST', '/api/v1/recruit/candidates/parse', { text: resume }),
    onSuccess: (r) => {
      const f = r.fields
      if (f.full_name) setName(f.full_name)
      if (f.phone) setPhone(f.phone)
      if (f.email) setEmail(f.email)
      if (f.birth_date) setBirth(f.birth_date)
      if (f.address) setAddress(f.address)
      if (f.skills?.length) setSkills(f.skills.join(', '))
      setParsedInfo(r.found.length ? t('recruit.candidate.parsed', { count: r.found.length }) : t('recruit.candidate.parsedNone'))
    },
  })
  const save = useMutation({
    mutationFn: () => {
      const body = { full_name: name, phone: phone || null, email: email || null, birth_date: birth || null, address: address || null, source: source || null, skills: skills.split(',').map((s) => s.trim()).filter(Boolean), resume_text: resume || null, note: note || null }
      return c ? send<CandidateDetail>('PUT', `/api/v1/recruit/candidates/${c.id}`, body) : send<CandidateDetail>('POST', '/api/v1/recruit/candidates', body)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['recruit'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(`/recruit/candidates/${r.id}`, { replace: true })
    },
    onError: (e) => {
      if (e instanceof ApiError && e.code === 'candidate_exists') navigate(`/recruit/candidates/${e.extra.id}`)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/recruit/candidates/${c?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['recruit'] })
      toast.push({ title: t('recruit.candidate.deleted'), tone: 'success' })
      navigate('/recruit/candidates', { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const fe = save.isError ? fieldErrors(t, save.error) : {}
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={c ? t('recruit.candidate.edit') : t('recruit.candidate.add')} subtitle={c?.full_name} backTo={back} backLabel={c ? c.full_name : t('recruit.tabs.candidates')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('recruit.candidate.resumeText')} description={t('recruit.candidate.resumeHint')}>
          <textarea value={resume} onChange={(e) => setResume(e.target.value)} rows={6} maxLength={50000} className={area} aria-label={t('recruit.candidate.resumeText')} />
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="outline" disabled={parse.isPending || resume.trim().length < 10} onClick={() => parse.mutate()}>
              <Sparkles className="size-4" />
              {t('recruit.candidate.autofill')}
            </Button>
            {parsedInfo && <span className="text-sm text-muted">{parsedInfo}</span>}
            {parse.isError && (
              <span role="alert" className="text-sm text-danger">
                {errorText(t, parse.error)}
              </span>
            )}
          </div>
        </FormSection>
        <FormSection title={t('needs.form.main')}>
          <Field label={t('recruit.candidate.name')} error={fe.full_name}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={250} autoFocus={!c} />}</Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('recruit.candidate.phone')} error={fe.phone}>{(id) => <Input id={id} value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+998 90 123 45 67" inputMode="tel" />}</Field>
            <Field label="Email" error={fe.email}>{(id) => <Input id={id} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
            <Field label={t('recruit.candidate.birth')}>{(id) => <Input id={id} type="date" value={birth} onChange={(e) => setBirth(e.target.value)} />}</Field>
            <Field label={t('recruit.candidate.source')}>
              {(id) => (
                <Select id={id} value={source} onChange={(e) => setSource(e.target.value)}>
                  <option value="">—</option>
                  {SOURCES.map((s) => (
                    <option key={s} value={s}>
                      {t(`recruit.source.${s}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <Field label={t('recruit.candidate.address')}>{(id) => <Input id={id} value={address} onChange={(e) => setAddress(e.target.value)} maxLength={300} />}</Field>
          <Field label={t('recruit.candidate.skills')} hint={t('recruit.candidate.skillsHint')}>{(id) => <Input id={id} value={skills} onChange={(e) => setSkills(e.target.value)} />}</Field>
          <Field label={t('recruit.candidate.note')}>{(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={5000} className={area} />}</Field>
        </FormSection>
        <FormFooter error={save.isError && !Object.keys(fe).length ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || name.trim().length < 2}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {c && (
        <FormSection title={t('org.dangerZone')} description={t('recruit.candidate.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('recruit.candidate.delete'), body: t('org.deleteConfirm', { name: c.full_name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('recruit.candidate.delete')}
            </Button>
            {deleteError && (
              <span role="alert" className="text-sm text-danger">
                {deleteError}
              </span>
            )}
          </div>
        </FormSection>
      )}
    </div>
  )
}
