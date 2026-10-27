import { ArrowDownRight, ArrowUpRight } from 'lucide-react'
import { useId, useRef, useState, type ComponentType, type ReactNode } from 'react'

import { useLocation } from 'react-router-dom'

import { cn } from '../lib/cn'
import { routeTheme } from '../lib/navTheme'
import { Card } from './ui/Card'

/* Namuna (Skymetrics) uslubidagi grafik komponentlari: yumshoq yashil chiziq, kulrang taqqoslash chizig'i,
   punktir to'r, hover'da vertikal yo'riqchi va kichik tooltip. Hammasi SVG, qo'shimcha kutubxonasiz. */

/** Davr bo'yicha o'zgarish (%): yaxshi tomonga yashil, yomonga qizil. `value` null/0 bo'lsa ko'rsatilmaydi. */
export function Delta({ value, goodWhen = 'up', suffix = '%', className }: { value: number | null | undefined; goodWhen?: 'up' | 'down'; suffix?: string; className?: string }) {
  if (value === null || value === undefined || !Number.isFinite(value) || Math.abs(value) < 0.05) return null
  const good = goodWhen === 'up' ? value > 0 : value < 0
  const shown = Math.abs(value) >= 100 ? Math.round(value) : Math.round(value * 10) / 10
  return (
    <span className={cn('inline-flex items-center rounded-md px-1.5 py-0.5 text-[11px] font-medium tabular-nums', good ? 'bg-success/12 text-success' : 'bg-danger/12 text-danger', className)} title={good ? '↑' : '↓'}>
      {value > 0 ? '+' : '−'}
      {Math.abs(shown)}
      {suffix}
    </span>
  )
}

/** KPI karta: yuqorida nom va o'zgarish belgisi, katta mono raqam, pastda izoh. */
export function KpiCard({ label, value, delta, hint, trend, icon: Icon, color }: { label: string; value: string; delta?: ReactNode; hint?: string; trend?: 'up' | 'down' | null; icon?: ComponentType<{ className?: string }>; color?: string }) {
  const { pathname } = useLocation()
  return (
    <Card className="relative flex flex-col overflow-hidden p-4" style={{ ['--gc' as string]: color ?? routeTheme(pathname)?.color ?? 'var(--c-blue)' }}>
      <span aria-hidden className="absolute inset-x-0 top-0 h-[3px]" style={{ background: 'var(--gc)' }} />
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          {Icon && (
            <span className="grid size-8 place-items-center rounded-lg bg-[color-mix(in_oklab,var(--gc)_14%,transparent)] text-(--gc)">
              <Icon className="size-4" />
            </span>
          )}
          <span className="text-xs text-muted">{label}</span>
        </div>
        {delta}
      </div>
      <div className="mt-3 flex items-center gap-2 font-mono text-[26px] font-medium leading-none tracking-tight tabular-nums">
        {value}
        {trend && (
          <span className={cn('grid size-4 place-items-center rounded-full', trend === 'up' ? 'bg-success/15 text-success' : 'bg-danger/15 text-danger')}>
            {trend === 'up' ? <ArrowUpRight className="size-3" /> : <ArrowDownRight className="size-3" />}
          </span>
        )}
      </div>
      {hint && <div className="mt-2 text-[11px] text-muted">{hint}</div>}
    </Card>
  )
}

function niceMax(v: number): number {
  if (v <= 0) return 1
  const exp = Math.pow(10, Math.floor(Math.log10(v)))
  const f = v / exp
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * exp
}

const dmy = (iso: string) => iso.split('-').reverse().join('.')

export interface Series {
  key: string
  label: string
  color: string
  values: number[]
  /** Kulrang taqqoslash chizig'i: yupqaroq, maydonsiz */
  muted?: boolean
}

/** Silliq (monoton kubik) yo'l: nuqtalar orasida egilgan chiziq, tebranishsiz. */
function smooth(pts: [number, number][]): string {
  if (pts.length < 2) return pts.length ? `M${pts[0][0]},${pts[0][1]}` : ''
  const n = pts.length
  const dx: number[] = []
  const m: number[] = []
  for (let i = 0; i < n - 1; i++) {
    dx.push(pts[i + 1][0] - pts[i][0])
    m.push((pts[i + 1][1] - pts[i][1]) / dx[i])
  }
  const t: number[] = [m[0]]
  for (let i = 1; i < n - 1; i++) t.push(m[i - 1] * m[i] <= 0 ? 0 : (m[i - 1] + m[i]) / 2)
  t.push(m[n - 2])
  let d = `M${pts[0][0]},${pts[0][1]}`
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i] / 3
    d += ` C${pts[i][0] + h},${pts[i][1] + t[i] * h} ${pts[i + 1][0] - h},${pts[i + 1][1] - t[i + 1] * h} ${pts[i + 1][0]},${pts[i + 1][1]}`
  }
  return d
}

