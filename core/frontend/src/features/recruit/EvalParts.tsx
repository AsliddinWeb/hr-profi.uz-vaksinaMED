import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Copy, FileDown, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import type { ApplicationDetail, BgCheck, CandTest, TestBankRow } from './api'

const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'

interface ScoreCard {
  application: { id: number; candidate: string | null; vacancy: string | null }
  competencies: { key: string; group: 'hard' | 'soft' }[]
  questions: string[]
  mine: { scores: Record<string, number>; notes: string | null } | null
  summary: { by_competency: Record<string, number>; overall: number | null; interviewers: number } | null
  interviewers?: { name: string | null; scores: Record<string, number>; notes: string | null; avg: number | null }[]
}

/** Suhbat kartochkasi: kompetensiya bo'yicha 1–5 baho (har suhbatdosh o'ziniki), HR o'rtachani ko'radi. */
export function ScorecardPanel({ appId }: { appId: number }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['recruit', 'scorecard', appId], queryFn: () => api<ScoreCard>(`/api/v1/recruit/applications/${appId}/scorecard`), retry: false })
  if (!q.data) return null
  return <ScoreForm key={q.data.mine ? 'm' : 'n'} data={q.data} onSaved={() => (void qc.invalidateQueries({ queryKey: ['recruit'] }), toast.push({ title: t('recruitEval.score.saved'), tone: 'success' }))} appId={appId} />
}

function ScoreForm({ data, appId, onSaved }: { data: ScoreCard; appId: number; onSaved: () => void }) {
  const { t } = useTranslation()
  const [scores, setScores] = useState<Record<string, number>>(data.mine?.scores ?? {})
  const [notes, setNotes] = useState(data.mine?.notes ?? '')
  const save = useMutation({ mutationFn: () => send('PUT', `/api/v1/recruit/applications/${appId}/scorecard`, { scores, notes: notes || null }), onSuccess: onSaved })
  return (
    <Card className="flex flex-col gap-4 p-5">
      <h2 className="font-semibold">{t('recruitEval.score.title')}</h2>
      {data.questions.length > 0 && (
        <div className="rounded-xl border border-border bg-surface-2 p-3 text-sm">
          <div className="mb-1 text-xs font-semibold">{t('recruitEval.score.questions')}</div>
          <ol className="list-decimal pl-5">
            {data.questions.map((x) => (
              <li key={x}>{x}</li>
            ))}
          </ol>
        </div>
      )}
      <ul className="flex flex-col gap-3">
        {data.competencies.map((c) => (
          <li key={c.key} className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <span>
              {c.key} <span className="text-xs text-muted">· {t(`recruitEval.score.group.${c.group}`)}</span>
              {data.summary?.by_competency[c.key] !== undefined && <span className="ml-2 text-xs text-muted">Ø {data.summary.by_competency[c.key]}</span>}
            </span>
            <div className="flex gap-1.5">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} type="button" aria-pressed={scores[c.key] === n} onClick={() => setScores({ ...scores, [c.key]: n })} className={'size-9 rounded-full border text-sm font-medium ' + (scores[c.key] === n ? 'border-primary bg-primary text-primary-fg' : 'border-border text-muted')}>
                  {n}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ul>
      <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} maxLength={2000} placeholder={t('recruitEval.score.notes')} aria-label={t('recruitEval.score.notes')} className={area} />
      {save.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, save.error)}
        </p>
      )}
      <div className="flex items-center gap-3">
        <Button disabled={save.isPending || Object.keys(scores).length === 0} onClick={() => save.mutate()}>
          {t('common.save')}
        </Button>
        {data.summary && data.summary.overall !== null && (
          <span className="text-sm text-muted">
            {t('recruitEval.score.overall', { v: data.summary.overall, n: data.summary.interviewers })}
          </span>
        )}
      </div>
      {data.interviewers && data.interviewers.length > 0 && (
        <ul className="grid gap-1 border-t border-border pt-3 text-xs text-muted sm:grid-cols-2">
          {data.interviewers.map((i, idx) => (
            <li key={idx}>
              {i.name}: Ø {i.avg ?? '—'}
              {i.notes ? ` · ${i.notes}` : ''}
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}

/** Testlar: bankdan test berish (havola), natija avtomatik. */
export function TestsPanel({ appId, open }: { appId: number; open: boolean }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const banks = useQuery({ queryKey: ['recruit', 'tests'], queryFn: () => api<TestBankRow[]>('/api/v1/recruit/tests') })
  const list = useQuery({ queryKey: ['recruit', 'app-tests', appId], queryFn: () => api<CandTest[]>(`/api/v1/recruit/applications/${appId}/tests`), refetchInterval: 30_000 })
  const [bank, setBank] = useState('')
  const assign = useMutation({
    mutationFn: () => send<{ url: string; telegram_sent: boolean }>('POST', `/api/v1/recruit/applications/${appId}/tests`, { bank_id: Number(bank) }),
    onSuccess: (r) => {
      void navigator.clipboard?.writeText(r.url)
      void qc.invalidateQueries({ queryKey: ['recruit'] })
      toast.push({ title: r.telegram_sent ? t('recruitEval.tests.sentTelegram') : t('recruitEval.tests.copied'), tone: 'success' })
    },
  })
  const active = (banks.data ?? []).filter((b) => b.is_active)
  return (
    <Card className="flex flex-col gap-3 p-5">
      <h2 className="font-semibold">{t('recruitEval.tests.title')}</h2>
      <ul className="flex flex-col gap-2 text-sm">
        {(list.data ?? []).map((x) => (
          <li key={x.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-border px-3 py-2">
            <span>
              {x.bank.name} <span className="text-xs text-muted">· {t(`recruitEval.tests.kind.${x.bank.kind ?? 'logic'}`)}</span>
            </span>
            <span className="flex items-center gap-2">
              {x.score_pct !== null && <Badge tone={x.passed ? 'success' : 'danger'}>{x.score_pct}%</Badge>}
              <Badge tone={x.status === 'submitted' ? 'success' : x.status === 'expired' ? 'danger' : 'neutral'}>{t(`recruitEval.tests.status.${x.status}`)}</Badge>
              {x.url && (
                <Button variant="outline" className="h-8 px-2" aria-label={t('recruitEval.tests.copy')} onClick={() => void navigator.clipboard?.writeText(x.url as string)}>
                  <Copy className="size-4" />
                </Button>
              )}
            </span>
          </li>
        ))}
        {list.data?.length === 0 && <li className="text-muted">{t('recruitEval.tests.none')}</li>}
      </ul>
      {open && (
        <div className="flex flex-wrap gap-2">
          <Select className="w-64" value={bank} onChange={(e) => setBank(e.target.value)} aria-label={t('recruitEval.tests.pick')}>
            <option value="">{t('recruitEval.tests.pick')}</option>
            {active.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} · {b.time_limit_min} {t('recruitEval.tests.min')}
              </option>
            ))}
          </Select>
          <Button disabled={!bank || assign.isPending} onClick={() => assign.mutate()}>
            {t('recruitEval.tests.assign')}
          </Button>
        </div>
      )}
      {assign.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, assign.error)}
        </p>
      )}
    </Card>
  )
}

