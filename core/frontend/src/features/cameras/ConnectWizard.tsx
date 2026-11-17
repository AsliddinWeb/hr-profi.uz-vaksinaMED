import { useMutation, useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { ArrowLeft, Camera as CameraIcon, Check, CheckCircle2, Copy, ExternalLink, Laptop, Loader2, RefreshCw, Smartphone, TriangleAlert, X } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '../../components/ui/Button'
import { Field, Input, Select } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import type { BranchPage } from '../branches/api'

type Kind = 'ip' | 'webcam' | 'phone'
type Created = { id: number; name: string; kind: Kind; status: string; station_url: string | null; last_error: string | null; host: string | null; port: number | null }

const BRANDS: { key: string; port: number }[] = [
  { key: 'Hikvision', port: 554 },
  { key: 'Dahua', port: 554 },
  { key: 'Uniview', port: 554 },
  { key: 'Imou / Ezviz', port: 554 },
  { key: 'other', port: 554 },
]
const ICON = { ip: CameraIcon, webcam: Laptop, phone: Smartphone }

/** Qurilmani ulash yo'riqnomasi: Telefon (QR), Kompyuter (havola) yoki IP kamera (tekshiruv) — qadamma-qadam. */
export function ConnectWizard({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { t } = useTranslation()
  const can = useCan()
  const [kind, setKind] = useState<Kind | null>(null)
  const [cam, setCam] = useState<Created | null>(null)
  const [name, setName] = useState('')
  const [branch, setBranch] = useState('')
  const [location, setLocation] = useState('')
  const [brand, setBrand] = useState('Hikvision')
  const [host, setHost] = useState('')
  const [port, setPort] = useState('554')
  const branches = useQuery({ queryKey: ['branches', 'select'], queryFn: () => api<BranchPage>('/api/v1/branches?size=200'), enabled: can('branches.read') })
  const create = useMutation({
    mutationFn: async () => {
      const c = await send<Created>('POST', '/api/v1/cameras', {
        name: name.trim(), kind, branch_id: branch ? Number(branch) : null, location: location.trim() || null,
        brand: kind === 'ip' && brand !== 'other' ? brand : null, host: kind === 'ip' ? host.trim() : null, port: kind === 'ip' ? Number(port) || 554 : null,
      })  // prettier-ignore
      return kind === 'ip' ? send<Created>('POST', `/api/v1/cameras/${c.id}/check`) : c
    },
    onSuccess: (c) => (setCam(c), onDone()),
  })
  const step = !kind ? 1 : !cam ? 2 : 3
  const close = () => (cam && onDone(), onClose())

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-3" onClick={close}>
      <div className="flex max-h-[92vh] w-full max-w-2xl flex-col overflow-y-auto rounded-card bg-surface shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between gap-2 border-b border-border px-5 py-4">
          <div className="flex items-center gap-2">
            {step === 2 && (
              <Button variant="ghost" onClick={() => setKind(null)} aria-label={t('wiz.back')}>
                <ArrowLeft className="size-4" />
              </Button>
            )}
            <div>
              <h2 className="font-semibold">{kind ? t(`wiz.title.${kind}`) : t('wiz.chooseTitle')}</h2>
              <div className="text-xs text-muted">{t('wiz.stepOf', { n: step, total: 3 })}</div>
            </div>
          </div>
          <Button variant="ghost" onClick={close} aria-label={t('common.close', { defaultValue: 'Close' })}>
            <X className="size-4" />
          </Button>
        </div>
        <div className="flex gap-1 px-5 pt-3">
          {[1, 2, 3].map((n) => (
            <span key={n} className={clsx('h-1 flex-1 rounded-full', n <= step ? 'bg-primary' : 'bg-surface-2')} />
          ))}
        </div>

        <div className="flex flex-col gap-4 p-5">
          {step === 1 && (
            <>
              <p className="text-sm text-muted">{t('wiz.chooseHint')}</p>
              <div className="grid gap-3 sm:grid-cols-3">
                {(['phone', 'webcam', 'ip'] as const).map((k) => {
                  const Icon = ICON[k]
                  return (
                    <button key={k} type="button" onClick={() => (setKind(k), setPort('554'))} className="flex flex-col items-center gap-2 rounded-card border border-border p-5 text-center transition hover:border-primary hover:bg-primary/5">
                      <span className="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                        <Icon className="size-7" />
                      </span>
                      <span className="font-semibold">{t(`cam.kinds.${k}`)}</span>
                      <span className="text-xs text-muted">{t(`wiz.choose.${k}`)}</span>
                    </button>
                  )
                })}
              </div>
            </>
          )}

          {step === 2 && kind && (
            <>
              <Field label={t('wiz.nameLabel')}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} placeholder={t(`wiz.namePh.${kind}`)} autoFocus />}</Field>
              <div className="grid gap-3 sm:grid-cols-2">
                <Field label={t('cam.branch')}>
                  {(id) => (
                    <Select id={id} value={branch} onChange={(e) => setBranch(e.target.value)}>
                      <option value="">{t('wiz.noBranch')}</option>
                      {branches.data?.items.map((b) => (
                        <option key={b.id} value={b.id}>
                          {b.name}
                        </option>
                      ))}
                    </Select>
                  )}
                </Field>
                <Field label={t('cam.location')}>{(id) => <Input id={id} value={location} onChange={(e) => setLocation(e.target.value)} placeholder={t('cam.locationPh')} />}</Field>
              </div>
              {kind === 'ip' && (
                <>
                  <div>
                    <div className="mb-1.5 text-sm font-medium">{t('cam.brand')}</div>
                    <div className="flex flex-wrap gap-2">
                      {BRANDS.map((b) => (
                        <button key={b.key} type="button" onClick={() => (setBrand(b.key), setPort(String(b.port)))} className={clsx('rounded-full border px-3 py-1 text-sm', brand === b.key ? 'border-primary bg-primary text-white' : 'border-border hover:bg-surface-2')}>
                          {b.key === 'other' ? t('wiz.otherBrand') : b.key}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="col-span-2">
                      <Field label={t('wiz.hostLabel')}>{(id) => <Input id={id} value={host} onChange={(e) => setHost(e.target.value)} placeholder="93.170.12.34" inputMode="url" />}</Field>
                    </div>
                    <Field label={t('cam.port')}>{(id) => <Input id={id} type="number" value={port} onChange={(e) => setPort(e.target.value)} />}</Field>
                  </div>
                  <div className="rounded-lg bg-surface-2 p-3 text-xs leading-relaxed text-muted">
                    <div className="mb-1 font-medium text-fg">{t('wiz.ipWhereTitle')}</div>
                    <ol className="list-decimal space-y-0.5 pl-4">
                      <li>{t('wiz.ipWhere1')}</li>
                      <li>{t('wiz.ipWhere2')}</li>
                      <li>{t('wiz.ipWhere3')}</li>
                    </ol>
                  </div>
                </>
              )}
              {create.isError && (
                <p role="alert" className="text-sm text-danger">
                  {errorText(t, create.error)}
                </p>
              )}
              <Button className="h-11" disabled={create.isPending || !name.trim() || (kind === 'ip' && !host.trim())} onClick={() => create.mutate()}>
                {create.isPending && <Loader2 className="size-4 animate-spin" />}
                {kind === 'ip' ? t('wiz.saveCheck') : t('wiz.next')}
              </Button>
            </>
          )}

          {step === 3 && cam && (cam.kind === 'ip' ? <IpResult cam={cam} onChange={setCam} onClose={close} /> : <StationConnect cam={cam} onClose={close} />)}
        </div>
      </div>
    </div>
  )
}

function IpResult({ cam, onChange, onClose }: { cam: Created; onChange: (c: Created) => void; onClose: () => void }) {
  const { t } = useTranslation()
  const again = useMutation({ mutationFn: () => send<Created>('POST', `/api/v1/cameras/${cam.id}/check`), onSuccess: onChange })
  const ok = cam.status === 'online'
  const reason = cam.last_error === 'timeout' ? 'timeout' : cam.last_error?.toLowerCase().includes('refused') ? 'refused' : 'other'
  return (
    <div className="flex flex-col gap-4">
      {ok ? (
        <div className="flex items-center gap-3 rounded-card bg-success/10 p-4 text-success">
          <CheckCircle2 className="size-8 shrink-0" />
          <div>
            <div className="font-semibold">{t('wiz.ipOk')}</div>
            <div className="text-sm">{t('wiz.ipOkHint', { addr: `${cam.host}:${cam.port}` })}</div>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-3 rounded-card bg-danger/10 p-4">
          <div className="flex items-center gap-3 text-danger">
            <TriangleAlert className="size-8 shrink-0" />
            <div>
              <div className="font-semibold">{t('wiz.ipFail')}</div>
              <div className="text-sm">{t(`wiz.reason.${reason}`)}</div>
            </div>
          </div>
          <div className="text-sm">
            <div className="mb-1 font-medium">{t('wiz.fixTitle')}</div>
            <ol className="list-decimal space-y-1 pl-5 text-muted">
              {[1, 2, 3].map((n) => (
                <li key={n}>{t(`wiz.fix.${reason}${n}`)}</li>
              ))}
            </ol>
          </div>
        </div>
      )}
      <p className="text-xs text-muted">{t('wiz.ipSaved')}</p>
      <div className="flex justify-end gap-2">
        {!ok && (
          <Button variant="outline" disabled={again.isPending} onClick={() => again.mutate()}>
            <RefreshCw className={clsx('size-4', again.isPending && 'animate-spin')} />
            {t('wiz.recheck')}
          </Button>
        )}
        <Button onClick={onClose}>
          <Check className="size-4" />
          {t('wiz.done')}
        </Button>
      </div>
    </div>
  )
}

function StationConnect({ cam, onClose }: { cam: Created; onClose: () => void }) {
  const { t } = useTranslation()
  const toast = useToast()
  const origin = window.location.origin
  const link = `${origin}${cam.station_url ?? ''}`
  const localOnly = /\/\/(localhost|127\.0\.0\.1|\[::1\])(:|\/|$)/.test(origin)
  const qr = useQuery({
    queryKey: ['cameras', 'qr', cam.id],
    queryFn: () => api<{ url: string; svg: string }>(`/api/v1/cameras/${cam.id}/station-qr?origin=${encodeURIComponent(origin)}`),
    enabled: cam.kind === 'phone',
  })
  // ulanishni kutish: birinchi «onlayn» hodisasi kelganda tayyor
  const events = useQuery({
    queryKey: ['cameras', 'events', cam.id, 'wait'],
    queryFn: () => api<{ status: string }[]>(`/api/v1/cameras/${cam.id}/events`),
    refetchInterval: (q) => (q.state.data?.some((e) => e.status === 'online') ? false : 3000),
  })
  const connected = !!events.data?.some((e) => e.status === 'online')
  const url = qr.data?.url ?? link
  const copy = () => void navigator.clipboard.writeText(url).then(() => toast.push({ tone: 'success', title: t('cam.copied') }))
  const steps = [1, 2, 3, 4].map((n) => t(`wiz.${cam.kind}Step${n}`))
  return (
    <div className="flex flex-col gap-4">
      {localOnly && cam.kind === 'phone' && (
        <div className="flex gap-2 rounded-lg bg-warning/10 p-3 text-xs text-warning">
          <TriangleAlert className="size-4 shrink-0" />
          {t('wiz.localWarn')}
        </div>
      )}
      <div className={clsx('grid gap-4', cam.kind === 'phone' && 'sm:grid-cols-[220px_1fr]')}>
        {cam.kind === 'phone' && (
          <div className="flex flex-col items-center gap-2">
            {qr.data ? <div className="w-[220px] rounded-lg bg-white p-2" dangerouslySetInnerHTML={{ __html: qr.data.svg }} /> : <div className="size-[220px] animate-pulse rounded-lg bg-surface-2" />}
            <span className="text-center text-xs text-muted">{t('wiz.scanQr')}</span>
          </div>
        )}
        <div className="flex min-w-0 flex-col gap-3">
          <ol className="flex flex-col gap-2.5">
            {steps.map((s, i) => (
              <li key={i} className="flex gap-3 text-sm">
                <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-semibold text-white">{i + 1}</span>
                <span className="pt-0.5">{s}</span>
              </li>
            ))}
          </ol>
          <div className="flex min-w-0 gap-2">
            <Input readOnly value={url} className="min-w-0 flex-1 font-mono text-xs" aria-label={t('cam.stationTitle')} />
            <Button variant="outline" onClick={copy} aria-label={t('cam.copy')}>
              <Copy className="size-4" />
            </Button>
            {cam.kind === 'webcam' && (
              <a href={url} target="_blank" rel="noopener">
                <Button variant="outline" aria-label={t('wiz.openHere')}>
                  <ExternalLink className="size-4" />
                </Button>
              </a>
            )}
          </div>
        </div>
      </div>
      {connected ? (
        <div className="flex flex-col gap-3 rounded-card bg-success/10 p-4">
          <div className="flex items-center gap-3 text-success">
            <CheckCircle2 className="size-7 shrink-0" />
            <div className="font-semibold">{t('wiz.connected')}</div>
          </div>
          <img src={`/api/v1/cameras/${cam.id}/snapshot?t=${events.dataUpdatedAt}`} alt={t('cam.snapshot')} className="max-h-64 w-full rounded-lg bg-black object-contain" />
        </div>
      ) : (
        <div className="flex items-center gap-3 rounded-card bg-surface-2 p-4 text-sm text-muted">
          <Loader2 className="size-5 animate-spin text-primary" />
          {t(`wiz.waiting.${cam.kind}`)}
        </div>
      )}
      <div className="flex justify-end">
        <Button onClick={onClose} variant={connected ? 'primary' : 'outline'}>
          {connected ? t('wiz.done') : t('wiz.later')}
        </Button>
      </div>
    </div>
  )
}
