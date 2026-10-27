import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Paperclip, Plus, Trash2, X } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send, upload } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { sizeText } from '../tasks/api'
import { KINDS, type Kind, type Question, type Step } from './api'

const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'
const blankQ = (): Question => ({ id: '', text: '', options: ['', ''], correct: [0] })

/** /internship/programs/:pid/steps/new va /internship/steps/:sid/edit */
export function StepFormPage() {
  const { pid, sid } = useParams()
  const stepId = sid ? Number(sid) : null
  const q = useQuery({ queryKey: ['internship', 'step', stepId], queryFn: () => api<Step>(`/api/v1/internship/steps/${stepId}`), enabled: stepId !== null, retry: false })
  if (stepId === null) return <StepForm step={null} programId={Number(pid)} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!q.data) return null
  return <StepForm key={q.data.id} step={q.data} programId={null} />
}

function StepForm({ step, programId }: { step: Step | null; programId: number | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const input = useRef<HTMLInputElement>(null)
  const [kind, setKind] = useState<Kind>(step?.kind ?? 'video')
  const [title, setTitle] = useState(step?.title ?? '')
  const [description, setDescription] = useState(step?.description ?? '')
  const [url, setUrl] = useState(step?.url ?? '')
  const [required, setRequired] = useState(step?.required ?? true)
  const [pass, setPass] = useState(step?.pass_score?.toString() ?? '')
  const [attempts, setAttempts] = useState(String(step?.max_attempts ?? 3))
  const [questions, setQuestions] = useState<Question[]>(step?.questions?.length ? step.questions : [blankQ()])
  const [file, setFile] = useState(step?.file ?? null)
  const [deleteError, setDeleteError] = useState<string | null>(null)
  const pid = programId ?? step?.program_id
  const back = pid ? `/internship/programs/${pid}` : '/internship/programs'

  const patchQ = (i: number, p: Partial<Question>) => setQuestions(questions.map((x, j) => (j === i ? { ...x, ...p } : x)))
  const save = useMutation({
    mutationFn: async () => {
      const body = {
        kind, title, description: description || null, url: url || null, required, pass_score: kind === 'test' && pass ? Number(pass) : null, max_attempts: Number(attempts) || 0,
        questions: kind === 'test' ? questions.map((x) => ({ id: x.id || null, text: x.text, options: x.options, correct: x.correct ?? [] })) : [],
      } // fmt: skip
      return step ? send<Step>('PUT', `/api/v1/internship/steps/${step.id}`, body) : send<Step>('POST', `/api/v1/internship/programs/${programId}/steps`, body)
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ['internship'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(back, { replace: true })
    },
  })
  const up = useMutation({
    mutationFn: (f: File) => {
      const form = new FormData()
      form.append('file', f)
      return upload<Step>('POST', `/api/v1/internship/steps/${step?.id}/file`, form)
    },
    onSuccess: (s) => (setFile(s.file), void qc.invalidateQueries({ queryKey: ['internship'] })),
  })
  const delFile = useMutation({ mutationFn: () => send('DELETE', `/api/v1/internship/steps/${step?.id}/file`), onSuccess: () => (setFile(null), void qc.invalidateQueries({ queryKey: ['internship'] })) })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/internship/steps/${step?.id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['internship'] })
      toast.push({ title: t('internship.step.deleted'), tone: 'success' })
      navigate(back, { replace: true })
    },
    onError: (e) => setDeleteError(errorText(t, e)),
  })
  const valid = title.trim() && (kind !== 'video' || url.trim()) && (kind !== 'test' || questions.every((x) => x.text.trim() && x.options.every((o) => o.trim()) && (x.correct?.length ?? 0) > 0))
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <PageHeader title={step ? t('internship.step.edit') : t('internship.step.add')} subtitle={step?.title} backTo={back} backLabel={t('internship.programs.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('needs.form.main')}>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label={t('internship.step.kind')}>
              {(id) => (
                <Select id={id} value={kind} onChange={(e) => setKind(e.target.value as Kind)} disabled={!!step}>
                  {KINDS.map((k) => (
                    <option key={k} value={k}>
                      {t(`internship.kind.${k}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <div className="sm:col-span-2">
              <Field label={t('internship.step.title')}>{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} autoFocus />}</Field>
            </div>
          </div>
          {(kind === 'video' || kind === 'document') && (
            <Field label={t('internship.step.url')} hint={kind === 'video' ? t('internship.step.videoHint') : t('internship.step.docHint')}>{(id) => <Input id={id} type="url" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://" required={kind === 'video'} maxLength={500} />}</Field>
          )}
          <Field label={kind === 'text' ? t('internship.step.content') : t('needs.form.description')}>{(id) => <textarea id={id} value={description} onChange={(e) => setDescription(e.target.value)} rows={kind === 'text' ? 10 : 4} maxLength={10000} className={area} />}</Field>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={required} onChange={(e) => setRequired(e.target.checked)} />
            {t('checklists.templates.required')}
          </label>
        </FormSection>

        {kind === 'test' && (
          <FormSection title={t('internship.step.questions')} description={t('internship.step.questionsHint')}>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t('internship.step.passScore')} hint={t('internship.step.passScoreHint')}>{(id) => <Input id={id} type="number" min={1} max={100} value={pass} onChange={(e) => setPass(e.target.value)} />}</Field>
              <Field label={t('internship.step.maxAttempts')} hint={t('internship.step.maxAttemptsHint')}>{(id) => <Input id={id} type="number" min={0} max={20} value={attempts} onChange={(e) => setAttempts(e.target.value)} />}</Field>
            </div>
            <ol className="flex flex-col gap-3">
              {questions.map((qu, i) => (
                <li key={qu.id || `n${i}`}>
                  <Card tint="sand" className="flex flex-col gap-3 p-4">
                    <div className="flex items-center gap-2">
                      <span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface text-xs font-semibold">{i + 1}</span>
                      <Input value={qu.text} onChange={(e) => patchQ(i, { text: e.target.value })} maxLength={500} placeholder={t('internship.step.questionText')} aria-label={t('internship.step.questionText')} />
                      <Button variant="ghost" className="h-9 px-2 text-danger" onClick={() => setQuestions(questions.filter((_, j) => j !== i))} disabled={questions.length === 1} aria-label={t('common.delete')}>
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                    {qu.options.map((o, j) => (
                      <div key={j} className="flex items-center gap-2 pl-9">
                        <input
                          type="checkbox"
                          className="size-4"
                          checked={qu.correct?.includes(j) ?? false}
                          aria-label={t('internship.step.correct')}
                          title={t('internship.step.correct')}
                          onChange={(e) => patchQ(i, { correct: e.target.checked ? [...(qu.correct ?? []), j] : (qu.correct ?? []).filter((c) => c !== j) })}
                        />
                        <Input value={o} onChange={(e) => patchQ(i, { options: qu.options.map((x, k) => (k === j ? e.target.value : x)) })} maxLength={200} placeholder={t('internship.step.option', { n: j + 1 })} aria-label={t('internship.step.option', { n: j + 1 })} />
                        <Button
                          variant="ghost"
                          className="h-9 px-2"
                          disabled={qu.options.length <= 2}
                          aria-label={t('common.delete')}
                          onClick={() => patchQ(i, { options: qu.options.filter((_, k) => k !== j), correct: (qu.correct ?? []).filter((c) => c !== j).map((c) => (c > j ? c - 1 : c)) })}
                        >
                          <X className="size-4" />
                        </Button>
                      </div>
                    ))}
                    <div className="pl-9">
                      <Button variant="ghost" className="h-8 px-2 text-sm" disabled={qu.options.length >= 6} onClick={() => patchQ(i, { options: [...qu.options, ''] })}>
                        <Plus className="size-4" />
                        {t('internship.step.addOption')}
                      </Button>
                    </div>
                  </Card>
                </li>
              ))}
            </ol>
            <div>
              <Button variant="outline" onClick={() => setQuestions([...questions, blankQ()])}>
                <Plus className="size-4" />
                {t('internship.step.addQuestion')}
              </Button>
            </div>
          </FormSection>
        )}

        {step && kind !== 'test' && (
          <FormSection title={t('internship.step.file')} description={t('internship.step.fileHint')}>
            <input ref={input} type="file" className="sr-only" aria-label={t('tasks.attach')} onChange={(e) => (e.target.files?.[0] && up.mutate(e.target.files[0]), (e.target.value = ''))} />
            {file ? (
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <span className="font-medium">{file.name}</span>
                <span className="text-muted">{sizeText(file.size)}</span>
                <Button variant="ghost" className="text-danger" disabled={delFile.isPending} onClick={() => delFile.mutate()}>
                  <Trash2 className="size-4" />
                  {t('common.delete')}
                </Button>
              </div>
            ) : null}
            <div>
              <Button variant="outline" disabled={up.isPending} onClick={() => input.current?.click()}>
                <Paperclip className="size-4" />
                {file ? t('internship.step.replaceFile') : t('tasks.attach')}
              </Button>
            </div>
            {(up.isError || delFile.isError) && (
              <p role="alert" className="text-sm text-danger">
                {errorText(t, up.error ?? delFile.error)}
              </p>
            )}
          </FormSection>
        )}
        {!step && kind !== 'test' && <p className="text-sm text-muted">{t('internship.step.fileAfterSave')}</p>}

        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(back)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !valid}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {step && (
        <FormSection title={t('org.dangerZone')} description={t('internship.step.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              disabled={remove.isPending}
              onClick={async () => {
                if (await confirm({ title: t('internship.step.delete'), body: t('org.deleteConfirm', { name: step.title }), danger: true, confirmLabel: t('common.delete') })) {
                  setDeleteError(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('internship.step.delete')}
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