const BG_KEYS = ['reference', 'documents', 'social', 'other'] as const

/** Fon tekshiruvi: nomzod roziligi (havola) -> bandlar -> qaror. */
export function BackgroundPanel({ appId }: { appId: number }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const can = useCan()
  const allowed = can('recruit.manage') || can('recruit.background')
  const q = useQuery({ queryKey: ['recruit', 'bgcheck', appId], queryFn: () => api<BgCheck | null>(`/api/v1/recruit/applications/${appId}/background-check`), enabled: allowed, retry: false })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['recruit'] })
  const start = useMutation({
    mutationFn: () => send<BgCheck & { telegram_sent: boolean }>('POST', `/api/v1/recruit/applications/${appId}/background-check`),
    onSuccess: (r) => {
      if (r.consent_url) void navigator.clipboard?.writeText(r.consent_url)
      toast.push({ title: r.telegram_sent ? t('recruitEval.bg.sentTelegram') : t('recruitEval.bg.copied'), tone: 'success' })
      refresh()
    },
  })
  const [draft, setDraft] = useState<Record<string, { result: string; note: string }>>({})
  const [note, setNote] = useState('')
  const saveItems = useMutation({
    mutationFn: () => send('PUT', `/api/v1/recruit/applications/${appId}/background-check/items`, { items: BG_KEYS.map((k) => ({ key: k, result: (draft[k]?.result ?? q.data?.items.find((i) => i.key === k)?.result) || null, note: (draft[k]?.note ?? q.data?.items.find((i) => i.key === k)?.note) || null })) }),
    onSuccess: refresh,
  })
  const finish = useMutation({ mutationFn: (decision: 'passed' | 'failed') => send('POST', `/api/v1/recruit/applications/${appId}/background-check/finish`, { decision, note: note || null }), onSuccess: refresh })
  if (!allowed) return null
  const bg = q.data
  const done = bg?.status === 'done'
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-semibold">
          <ShieldCheck className="size-5" />
          {t('recruitEval.bg.title')}
        </h2>
        {bg && <Badge tone={done ? (bg.decision === 'passed' ? 'success' : 'danger') : bg.consent_at ? 'warning' : 'neutral'}>{done ? t(`recruitEval.bg.decision.${bg.decision}`) : t(`recruitEval.bg.status.${bg.status}`)}</Badge>}
      </div>
      {!bg && (
        <>
          <p className="text-sm text-muted">{t('recruitEval.bg.hint')}</p>
          <div>
            <Button disabled={start.isPending} onClick={() => start.mutate()}>
              {t('recruitEval.bg.start')}
            </Button>
          </div>
        </>
      )}
      {bg && !bg.consent_at && (
        <div className="flex flex-col gap-2 text-sm">
          <p className="text-muted">{t('recruitEval.bg.waitingConsent')}</p>
          {bg.consent_url && <code className="truncate rounded bg-surface-2 px-2 py-1 text-xs">{bg.consent_url}</code>}
          <div>
            <Button variant="outline" onClick={() => start.mutate()}>
              {t('recruitEval.bg.resend')}
            </Button>
          </div>
        </div>
      )}
      {bg && bg.consent_at && (
        <>
          <p className="text-xs text-muted">{t('recruitEval.bg.consentAt', { when: formatDateTime(bg.consent_at, i18n.language) })}</p>
          <ul className="flex flex-col gap-2">
            {BG_KEYS.map((k) => {
              const cur = bg.items.find((i) => i.key === k)
              return (
                <li key={k} className="grid gap-2 sm:grid-cols-[1fr_9rem_1.2fr] sm:items-center">
                  <span className="text-sm">{t(`recruitEval.bg.items.${k}`)}</span>
                  <Select disabled={done} value={draft[k]?.result ?? cur?.result ?? ''} onChange={(e) => setDraft({ ...draft, [k]: { result: e.target.value, note: draft[k]?.note ?? cur?.note ?? '' } })} aria-label={t(`recruitEval.bg.items.${k}`)}>
                    <option value="">—</option>
                    {['positive', 'negative', 'unknown'].map((r) => (
                      <option key={r} value={r}>
                        {t(`recruitEval.bg.result.${r}`)}
                      </option>
                    ))}
                  </Select>
                  <Input disabled={done} value={draft[k]?.note ?? cur?.note ?? ''} onChange={(e) => setDraft({ ...draft, [k]: { result: draft[k]?.result ?? cur?.result ?? '', note: e.target.value } })} placeholder={t('recruitEval.bg.note')} maxLength={500} aria-label={t('recruitEval.bg.note')} />
                </li>
              )
            })}
          </ul>
          {done ? (
            bg.decision_note && <p className="text-sm text-muted">{bg.decision_note}</p>
          ) : (
            <>
              <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder={t('recruitEval.bg.conclusionNote')} maxLength={2000} aria-label={t('recruitEval.bg.conclusionNote')} />
              <div className="flex flex-wrap gap-2">
                <Button variant="outline" disabled={saveItems.isPending} onClick={() => saveItems.mutate()}>
                  {t('common.save')}
                </Button>
                <Button disabled={finish.isPending} onClick={() => finish.mutate('passed')}>
                  {t('recruitEval.bg.passed')}
                </Button>
                <Button variant="outline" className="text-danger" disabled={finish.isPending || !note.trim()} onClick={() => finish.mutate('failed')}>
                  {t('recruitEval.bg.failed')}
                </Button>
              </div>
            </>
          )}
        </>
      )}
      {[start, saveItems, finish].map((m, i) => m.isError && (
        <p key={i} role="alert" className="text-sm text-danger">
          {errorText(t, m.error)}
        </p>
      ))}
    </Card>
  )
}

