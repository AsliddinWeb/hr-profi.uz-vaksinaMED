import { EDocsTab } from '../hrdocs/EDocsTab'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowRightLeft, CalendarDays, Download, ExternalLink, FileText, KeyRound, Pencil, Plus, Repeat, RotateCcw, Trash2, UserMinus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Info, InfoGrid } from '../../components/ui/Info'
import { Tabs } from '../../components/ui/Tabs'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { Avatar } from './Avatar'
import { formatSize, type Employee, type EmployeeDocument, type EmployeeEvent } from './api'

type Tab = 'overview' | 'history' | 'documents' | 'edocs'

export function EmployeeCardPage() {
  const { id } = useParams()
  const empId = Number(id)
  const { t, i18n } = useTranslation()
  const can = useCan()
  const [params, setParams] = useSearchParams()
  const tab = (params.get('tab') as Tab) || 'overview'
  const lang = i18n.language

  const emp = useQuery({ queryKey: ['employees', 'one', empId], queryFn: () => api<Employee>(`/api/v1/employees/${empId}`), retry: false })
  if (emp.isLoading) return <Skeleton className="mx-auto h-96 max-w-5xl" />
  if (emp.error instanceof ApiError && emp.error.status === 404) return <NotFound />
  const e = emp.data
  if (!e) return null

  const tabs: { key: Tab; show: boolean }[] = [
    { key: 'overview', show: true },
    { key: 'history', show: true },
    { key: 'documents', show: can('employees.documents') },
    { key: 'edocs', show: can('employees.documents') || can('staffdocs.read') || can('staffdocs.manage') },
  ]

  const actions = (
    <>
      {can('employees.transfer') && e.status === 'active' && (
        <Link to={`/employees/${e.id}/transfer`}>
          <Button variant="violet">
            <ArrowRightLeft />
            {t('employees.transfer')}
          </Button>
        </Link>
      )}
      {(can('rotations.manage') || can('rotations.request')) && e.status === 'active' && e.branch && (
        <Link to={`/org/rotations/new?employee=${e.id}`}>
          <Button variant="violet">
            <Repeat />
            {t('employees.rotation')}
          </Button>
        </Link>
      )}
      {can('schedule.read') && e.status === 'active' && (
        <Link to={`/schedule/employee/${e.id}`}>
          <Button variant="teal">
            <CalendarDays />
            {t('employees.schedule')}
          </Button>
        </Link>
      )}
      {can('employees.accounts') && (
        <Link to={`/employees/${e.id}/account`}>
          <Button variant="warning">
            <KeyRound />
            {t('employees.account')}
          </Button>
        </Link>
      )}
      {can('employees.dismiss') &&
        (e.status === 'active' ? (
          <Link to={`/employees/${e.id}/dismiss`}>
            <Button variant="danger">
              <UserMinus />
              {t('employees.dismiss')}
            </Button>
          </Link>
        ) : (
          <Link to={`/employees/${e.id}/reinstate`}>
            <Button variant="success">
              <RotateCcw />
              {t('employees.reinstate')}
            </Button>
          </Link>
        ))}
      {can('employees.update') && (
        <Link to={`/employees/${e.id}/edit`}>
          <Button>
            <Pencil />
            {t('common.edit')}
          </Button>
        </Link>
      )}
    </>
  )

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={e.full_name} backTo="/employees" backLabel={t('employees.title')} actions={actions} />

      <Card className="overflow-hidden">
        <div className="flex items-center gap-5 p-6">
          <Avatar id={e.id} name={e.full_name} hasPhoto={e.has_photo} size={72} />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs text-muted">№{e.employee_no}</span>
              <Badge tone={e.status === 'active' ? 'success' : 'danger'}>{t(`employees.status_${e.status}`)}</Badge>
              {e.user && <Badge tone={e.user.is_active ? 'neutral' : 'warning'}>{e.user.login}</Badge>}
            </div>
            <div className="mt-1.5 text-lg font-medium tracking-tight">{e.position?.name ?? t('employees.noPosition')}</div>
            <div className="text-[13px] text-muted">{[e.department?.name, e.branch ? `${e.branch.number ? `№${e.branch.number} ` : ''}${e.branch.name}` : null].filter(Boolean).join(' · ') || '—'}</div>
          </div>
        </div>
        <InfoGrid cols={4} className="border-t border-border bg-surface-2/50 px-6 py-4">
          <Info label={t('employees.tenure')}>{tenure(e.hire_date, e.dismissal_date, t)}</Info>
          <Info label={t('employees.hireDate')}>{e.hire_date ? formatDate(e.hire_date, lang) : null}</Info>
          <Info label={t('employees.phone')}>{e.phone}</Info>
          <Info label={t('employees.workGroup')}>{e.work_group?.name ?? t('employees.defaultGroup')}</Info>
        </InfoGrid>
      </Card>

      <Tabs
        items={tabs.filter((x) => x.show).map(({ key }) => ({ key, label: t(`employees.tab_${key}`) }))}
        value={tab}
        onChange={(key) => setParams(key === 'overview' ? {} : { tab: key }, { replace: true })}
      />

      {tab === 'overview' && <Overview e={e} lang={lang} />}
      {tab === 'history' && <History empId={e.id} lang={lang} />}
      {tab === 'documents' && can('employees.documents') && <Documents empId={e.id} lang={lang} />}
      {tab === 'edocs' && <EDocsTab empId={e.id} lang={lang} />}
    </div>
  )
}

