import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Check, FileSignature, FileText, Plus, Trash2, Upload, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, send, upload } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { SignaturePad } from '../letters/SignaturePad'

type Upl = { id: number; status: 'pending' | 'approved' | 'returned'; filename: string; note: string | null; employee_id: number } | null
type PosDocs = {
  position: { id: number; name: string }
  documents: { id: number; title: string; version: number; signed: number }[]
  required: { id: number; kind: string; title: string }[]
  employees: { id: number; name: string; has_account: boolean; signed: number[]; uploads: Record<string, Upl> }[]
  library: { id: number; title: string }[]
  kinds: string[]
}
const UTONE = { pending: 'warning', approved: 'success', returned: 'danger' } as const

/** Lavozim panelidagi «Hujjatlar»: imzolanadigan hujjatlar, xodimdan so'raladigan hujjatlar va xodimlar bo'yicha holat. */
export function PositionDocsSection({ positionId }: { positionId: number }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const key = ['org', 'position-docs', positionId]
  const q = useQuery({ queryKey: key, queryFn: () => api<PosDocs>(`/api/v1/position-docs/positions/${positionId}`), retry: false })
  const [lib, setLib] = useState('')
  const [reqDraft, setReqDraft] = useState<{ kind: string; title: string }[] | null>(null)
  const [rejectFor, setRejectFor] = useState<number | null>(null)
  const [note, setNote] = useState('')
  const done = (msg?: string) => {
    void qc.invalidateQueries({ queryKey: key })
    if (msg) toast.push({ title: msg, tone: 'success' })
  }
  const fail = (e: unknown) => toast.push({ title: errorText(t, e), tone: 'danger' })
  const instr = useMutation({ mutationFn: () => send<{ version: number }>('POST', `/api/v1/position-docs/positions/${positionId}/instruction`), onSuccess: (r) => done(t('pdocs.instrDone', { v: r.version })), onError: fail })
  const link = useMutation({ mutationFn: (id: number) => send('POST', `/api/v1/position-docs/positions/${positionId}/documents`, { document_id: id }), onSuccess: () => (setLib(''), done()), onError: fail })
  const unlink = useMutation({ mutationFn: (id: number) => send('DELETE', `/api/v1/position-docs/positions/${positionId}/documents/${id}`), onSuccess: () => done(), onError: fail })
  const saveReq = useMutation({ mutationFn: (items: { kind: string; title: string }[]) => send('PUT', `/api/v1/position-docs/positions/${positionId}/required`, { items }), onSuccess: () => (setReqDraft(null), done(t('common.saved'))), onError: fail })
  const review = useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'approve' | 'return' }) => send('POST', `/api/v1/position-docs/uploads/${id}/review`, { action, note: note || null }),
    onSuccess: () => (setRejectFor(null), setNote(''), done()),
    onError: fail,
  })
  if (q.isError) return null
  const d = q.data
  if (!d) return <Skeleton className="h-40" />
  const req = reqDraft ?? d.required.map((r) => ({ kind: r.kind, title: r.title }))
  return (
    <div className="flex flex-col gap-4">
      <Card className="flex flex-col gap-3 p-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="font-medium">{t('pdocs.signDocs')}</div>
          <Button variant="outline" className="h-8" disabled={instr.isPending} onClick={() => instr.mutate()}>
            <FileText className="size-4" />
            {t('pdocs.makeInstr')}
          </Button>
        </div>
        <div className="text-xs text-muted">{t('pdocs.signHint')}</div>
        {d.documents.length === 0 && <div className="text-sm text-muted">{t('pdocs.noDocs')}</div>}
        {d.documents.map((x) => (
          <div key={x.id} className="flex items-center gap-2 rounded-lg bg-surface-2 px-3 py-2 text-sm">
            <FileSignature className="size-4 text-primary" />
            <span className="min-w-0 flex-1 truncate">
              {x.title} <span className="text-xs text-muted">v{x.version}</span>
            </span>
            <Badge tone={x.signed >= d.employees.length && d.employees.length ? 'success' : 'warning'}>{t('pdocs.signedN', { n: x.signed, total: d.employees.length })}</Badge>
            <button type="button" aria-label={t('common.delete')} onClick={() => unlink.mutate(x.id)} className="text-muted hover:text-danger">
              <X className="size-4" />
            </button>
          </div>
        ))}
        <div className="flex gap-2">
          <Select className="flex-1" value={lib} onChange={(e) => setLib(e.target.value)} aria-label={t('pdocs.fromLibrary')}>
            <option value="">{t('pdocs.fromLibrary')}</option>
            {d.library.filter((l) => !d.documents.some((x) => x.id === l.id)).map((l) => (
              <option key={l.id} value={l.id}>
                {l.title}
              </option>
            ))}
          </Select>
          <Button variant="outline" disabled={!lib || link.isPending} onClick={() => link.mutate(Number(lib))}>
            <Plus className="size-4" />
            {t('pdocs.attach')}
          </Button>
        </div>
      </Card>

      <Card className="flex flex-col gap-3 p-5">
        <div className="font-medium">{t('pdocs.requiredTitle')}</div>
        <div className="text-xs text-muted">{t('pdocs.requiredHint')}</div>
        {req.map((r, i) => (
          <div key={i} className="grid grid-cols-[150px_1fr_auto] gap-2">
            <Select value={r.kind} onChange={(e) => setReqDraft(req.map((x, j) => (j === i ? { ...x, kind: e.target.value } : x)))} aria-label={t('pdocs.kind')}>
              {d.kinds.map((k) => (
                <option key={k} value={k}>
                  {t(`pdocs.kinds.${k}`)}
                </option>
              ))}
            </Select>
            <Input value={r.title} onChange={(e) => setReqDraft(req.map((x, j) => (j === i ? { ...x, title: e.target.value } : x)))} aria-label={t('pdocs.docTitle')} />
            <Button variant="ghost" className="px-2" aria-label={t('common.delete')} onClick={() => setReqDraft(req.filter((_, j) => j !== i))}>
              <Trash2 className="size-4" />
            </Button>
          </div>
        ))}
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" className="h-8" onClick={() => setReqDraft([...req, { kind: 'passport', title: t('pdocs.kinds.passport') }])}>
            <Plus className="size-4" />
            {t('pdocs.addRequired')}
          </Button>
          {req.length === 0 && (
            <Button variant="outline" className="h-8" onClick={() => setReqDraft(['photo', 'passport', 'diploma', 'medical'].map((k) => ({ kind: k, title: t(`pdocs.kinds.${k}`) })))}>
              {t('pdocs.standardSet')}
            </Button>
          )}
          {reqDraft && (
            <Button className="h-8" disabled={saveReq.isPending} onClick={() => saveReq.mutate(req)}>
              {t('common.save')}
            </Button>
          )}
        </div>
      </Card>

      <Card className="overflow-hidden">
        <div className="border-b border-border px-4 py-3 font-medium">{t('pdocs.statusTitle')}</div>
        {d.employees.length === 0 ? (
          <div className="p-5 text-sm text-muted">{t('pdocs.noEmployees')}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-xs text-muted">
                <tr>
                  <th className="px-4 py-2 font-medium">{t('pdocs.employee')}</th>
                  <th className="px-2 py-2 font-medium">{t('pdocs.signed')}</th>
                  {d.required.map((r) => (
                    <th key={r.id} className="px-2 py-2 font-medium">
                      {r.title}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {d.employees.map((e) => (
                  <tr key={e.id}>
                    <td className="px-4 py-2">
                      {e.name}
                      {!e.has_account && <div className="text-[11px] text-warning">{t('pdocs.noAccount')}</div>}
                    </td>
                    <td className="px-2 py-2 tabular-nums">
                      {e.signed.length}/{d.documents.length}
                    </td>
                    {d.required.map((r) => {
                      const u = e.uploads[r.kind]
                      return (
                        <td key={r.id} className="px-2 py-2">
                          {!u ? (
                            <span className="text-xs text-muted">—</span>
                          ) : (
                            <div className="flex flex-col items-start gap-1">
                              <a href={`/api/v1/employees/${u.employee_id}/documents/${u.id}/download?inline=true`} target="_blank" rel="noreferrer">
                                <Badge tone={UTONE[u.status]}>{t(`pdocs.ust.${u.status}`)}</Badge>
                              </a>
                              {u.status === 'pending' &&
                                (rejectFor === u.id ? (
                                  <span className="flex gap-1">
                                    <Input className="h-7 w-32" value={note} onChange={(ev) => setNote(ev.target.value)} placeholder={t('comp.dec.reason')} aria-label={t('comp.dec.reason')} />
                                    <Button className="h-7 bg-danger px-2" disabled={!note.trim()} onClick={() => review.mutate({ id: u.id, action: 'return' })}>
                                      {t('pdocs.return')}
                                    </Button>
                                  </span>
                                ) : (
                                  <span className="flex gap-1">
                                    <Button className="h-7 px-2" onClick={() => review.mutate({ id: u.id, action: 'approve' })}>
                                      <Check className="size-3.5" />
                                    </Button>
                                    <Button variant="outline" className="h-7 px-2 text-danger" onClick={() => setRejectFor(u.id)}>
                                      <X className="size-3.5" />
                                    </Button>
                                  </span>
                                ))}
                            </div>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  )
}

type MyDocs = {
  position: { id: number; name: string } | null
  documents: { id: number; title: string; version: number; body: string | null; signed_at: string | null }[]
  required: { id: number; kind: string; title: string; upload: Upl }[]
  todo: number
}

/** /my-documents — xodimning o'z paneli: lavozim hujjatlarini o'qib onlayn imzolash va kerakli shaxsiy hujjatlarni yuklash (telefonda kamera bilan). */
export function MyDocumentsPage() {
  const { t, i18n } = useTranslation()
  const qc = useQueryClient()
  const toast = useToast()
  const q = useQuery({ queryKey: ['position-docs', 'my'], queryFn: () => api<MyDocs>('/api/v1/position-docs/my') })
  const [openDoc, setOpenDoc] = useState<number | null>(null)
  const [signing, setSigning] = useState<number | null>(null)
  const refresh = () => void qc.invalidateQueries({ queryKey: ['position-docs'] })
  const sign = useMutation({
    mutationFn: ({ id, png }: { id: number; png: string }) => send('POST', `/api/v1/position-docs/my/sign/${id}`, { signature: png }),
    onSuccess: () => (setSigning(null), refresh(), toast.push({ title: t('pdocs.signedOk'), tone: 'success' })),
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const up = useMutation({
    mutationFn: ({ kind, title, file }: { kind: string; title: string; file: File }) => {
      const fd = new FormData()
      fd.append('kind', kind)
      fd.append('title', title)
      fd.append('file', file)
      return upload('POST', '/api/v1/position-docs/my/upload', fd)
    },
    onSuccess: () => (refresh(), toast.push({ title: t('pdocs.uploadedOk'), tone: 'success' })),
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const d = q.data
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('pdocs.myTitle')} subtitle={d?.position ? t('pdocs.mySubtitle', { position: d.position.name }) : t('pdocs.mySubtitleNone')} />
      {!d ? (
        <Skeleton className="h-60" />
      ) : !d.position ? (
        <Card>
          <EmptyState icon={FileText} title={t('pdocs.noPosition')} />
        </Card>
      ) : (
        <>
          {d.todo > 0 && <Card className="border-warning/50 bg-warning/5 p-4 text-sm">{t('pdocs.todo', { n: d.todo })}</Card>}
          <Card className="flex flex-col gap-3 p-5">
            <div className="font-medium">{t('pdocs.toSign')}</div>
            {d.documents.length === 0 && <div className="text-sm text-muted">{t('pdocs.noDocs')}</div>}
            {d.documents.map((x) => (
              <div key={x.id} className="flex flex-col gap-2 rounded-lg border border-border p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <FileSignature className="size-4 text-primary" />
                  <span className="flex-1 font-medium">{x.title}</span>
                  {x.signed_at ? <Badge tone="success">{t('pdocs.signedAt', { at: formatDateTime(x.signed_at, i18n.language) })}</Badge> : <Badge tone="warning">{t('pdocs.needSign')}</Badge>}
                  <Button variant="outline" className="h-8" onClick={() => setOpenDoc(openDoc === x.id ? null : x.id)}>
                    {t(openDoc === x.id ? 'pdocs.hide' : 'pdocs.read')}
                  </Button>
                </div>
                {openDoc === x.id && x.body && <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-lg bg-surface-2 p-3 font-sans text-sm">{x.body}</pre>}
                {!x.signed_at &&
                  (signing === x.id ? (
                    <SignaturePad busy={sign.isPending} onCancel={() => setSigning(null)} onSave={(png) => sign.mutate({ id: x.id, png })} />
                  ) : (
                    <Button className="w-fit" onClick={() => (setOpenDoc(x.id), setSigning(x.id))}>
                      <FileSignature className="size-4" />
                      {t('pdocs.signNow')}
                    </Button>
                  ))}
              </div>
            ))}
          </Card>
          <Card className="flex flex-col gap-3 p-5">
            <div className="font-medium">{t('pdocs.toUpload')}</div>
            <div className="text-xs text-muted">{t('pdocs.uploadHint')}</div>
            {d.required.length === 0 && <div className="text-sm text-muted">{t('pdocs.noRequired')}</div>}
            {d.required.map((r) => (
              <div key={r.id} className="flex flex-wrap items-center gap-2 rounded-lg border border-border p-3 text-sm">
                <span className="flex-1 font-medium">{r.title}</span>
                {r.upload ? <Badge tone={UTONE[r.upload.status]}>{t(`pdocs.ust.${r.upload.status}`)}</Badge> : <Badge tone="warning">{t('pdocs.notUploaded')}</Badge>}
                {r.upload?.status === 'returned' && r.upload.note && <span className="w-full text-xs text-danger">{r.upload.note}</span>}
                {(!r.upload || r.upload.status === 'returned') && (
                  <>
                    <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-control bg-primary px-3 text-primary-fg">
                      <Camera className="size-4" />
                      {t('pdocs.camera')}
                      <input type="file" accept="image/*" capture="environment" className="hidden" onChange={(e) => (e.target.files?.[0] && up.mutate({ kind: r.kind, title: r.title, file: e.target.files[0] }), (e.target.value = ''))} />
                    </label>
                    <label className="inline-flex h-8 cursor-pointer items-center gap-1.5 rounded-control border border-border px-3">
                      <Upload className="size-4" />
                      {t('pdocs.file')}
                      <input type="file" accept="image/*,application/pdf" className="hidden" onChange={(e) => (e.target.files?.[0] && up.mutate({ kind: r.kind, title: r.title, file: e.target.files[0] }), (e.target.value = ''))} />
                    </label>
                  </>
                )}
              </div>
            ))}
          </Card>
        </>
      )}
    </div>
  )
}