const REC_TONE = { hire: 'success', reserve: 'warning', reject: 'danger' } as const

/** Yakuniy xulosa: loyiha (intervyu + test + moslik + fon) -> rekruter tahrirlaydi -> HR rahbariyati tasdiqlaydi. */
export function ConclusionPanel({ a }: { a: ApplicationDetail }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const can = useCan()
  const c = a.conclusion
  const [text, setText] = useState(c?.text ?? c?.draft ?? '')
  const [rec, setRec] = useState<string>(c?.recommendation ?? 'reserve')
  const base = `/api/v1/recruit/applications/${a.id}/conclusion`
  const refresh = () => void qc.invalidateQueries({ queryKey: ['recruit'] })
  const draft = useMutation({ mutationFn: () => send<{ draft: string; recommendation: string }>('POST', `${base}/draft`), onSuccess: (r) => (setText(r.draft), setRec(r.recommendation), refresh()) })
  const save = useMutation({ mutationFn: () => send('PUT', base, { text, recommendation: rec }), onSuccess: refresh })
  const approve = useMutation({ mutationFn: () => send('POST', `${base}/approve`), onSuccess: refresh })
  const approved = c?.status === 'approved'
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{t('recruitEval.conclusion.title')}</h2>
        {c && <Badge tone={REC_TONE[c.recommendation]}>{t(`recruitEval.conclusion.rec.${c.recommendation}`)}{c.score !== null ? ` · ${c.score}` : ''}</Badge>}
      </div>
      {!c && <p className="text-sm text-muted">{t('recruitEval.conclusion.hint')}</p>}
      {c && (
        <>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={9} maxLength={6000} disabled={approved || !a.can.manage} className={area} aria-label={t('recruitEval.conclusion.title')} />
          {!approved && a.can.manage && (
            <Select className="w-64" value={rec} onChange={(e) => setRec(e.target.value)} aria-label={t('recruitEval.conclusion.recLabel')}>
              {(['hire', 'reserve', 'reject'] as const).map((r) => (
                <option key={r} value={r}>
                  {t(`recruitEval.conclusion.rec.${r}`)}
                </option>
              ))}
            </Select>
          )}
          {approved && <p className="text-sm text-success">{t('recruitEval.conclusion.approvedBy', { who: c.approved_by_name ?? '—', when: c.approved_at ? formatDateTime(c.approved_at, i18n.language) : '' })}</p>}
        </>
      )}
      <div className="flex flex-wrap gap-2">
        {a.can.manage && !approved && (
          <Button variant="outline" disabled={draft.isPending} onClick={() => draft.mutate()}>
            {t(c ? 'recruitEval.conclusion.regenerate' : 'recruitEval.conclusion.generate')}
          </Button>
        )}
        {a.can.manage && c && !approved && (
          <Button disabled={save.isPending || text.trim().length < 10} onClick={() => save.mutate()}>
            {t('common.save')}
          </Button>
        )}
        {can('recruit.approve') && c && !approved && (
          <Button disabled={approve.isPending} onClick={() => approve.mutate()}>
            {t('recruitEval.conclusion.approve')}
          </Button>
        )}
      </div>
      {[draft, save, approve].map((m, i) => m.isError && (
        <p key={i} role="alert" className="text-sm text-danger">
          {errorText(t, m.error)}
        </p>
      ))}
    </Card>
  )
}

