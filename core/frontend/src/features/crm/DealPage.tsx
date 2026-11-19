import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Archive, Phone, RotateCcw, Save, ThumbsDown, Trophy } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatDateTime } from '../../lib/format'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { shortMoney, type Deal } from './api'
import { Chatter } from './Chatter'
import { DealFields } from './DealFields'
import { emptyDraft, toInput, type DealDraft } from './draft'

function draftOf(d: Deal): DealDraft {
  return {
    title: d.title, company: d.company, contact_name: d.contact_name, phone: d.phone, email: d.email, amount: String(d.amount || ''),
    probability: String(d.probability), priority: d.priority, tags: d.tags.join(', '), source: d.source, description: d.description,
    expected_close: d.expected_close, stage_id: d.stage_id, owner_id: d.owner?.id ?? null, owner: d.owner ? [d.owner] : [],
  } // prettier-ignore
}

/** /crm/deals/:id: chapda bitim (bosqichlar paneli, maydonlar), o'ngda «Muhokama» paneli. */
export function CrmDealPage() {
  const { t, i18n } = useTranslation()
  const id = Number(useParams().id)
  const qc = useQueryClient()
  const navigate = useNavigate()
  const toast = useToast()
  const confirm = useConfirm()
  const q = useQuery({ queryKey: ['crm', 'deal', id], queryFn: () => api<Deal>(`/api/v1/crm/deals/${id}`), retry: false })
  const [draft, setDraft] = useState<DealDraft | null>(null)
  const [seen, setSeen] = useState<string | null>(null)
  const [lostOpen, setLostOpen] = useState(false)
  const [reason, setReason] = useState('')
  const deal = q.data
  if (deal && deal.updated_at !== seen) {
    setSeen(deal.updated_at)
    setDraft(draftOf(deal))
  }
  const refresh = () => void qc.invalidateQueries({ queryKey: ['crm'] })
  const save = useMutation({ mutationFn: (d: DealDraft) => send('PUT', `/api/v1/crm/deals/${id}`, toInput(d)), onSuccess: () => (refresh(), toast.push({ title: t('common.saved'), tone: 'success' })) })
  const move = useMutation({ mutationFn: (stage: number) => send('POST', `/api/v1/crm/deals/${id}/move`, { stage_id: stage }), onSuccess: refresh })
  const won = useMutation({ mutationFn: () => send('POST', `/api/v1/crm/deals/${id}/won`), onSuccess: () => (refresh(), toast.push({ title: t('crm.wonToast'), tone: 'success' })) })
  const lost = useMutation({ mutationFn: () => send('POST', `/api/v1/crm/deals/${id}/lost`, { reason }), onSuccess: () => (setLostOpen(false), setReason(''), refresh()) })
  const reopen = useMutation({ mutationFn: () => send('POST', `/api/v1/crm/deals/${id}/reopen`), onSuccess: refresh })
  const archive = useMutation({ mutationFn: () => send('DELETE', `/api/v1/crm/deals/${id}`), onSuccess: () => (refresh(), navigate('/crm')) })

  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  if (!deal || !draft) return <Skeleton className="mx-auto h-96 max-w-6xl" />
  const dirty = JSON.stringify(toInput(draft)) !== JSON.stringify(toInput(draftOf(deal)))
  const err = save.error ?? move.error ?? won.error ?? lost.error ?? reopen.error ?? archive.error
  const submit = (e: FormEvent) => (e.preventDefault(), save.mutate(draft))

  return (
    <div className="mx-auto grid max-w-[1500px] gap-5 lg:grid-cols-[minmax(0,1fr)_400px]">
      <div className="flex min-w-0 flex-col gap-4">
        <PageHeader
          title={deal.title}
          subtitle={`${deal.company ?? ''}${deal.company ? ' · ' : ''}${t('crm.createdBy', { name: deal.created_by ?? '—', at: formatDateTime(deal.created_at, i18n.language) })}`}
          backTo="/crm"
          backLabel={t('crm.title')}
          actions={
            deal.can_edit && (
              <>
                {deal.lost ? (
                  <Button variant="outline" onClick={() => reopen.mutate()} disabled={reopen.isPending}>
                    <RotateCcw className="size-4" />
                    {t('crm.reopen')}
                  </Button>
                ) : (
                  <>
                    {!deal.won && (
                      <Button variant="success" onClick={() => won.mutate()} disabled={won.isPending}>
                        <Trophy className="size-4" />
                        {t('crm.markWon')}
                      </Button>
                    )}
                    <Button variant="danger" onClick={() => setLostOpen((v) => !v)}>
                      <ThumbsDown className="size-4" />
                      {t('crm.markLost')}
                    </Button>
                  </>
                )}
                <Button
                  variant="ghost"
                  aria-label={t('crm.archive')}
                  onClick={async () => {
                    if (await confirm({ title: t('crm.archive'), body: deal.title, danger: true, confirmLabel: t('crm.archive') })) archive.mutate()
                  }}
                >
                  <Archive className="size-4" />
                </Button>
              </>
            )
          }
        />

        {lostOpen && (
          <Card className="flex flex-wrap items-center gap-2 p-4">
            <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder={t('crm.lostReasonPh')} aria-label={t('crm.lostReason')} maxLength={300} className="min-w-60 flex-1" autoFocus />
            <Button variant="danger" disabled={reason.trim().length < 2 || lost.isPending} onClick={() => lost.mutate()}>
              {t('crm.markLost')}
            </Button>
          </Card>
        )}

        {/* Bosqichlar paneli: bosilgan bosqichga o'tadi (ehtimollik va keyingi faoliyat avtomatik) */}
        <Card className="flex flex-col gap-3 p-4">
          <div className="flex flex-wrap items-center gap-2">
            {deal.won && <Badge tone="success">{t('crm.won')}</Badge>}
            {deal.lost && <Badge tone="danger">{t('crm.lost')}{deal.lost_reason ? `: ${deal.lost_reason}` : ''}</Badge>}
            <span className="ml-auto text-sm font-semibold tabular-nums">
              {shortMoney(deal.amount, i18n.language)} UZS · {deal.probability}%
            </span>
          </div>
          <ol className="flex overflow-x-auto rounded-control bg-surface-2 p-1" aria-label={t('crm.field.stage')}>
            {deal.stages.map((s, i) => {
              const cur = s.id === deal.stage_id
              const passed = deal.stages.findIndex((x) => x.id === deal.stage_id) > i
              return (
                <li key={s.id} className="flex-1">
                  <button
                    type="button"
                    disabled={!deal.can_edit || deal.lost || cur || move.isPending}
                    onClick={() => move.mutate(s.id)}
                    aria-current={cur ? 'step' : undefined}
                    className={cn(
                      'w-full whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                      cur ? (s.is_won ? 'bg-success text-white' : 'bg-primary text-primary-fg') : passed ? 'text-text' : 'text-muted',
                      !cur && deal.can_edit && !deal.lost && 'hover:bg-surface',
                    )}
                  >
                    {s.name}
                  </button>
                </li>
              )
            })}
          </ol>
          {deal.phone && (
            <a href={`tel:${deal.phone}`} className="inline-flex w-fit items-center gap-1.5 text-sm text-primary hover:underline">
              <Phone className="size-4" />
              {deal.phone}
            </a>
          )}
        </Card>

        <form onSubmit={submit}>
          <Card className="flex flex-col gap-4 p-5">
            <DealFields value={draft} onChange={setDraft} canAssign={deal.can_assign} disabled={!deal.can_edit} />
            {deal.can_edit && (
              <div className="flex items-center justify-end gap-2 border-t border-border pt-4">
                {dirty && (
                  <Button variant="ghost" onClick={() => setDraft(draftOf(deal))}>
                    {t('common.cancel')}
                  </Button>
                )}
                <Button type="submit" disabled={!dirty || save.isPending || !draft.title.trim()}>
                  <Save className="size-4" />
                  {t('common.save')}
                </Button>
              </div>
            )}
          </Card>
        </form>
        {err && (
          <p role="alert" className="text-sm text-danger">
            {errorText(t, err)}
          </p>
        )}
      </div>
      <Chatter dealId={id} canPlan={deal.can_edit && !deal.lost} />
    </div>
  )
}