/** Ish staji matni: "2 yil 3 oy" (ishdan ketgan bo'lsa ketgan sanagacha). */
function tenure(hire: string | null, end: string | null, t: (k: string, o?: Record<string, unknown>) => string): string | null {
  if (!hire) return null
  const a = new Date(hire)
  const b = end ? new Date(end) : new Date()
  let months = (b.getFullYear() - a.getFullYear()) * 12 + (b.getMonth() - a.getMonth())
  if (b.getDate() < a.getDate()) months -= 1
  if (months < 1) return t('employees.tenureNew')
  const y = Math.floor(months / 12)
  const m = months % 12
  return [y ? t('employees.tenureYears', { y }) : '', m ? t('employees.tenureMonths', { m }) : ''].filter(Boolean).join(' ')
}

const Row = Info

function Overview({ e, lang }: { e: Employee; lang: string }) {
  const { t } = useTranslation()
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <Card className="p-6">
        <h2 className="mb-4 text-[13px] text-muted">{t('employees.sectionPersonal')}</h2>
        <InfoGrid cols={2}>
          <Row label={t('employees.gender')}>{e.gender ? t(e.gender === 'm' ? 'employees.male' : 'employees.female') : null}</Row>
          <Row label={t('employees.birthDate')}>{e.sensitive ? formatDate(e.birth_date, lang) : <span className="text-muted">{t('employees.hidden')}</span>}</Row>
          <Row label={t('employees.phone')}>{e.phone}</Row>
          <Row label={t('employees.phone2')}>{e.phone2}</Row>
          <Row label={t('employees.email')}>{e.email}</Row>
          <Row label={t('employees.address')}>{e.sensitive ? e.address : <span className="text-muted">{t('employees.hidden')}</span>}</Row>
          <Row label={t('employees.passport')}>{e.passport_no}</Row>
          <Row label={t('employees.pinfl')}>{e.pinfl}</Row>
        </InfoGrid>
      </Card>
      <Card className="p-6">
        <h2 className="mb-4 text-[13px] text-muted">{t('employees.sectionJob')}</h2>
        <InfoGrid cols={2}>
          <Row label={t('employees.department')}>{e.department?.name}</Row>
          <Row label={t('employees.position')}>{e.position?.name}</Row>
          <Row label={t('employees.branch')}>{e.branch ? `${e.branch.number ? `№${e.branch.number} ` : ''}${e.branch.name}` : null}</Row>
          <Row label={t('employees.workGroup')}>{e.work_group?.name ?? t('employees.defaultGroup')}</Row>
          <Row label={t('employees.hireDate')}>{formatDate(e.hire_date, lang)}</Row>
          {e.status === 'dismissed' && (
            <>
              <Row label={t('employees.dismissalDate')}>{formatDate(e.dismissal_date, lang)}</Row>
              <Row label={t('employees.dismissalReason')}>{e.dismissal_reason ? t(`employees.reasons.${e.dismissal_reason}`) : null}</Row>
              {e.dismissal_note && <Row label={t('employees.note')}>{e.dismissal_note}</Row>}
            </>
          )}
          <Row label={t('employees.account')}>{e.user ? e.user.login : <span className="text-muted">{t('employees.noAccount')}</span>}</Row>
        </InfoGrid>
      </Card>
    </div>
  )
}

function History({ empId, lang }: { empId: number; lang: string }) {
  const { t } = useTranslation()
  const events = useQuery({ queryKey: ['employees', 'events', empId], queryFn: () => api<EmployeeEvent[]>(`/api/v1/employees/${empId}/events`) })
  if (events.isLoading) return <Skeleton className="h-48" />
  return (
    <Card className="p-6">
      <ol className="relative flex flex-col gap-6 border-l border-border pl-6">
        {events.data?.map((ev) => (
          <li key={ev.id} className="relative">
            <span className="absolute -left-[31px] top-1 size-3 rounded-full border-2 border-surface bg-primary" />
            <div className="flex flex-wrap items-baseline gap-x-3">
              <span className="font-semibold">{t(`employees.events.${ev.kind}`, { defaultValue: ev.kind })}</span>
              <span className="text-sm text-muted">{formatDate(ev.effective_date, lang)}</span>
            </div>
            <EventDetails ev={ev} />
            {ev.note && <p className="mt-1 text-sm italic text-muted">«{ev.note}»</p>}
            {ev.actor && <p className="mt-1 text-xs text-muted">{ev.actor} · {formatDateTime(ev.created_at, lang)}</p>}
          </li>
        ))}
        {events.data?.length === 0 && <li className="text-sm text-muted">{t('common.empty')}</li>}
      </ol>
    </Card>
  )
}

