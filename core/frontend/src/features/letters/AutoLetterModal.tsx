import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, CheckCircle2, Clock, FileDown, FileSignature, Lock, MapPin, PenLine, Phone, QrCode, X } from 'lucide-react'
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatDate } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { useMe } from '../auth/useAuth'
import { money, OPEN_EVENT, shortName, tashkentTime, wordCount, type AutoFacts, type AutoLetter } from './autoApi'
import { SignaturePad } from './SignaturePad'

const KEY = ['letters', 'auto', 'pending']

/**
 * Avtomatik tushuntirish xati oynasi: qoidabuzarlik (kechikish, kelmaslik...) bo'lsa har sahifada o'zi ochiladi.
 * 1) xatni o'qib sababni yozish -> 2) tasdiqlash (QR qo'yiladi) -> 3) imzoni chizish. Imzolanmaguncha «Keldim» yopiq.
 */
export function AutoLetterModal() {
  const me = useMe()
  const qc = useQueryClient()
  const [shown, setShown] = useState<AutoLetter | null>(null) // imzolangandan keyin ham yakuniy holat ko'rinib turadi
  const [dismissed, setDismissed] = useState<number | null>(null)
  const q = useQuery({ queryKey: KEY, queryFn: () => api<AutoLetter | null>('/api/v1/letters/auto/pending'), enabled: !!me.data, refetchInterval: 60_000, retry: false })

  useEffect(() => {
    const reopen = () => {
      setDismissed(null)
      void qc.invalidateQueries({ queryKey: KEY })
    }
    window.addEventListener(OPEN_EVENT, reopen)
    return () => window.removeEventListener(OPEN_EVENT, reopen)
  }, [qc])

  const pending = q.data ?? null
  const letter = shown ?? (pending && pending.id !== dismissed ? pending : null)
  if (!letter) return null
  return (
    <LetterDialog
      key={letter.id}
      letter={letter}
      onChange={(l) => setShown(l)}
      onLater={() => {
        setShown(null)
        setDismissed(letter.id)
      }}
      onClose={() => {
        setShown(null)
        void qc.invalidateQueries({ queryKey: KEY })
        void qc.invalidateQueries({ queryKey: ['letters'] })
      }}
    />
  )
}

function LetterDialog({ letter, onChange, onLater, onClose }: { letter: AutoLetter; onChange: (l: AutoLetter) => void; onLater: () => void; onClose: () => void }) {
  const { t } = useTranslation()
  const ref = useRef<HTMLDialogElement>(null)
  const signed = letter.status !== 'requested' && letter.status !== 'returned'
  const f = letter.facts

  useEffect(() => {
    const d = ref.current
    if (d && !d.open) d.showModal()
    return () => d?.close()
  }, [])

  return (
    <dialog
      ref={ref}
      aria-labelledby="auto-letter-title"
      onCancel={(e) => {
        e.preventDefault()
        if (signed) onClose()
        else onLater()
      }}
      className="m-auto flex h-[min(56rem,calc(100dvh-1rem))] w-[min(72rem,calc(100vw-1rem))] max-w-none flex-col overflow-hidden rounded-card bg-surface p-0 text-text shadow-pop backdrop:bg-black/50 backdrop:backdrop-blur-[2px] open:flex"
    >
      <header className="flex items-start gap-3 border-b border-border px-4 py-3 sm:px-6">
        <span className="grid size-9 shrink-0 place-items-center rounded-full bg-primary text-primary-fg">
          <FileSignature className="size-4" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 id="auto-letter-title" className="text-lg font-semibold tracking-tight">
              {t('autoLetter.title')}
            </h2>
            <Badge tone={signed ? 'success' : 'warning'}>{t(signed ? 'autoLetter.signed' : 'autoLetter.waiting')}</Badge>
            <Badge tone="warning">{t('autoLetter.stepBadge', { n: f.step })}</Badge>
          </div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-muted">
            <span className="font-medium text-text">{f.employee}</span>
            {f.amount > 0 && <span>· {t('autoLetter.fine', { amount: money(f.amount) })}</span>}
            <span className="inline-flex items-center gap-1">
              · <Clock className="size-3" /> {f.incident_label.charAt(0).toUpperCase() + f.incident_label.slice(1)} {formatDate(letter.incident_date, 'uz')}
            </span>
            <span className="inline-flex items-center gap-1">
              · <MapPin className="size-3" /> {f.branch ?? '—'}
            </span>
          </div>
        </div>
        <button
          type="button"
          onClick={signed ? onClose : onLater}
          aria-label={t('common.close')}
          className="grid size-8 place-items-center rounded-full text-muted hover:bg-surface-2 hover:text-text"
        >
          <X className="size-4" />
        </button>
      </header>
      <div className="grid min-h-0 flex-1 grid-rows-[minmax(0,1fr)_auto] lg:grid-cols-[minmax(0,1fr)_22rem] lg:grid-rows-1">
        <div className="min-h-0 overflow-y-auto bg-surface-2 p-2 sm:p-5">
          <Paper letter={letter} />
        </div>
        <Side letter={letter} signed={signed} onChange={onChange} onLater={onLater} onClose={onClose} />
      </div>
    </dialog>
  )
}

