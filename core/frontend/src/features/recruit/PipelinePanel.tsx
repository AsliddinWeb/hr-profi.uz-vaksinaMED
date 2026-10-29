import { OfferExtras } from './EvalParts'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Send, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { send } from '../../lib/api'
import { fromLocalInput } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { money, type ApplicationDetail } from './api'

const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'
const LEVELS = ['intern', 'pharmacist', 'senior'] as const

/** Suhbat natijasi, fon tekshiruv, AI skaner, taklif va job offer (HRD tasdig'i). */
export function PipelinePanel({ a }: { a: ApplicationDetail }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const base = `/api/v1/recruit/applications/${a.id}`
  const [exp, setExp] = useState<string>(a.experience_level ?? '')
  const [hard, setHard] = useState(String(a.hard_skill ?? 3))
  const [soft, setSoft] = useState(String(a.soft_skill ?? 3))
  const [notes, setNotes] = useState(a.interview_notes ?? '')
  const [bgNote, setBgNote] = useState(a.bg_note ?? '')
  const [pickedLevel, setLevel] = useState<string>(a.offer?.level ?? '')
  const level = pickedLevel && a.stages_unlocked.includes(pickedLevel as never) ? pickedLevel : (a.stages_unlocked.at(-1) ?? '')
  const [salary, setSalary] = useState(String(a.offer?.salary ?? ''))
  const [start, setStart] = useState(a.offer?.start ?? '')
  const [schedule, setSchedule] = useState(a.offer?.schedule ?? '')
  const [probation, setProbation] = useState(String(a.offer?.probation_days ?? 7))
  const [decision, setDecision] = useState('')
  const [when, setWhen] = useState('')
  const [place, setPlace] = useState('')
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body?: unknown }) => send('POST', `${base}/${path}`, body),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['recruit'] }),
  })
  const run = (path: string, body?: unknown) => act.mutate({ path, body })
  const open = a.stage !== 'hired' && a.stage !== 'rejected'
  if (!open && !a.offer && !a.experience_level) return null
  const scan = a.ai_scan

  return (
    <Card className="flex flex-col gap-6 p-6">
      {a.can.manage && open && (
        <section className="flex flex-col gap-3" aria-labelledby="pp-invite">
          <h2 id="pp-invite" className="font-semibold">{t('pipeline.invite')}</h2>
          <p className="text-xs text-muted">{a.has_telegram ? t('pipeline.inviteTg') : t('pipeline.inviteNoTg')}</p>
          <div className="grid gap-3 sm:grid-cols-3">
            <Input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} aria-label={t('recruit.application.interviewAt')} />
            <Input value={place} onChange={(e) => setPlace(e.target.value)} maxLength={200} placeholder={t('pipeline.place')} aria-label={t('pipeline.place')} className="sm:col-span-2" />
          </div>
          <div>
            <Button variant="outline" disabled={act.isPending || !when} onClick={() => run('invite', { interview_at: fromLocalInput(when), place: place || null })}>
              <Send className="size-4" />
              {t('pipeline.inviteBtn')}
            </Button>
          </div>
        </section>
      )}

      <section className="flex flex-col gap-3 border-t border-border pt-5 first:border-0 first:pt-0" aria-labelledby="pp-int">
        <h2 id="pp-int" className="font-semibold">{t('pipeline.interview')}</h2>
        {a.can.manage && open ? (
          <>
            <div className="grid gap-3 sm:grid-cols-3">
              <Select value={exp} onChange={(e) => setExp(e.target.value)} aria-label={t('pipeline.experience')}>
                <option value="">{t('pipeline.experience')}</option>
                {(['high', 'mid', 'none'] as const).map((x) => (
                  <option key={x} value={x}>
                    {t(`pipeline.exp.${x}`)}
                  </option>
                ))}
              </Select>
              <Select value={hard} onChange={(e) => setHard(e.target.value)} aria-label="Hard skill">
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    Hard skill: {n}/5
                  </option>
                ))}
              </Select>
              <Select value={soft} onChange={(e) => setSoft(e.target.value)} aria-label="Soft skill">
                {[1, 2, 3, 4, 5].map((n) => (
                  <option key={n} value={n}>
                    Soft skill: {n}/5
                  </option>
                ))}
              </Select>
            </div>
            <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={3000} placeholder={t('pipeline.notes')} aria-label={t('pipeline.notes')} className={area} />
            <div>
              <Button disabled={act.isPending || !exp} onClick={() => run('interview', { experience_level: exp, hard_skill: Number(hard), soft_skill: Number(soft), notes: notes || null })}>
                {t('pipeline.saveInterview')}
              </Button>
            </div>
          </>
        ) : null}
        {a.experience_level && (
          <p className="text-sm text-muted">
            {t(`pipeline.exp.${a.experience_level}`)} · {t('pipeline.unlocked')}: {a.stages_unlocked.map((s) => t(`pipeline.level.${s}`)).join(' → ')}
          </p>
        )}
      </section>

      <section className="flex flex-col gap-3 border-t border-border pt-5" aria-labelledby="pp-bg">
        <h2 id="pp-bg" className="font-semibold">{t('pipeline.background')}</h2>
        {a.bg_status && <Badge tone={a.bg_status === 'passed' ? 'success' : a.bg_status === 'failed' ? 'danger' : 'warning'}>{t(`pipeline.bg.${a.bg_status}`)}</Badge>}
        {a.can.manage && open && (
          <>
            <Input value={bgNote} onChange={(e) => setBgNote(e.target.value)} maxLength={2000} placeholder={t('pipeline.bgNote')} aria-label={t('pipeline.bgNote')} />
            <div className="flex flex-wrap gap-2">
              <Button variant="outline" disabled={act.isPending} onClick={() => run('background', { status: 'passed', note: bgNote || null })}>
                {t('pipeline.bg.passed')}
              </Button>
              <Button variant="outline" className="text-danger" disabled={act.isPending || !bgNote.trim()} onClick={() => run('background', { status: 'failed', note: bgNote })}>
                {t('pipeline.bg.failed')}
              </Button>
              <Button variant="outline" disabled={act.isPending} onClick={() => run('background', { status: 'pending', note: bgNote || null })}>
                {t('pipeline.bg.pending')}
              </Button>
            </div>
          </>
        )}
      </section>

      <section className="flex flex-col gap-3 border-t border-border pt-5" aria-labelledby="pp-ai">
        <h2 id="pp-ai" className="font-semibold">{t('pipeline.ai')}</h2>
        {scan && (
          <div className="flex flex-col gap-2 rounded-control bg-surface-2 p-4 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={scan.recommendation === 'advance' ? 'success' : scan.recommendation === 'reject' ? 'danger' : 'warning'}>{t(`pipeline.rec.${scan.recommendation}`)}</Badge>
              {scan.score !== null && <span className="font-semibold">{scan.score}/100</span>}
            </div>
            <p>{scan.summary}</p>
            {scan.strengths.length > 0 && <p><span className="text-muted">{t('pipeline.strengths')}:</span> {scan.strengths.join('; ')}</p>}
            {scan.risks.length > 0 && <p><span className="text-muted">{t('pipeline.risks')}:</span> {scan.risks.join('; ')}</p>}
            {scan.questions.length > 0 && <p><span className="text-muted">{t('pipeline.questions')}:</span> {scan.questions.join('; ')}</p>}
            <p className="text-xs text-muted">{t('pipeline.aiHint')}</p>
          </div>
        )}
        {a.can.manage && open && (
          <div>
            <Button variant="outline" disabled={act.isPending} onClick={() => run('ai-scan')}>
              <Sparkles className="size-4" />
              {scan ? t('pipeline.aiAgain') : t('pipeline.aiRun')}
            </Button>
          </div>
        )}
      </section>

      <section className="flex flex-col gap-3 border-t border-border pt-5" aria-labelledby="pp-offer">
        <h2 id="pp-offer" className="font-semibold">{t('pipeline.offer')}</h2>
        {a.offer && (
          <p className="text-sm">
            <Badge tone={a.offer.status === 'approved' ? 'success' : a.offer.status === 'rejected' ? 'danger' : 'warning'}>{t(`pipeline.offerStatus.${a.offer.status}`)}</Badge>{' '}
            {a.offer.level && t(`pipeline.level.${a.offer.level}`)} · {money(a.offer.salary)} {t('apply.currency')}
            {a.offer.start && ` · ${a.offer.start}`}
            {a.offer.decision_note && <span className="text-muted"> · {a.offer.decision_note}</span>}
            {a.offer.sent_at && <span className="text-muted"> · {t('pipeline.sent')}</span>}
          </p>
        )}
        <OfferExtras a={a as never} />
        {a.can.manage && open && a.experience_level && (
          <div className="grid gap-3 sm:grid-cols-3">
            <Select value={level} onChange={(e) => setLevel(e.target.value)} aria-label={t('pipeline.levelLabel')}>
              {LEVELS.filter((l) => a.stages_unlocked.includes(l)).map((l) => (
                <option key={l} value={l}>
                  {t(`pipeline.level.${l}`)}
                </option>
              ))}
            </Select>
            <Input type="number" min={0} value={salary} onChange={(e) => setSalary(e.target.value)} placeholder={t('pipeline.salary')} aria-label={t('pipeline.salary')} />
            <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} aria-label={t('pipeline.startDate')} />
            <Input value={schedule} onChange={(e) => setSchedule(e.target.value)} placeholder={t('recruitEval.offer.schedule')} aria-label={t('recruitEval.offer.schedule')} maxLength={200} className="sm:col-span-2" />
            <Input type="number" min={0} max={180} value={probation} onChange={(e) => setProbation(e.target.value)} placeholder={t('recruitEval.offer.probationLabel')} aria-label={t('recruitEval.offer.probationLabel')} />
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          {a.can.manage && open && a.experience_level && (
            <Button disabled={act.isPending || !level || !salary} onClick={() => run('offer', { level, salary: Number(salary), start_date: start || null, schedule: schedule || null, probation_days: probation === '' ? null : Number(probation) })}>
              {a.offer ? t('pipeline.offerAgain') : t('pipeline.offerMake')}
            </Button>
          )}
          {a.can.manage && a.offer?.status === 'approved' && (
            <Button variant="outline" disabled={act.isPending || !a.has_telegram} onClick={() => run('offer/send')} title={a.has_telegram ? undefined : t('pipeline.noTg')}>
              <Send className="size-4" />
              {t('pipeline.offerSend')}
            </Button>
          )}
        </div>
        {a.can.approve && a.offer?.status === 'pending_hrd' && (
          <div className="flex flex-col gap-2 rounded-control border border-border p-3">
            <p className="text-sm font-medium">{t('pipeline.hrdDecision')}</p>
            <Input value={decision} onChange={(e) => setDecision(e.target.value)} maxLength={1000} placeholder={t('answers.decision.note')} aria-label={t('answers.decision.note')} />
            <div className="flex gap-2">
              <Button disabled={act.isPending} onClick={() => run('offer/decide', { action: 'approve', note: decision || null })}>
                {t('pipeline.approve')}
              </Button>
              <Button variant="outline" className="text-danger" disabled={act.isPending || !decision.trim()} onClick={() => run('offer/decide', { action: 'reject', note: decision })}>
                {t('pipeline.reject')}
              </Button>
            </div>
          </div>
        )}
      </section>
      {act.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, act.error)}
        </p>
      )}
    </Card>
  )
}