/** Offer: nomzodga havola, PDF va nomzod javobi. */
export function OfferExtras({ a }: { a: ApplicationDetail }) {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const link = useMutation({
    mutationFn: () => send<{ url: string }>('POST', `/api/v1/recruit/applications/${a.id}/offer/link`),
    onSuccess: (r) => {
      void navigator.clipboard?.writeText(r.url)
      toast.push({ title: t('recruitEval.offer.copied'), tone: 'success' })
      void qc.invalidateQueries({ queryKey: ['recruit'] })
    },
  })
  const o = a.offer
  if (!o || o.status === 'rejected') return null
  return (
    <div className="flex flex-col gap-2 text-sm">
      {(o.schedule || o.probation_days !== null) && (
        <p className="text-muted">
          {o.schedule && `${t('recruitEval.offer.schedule')}: ${o.schedule}`}
          {o.probation_days !== null && o.probation_days !== undefined && ` · ${t('recruitEval.offer.probation', { n: o.probation_days })}`}
        </p>
      )}
      {o.response && (
        <p className={o.response === 'accepted' ? 'font-medium text-success' : 'font-medium text-danger'}>
          {t(`recruitEval.offer.response.${o.response}`)}
          {o.response_at ? ` · ${formatDateTime(o.response_at, i18n.language)}` : ''}
          {o.decline_reason ? ` · ${o.decline_reason}` : ''}
        </p>
      )}
      {a.can.manage && o.status === 'approved' && (
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" disabled={link.isPending} onClick={() => link.mutate()}>
            <Copy className="size-4" />
            {t('recruitEval.offer.link')}
          </Button>
          <a href={`/api/v1/recruit/applications/${a.id}/offer/pdf`} download>
            <Button variant="outline">
              <FileDown className="size-4" />
              PDF
            </Button>
          </a>
        </div>
      )}
    </div>
  )
}
