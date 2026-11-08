import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, CalendarOff, Clock, FileSignature, FileWarning, LocateFixed, LogIn, LogOut, MapPin, Navigation, QrCode, ScanFace, X } from 'lucide-react'
import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'

import { GeofenceMap } from '../../components/map/GeofenceMap'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { api, ApiError } from '../../lib/api'
import { cn } from '../../lib/cn'
import { formatDate } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { openAutoLetter } from '../letters/autoApi'
import { fmtMin, fmtTime, type MeData } from './api'
import { QrScanner } from './QrScanner'
import { distanceM, fmtDistance, qrSupported, useGeoWatch } from './useGeoWatch'
import { usePunch } from './usePunch'

const TZ = 'Asia/Tashkent'
const WEEKDAYS = { uz: ['Yakshanba', 'Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba'], ru: ['Воскресенье', 'Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота'] }
const MONTHS = {
  uz: ['yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun', 'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'],
  ru: ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня', 'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
}

/** Toshkent vaqtidagi soat qismlari (telefon soati noto'g'ri bo'lsa ham server vaqti bilan). */
function tashkent(ms: number) {
  const p = Object.fromEntries(
    new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false, year: 'numeric', month: 'numeric', day: 'numeric', weekday: 'short' })
      .formatToParts(new Date(ms))
      .map((x) => [x.type, x.value]),
  )
  return p as Record<string, string>
}