/** Chiziqli grafik (ko'p qatorli): yashil asosiy chiziq + yengil maydon, kulrang taqqoslash; hover'da yo'riqchi va tooltip. */
export function LineChart({ labels, series, height = 220, format = (v: number) => String(Math.round(v * 10) / 10), label }: { labels: string[]; series: Series[]; height?: number; format?: (v: number) => string; label: string }) {
  const gid = useId().replace(/:/g, '')
  const box = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<number | null>(null)
  const W = 800
  const pad = { l: 44, r: 12, t: 12, b: 26 }
  const n = labels.length
  const max = niceMax(Math.max(0, ...series.flatMap((s) => s.values)))
  const x = (i: number) => pad.l + (n <= 1 ? (W - pad.l - pad.r) / 2 : (i * (W - pad.l - pad.r)) / (n - 1))
  const y = (v: number) => pad.t + (height - pad.t - pad.b) * (1 - v / max)
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => max * f)
  const step = Math.max(1, Math.ceil(n / 7))
  const move = (clientX: number) => {
    const r = box.current?.getBoundingClientRect()
    if (!r || n === 0) return
    const px = ((clientX - r.left) / r.width) * W
    let best = 0
    for (let i = 1; i < n; i++) if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i
    setHover(best)
  }
  return (
    <div ref={box} className="relative mt-4 select-none" onPointerMove={(e) => move(e.clientX)} onPointerLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${height}`} className="block w-full" role="img" aria-label={label}>
        <defs>
          {series.filter((s) => !s.muted).map((s) => (
            <linearGradient key={s.key} id={`${gid}-${s.key}`} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity="0.16" />
              <stop offset="100%" stopColor={s.color} stopOpacity="0" />
            </linearGradient>
          ))}
        </defs>
        {ticks.map((tk, i) => (
          <g key={i}>
            <line x1={pad.l} x2={W - pad.r} y1={y(tk)} y2={y(tk)} stroke="var(--border-strong)" strokeOpacity={i === 0 ? 0.9 : 0.55} strokeDasharray={i === 0 ? undefined : '3 5'} />
            <text x={pad.l - 8} y={y(tk) + 3.5} textAnchor="end" fontSize="10.5" fill="var(--muted)" fontFamily="var(--font-mono)">{format(tk)}</text>
          </g>
        ))}
        {labels.map((l, i) =>
          i % step === 0 || i === n - 1 ? (
            <text key={l} x={x(i)} y={height - 7} textAnchor="middle" fontSize="10.5" fill="var(--muted)">{l.slice(8)}</text>
          ) : null,
        )}
        {[...series].sort((a, b) => Number(!!b.muted) - Number(!!a.muted)).map((s) => {
          const pts: [number, number][] = s.values.map((v, i) => [x(i), y(v)])
          const d = smooth(pts)
          return (
            <g key={s.key}>
              {!s.muted && pts.length > 1 && <path d={`${d} L${pts[pts.length - 1][0]},${y(0)} L${pts[0][0]},${y(0)} Z`} fill={`url(#${gid}-${s.key})`} />}
              <path d={d} fill="none" stroke={s.color} strokeWidth={s.muted ? 1.5 : 2} strokeLinecap="round" strokeLinejoin="round" />
              {pts.length === 1 && <circle cx={pts[0][0]} cy={pts[0][1]} r="3" fill={s.color} />}
            </g>
          )
        })}
        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={y(0)} stroke="var(--border-strong)" />
            {series.map((s) => (
              <circle key={s.key} cx={x(hover)} cy={y(s.values[hover] ?? 0)} r="4" fill="var(--surface)" stroke={s.color} strokeWidth="2" />
            ))}
          </g>
        )}
      </svg>
      {hover !== null && (
        <div
          className="pointer-events-none absolute top-1 z-10 min-w-32 rounded-lg bg-surface px-3 py-2 text-xs shadow-pop"
          style={{ left: `${(x(hover) / W) * 100}%`, transform: `translateX(${hover > n * 0.65 ? 'calc(-100% - 10px)' : '10px'})` }}
        >
          <div className="mb-1 text-[11px] text-muted">{dmy(labels[hover])}</div>
          {series.map((s) => (
            <div key={s.key} className="flex items-center justify-between gap-4">
              <span className="inline-flex items-center gap-1.5 text-muted">
                <span className="size-1.5 rounded-full" style={{ background: s.color }} />
                {s.label}
              </span>
              <span className="font-mono font-medium tabular-nums">{format(s.values[hover] ?? 0)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

/** Ustunli grafik: kulrang ustunlar, ustiga borilgani yashil (namunadagi "Net revenue" kabi). */
export function BarChart({ labels, values, height = 180, color = 'var(--chart-ok)', format = (v: number) => String(v), name, label }: { labels: string[]; values: number[]; height?: number; color?: string; format?: (v: number) => string; name: string; label: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const W = 800
  const pad = { l: 36, r: 8, t: 10, b: 24 }
  const n = labels.length
  const max = niceMax(Math.max(0, ...values))
  const bw = (W - pad.l - pad.r) / Math.max(n, 1)
  const y = (v: number) => pad.t + (height - pad.t - pad.b) * (1 - v / max)
  const step = Math.max(1, Math.ceil(n / 12))
  return (
    <div className="relative mt-4" onPointerLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${height}`} className="block w-full" role="img" aria-label={label}>
        {[0, 0.5, 1].map((f, i) => (
          <g key={i}>
            <line x1={pad.l} x2={W - pad.r} y1={y(max * f)} y2={y(max * f)} stroke="var(--border-strong)" strokeOpacity={i === 0 ? 0.9 : 0.55} strokeDasharray={i === 0 ? undefined : '3 5'} />
            <text x={pad.l - 7} y={y(max * f) + 3.5} textAnchor="end" fontSize="10.5" fill="var(--muted)" fontFamily="var(--font-mono)">{format(max * f)}</text>
          </g>
        ))}
        {values.map((v, i) => (
          <g key={labels[i]} onPointerEnter={() => setHover(i)}>
            <rect x={pad.l + i * bw} y={pad.t} width={bw} height={height - pad.t - pad.b} fill="transparent" />
            <rect x={pad.l + i * bw + bw * 0.18} y={y(v)} width={bw * 0.64} height={Math.max(0, height - pad.b - y(v))} rx={2} fill={hover === i ? color : 'var(--chart-muted)'} fillOpacity={hover === i ? 1 : 0.55} style={{ transition: 'fill 120ms' }} />
            {(i % step === 0 || i === n - 1) && <text x={pad.l + i * bw + bw / 2} y={height - 7} textAnchor="middle" fontSize="10.5" fill="var(--muted)">{labels[i].slice(8)}</text>}
          </g>
        ))}
      </svg>
      {hover !== null && (
        <div className="pointer-events-none absolute top-0 z-10 rounded-lg bg-surface px-3 py-2 text-xs shadow-pop" style={{ left: `${((pad.l + (hover + 0.5) * bw) / W) * 100}%`, transform: 'translateX(-50%)' }}>
          <div className="text-[11px] text-muted">{dmy(labels[hover])}</div>
          <div className="font-mono font-medium tabular-nums">
            {format(values[hover])} <span className="font-sans text-muted">{name}</span>
          </div>
        </div>
      )}
    </div>
  )
}

/** Yarim doira ko'rsatkich (gauge): yashil yoy, markazda katta raqam, pastda izoh. */
export function Gauge({ value, display, caption, label, tone = 'var(--chart-ok)' }: { value: number | null; display: string; caption: string; label: string; tone?: string }) {
  const R = 92
  const C = Math.PI * R
  const v = Math.max(0, Math.min(1, value ?? 0))
  return (
    <div className="relative mx-auto w-full max-w-[280px]">
      <svg viewBox="0 0 220 124" className="block w-full" role="img" aria-label={`${label}: ${display}`}>
        <path d="M18,112 A92,92 0 0 1 202,112" fill="none" stroke="var(--surface-3)" strokeWidth="11" strokeLinecap="round" />
        <path d="M18,112 A92,92 0 0 1 202,112" fill="none" stroke={tone} strokeWidth="11" strokeLinecap="round" strokeDasharray={`${C * v} ${C}`} style={{ transition: 'stroke-dasharray 600ms cubic-bezier(.2,.7,.2,1)' }} />
      </svg>
      <div className="absolute inset-x-0 bottom-1 text-center">
        <div className="font-mono text-[30px] font-medium leading-none tracking-tight tabular-nums">{display}</div>
        <div className="mt-1.5 text-xs text-muted">{caption}</div>
      </div>
    </div>
  )
}

/** Ulushlar chizig'i + ro'yxat: yupqa segmentlarga bo'lingan bar va har bir qator uchun nuqta, nom, qiymat. */
export function SegmentBar({ items }: { items: { key: string; label: string; value: number; color: string }[] }) {
  const total = items.reduce((a, b) => a + b.value, 0)
  return (
    <div>
      <div className="flex h-1.5 gap-0.5 overflow-hidden rounded-full" role="img" aria-label={items.map((i) => `${i.label}: ${i.value}`).join(', ')}>
        {total === 0 ? <div className="h-full flex-1 rounded-full bg-surface-3" /> : items.filter((i) => i.value > 0).map((i) => <div key={i.key} className="h-full rounded-full" style={{ flex: i.value, background: i.color }} />)}
      </div>
      <ul className="mt-4 divide-y divide-border text-[13px]">
        {items.map((i) => (
          <li key={i.key} className="flex items-center justify-between gap-3 py-2">
            <span className="inline-flex items-center gap-2">
              <span className="size-2 rounded-full" style={{ background: i.color }} />
              {i.label}
            </span>
            <span className="font-mono tabular-nums text-muted">
              {i.value}
              {total > 0 && <span className="ml-2 text-[11px]">{Math.round((i.value / total) * 100)}%</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
