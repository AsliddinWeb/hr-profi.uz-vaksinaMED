import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Download, ExternalLink } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { sizeText } from '../tasks/api'
import type { EnrollmentDetail, StepState, TestResult } from './api'

/** YouTube/Vimeo havolasini ichki ko'rinishga aylantiradi; boshqa havolalar tashqi sahifada ochiladi. */
function embedUrl(url: string): string | null {
  try {
    const u = new URL(url)
    if (u.hostname.endsWith('youtube.com') && u.searchParams.get('v')) return `https://www.youtube-nocookie.com/embed/${u.searchParams.get('v')}`
    if (u.hostname === 'youtu.be') return `https://www.youtube-nocookie.com/embed${u.pathname}`
    if (u.hostname.endsWith('vimeo.com')) return `https://player.vimeo.com/video${u.pathname}`
  } catch {
    /* noto'g'ri havola */
  }
  return null
}

/** /internship/enrollments/:id/steps/:sid: stajyor bosqichni o'qiydi / testni topshiradi. */
export function LearnPage() {
  const eid = Number(useParams().id)
  const sid = Number(useParams().sid)
  const q = useQuery({ queryKey: ['internship', 'enrollment', eid], queryFn: () => api<EnrollmentDetail>(`/api/v1/internship/enrollments/${eid}`), retry: false })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const e = q.data
  if (!e) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  const s = e.steps.find((x) => x.id === sid)
  if (!s) return <NotFound />
  return <Learn e={e} s={s} key={s.id} />
}

function Learn({ e, s }: { e: EnrollmentDetail; s: StepState }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [answers, setAnswers] = useState<Record<string, number[]>>({})
  const [result, setResult] = useState<TestResult | null>(null)
  const back = `/internship/enrollments/${e.id}`
  const next = e.steps[e.steps.findIndex((x) => x.id === s.id) + 1]
  const refresh = () => void qc.invalidateQueries({ queryKey: ['internship'] })
  const done = useMutation({
    mutationFn: () => send('POST', `/api/v1/internship/enrollments/${e.id}/steps/${s.id}/done`),
    onSuccess: () => (refresh(), navigate(next ? `${back}/steps/${next.id}` : back, { replace: true })),
  })
  const submit = useMutation({
    mutationFn: () => send<TestResult>('POST', `/api/v1/internship/enrollments/${e.id}/steps/${s.id}/submit`, { answers }),
    onSuccess: (r) => (setResult(r), refresh()),
  })
  const embed = s.url ? embedUrl(s.url) : null
  const locked = !e.can.learn
  const exhausted = s.kind === 'test' && s.max_attempts > 0 && s.attempts >= s.max_attempts && s.state !== 'done'
  const toggle = (qid: string, i: number, multiple: boolean) => setAnswers((a) => ({ ...a, [qid]: multiple ? (a[qid]?.includes(i) ? a[qid].filter((x) => x !== i) : [...(a[qid] ?? []), i]) : [i] }))

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={s.title} subtitle={e.program.name} backTo={back} backLabel={e.employee.name ?? ''} actions={s.state === 'done' && <Badge tone="success">{t('internship.doneBadge')}</Badge>} />
      {s.kind !== 'test' && (
        <Card className="flex flex-col gap-4 p-6">
          {embed && <iframe src={embed} title={s.title} className="aspect-video w-full rounded-control border border-border" allow="fullscreen; picture-in-picture" allowFullScreen referrerPolicy="no-referrer" />}
          {s.url && !embed && (
            <a href={s.url} target="_blank" rel="noreferrer noopener">
              <Button variant="outline">
                <ExternalLink className="size-4" />
                {t('internship.openLink')}
              </Button>
            </a>
          )}
          {s.file && (
            <a href={`/api/v1/internship/steps/${s.id}/file`} target="_blank" rel="noreferrer">
              <Button variant="outline">
                <Download className="size-4" />
                {s.file.name} · {sizeText(s.file.size)}
              </Button>
            </a>
          )}
          {s.description && <p className="whitespace-pre-wrap text-sm leading-relaxed">{s.description}</p>}
          {s.state !== 'done' && !locked && (
            <div>
              <Button disabled={done.isPending} onClick={() => done.mutate()}>
                <Check className="size-4" />
                {t('internship.markDone')}
              </Button>
            </div>
          )}
          {done.isError && (
            <p role="alert" className="text-sm text-danger">
              {errorText(t, done.error)}
            </p>
          )}
        </Card>
      )}
      {s.kind === 'test' && (
        <>
          {s.description && <p className="whitespace-pre-wrap text-sm">{s.description}</p>}
          {s.state === 'done' ? (
            <Card tint="mint" className="p-6 text-center">
              <div className="text-3xl font-semibold tabular-nums">{s.score}%</div>
              <p className="mt-1 text-sm text-muted">{t('internship.testPassed')}</p>
            </Card>
          ) : (
            <>
              <Card className="p-4 text-sm text-muted">
                {t('internship.testInfo', { pass: s.pass_score ?? e.pass_score })}
                {s.max_attempts > 0 && ` · ${t('internship.attemptsLeft', { count: Math.max(s.max_attempts - s.attempts, 0) })}`}
              </Card>
              {result && !result.passed && (
                <Card tint="rose" className="p-5 text-center" role="alert">
                  <div className="text-2xl font-semibold tabular-nums">{result.score}%</div>
                  <p className="mt-1 text-sm">{t('internship.testFailed', { pass: result.threshold })}</p>
                </Card>
              )}
              {exhausted && <p role="alert" className="text-sm font-medium text-danger">{t('internship.attemptsExhausted')}</p>}
              <form
                onSubmit={(ev) => {
                  ev.preventDefault()
                  setResult(null)
                  submit.mutate()
                }}
                className="flex flex-col gap-4"
              >
                {s.questions.map((qu, i) => {
                  const wrong = result?.wrong.includes(qu.id)
                  return (
                    <Card key={qu.id} className={'p-5 ' + (wrong ? 'ring-2 ring-danger/40' : '')}>
                      <fieldset className="flex flex-col gap-2">
                        <legend className="mb-2 text-sm font-medium">
                          {i + 1}. {qu.text}
                          {qu.multiple && <span className="ml-2 text-xs font-normal text-muted">{t('internship.multiple')}</span>}
                        </legend>
                        {qu.options.map((o, j) => (
                          <label key={j} className="flex cursor-pointer items-center gap-3 rounded-control border border-border px-3 py-2.5 text-sm hover:bg-surface-2">
                            <input type={qu.multiple ? 'checkbox' : 'radio'} name={qu.id} className="size-4" disabled={exhausted || locked} checked={answers[qu.id]?.includes(j) ?? false} onChange={() => toggle(qu.id, j, !!qu.multiple)} />
                            {o}
                          </label>
                        ))}
                      </fieldset>
                    </Card>
                  )
                })}
                {submit.isError && (
                  <p role="alert" className="text-sm text-danger">
                    {errorText(t, submit.error)}
                  </p>
                )}
                {!locked && (
                  <div>
                    <Button type="submit" disabled={submit.isPending || exhausted || Object.keys(answers).length < s.questions.length}>
                      {t('internship.submitTest')}
                    </Button>
                  </div>
                )}
              </form>
            </>
          )}
          {result?.passed && (
            <Button onClick={() => navigate(result.status === 'ready' || !next ? back : `${back}/steps/${next.id}`, { replace: true })}>{result.status === 'ready' ? t('internship.finished') : t('internship.nextStep')}</Button>
          )}
        </>
      )}
    </div>
  )
}