/** /crm/new: yangi bitim. Saqlangach kartasi ochiladi (birinchi bosqich va uning avtomatik faoliyati bilan). */
export function CrmNewDealPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const board = useQuery({ queryKey: ['crm', 'board', ''], queryFn: () => api<{ can_manage: boolean; stages: Deal['stages'] }>(`/api/v1/crm/board`) })
  const [draft, setDraft] = useState<DealDraft>(emptyDraft())
  const create = useMutation({
    mutationFn: () => send<{ id: number }>('POST', '/api/v1/crm/deals', toInput({ ...draft, stage_id: draft.stage_id ?? board.data?.stages[0]?.id ?? null })),
    onSuccess: (r) => (void qc.invalidateQueries({ queryKey: ['crm'] }), navigate(`/crm/deals/${r.id}`)),
  })
  return (
    <form onSubmit={(e) => (e.preventDefault(), create.mutate())} className="mx-auto flex max-w-3xl flex-col gap-4">
      <PageHeader title={t('crm.newDeal')} subtitle={t('crm.newHint')} backTo="/crm" backLabel={t('crm.title')} />
      <Card className="p-5">{board.data ? <DealFields value={draft} onChange={setDraft} stages={board.data.stages} canAssign={board.data.can_manage} /> : <Skeleton className="h-64" />}</Card>
      {create.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, create.error)}
        </p>
      )}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={() => navigate('/crm')}>
          {t('common.cancel')}
        </Button>
        <Button type="submit" disabled={!draft.title.trim() || create.isPending}>
          {t('crm.create')}
        </Button>
      </div>
    </form>
  )
}
