import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { todayLocal } from '../attendance/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'

export interface Att {
  id: number
  month: string
  status: 'open' | 'scored' | 'decided'
  employee: { id: number; name: string }
  branch: string | null
  level: string | null
  test_score: number | null
  practical_score: number | null
  total: number | null
  pass_score: number
  passes: boolean
  feedbacks: { role: string; author: string; text: string; at: string }[]
  decision: 'passed' | 'retake' | 'extra_lessons' | null
  decision_note: string | null
  can: { score: boolean; feedback: boolean; decide: boolean }
}
interface Report {
  levels: { level: string | null; total: number; open: number; scored: number; passed: number; retake: number; extra_lessons: number; avg: number | null }[]
}
const TONE = { open: 'neutral', scored: 'warning', decided: 'success' } as const

/** /attestation: oylik attestatsiyalar (o'zimniki yoki ko'ra oladiganlarim) va HRD hisoboti. */
export function AttestationPage() {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const can = useCan()
  const [month, setMonth] = useState(() => todayLocal().slice(0, 7))
  const manage = can('attestation.manage')
  const sees = manage || can('attestation.read')
  const list = useQuery({ queryKey: ['attestation', month], queryFn: () => api<Att[]>(`/api/v1/attestation?month=${month}&scope=${sees || can('attestation.own') ? 'all' : 'mine'}`) })
  const report = useQuery({ queryKey: ['attestation', 'report', month], queryFn: () => api<Report>(`/api/v1/attestation/report?month=${month}`), enabled: sees })
  const open = useMutation({
    mutationFn: () => send<{ created: number }>('POST', `/api/v1/attestation/cycles?month=${month}`),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['attestation'] })
      toast.push({ title: t('growth.att.opened', { n: r.created }), tone: 'success' })
    },
  })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('growth.att.title')}
        subtitle={t('growth.att.subtitle')}
        actions={
          manage && (
            <Button variant="outline" disabled={open.isPending} onClick={() => open.mutate()}>
              {t('growth.att.open')}
            </Button>
          )
        }
      />
      <div className="flex items-center gap-3">
        <Input type="month" value={month} onChange={(e) => setMonth(e.target.value)} className="w-auto" aria-label={t('growth.att.month')} />
        {open.isError && <span role="alert" className="text-sm text-danger">{errorText(t, open.error)}</span>}
      </div>
      {report.data && report.data.levels.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-border text-xs text-muted">
              <tr>
                {['level', 'total', 'open', 'scored', 'passed', 'retake', 'extra', 'avg'].map((c) => (
                  <th key={c} className="px-3 py-2.5 font-medium">{t(`growth.att.col.${c}`)}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {report.data.levels.map((r, i) => (
                <tr key={i}>
                  <td className="px-3 py-2.5">{r.level ?? '—'}</td>
                  <td className="px-3 py-2.5 tabular-nums">{r.total}</td>
                  <td className="px-3 py-2.5 tabular-nums">{r.open}</td>
                  <td className="px-3 py-2.5 tabular-nums">{r.scored}</td>
                  <td className="px-3 py-2.5 tabular-nums">{r.passed}</td>
                  <td className="px-3 py-2.5 tabular-nums">{r.retake}</td>
                  <td className="px-3 py-2.5 tabular-nums">{r.extra_lessons}</td>
                  <td className="px-3 py-2.5 tabular-nums">{r.avg ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
      {!list.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {list.data.map((a) => (
            <Link key={a.id} to={`/attestation/${a.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
                <div>
                  <div className="font-medium">{a.employee.name}</div>
                  <div className="text-sm text-muted">{[a.level, a.branch].filter(Boolean).join(' · ')}</div>
                </div>
                <div className="flex items-center gap-2">
                  {a.total !== null && <span className="font-semibold tabular-nums">{a.total}</span>}
                  <Badge tone={a.decision === 'passed' ? 'success' : a.decision ? 'danger' : TONE[a.status]}>{a.decision ? t(`growth.att.decision.${a.decision}`) : t(`growth.att.status.${a.status}`)}</Badge>
                </div>
              </Card>
            </Link>
          ))}
          {list.data.length === 0 && <Card className="p-8 text-center text-muted">{t('growth.att.empty')}</Card>}
        </div>
      )}
    </div>
  )
}

/** /attestation/:id: ball, fidbek va qaror. */
export function AttestationDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['attestation', 'one', id], queryFn: () => api<Att>(`/api/v1/attestation/${id}`), retry: false })
  const [test, setTest] = useState('')
  const [practical, setPractical] = useState('')
  const [fb, setFb] = useState('')
  const [note, setNote] = useState('')
  const act = useMutation({
    mutationFn: ({ path, body }: { path: string; body: unknown }) => send('POST', `/api/v1/attestation/${id}/${path}`, body),
    onSuccess: () => (setFb(''), void qc.invalidateQueries({ queryKey: ['attestation'] })),
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const a = q.data
  if (!a) return <Skeleton className="mx-auto h-72 max-w-3xl" />
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={a.employee.name} subtitle={`${a.month} · ${a.level ?? '—'}`} backTo="/attestation" backLabel={t('growth.att.title')} />
      <Card className="flex flex-col gap-3 p-5">
        <div className="grid gap-3 text-sm sm:grid-cols-4">
          <Stat label={t('growth.att.test')} v={a.test_score} />
          <Stat label={t('growth.att.practical')} v={a.practical_score} />
          <Stat label={t('growth.att.total')} v={a.total} />
          <Stat label={t('growth.att.passScore')} v={a.pass_score} />
        </div>
        {a.total !== null && <Badge tone={a.passes ? 'success' : 'warning'}>{a.passes ? t('growth.att.meets') : t('growth.att.below')}</Badge>}
        {a.decision && (
          <p className="text-sm">
            <Badge tone={a.decision === 'passed' ? 'success' : 'danger'}>{t(`growth.att.decision.${a.decision}`)}</Badge> {a.decision_note}
          </p>
        )}
        {a.can.score && (
          <div className="flex flex-wrap items-end gap-3 border-t border-border pt-3">
            <Input type="number" min={0} max={100} value={test} onChange={(e) => setTest(e.target.value)} placeholder={t('growth.att.test')} aria-label={t('growth.att.test')} className="w-36" />
            <Input type="number" min={0} max={100} value={practical} onChange={(e) => setPractical(e.target.value)} placeholder={t('growth.att.practical')} aria-label={t('growth.att.practical')} className="w-36" />
            <Button disabled={act.isPending || (!test && !practical)} onClick={() => act.mutate({ path: 'scores', body: { test_score: test ? Number(test) : null, practical_score: practical ? Number(practical) : null } })}>
              {t('growth.att.saveScores')}
            </Button>
          </div>
        )}
      </Card>
      <Card className="flex flex-col gap-3 p-5">
        <h2 className="font-semibold">{t('growth.att.feedback')}</h2>
        {a.feedbacks.map((f, i) => (
          <p key={i} className="text-sm">
            <Badge>{t(`growth.att.role.${f.role}`)}</Badge> {f.author}: {f.text} <span className="text-xs text-muted">· {formatDateTime(f.at, i18n.language)}</span>
          </p>
        ))}
        {a.can.feedback && (
          <div className="flex gap-2">
            <Input value={fb} onChange={(e) => setFb(e.target.value)} maxLength={2000} placeholder={t('onboarding.feedbackPlaceholder')} aria-label={t('onboarding.feedbackPlaceholder')} />
            <Button variant="outline" disabled={fb.trim().length < 2 || act.isPending} onClick={() => act.mutate({ path: 'feedback', body: { text: fb } })}>
              {t('tasks.send')}
            </Button>
          </div>
        )}
      </Card>
      {a.can.decide && (
        <Card className="flex flex-col gap-3 p-5">
          <h2 className="font-semibold">{t('growth.att.decideTitle')}</h2>
          <p className="text-xs text-muted">{t('growth.att.decideHint')}</p>
          <Input value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} placeholder={t('answers.decision.note')} aria-label={t('answers.decision.note')} />
          <div className="flex flex-wrap gap-2">
            {(['passed', 'retake', 'extra_lessons'] as const).map((d) => (
              <Button key={d} variant={d === 'passed' ? 'primary' : 'outline'} disabled={act.isPending || a.total === null} onClick={() => act.mutate({ path: 'decide', body: { decision: d, note: note || null } })}>
                {t(`growth.att.decision.${d}`)}
              </Button>
            ))}
          </div>
        </Card>
      )}
      {act.isError && <p role="alert" className="text-sm text-danger">{errorText(t, act.error)}</p>}
    </div>
  )
}

function Stat({ label, v }: { label: string; v: number | null }) {
  return (
    <div>
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold tabular-nums">{v ?? '—'}</div>
    </div>
  )
}
