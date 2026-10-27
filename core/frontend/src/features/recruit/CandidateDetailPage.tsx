import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, Paperclip, Pencil, Trash2, UserPlus } from 'lucide-react'
import { useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { AiSummary } from '../ai/AiSummary'
import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, ApiError, send, upload } from '../../lib/api'
import { formatDate, formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { sizeText } from '../tasks/api'
import { STAGE_TONE, type CandidateDetail } from './api'

/** /recruit/candidates/:id: nomzod kartasi, rezyume fayllari va arizalari. */
export function CandidateDetailPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const confirm = useConfirm()
  const manage = useCan()('recruit.manage')
  const input = useRef<HTMLInputElement>(null)
  const q = useQuery({ queryKey: ['recruit', 'candidate', id], queryFn: () => api<CandidateDetail>(`/api/v1/recruit/candidates/${id}`), retry: false })
  const refresh = () => void qc.invalidateQueries({ queryKey: ['recruit'] })
  const up = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return upload('POST', `/api/v1/recruit/candidates/${id}/files`, form)
    },
    onSuccess: refresh,
  })
  const del = useMutation({ mutationFn: (fid: number) => send('DELETE', `/api/v1/recruit/candidates/${id}/files/${fid}`), onSuccess: refresh })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const c = q.data
  if (!c) return <Skeleton className="mx-auto h-96 max-w-4xl" />

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={c.full_name}
        subtitle={[c.phone, c.email].filter(Boolean).join(' · ')}
        backTo="/recruit/candidates"
        backLabel={t('recruit.tabs.candidates')}
        actions={
          manage && (
            <>
              <Link to={`/recruit/applications/new?candidate_id=${c.id}`}>
                <Button>
                  <UserPlus className="size-4" />
                  {t('recruit.application.add')}
                </Button>
              </Link>
              <Link to={`/recruit/candidates/${c.id}/edit`}>
                <Button variant="outline">
                  <Pencil className="size-4" />
                  {t('common.edit')}
                </Button>
              </Link>
            </>
          )
        }
      />
      <AiSummary entity="candidate" id={c.id} />
      <Card className="flex flex-col gap-4 p-6">
        <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <Info label={t('recruit.candidate.birth')}>{c.birth_date ? formatDate(c.birth_date, i18n.language) : '—'}</Info>
          <Info label={t('recruit.candidate.source')}>{c.source ? t(`recruit.source.${c.source}`) : '—'}</Info>
          <Info label={t('recruit.candidate.address')}>{c.address ?? '—'}</Info>
        </dl>
        {c.skills.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {c.skills.map((s) => (
              <Badge key={s}>{s}</Badge>
            ))}
          </div>
        )}
        {c.note && <p className="whitespace-pre-wrap border-t border-border pt-4 text-sm">{c.note}</p>}
        {c.resume_text && (
          <details className="border-t border-border pt-4 text-sm">
            <summary className="cursor-pointer text-muted">{t('recruit.candidate.resumeText')}</summary>
            <p className="mt-2 whitespace-pre-wrap">{c.resume_text}</p>
          </details>
        )}
      </Card>

      <Card className="p-6">
        <h2 className="font-semibold">{t('recruit.tabs.applications')}</h2>
        <ul className="mt-3 divide-y divide-border text-sm">
          {c.applications.map((a) => (
            <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <Link to={`/recruit/applications/${a.id}`} className="font-medium hover:text-primary hover:underline">
                {a.vacancy.title}
              </Link>
              <span className="flex items-center gap-3">
                <span className="text-xs text-muted tabular-nums">{formatDateTime(a.applied_at, i18n.language)}</span>
                <Badge tone={STAGE_TONE[a.stage]}>{t(`recruit.stage.${a.stage}`)}</Badge>
              </span>
            </li>
          ))}
          {c.applications.length === 0 && <li className="py-4 text-center text-muted">{t('common.empty')}</li>}
        </ul>
      </Card>

      <Card className="flex flex-col gap-4 p-6">
        <div className="flex items-center justify-between gap-3">
          <h2 className="font-semibold">{t('recruit.candidate.files')}</h2>
          {manage && (
            <>
              <input ref={input} type="file" className="sr-only" aria-label={t('tasks.attach')} onChange={(e) => (e.target.files?.[0] && up.mutate(e.target.files[0]), (e.target.value = ''))} />
              <Button variant="outline" disabled={up.isPending} onClick={() => input.current?.click()}>
                <Paperclip className="size-4" />
                {t('tasks.attach')}
              </Button>
            </>
          )}
        </div>
        {(up.isError || del.isError) && (
          <p role="alert" className="text-sm text-danger">
            {errorText(t, up.error ?? del.error)}
          </p>
        )}
        <ul className="divide-y divide-border text-sm">
          {c.files.map((f) => (
            <li key={f.id} className="flex items-center justify-between gap-2 py-2.5">
              <span className="min-w-0">
                <span className="block truncate font-medium">{f.filename}</span>
                <span className="text-xs text-muted">{sizeText(f.size)} · {formatDateTime(f.created_at, i18n.language)}</span>
              </span>
              <span className="flex gap-1">
                <a href={`/api/v1/recruit/candidates/${id}/files/${f.id}`} download aria-label={t('tasks.download')}>
                  <Button variant="ghost" className="h-8 px-2">
                    <Download className="size-4" />
                  </Button>
                </a>
                {manage && (
                  <Button
                    variant="ghost"
                    className="h-8 px-2 text-danger"
                    aria-label={t('common.delete')}
                    onClick={async () => {
                      if (await confirm({ title: t('tasks.deleteFile'), body: f.filename, danger: true, confirmLabel: t('common.delete') })) del.mutate(f.id)
                    }}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                )}
              </span>
            </li>
          ))}
          {c.files.length === 0 && <li className="py-4 text-center text-muted">{t('common.empty')}</li>}
        </ul>
      </Card>
    </div>
  )
}

function Info({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-1">{children}</dd>
    </div>
  )
}