const hms = (sec: number) => {
  const s = Math.max(0, Math.floor(sec))
  return `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

/** /attendance: xodimning davomat paneli: jonli soat, keldi/ketdi, geozona xaritasi, usul tanlash (GPS, Face ID, QR). */
export function MyAttendancePage() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const navigate = useNavigate()
  const can = useCan()
  const confirm = useConfirm()
  const me = useQuery({ queryKey: ['attendance', 'me'], queryFn: () => api<MeData>('/api/v1/attendance/me'), retry: false, refetchInterval: 60_000 })
  const punch = usePunch()
  const data = me.data
  const branch = data?.branch
  const hasGeo = !!(branch?.has_geo && branch.lat != null && branch.lng != null)
  const geo = useGeoWatch(hasGeo)
  const [scan, setScan] = useState(false)
  const [recenter, setRecenter] = useState(0)

  // Server vaqti bilan jonli soat
  const offset = data?.now ? new Date(data.now).getTime() - me.dataUpdatedAt : 0 // telefon soati xato bo'lsa ham server vaqti
  const [tick, setTick] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setTick(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [])
  const nowMs = tick + offset

  const open = data?.open_record ?? null
  const rec = data?.today_record ?? open
  const doneToday = !!(rec && rec.check_out_at && !open)
  const workedSec = open ? (nowMs - new Date(open.check_in_at).getTime()) / 1000 : rec?.check_out_at ? rec.worked_minutes * 60 : 0

  const distance = geo.status === 'ok' && hasGeo ? distanceM(geo.pos, { lat: branch!.lat!, lng: branch!.lng! }) : null
  const inside = distance != null ? distance <= branch!.radius : undefined
  const lowAccuracy = geo.status === 'ok' && geo.pos.accuracy > (branch?.max_accuracy ?? 150)
  const away = distance != null && inside === false ? distance - branch!.radius : 0

  const clock = tashkent(nowMs)
  const dateLine = useMemo(() => {
    if (!data) return ''
    const d = new Date(`${data.today}T12:00:00Z`)
    return `${WEEKDAYS[lang][d.getUTCDay()]}|${d.getUTCDate()} ${MONTHS[lang][d.getUTCMonth()]} ${d.getUTCFullYear()}`
  }, [data, lang])

  if (me.error instanceof ApiError) {
    return (
      <div className="mx-auto max-w-xl">
        <Card className="mt-5 p-6 text-sm text-danger" role="alert">
          {errorText(t, me.error)}
        </Card>
      </div>
    )
  }
  if (!data) return <Skeleton className="mx-auto h-[36rem] max-w-xl" />

  const s = data.schedule
  const plannedStart = s.planned_start ? fmtTime(s.planned_start) : s.shift?.start_time ?? null
  const plannedEnd = s.planned_end ? fmtTime(s.planned_end) : s.shift?.end_time ?? null
  const blocked = !!data.letter_pending && !open

  // Asosiy tugma holati
  let main: { label: string; sub?: string; tone: 'go' | 'out' | 'stop'; disabled: boolean; icon: ReactNode; onClick?: () => void }
  if (blocked) {
    main = { label: t('attendance.panel.signLetter'), sub: data.letter_pending!.number, tone: 'stop', disabled: false, icon: <FileSignature className="size-5" />, onClick: openAutoLetter }
  } else if (doneToday) {
    main = { label: t('attendance.panel.dayDone'), sub: t('attendance.panel.workedTotal', { time: fmtMin(rec!.worked_minutes) }), tone: 'stop', disabled: true, icon: <Clock className="size-5" /> }
  } else if (!branch || !hasGeo) {
    main = { label: t('attendance.panel.useQr'), sub: t(branch ? 'attendance.panel.branchNoGeo' : 'attendance.panel.noBranch'), tone: 'stop', disabled: !qrSupported(), icon: <QrCode className="size-5" />, onClick: () => setScan(true) }
  } else if (geo.status === 'denied') {
    main = { label: t('attendance.panel.geoDenied'), sub: t('attendance.panel.geoDeniedHint'), tone: 'stop', disabled: true, icon: <MapPin className="size-5" /> }
  } else if (geo.status !== 'ok') {
    main = { label: t(geo.status === 'unavailable' ? 'attendance.panel.geoOff' : 'attendance.my.locating'), tone: 'stop', disabled: true, icon: <LocateFixed className="size-5 animate-pulse" /> }
  } else if (inside === false) {
    main = { label: t('attendance.panel.outside'), sub: t('attendance.panel.comeCloser', { d: fmtDistance(away) }), tone: 'stop', disabled: true, icon: <Navigation className="size-5" /> }
  } else if (lowAccuracy) {
    main = { label: t('attendance.panel.lowAccuracy', { m: Math.round(geo.pos.accuracy) }), sub: t('attendance.panel.lowAccuracyHint'), tone: 'stop', disabled: true, icon: <LocateFixed className="size-5" /> }
  } else {
    main = {
      label: punch.isPending ? t('attendance.my.locating') : open ? t('attendance.my.checkOut') : t('attendance.my.checkIn'),
      sub: open ? t('attendance.panel.inSince', { time: fmtTime(open.check_in_at) }) : t('attendance.panel.insideZone'),
      tone: open ? 'out' : 'go',
      disabled: punch.isPending,
      icon: open ? <LogOut className="size-5" /> : <LogIn className="size-5" />,
      onClick: async () => {
        if (open && !(await confirm({ title: t('attendance.my.confirmOutTitle'), body: t('attendance.my.confirmOutBody', { time: fmtTime(open.check_in_at) }), confirmLabel: t('attendance.my.confirmOutBtn') }))) return
        punch.mutate()
      },
    }
  }
  const methodsLocked = blocked || doneToday || inside === false

  const dayOff = !s.working
  const greet = Number(clock.hour) < 11 ? 'morning' : Number(clock.hour) < 17 ? 'day' : 'evening'

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-4 pb-6">
      {dayOff && (
        <div className="rounded-card border border-info/30 bg-info/10 p-4 text-sm" role="status">
          <div className="flex items-center gap-2 font-semibold text-info">
            <CalendarOff className="size-4" />
            {s.reason === 'holiday' ? t('attendance.panel.holiday', { name: s.holiday ?? '' }) : s.reason === 'weekly_off' || s.reason === 'entry_off' ? t('attendance.panel.dayOff') : t('attendance.panel.noSchedule')}
          </div>
          <p className="mt-1 text-xs text-muted">{t(s.reason === 'no_shift' || s.reason === 'no_group' ? 'attendance.panel.noScheduleHint' : 'attendance.panel.dayOffHint')}</p>
        </div>
      )}
      {data.letter_pending && (
        <button type="button" onClick={openAutoLetter} className="flex items-start gap-3 rounded-card border border-danger/30 bg-danger/10 p-4 text-left text-sm">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-danger" />
          <span>
            <span className="block font-semibold text-danger">{t('attendance.panel.letterTitle', { number: data.letter_pending.number })}</span>
            <span className="block text-xs text-muted">{t('attendance.panel.letterHint')}</span>
          </span>
        </button>
      )}

      {/* Sarlavha: salom, sana, jonli soat, bugun ishlangan vaqt */}
      <section className="relative overflow-hidden rounded-card bg-gradient-to-br from-slate-900 via-indigo-950 to-blue-900 p-5 text-white shadow-card">
        <div aria-hidden className="pointer-events-none absolute -right-16 -top-16 size-56 rounded-full bg-amber-400/20 blur-3xl" />
        <div aria-hidden className="pointer-events-none absolute -bottom-20 left-10 size-56 rounded-full bg-sky-400/10 blur-3xl" />
        <div className="relative flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="text-sm text-white/70">{t(`attendance.panel.greet.${greet}`)}</div>
            <h1 className="truncate text-2xl font-bold tracking-tight">{data.employee.full_name}</h1>
            <div className="truncate text-sm text-white/70">{[data.employee.position, branch?.name].filter(Boolean).join(' · ') || '—'}</div>
          </div>
          <div className="shrink-0 rounded-control bg-white/10 px-3 py-1.5 text-right text-xs ring-1 ring-white/15 backdrop-blur">
            <div className="font-semibold">{dateLine.split('|')[0]}</div>
            <div className="text-white/70">{dateLine.split('|')[1]}</div>
          </div>
        </div>
        <div className="relative mt-4 flex items-center justify-between gap-3 rounded-card bg-white/10 p-4 ring-1 ring-white/15 backdrop-blur">
          <div className="flex items-center gap-3">
            <span className="grid size-11 place-items-center rounded-full bg-white/15">
              <Clock className="size-5" />
            </span>
            <div>
              <div className="text-xs text-white/70">{t('attendance.panel.now')}</div>
              <div className="font-mono text-3xl font-semibold tabular-nums" aria-live="off">
                {clock.hour}:{clock.minute}:{clock.second}
              </div>
            </div>
          </div>
          <div className="rounded-control bg-black/20 px-3 py-2 text-center ring-1 ring-white/10">
            <div className="text-[10px] uppercase tracking-wide text-white/70">{t('attendance.panel.workedToday')}</div>
            <div className="font-mono text-lg font-semibold tabular-nums">{hms(workedSec)}</div>
            <div className="text-[10px] text-white/60">{open ? t('attendance.panel.running') : rec ? t('attendance.panel.finished') : t('attendance.panel.notStarted')}</div>
          </div>
        </div>
      </section>

      {/* Keldi / Ketdi */}
      <div className="grid grid-cols-2 gap-3">
        <TimeCard tone="in" icon={<LogIn className="size-4" />} label={t('attendance.panel.came')} time={rec ? fmtTime(rec.check_in_at) : null} plan={plannedStart} note={rec && rec.late_minutes > 0 ? t('attendance.my.late', { m: rec.late_minutes }) : null} planLabel={t('attendance.panel.plan')} />
        <TimeCard tone="out" icon={<LogOut className="size-4" />} label={t('attendance.panel.left')} time={rec?.check_out_at ? fmtTime(rec.check_out_at) : null} plan={plannedEnd} note={rec && rec.early_leave_minutes > 0 ? t('attendance.my.early', { m: rec.early_leave_minutes }) : null} planLabel={t('attendance.panel.plan')} />
      </div>

      {/* Xarita va masofa */}
      {hasGeo && (
        <section className="relative">
          <GeofenceMap center={{ lat: branch!.lat!, lng: branch!.lng! }} radius={branch!.radius} me={geo.status === 'ok' ? geo.pos : null} inside={inside} recenterKey={recenter} />
          {distance != null && (
            <span className={cn('absolute left-1/2 top-3 -translate-x-1/2 rounded-full px-3 py-1 text-xs font-semibold text-white shadow', inside ? 'bg-success' : 'bg-danger')}>
              {inside ? t('attendance.panel.inZone', { d: fmtDistance(distance) }) : t('attendance.panel.away', { d: fmtDistance(away) })}
            </span>
          )}
          <span className="absolute bottom-3 left-3 inline-flex items-center gap-1 rounded-full bg-surface/90 px-2.5 py-1 text-xs font-medium shadow">
            <MapPin className="size-3" /> {branch!.name}
          </span>
          <span className="absolute bottom-3 right-12 rounded-full bg-surface/90 px-2.5 py-1 text-xs font-medium shadow">{t('attendance.panel.radius', { m: branch!.radius })}</span>
          <button type="button" onClick={() => setRecenter((x) => x + 1)} aria-label={t('attendance.panel.recenter')} className="absolute bottom-3 right-3 grid size-8 place-items-center rounded-full bg-surface shadow hover:bg-surface-2">
            <LocateFixed className="size-4" />
          </button>
        </section>
      )}

      {/* Usul tanlash */}
      <section>
        <h2 className="text-sm font-semibold">{t('attendance.panel.methods')}</h2>
        <p className="text-xs text-muted">{t('attendance.panel.methodsHint')}</p>
        <div className="mt-2 grid grid-cols-2 gap-3">
          {can('face.enroll') && (
            <MethodCard icon={<ScanFace className="size-5" />} title="Face ID" sub={methodsLocked ? t('attendance.panel.locked') : t('attendance.panel.faceSub')} disabled={methodsLocked} onClick={() => navigate('/face/punch')} />
          )}
          <MethodCard
            icon={<QrCode className="size-5" />}
            title={t('attendance.panel.qrTitle')}
            sub={!qrSupported() ? t('attendance.panel.qrPhone') : methodsLocked ? t('attendance.panel.locked') : t('attendance.panel.qrSub')}
            disabled={methodsLocked || !qrSupported()}
            onClick={() => setScan(true)}
          />
        </div>
      </section>

      {scan && (
        <Card className="flex flex-col gap-3 p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold">{t('attendance.panel.qrTitle')}</h2>
            <button type="button" onClick={() => setScan(false)} aria-label={t('common.close')} className="grid size-8 place-items-center rounded-full hover:bg-surface-2">
              <X className="size-4" />
            </button>
          </div>
          <QrScanner onToken={(tok) => navigate(`/attendance/punch?t=${encodeURIComponent(tok)}`)} />
        </Card>
      )}

      {/* Asosiy tugma */}
      <button
        type="button"
        disabled={main.disabled}
        onClick={main.onClick}
        className={cn(
          'flex w-full flex-col items-center justify-center gap-0.5 rounded-card px-4 py-4 text-white shadow-card transition active:scale-[0.99] disabled:cursor-not-allowed',
          main.tone === 'go' && 'bg-gradient-to-r from-emerald-600 to-green-600 hover:brightness-110',
          main.tone === 'out' && 'bg-gradient-to-r from-rose-600 to-red-600 hover:brightness-110',
          main.tone === 'stop' && 'bg-gradient-to-r from-rose-900 to-red-800 disabled:opacity-90',
        )}
      >
        <span className="flex items-center gap-2 text-base font-semibold">
          {main.icon}
          {main.label}
        </span>
        {main.sub && <span className="text-xs text-white/80">{main.sub}</span>}
      </button>
      {punch.message && (
        <p role="alert" className="text-center text-sm text-danger">
          {punch.message}
        </p>
      )}
      {punch.data && !punch.isPending && (
        <p role="status" className="text-center text-sm font-medium text-success">
          {punch.data.action === 'check_in' ? t('attendance.my.doneIn', { time: fmtTime(punch.data.record.check_in_at) }) : t('attendance.my.doneOut', { time: fmtTime(punch.data.record.check_out_at) })}
        </p>
      )}
      {geo.status === 'ok' && (
        <p className="text-center text-[11px] text-muted">{t('attendance.panel.accuracy', { m: Math.round(geo.pos.accuracy) })}</p>
      )}
      <Link to="/attendance/issues/new" className="flex items-center justify-center gap-2 text-sm font-medium text-primary hover:underline">
        <FileWarning className="size-4" />
        {t('attendance.my.report')}
      </Link>

      {/* Oxirgi yozuvlar */}
      <Card className="overflow-hidden">
        <h2 className="px-5 pt-5 font-semibold">{t('attendance.my.recent')}</h2>
        <div className="overflow-x-auto">
          <table className="mt-3 w-full text-left text-sm">
            <thead className="border-y border-border text-xs text-muted">
              <tr>
                <th className="px-4 py-2.5 font-medium">{t('attendance.date')}</th>
                <th className="px-4 py-2.5 font-medium">{t('attendance.in')}</th>
                <th className="px-4 py-2.5 font-medium">{t('attendance.out')}</th>
                <th className="hidden px-4 py-2.5 font-medium sm:table-cell">{t('attendance.worked')}</th>
                <th className="px-4 py-2.5 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.recent.map((r) => (
                <tr key={r.id}>
                  <td className="px-4 py-2.5 tabular-nums">{formatDate(r.work_date, i18n.language)}</td>
                  <td className="px-4 py-2.5 tabular-nums">{fmtTime(r.check_in_at)}</td>
                  <td className="px-4 py-2.5 tabular-nums">{fmtTime(r.check_out_at)}</td>
                  <td className="hidden px-4 py-2.5 tabular-nums sm:table-cell">{r.check_out_at ? fmtMin(r.worked_minutes) : '—'}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1.5">
                      {r.late_minutes > 0 && <Badge tone="warning">{t('attendance.my.late', { m: r.late_minutes })}</Badge>}
                      {r.early_leave_minutes > 0 && <Badge tone="warning">{t('attendance.my.early', { m: r.early_leave_minutes })}</Badge>}
                      {r.is_manual && <Badge>{t('attendance.manual')}</Badge>}
                    </div>
                  </td>
                </tr>
              ))}
              {data.recent.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-5 py-8 text-center text-muted">
                    {t('common.empty')}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function TimeCard({ tone, icon, label, time, plan, note, planLabel }: { tone: 'in' | 'out'; icon: ReactNode; label: string; time: string | null; plan: string | null; note: string | null; planLabel: string }) {
  return (
    <div className={cn('rounded-card p-4 text-white shadow-card', tone === 'in' ? 'bg-gradient-to-br from-emerald-700 to-teal-800' : 'bg-gradient-to-br from-rose-700 to-red-900')}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-white/80">{label}</span>
        <span className="grid size-8 place-items-center rounded-full bg-white/15">{icon}</span>
      </div>
      <div className="mt-1 font-mono text-2xl font-semibold tabular-nums">{time ?? '—'}</div>
      <div className="text-[11px] text-white/70">
        {planLabel}: {plan ?? '—'}
      </div>
      {note && <div className="mt-1 inline-block rounded bg-black/20 px-1.5 py-0.5 text-[11px] font-medium">{note}</div>}
    </div>
  )
}

function MethodCard({ icon, title, sub, disabled, onClick }: { icon: ReactNode; title: string; sub: string; disabled?: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="flex flex-col items-start gap-1 rounded-card border border-border bg-surface p-4 text-left shadow-card transition hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-60"
    >
      <span className="grid size-9 place-items-center rounded-control bg-primary/10 text-primary">{icon}</span>
      <span className="text-sm font-semibold">{title}</span>
      <span className={cn('text-[11px]', disabled ? 'text-danger' : 'text-muted')}>{sub}</span>
    </button>
  )
}