type Ref = { name?: string | null; number?: number | null } | null

const refName = (r: Ref | undefined) => (r ? `${r.number ? `№${r.number} ` : ''}${r.name ?? ''}`.trim() : '—')

function EventDetails({ ev }: { ev: EmployeeEvent }) {
  const { t } = useTranslation()
  const d = ev.data as Record<string, unknown> | null
  if (!d) return null
  if (ev.kind === 'transfer') {
    const changes = (d.changes ?? {}) as Record<string, { from: Ref; to: Ref }>
    return (
      <ul className="mt-1 text-sm">
        {Object.entries(changes).map(([k, c]) => (
          <li key={k}>
            <span className="text-muted">{t(`employees.${k}`)}: </span>
            {refName(c.from)} → <b>{refName(c.to)}</b>
          </li>
        ))}
      </ul>
    )
  }
  if (ev.kind === 'hired' || ev.kind === 'reinstated' || ev.kind === 'dismissed') {
    const parts = ['department', 'position', 'branch'].map((k) => d[k] as Ref).filter(Boolean).map(refName)
    return (
      <p className="mt-1 text-sm text-muted">
        {parts.join(' · ')}
        {ev.kind === 'dismissed' && typeof d.reason === 'string' && ` — ${t(`employees.reasons.${d.reason}`)}`}
        {d.source === 'import' && ` (${t('employees.fromImport')})`}
      </p>
    )
  }
  if (ev.kind === 'merged') {
    const merged = (d.merged ?? []) as { name: string; employee_no: number }[]
    return <p className="mt-1 text-sm text-muted">{merged.map((m) => `№${m.employee_no} ${m.name}`).join(', ')}</p>
  }
  return null
}

function Documents({ empId, lang }: { empId: number; lang: string }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const docs = useQuery({ queryKey: ['employees', 'documents', empId], queryFn: () => api<EmployeeDocument[]>(`/api/v1/employees/${empId}/documents`) })
  const remove = useMutation({
    mutationFn: (id: number) => send('DELETE', `/api/v1/employees/${empId}/documents/${id}`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['employees', 'documents', empId] })
      toast.push({ title: t('employees.docDeleted'), tone: 'success' })
    },
  })

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <Link to={`/employees/${empId}/documents/new`}>
          <Button>
            <Plus className="size-4" />
            {t('employees.addDocument')}
          </Button>
        </Link>
      </div>
      {remove.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, remove.error)}
        </p>
      )}
      <Card className="divide-y divide-border">
        {docs.isLoading && <Skeleton className="m-4 h-20" />}
        {docs.data?.map((d) => (
          <div key={d.id} className="flex flex-wrap items-center gap-3 p-4">
            <span className="grid size-10 shrink-0 place-items-center rounded-control bg-surface-2 text-muted">
              <FileText className="size-5" />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium">{d.title}</span>
                <Badge>{t(`employees.docKinds.${d.kind}`)}</Badge>
                {d.expired && <Badge tone="danger">{t('employees.docExpired')}</Badge>}
                {d.expires_soon && !d.expired && <Badge tone="warning">{t('employees.docExpiresSoon')}</Badge>}
              </div>
              <div className="text-xs text-muted">
                {d.filename} · {formatSize(d.size)}
                {d.expires_at ? ` · ${t('employees.expiresAt')}: ${formatDate(d.expires_at, lang)}` : ''}
              </div>
            </div>
            <div className="flex gap-1">
              {d.mime === 'application/pdf' || d.mime.startsWith('image/') ? (
                <a href={`/api/v1/employees/${empId}/documents/${d.id}/download?inline=true`} target="_blank" rel="noopener noreferrer" title={t('employees.open')} aria-label={t('employees.open')}>
                  <Button variant="ghost" className="h-8 px-2">
                    <ExternalLink className="size-4" />
                  </Button>
                </a>
              ) : null}
              <a href={`/api/v1/employees/${empId}/documents/${d.id}/download`} title={t('employees.download')} aria-label={t('employees.download')}>
                <Button variant="ghost" className="h-8 px-2">
                  <Download className="size-4" />
                </Button>
              </a>
              <Link to={`/employees/${empId}/documents/${d.id}/edit`} title={t('common.edit')} aria-label={t('common.edit')}>
                <Button variant="ghost" className="h-8 px-2">
                  <Pencil className="size-4" />
                </Button>
              </Link>
              <Button
                variant="ghost"
                className="h-8 px-2 text-danger"
                aria-label={t('common.delete')}
                onClick={async () => {
                  if (await confirm({ title: t('common.delete'), body: t('org.deleteConfirm', { name: d.title }), danger: true, confirmLabel: t('common.delete') })) remove.mutate(d.id)
                }}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
          </div>
        ))}
        {docs.data?.length === 0 && <p className="p-8 text-center text-sm text-muted">{t('employees.noDocuments')}</p>}
      </Card>
    </div>
  )
}