/* ------------------------------------------------------------------------------------- */

export function Paper({ letter }: { letter: AutoLetter }) {
  const { t } = useTranslation()
  const d = letter.document
  const f = letter.facts
  const signedAt = letter.submitted_at ? tashkentTime(letter.submitted_at) : null
  return (
    <article className="mx-auto max-w-[46rem] bg-white text-[13px] leading-relaxed text-slate-800 shadow-card sm:text-sm">
      <div className="h-2 bg-slate-800" />
      <div className="px-5 pb-6 pt-5 sm:px-10 sm:pt-8">
        <div className="flex flex-col-reverse gap-5 sm:flex-row sm:justify-between">
          <div className="w-36 shrink-0 text-[10px] text-slate-500">
            <div className="grid size-24 place-items-center border border-dashed border-slate-300 p-1 text-center">
              {letter.confirmed_at ? <img src={`/api/v1/letters/${letter.id}/auto/qr`} alt={t('autoLetter.doc.qrAlt')} className="size-full" /> : <span>{t('autoLetter.doc.qrLater')}</span>}
            </div>
            <div className="mt-1">{t('autoLetter.doc.qrHint')}</div>
            <div className="mt-2">{t('autoLetter.doc.number')}</div>
            <div className="font-semibold text-slate-800">№ {letter.number}</div>
          </div>
          <div className="text-left sm:max-w-[60%] sm:text-right">
            <div className="font-semibold">{d.recipient}</div>
            <div className="mt-3 space-y-1.5 text-left">
              <Line>{t('autoLetter.doc.companyEmployee', { company: d.company })}</Line>
              <Line>{[f.position, f.branch ?? f.department].filter(Boolean).join(', ') || '—'}</Line>
              <Line bold>
                {f.employee} <span className="font-normal text-slate-500">{t('autoLetter.doc.from')}</span>
              </Line>
              <Line>{t('autoLetter.doc.tel', { phone: f.employee_phone ?? '—' })}</Line>
            </div>
          </div>
        </div>
        <hr className="my-5 border-t-2 border-double border-slate-300" />
        <h3 className="text-center text-base font-bold tracking-[0.4em] sm:text-lg">{d.title}</h3>
        <p className="mt-1 text-center text-xs font-medium text-orange-600">{d.subtitle}</p>
        <p className="text-center text-xs">
          {t('autoLetter.doc.measureLine')} <b>{d.measure_line}</b>
        </p>
        <div className="mt-4 space-y-3 text-justify [text-indent:2rem]">
          <p>{d.preamble}</p>
          <p>
            {d.intro} {d.incident}
          </p>
          {d.basis && <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800 [text-indent:0]">{d.basis}</p>}
          {letter.explanation ? (
            <p>
              {d.explanation_lead} <b>{letter.explanation}</b>
            </p>
          ) : (
            <div className="space-y-5 py-2 [text-indent:0]" aria-label={t('autoLetter.doc.reasonPlace')}>
              <div className="border-b border-slate-300" />
              <div className="border-b border-slate-300" />
              <div className="border-b border-slate-300" />
            </div>
          )}
          <p>{d.measure}</p>
          <p>{d.escalation}</p>
          <p>{d.closing}</p>
        </div>
        {d.steps.length > 0 && (
          <div className="mt-6">
            <div className="text-[10px] font-semibold uppercase tracking-wide text-slate-500">{t('autoLetter.doc.ladder')}</div>
            <ol className="mt-1.5 grid grid-cols-3 gap-1.5 sm:grid-cols-6">
              {d.steps.map((s) => (
                <li
                  key={s.step}
                  className={cn(
                    'rounded border px-1.5 py-1 text-[10px] leading-tight',
                    s.step === d.step ? 'border-orange-500 bg-orange-500 text-white' : s.step < d.step ? 'border-blue-200 bg-blue-50 text-blue-700' : 'border-slate-200 text-slate-400',
                  )}
                >
                  <div className="font-semibold">
                    {t('autoLetter.stepBadge', { n: s.step })}
                    {s.step === d.step && ` · ${t('autoLetter.doc.you')}`}
                  </div>
                  <div className="truncate" title={s.label}>
                    {s.label}
                    {s.amount > 0 ? ` · ${money(s.amount)}` : ''}
                  </div>
                </li>
              ))}
            </ol>
            {d.next && <p className="mt-1.5 text-[11px] font-medium text-orange-600">▶ {d.next}</p>}
          </div>
        )}
        <div className="mt-8 grid grid-cols-3 items-end gap-4 text-center text-xs">
          <SigCell label={t('autoLetter.doc.date')}>{signedAt?.date ?? ''}</SigCell>
          <SigCell label={t('autoLetter.doc.signature')}>{letter.signature_image && <img src={letter.signature_image} alt={t('autoLetter.doc.signature')} className="mx-auto h-14 object-contain" />}</SigCell>
          <SigCell label={t('autoLetter.doc.fio')}>{shortName(letter.signer)}</SigCell>
        </div>
        {signedAt && (
          <p className="mt-6 border-t border-slate-200 pt-2 text-center text-[10px] text-slate-400">
            {t('autoLetter.doc.footer', { date: signedAt.date, time: signedAt.time, number: letter.number, company: d.company })}
          </p>
        )}
      </div>
    </article>
  )
}

function Line({ children, bold }: { children: ReactNode; bold?: boolean }) {
  return <div className={cn('border-b border-slate-400 pb-0.5', bold && 'font-semibold')}>{children}</div>
}

function SigCell({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="flex min-h-14 items-end justify-center border-b border-slate-500 pb-1 text-sm text-slate-800">{children}</div>
      <div className="mt-1 text-slate-400">({label})</div>
    </div>
  )
}

/* ------------------------------------------------------------------------------------- */

function Side({ letter, signed, onChange, onLater, onClose }: { letter: AutoLetter; signed: boolean; onChange: (l: AutoLetter) => void; onLater: () => void; onClose: () => void }) {
  const { t } = useTranslation()
  const toast = useToast()
  const qc = useQueryClient()
  const [text, setText] = useState('')
  const [read, setRead] = useState(false)
  const [pad, setPad] = useState(false)
  const confirmed = !!letter.confirmed_at
  const step = signed ? 3 : confirmed ? 2 : 0
  const words = wordCount(text)
  const chars = text.trim().length
  const valid = words >= letter.min_words && chars >= letter.min_chars && read

  const confirm = useMutation({
    mutationFn: () => send<AutoLetter>('POST', `/api/v1/letters/${letter.id}/auto/confirm`, { explanation: text, read }),
    onSuccess: (l) => {
      onChange(l)
      qc.setQueryData(KEY, l)
    },
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const sign = useMutation({
    mutationFn: (signature: string) => send<AutoLetter>('POST', `/api/v1/letters/${letter.id}/auto/sign`, { signature }),
    onSuccess: (l) => {
      onChange(l)
      setPad(false)
      qc.setQueryData(KEY, null)
      toast.push({ title: t('autoLetter.sign.done'), tone: 'success' })
    },
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })

  return (
    <aside className="flex min-h-0 flex-col border-t border-border lg:border-l lg:border-t-0">
      <ol className="flex items-center gap-2 px-4 pt-4">
        {(['read', 'qr', 'sign'] as const).map((k, i) => {
          const done = i < step
          const current = i === step || (i === 2 && step === 2)
          return (
            <li key={k} className="flex min-w-0 flex-1 items-center gap-1.5" aria-current={current ? 'step' : undefined}>
              <span className={cn('grid size-7 shrink-0 place-items-center rounded-full text-xs font-semibold', done ? 'bg-success text-white' : current ? 'bg-primary text-primary-fg' : 'bg-surface-3 text-muted')}>
                {done ? <Check className="size-3.5" /> : i + 1}
              </span>
              <span className={cn('text-[11px] leading-tight', !done && !current && 'text-muted')}>{t(`autoLetter.steps.${k}`)}</span>
            </li>
          )
        })}
      </ol>
      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4">
        {pad ? (
          <SignaturePad busy={sign.isPending} onCancel={() => setPad(false)} onSave={(png) => sign.mutate(png)} />
        ) : !confirmed ? (
          <section className="space-y-3 rounded-card border border-border p-4">
            <div>
              <h3 className="text-sm font-semibold">{t('autoLetter.reason.title')}</h3>
              <p className="mt-0.5 text-xs text-muted">{t('autoLetter.reason.hint')}</p>
            </div>
            {letter.status === 'returned' && letter.review_note && (
              <p className="rounded-control bg-danger/10 px-3 py-2 text-xs text-danger">{t('autoLetter.reason.returned', { note: letter.review_note })}</p>
            )}
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              onPaste={(e) => e.preventDefault()}
              onDrop={(e) => e.preventDefault()}
              rows={6}
              maxLength={2000}
              placeholder={t('autoLetter.reason.placeholder')}
              aria-label={t('autoLetter.reason.title')}
              className="w-full resize-y rounded-control border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/30"
            />
            <div className={cn('text-right text-xs', words >= letter.min_words && chars >= letter.min_chars ? 'text-success' : 'text-muted')}>
              {t('autoLetter.reason.counter', { words, minWords: letter.min_words, chars, minChars: letter.min_chars })}
            </div>
            <label className="flex cursor-pointer items-start gap-2 rounded-control bg-surface-2 p-3 text-xs">
              <input type="checkbox" checked={read} onChange={(e) => setRead(e.target.checked)} className="mt-0.5" />
              <span>{t('autoLetter.reason.read')}</span>
            </label>
          </section>
        ) : (
          <>
            {signed ? (
              <section className="rounded-card border border-success/30 bg-success/10 p-4">
                <div className="flex items-center gap-2 font-semibold text-success">
                  <CheckCircle2 className="size-5" />
                  {t('autoLetter.final.title')}
                </div>
                {letter.submitted_at && (
                  <p className="mt-1 text-xs text-success">{t('autoLetter.final.body', { ...tashkentTime(letter.submitted_at), number: letter.number })}</p>
                )}
              </section>
            ) : (
              <section className="rounded-card border border-info/30 bg-info/10 p-4">
                <div className="flex items-center gap-2 font-semibold text-info">
                  <QrCode className="size-5" />
                  {t('autoLetter.qr.title')}
                </div>
                <p className="mt-1 text-xs text-muted">{t('autoLetter.qr.body')}</p>
              </section>
            )}
            <FactsTable f={letter.facts} date={letter.incident_date} />
            <section className="rounded-card border border-info/30 bg-info/5 px-4 py-3">
              <div className="text-[11px] font-semibold uppercase tracking-wide text-info">{t('autoLetter.coord.title')}</div>
              {letter.facts.coordinator ? (
                <div className="mt-1 flex items-center justify-between gap-2 text-sm">
                  <span>{letter.facts.coordinator}</span>
                  {letter.facts.coordinator_phone && <PhonePill phone={letter.facts.coordinator_phone} />}
                </div>
              ) : (
                <p className="mt-1 text-sm text-muted">{t('autoLetter.coord.none')}</p>
              )}
            </section>
            {letter.document.next && <p className="rounded-control bg-surface-2 px-3 py-2 text-xs font-medium">▶ {letter.document.next}</p>}
          </>
        )}
      </div>
      {!pad && (
        <footer className="space-y-2 border-t border-border p-4">
          {signed ? (
            <div className="grid grid-cols-3 gap-2">
              <a href={`/api/v1/letters/${letter.id}/pdf`} download className="inline-flex items-center justify-center gap-1.5 rounded-control border border-border px-3 py-2 text-sm font-medium hover:bg-surface-2">
                <FileDown className="size-4" />
                PDF
              </a>
              <a href={letter.verify_url ?? '#'} target="_blank" rel="noreferrer" className="inline-flex items-center justify-center gap-1.5 rounded-control border border-border px-3 py-2 text-sm font-medium hover:bg-surface-2">
                <QrCode className="size-4" />
                {t('autoLetter.final.verify')}
              </a>
              <Button onClick={onClose}>{t('common.close')}</Button>
            </div>
          ) : (
            <>
              <p className="flex items-start gap-2 rounded-control border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
                <Lock className="mt-0.5 size-3.5 shrink-0" />
                {t('autoLetter.blocked')}
              </p>
              {confirmed ? (
                <Button variant="ghost" className="w-full bg-success font-semibold text-white hover:bg-success hover:text-white hover:brightness-110" onClick={() => setPad(true)}>
                  <PenLine className="size-4" />
                  {t('autoLetter.sign.open')}
                </Button>
              ) : (
                <Button className="w-full" disabled={!valid || confirm.isPending} onClick={() => confirm.mutate()}>
                  <CheckCircle2 className="size-4" />
                  {t('autoLetter.reason.submit')}
                </Button>
              )}
              {!confirmed && !valid && <p className="text-center text-[11px] text-muted">{t('autoLetter.reason.need', { minWords: letter.min_words, minChars: letter.min_chars })}</p>}
              <button type="button" onClick={onLater} className="w-full text-center text-xs font-medium text-muted hover:text-text">
                {t('autoLetter.later')}
              </button>
            </>
          )}
        </footer>
      )}
    </aside>
  )
}

function FactsTable({ f, date }: { f: AutoFacts; date: string }) {
  const { t } = useTranslation()
  const state =
    f.incident === 'late'
      ? t('autoLetter.facts.lateState', { time: f.check_in, minutes: f.late_minutes })
      : f.incident === 'early_leave'
        ? t('autoLetter.facts.earlyState', { time: f.check_out, minutes: f.early_minutes })
        : f.incident_label.charAt(0).toUpperCase() + f.incident_label.slice(1)
  const rows: { k: string; v: ReactNode }[] = [
    { k: t('autoLetter.facts.employee'), v: f.employee },
    { k: t('autoLetter.facts.position'), v: f.position ?? '—' },
    { k: t('autoLetter.facts.branch'), v: f.branch ?? '—' },
    { k: t('autoLetter.facts.shift'), v: f.shift ?? '—' },
    { k: t('autoLetter.facts.state'), v: state },
    { k: t('autoLetter.facts.date'), v: formatDate(date, 'uz') },
    { k: t('autoLetter.facts.count'), v: t('autoLetter.facts.countValue', { n: f.month_count }) },
    { k: t('autoLetter.facts.measure'), v: `${f.measure}${f.amount ? ` (${money(f.amount)})` : ''}` },
    { k: t('autoLetter.facts.phone'), v: f.employee_phone ? <PhonePill phone={f.employee_phone} /> : <span className="text-muted">{t('autoLetter.facts.none')}</span> },
    { k: t('autoLetter.facts.branchPhone'), v: f.branch_phone ? <PhonePill phone={f.branch_phone} /> : <span className="text-muted">{t('autoLetter.facts.none')}</span> },
  ]
  return (
    <dl className="divide-y divide-border rounded-card border border-border text-xs">
      {rows.map(({ k, v }) => (
        <div key={k} className="flex items-center justify-between gap-3 px-3 py-2">
          <dt className="text-muted">{k}</dt>
          <dd className="text-right font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function PhonePill({ phone }: { phone: string }) {
  const pretty = phone.replace(/^\+998(\d{2})(\d{3})(\d{2})(\d{2})$/, '+998 $1-$2-$3-$4')
  return (
    <a href={`tel:${phone}`} className="inline-flex items-center gap-1 rounded-full bg-success px-2.5 py-1 text-xs font-semibold text-white hover:brightness-110">
      <Phone className="size-3" />
      {pretty}
    </a>
  )
}
