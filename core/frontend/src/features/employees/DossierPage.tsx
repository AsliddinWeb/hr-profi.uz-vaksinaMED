import { useQuery } from '@tanstack/react-query'
import { Briefcase, Download, FileSignature, FileText, MessagesSquare, Wallet } from 'lucide-react'
import type { ComponentType, ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { money } from '../recruit/api'

interface Dossier {
  employee: { id: number; employee_no: number; full_name: string; phone: string | null; status: string; hire_date: string | null; dismissal_date: string | null; position: string | null; department: string | null; branch: string | null }
  tenure: { years: number; months: number; total_days: number } | null
  recruitment: {
    application_id: number
    candidate_id: number
    applied_at: string
    hired_at: string | null
    vacancy: { id: number; title: string } | null
    source: string | null
    link: { label: string | null; channel: string; code: string } | null
    request: { id: number; number: string } | null
    recruiter: string | null
    interview: { at: string | null; rating: number | null; hard_skill: number | null; soft_skill: number | null; notes: string | null; match_score: number | null; ai: string | null; scorecards: { interviewer: string | null; scores: Record<string, number>; notes: string | null }[] }
    tests: { score: number | null; status: string; submitted_at: string | null }[]
    anketa: Record<string, unknown>
    resume_text: string | null
    files: { id: number; name: string; size: number }[]
  } | null
  documents: { id: number; kind: string; title: string; filename: string; issued_at: string | null; expires_at: string | null }[]
  orders: { id: number; kind: string; subtype: string; number: string | null; title: string; status: string; start_date: string | null; signed_at: string | null; created_at: string }[]
  payroll: { period: string; status: string; paid_days: number; plan_days: number; gross: number; bonus: number; penalties: number; net: number; to_pay: number }[]
  can: { documents: boolean; payroll: boolean }
}

const SKIP = new Set(['full_name', 'phone'])

/** /employees/:id/dossier: xodimning shaxsiy ishi — ishga qabuldan bugungacha barcha hujjat va natijalar bitta joyda. */
export function DossierPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const q = useQuery({ queryKey: ['employees', id, 'dossier'], queryFn: () => api<Dossier>(`/api/v1/employees/${id}/dossier`) })
  const d = q.data
  if (!d) return <Skeleton className="mx-auto h-96 max-w-5xl" />
  const e = d.employee
  const r = d.recruitment
  const lang = i18n.language
  const maxPay = Math.max(1, ...d.payroll.map((p) => p.to_pay || p.net))
  const contracts = d.documents.filter((x) => x.kind === 'contract')
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('dossier.title', { name: e.full_name })} subtitle={[e.position, e.department, e.branch].filter(Boolean).join(' · ')} backTo={`/employees/${e.id}`} backLabel={e.full_name} />

      <div className="grid gap-3 sm:grid-cols-4">
        <Kpi label={t('dossier.tenure')} value={d.tenure ? t('dossier.tenureVal', { y: d.tenure.years, m: d.tenure.months }) : '—'} hint={d.tenure ? t('dossier.days', { n: d.tenure.total_days }) : undefined} />
        <Kpi label={t('dossier.hired')} value={e.hire_date ? formatDate(e.hire_date, lang) : '—'} hint={e.status === 'dismissed' && e.dismissal_date ? t('dossier.dismissed', { d: formatDate(e.dismissal_date, lang) }) : undefined} />
        <Kpi label={t('dossier.source')} value={r ? (r.link?.label || r.link?.channel || (r.source ? t(`recruit.source.${r.source}`, { defaultValue: r.source }) : '—')) : t('dossier.noRecruit')} hint={r?.vacancy?.title} />
        <Kpi label={t('dossier.interview')} value={r?.interview.rating ? `${r.interview.rating}/5` : r?.interview.match_score ? `${r.interview.match_score}%` : '—'} hint={r?.interview.at ? formatDateTime(r.interview.at, lang) : undefined} />
      </div>

      <Section icon={Briefcase} title={t('dossier.recruitment')}>
        {!r ? (
          <p className="text-sm text-muted">{t('dossier.noRecruitHint')}</p>
        ) : (
          <dl className="grid gap-3 text-sm sm:grid-cols-3">
            <Item k={t('dossier.vacancy')} v={r.vacancy ? <Link className="text-primary hover:underline" to={`/recruit/vacancies/${r.vacancy.id}`}>{r.vacancy.title}</Link> : '—'} />
            <Item k={t('dossier.request')} v={r.request ? <Link className="text-primary hover:underline" to={`/recruit/requests/${r.request.id}`}>{r.request.number}</Link> : '—'} />
            <Item k={t('dossier.ad')} v={r.link ? `${r.link.label ?? r.link.code} (${r.link.channel})` : r.source ? t(`recruit.source.${r.source}`, { defaultValue: r.source }) : '—'} />
            <Item k={t('dossier.applied')} v={formatDateTime(r.applied_at, lang)} />
            <Item k={t('dossier.hiredAt')} v={r.hired_at ? formatDateTime(r.hired_at, lang) : '—'} />
            <Item k={t('dossier.recruiter')} v={r.recruiter ?? '—'} />
          </dl>
        )}
      </Section>

      {r && (
        <Section icon={MessagesSquare} title={t('dossier.interviewTitle')}>
          <div className="flex flex-wrap gap-2">
            {r.interview.match_score != null && <Badge tone="info">{t('dossier.match', { n: r.interview.match_score })}</Badge>}
            {r.interview.hard_skill != null && <Badge>Hard: {r.interview.hard_skill}</Badge>}
            {r.interview.soft_skill != null && <Badge>Soft: {r.interview.soft_skill}</Badge>}
            {r.tests.map((x, i) => (
              <Badge key={i} tone={x.score != null && x.score >= 60 ? 'success' : 'warning'}>
                {t('dossier.test')}: {x.score != null ? `${x.score}%` : x.status}
              </Badge>
            ))}
          </div>
          {r.interview.notes && <p className="whitespace-pre-wrap text-sm">{r.interview.notes}</p>}
          {r.interview.ai && <p className="rounded-control bg-surface-2 p-3 text-sm">{r.interview.ai}</p>}
          {r.interview.scorecards.map((s, i) => (
            <div key={i} className="rounded-control border border-border p-3 text-sm">
              <div className="font-medium">{s.interviewer ?? '—'}</div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {Object.entries(s.scores).map(([k, v]) => (
                  <Badge key={k}>
                    {k}: {v}
                  </Badge>
                ))}
              </div>
              {s.notes && <p className="mt-1 text-muted">{s.notes}</p>}
            </div>
          ))}
          {!r.interview.notes && !r.interview.scorecards.length && r.interview.hard_skill == null && <p className="text-sm text-muted">{t('dossier.noInterview')}</p>}
        </Section>
      )}

      {r && (
        <Section icon={FileText} title={t('dossier.resume')} action={<Link className="text-xs font-semibold text-primary hover:underline" to={`/recruit/candidates/${r.candidate_id}`}>{t('dossier.openCandidate')}</Link>}>
          <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-3">
            {Object.entries(r.anketa)
              .filter(([k]) => !SKIP.has(k))
              .map(([k, v]) => (
                <Item key={k} k={t(`recruitCore.profile.fields.${k}`, { defaultValue: k })} v={Array.isArray(v) ? v.join(', ') : String(v)} />
              ))}
          </dl>
          {r.files.length > 0 && (
            <ul className="flex flex-wrap gap-2 text-sm">
              {r.files.map((f) => (
                <li key={f.id} className="rounded-full bg-surface-2 px-3 py-1">
                  📎 {f.name}
                </li>
              ))}
            </ul>
          )}
          {r.resume_text && <p className="line-clamp-6 whitespace-pre-wrap text-xs text-muted">{r.resume_text}</p>}
        </Section>
      )}

      <Section icon={FileSignature} title={t('dossier.contractOrders')}>
        {d.can.documents && (
          <div className="flex flex-col gap-1.5">
            <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">{t('dossier.contract')}</h4>
            {contracts.length === 0 && <p className="text-sm text-warning">{t('dossier.noContract')}</p>}
            {d.documents.map((x) => (
              <a key={x.id} href={`/api/v1/employees/${e.id}/documents/${x.id}/download`} className="flex items-center gap-2 rounded-control px-2 py-1.5 text-sm hover:bg-surface-2">
                <Download className="size-4 text-muted" />
                <span className="font-medium">{x.title}</span>
                <Badge>{t(`dossier.kind.${x.kind}`, { defaultValue: x.kind })}</Badge>
                {x.issued_at && <span className="ml-auto text-xs text-muted">{formatDate(x.issued_at, lang)}</span>}
              </a>
            ))}
          </div>
        )}
        <div className="flex flex-col gap-1.5">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-muted">{t('dossier.orders')}</h4>
          {d.orders.length === 0 && <p className="text-sm text-muted">{t('dossier.noOrders')}</p>}
          {d.orders.map((o) => (
            <div key={o.id} className="flex flex-wrap items-center gap-2 rounded-control px-2 py-1.5 text-sm">
              <span className="font-mono text-xs text-muted">{o.number ?? '—'}</span>
              <span className="font-medium">{o.title}</span>
              <Badge tone={o.kind === 'order' ? 'violet' : 'neutral'}>{t(`dossier.okind.${o.kind}`, { defaultValue: o.kind })}</Badge>
              <Badge tone={o.signed_at ? 'success' : 'warning'}>{o.status}</Badge>
              <span className="ml-auto text-xs text-muted">{formatDate(o.start_date ?? o.created_at, lang)}</span>
            </div>
          ))}
        </div>
      </Section>

      {d.can.payroll && (
        <Section icon={Wallet} title={t('dossier.payroll')}>
          {d.payroll.length === 0 ? (
            <p className="text-sm text-muted">{t('dossier.noPayroll')}</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs text-muted">
                  <tr>
                    <th className="py-1.5 text-left font-medium">{t('dossier.period')}</th>
                    <th className="py-1.5 text-right font-medium">{t('dossier.daysCol')}</th>
                    <th className="py-1.5 text-right font-medium">{t('dossier.gross')}</th>
                    <th className="py-1.5 text-right font-medium">{t('dossier.bonus')}</th>
                    <th className="py-1.5 text-right font-medium">{t('dossier.penalties')}</th>
                    <th className="py-1.5 text-right font-medium">{t('dossier.toPay')}</th>
                    <th className="hidden w-40 py-1.5 sm:table-cell" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {d.payroll.map((p) => (
                    <tr key={p.period}>
                      <td className="py-1.5">{p.period}</td>
                      <td className="py-1.5 text-right">
                        {p.paid_days}/{p.plan_days}
                      </td>
                      <td className="py-1.5 text-right">{money(p.gross)}</td>
                      <td className="py-1.5 text-right text-emerald-600">{p.bonus ? `+${money(p.bonus)}` : '—'}</td>
                      <td className="py-1.5 text-right text-rose-600">{p.penalties ? `−${money(p.penalties)}` : '—'}</td>
                      <td className="py-1.5 text-right font-semibold">{money(p.to_pay || p.net)}</td>
                      <td className="hidden py-1.5 pl-3 sm:table-cell">
                        <div className="h-2 rounded-full bg-surface-2">
                          <div className="h-full rounded-full bg-primary" style={{ width: `${((p.to_pay || p.net) / maxPay) * 100}%` }} />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
      )}
    </div>
  )
}

function Kpi({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card className="flex flex-col gap-0.5 p-4">
      <span className="text-xs text-muted">{label}</span>
      <span className="truncate text-lg font-bold">{value}</span>
      {hint && <span className="truncate text-xs text-muted">{hint}</span>}
    </Card>
  )
}

function Section({ icon: Icon, title, action, children }: { icon: ComponentType<{ className?: string }>; title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex items-center gap-2">
        <Icon className="size-4 text-primary" />
        <h3 className="font-semibold">{title}</h3>
        <span className="ml-auto">{action}</span>
      </div>
      {children}
    </Card>
  )
}

function Item({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-muted">{k}</dt>
      <dd className="truncate font-medium">{v}</dd>
    </div>
  )
}
