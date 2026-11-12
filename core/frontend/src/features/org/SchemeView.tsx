import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Maximize2, Minimize2, Minus, Pencil, Plus, RotateCcw, ScanSearch, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { Avatar } from '../employees/Avatar'
import type { OrgStructureRow } from './api'

interface P {
  id: number | null
  full_name: string
  photo: boolean
  branches: number
}
export type SchemePos = Pos
export type SchemeDept = Dept

interface Pos {
  id: number
  name: string
  department_id: number | null
  parent_id: number | null
  slots: number
  is_head: boolean
  yqm: string | null
  occupants: P[]
}
interface Dept {
  id: number
  name: string
  parent_id: number | null
  reports_to_position_id: number | null
  yqm: string | null
  color: string | null
  headcount: number
}
interface Br {
  id: number
  number: number | null
  name: string
  department_id: number | null
  manager: string | null
  employees: (P & { position: string | null })[]
}

interface Scheme {
  company: string
  structure: OrgStructureRow | null
  departments: Dept[]
  positions: Pos[]
  branches?: Br[]
}

const MAX_SHOWN = 4

type Pick = ((n: { kind: 'dept'; d: Dept } | { kind: 'pos'; p: Pos }) => void) | undefined
// tugunni bosish: tugma yoki havola bosilmagan bo'lsa tanlaydi
const clickable = (fn: () => void) => (e: { target: EventTarget }) => !(e.target as HTMLElement).closest('a,button') && fn()

type Edit = { onAdd: (kind: 'dept' | 'pos', target: { dept?: Dept; pos?: Pos }) => void; onRemove: (kind: 'dept' | 'pos', id: number, name: string) => void } | null

/** Tahrirlash rejimida kartochka ostidagi kichik tugmalar: qo'shish va o'chirish. */
function EditBar({ edit, kind, dept, pos, name, id }: { edit: Edit; kind: 'dept' | 'pos'; dept?: Dept; pos?: Pos; name: string; id: number }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  if (!edit) return null
  return (
    <div className="relative mt-1 flex justify-center gap-1">
      <button type="button" title={t('scheme.add')} aria-label={t('scheme.add')} onClick={() => setOpen((v) => !v)} className="grid size-6 place-items-center rounded-full bg-primary text-white shadow-card hover:brightness-110">
        <Plus className="size-3.5" />
      </button>
      <button type="button" title={t('common.delete')} aria-label={t('common.delete')} onClick={() => edit.onRemove(kind, id, name)} className="grid size-6 place-items-center rounded-full bg-danger text-white shadow-card hover:brightness-110">
        <X className="size-3.5" />
      </button>
      {open && (
        <div className="absolute top-7 z-20 flex w-48 flex-col rounded-lg border border-border bg-surface p-1 text-left text-xs text-text shadow-pop">
          <button type="button" className="rounded px-2 py-1.5 hover:bg-surface-2" onClick={() => (setOpen(false), edit.onAdd('pos', { dept, pos }))}>
            + {t(kind === 'pos' ? 'scheme.addSubPos' : 'scheme.addPos')}
          </button>
          <button type="button" className="rounded px-2 py-1.5 hover:bg-surface-2" onClick={() => (setOpen(false), edit.onAdd('dept', { dept, pos }))}>
            + {t(kind === 'pos' ? 'scheme.addDeptUnderPos' : 'scheme.addSubDept')}
          </button>
        </div>
      )}
    </div>
  )
}

function Person({ p }: { p: P }) {
  const { t } = useTranslation()
  const body = (
    <span className="flex w-full items-center gap-1.5 rounded-lg bg-surface-2 px-1.5 py-1 text-left text-[11px] leading-tight">
      {p.id ? <Avatar id={p.id} name={p.full_name} hasPhoto={p.photo} size={22} className="rounded-full" /> : <span className="size-[22px] shrink-0 rounded-full bg-surface-3" />}
      <span className="min-w-0">
        <span className="block truncate font-medium">{p.full_name}</span>
        {p.branches > 0 && <span className="block text-[10px] text-muted">{t('scheme.pharmacies', { n: p.branches })}</span>}
      </span>
    </span>
  )
  return p.id ? <Link to={`/employees/${p.id}`} className="block w-full hover:opacity-80">{body}</Link> : body
}

/** Lavozim kartochkasi: nomi, egalari (rasm bilan), bo'sh o'rinlar — VAKANSIYA. */
function PositionCard({ p, color, edit, pick }: { p: Pos; color: string | null; edit: Edit; pick: Pick }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const occ = p.occupants
  const vacant = p.slots > 0 ? Math.max(0, p.slots - occ.length) : 0
  const shown = open ? occ : occ.slice(0, MAX_SHOWN)
  return (
    <div onClick={pick && clickable(() => pick({ kind: 'pos', p }))} className={`flex w-48 flex-col gap-1.5 rounded-xl border border-border bg-surface p-2 text-center shadow-card ${pick ? 'cursor-pointer hover:ring-2 hover:ring-primary/40' : ''}`} style={color ? { borderTop: `3px solid ${color}` } : undefined}>
      <div className={`text-[12px] font-semibold leading-snug ${p.is_head ? 'text-primary' : ''}`}>{p.name}</div>
      {p.slots > 1 && <div className="text-[10px] text-muted">{t('scheme.slots', { busy: occ.length, total: p.slots })}</div>}
      {p.slots === 0 && occ.length > 0 && <div className="text-[10px] text-muted">{t('scheme.peopleN', { n: occ.length })}</div>}
      <div className="flex flex-col gap-1">
        {shown.map((x, i) => (
          <Person key={x.id ?? `${x.full_name}-${i}`} p={x} />
        ))}
        {occ.length > MAX_SHOWN && (
          <button type="button" onClick={() => setOpen((v) => !v)} className="text-[10px] font-semibold text-primary hover:underline">
            {open ? t('scheme.less') : t('scheme.more', { n: occ.length - MAX_SHOWN })}
          </button>
        )}
      </div>
      {vacant > 0 && <span className="self-center rounded-md bg-orange-500 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">{vacant > 1 ? t('scheme.vacancyN', { n: vacant }) : t('scheme.vacancy')}</span>}
      {p.slots > 0 && occ.length === 0 && vacant === 0 && <span className="self-center rounded-md bg-orange-500 px-2 py-0.5 text-[10px] font-bold uppercase text-white">{t('scheme.vacancy')}</span>}
      {p.yqm && (
        <p className="text-left text-[10px] leading-snug text-muted">
          <b className="text-text">{t('scheme.yqm')}:</b> {p.yqm}
        </p>
      )}
      <EditBar edit={edit} kind="pos" pos={p} name={p.name} id={p.id} />
    </div>
  )
}

/** Filial kartochkasi: raqami, nomi, mudiri va filialda ishlayotgan xodimlar. */
function BranchCard({ b }: { b: Br }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const shown = open ? b.employees : b.employees.slice(0, MAX_SHOWN)
  return (
    <div className="flex w-48 flex-col gap-1.5 rounded-xl border border-orange-300 bg-orange-50 p-2 text-center shadow-card dark:border-orange-900 dark:bg-orange-950/30">
      <Link to={`/branches/${b.id}/edit`} className="text-[12px] font-semibold leading-snug text-orange-700 hover:underline dark:text-orange-300">
        {b.number ? `${b.number} · ` : ''}
        {b.name}
      </Link>
      {b.manager && <div className="text-[10px] text-muted">{t('scheme.manager')}: {b.manager}</div>}
      <div className="text-[10px] text-muted">{t('scheme.peopleN', { n: b.employees.length })}</div>
      <div className="flex flex-col gap-1">
        {shown.map((x, i) => (
          <div key={x.id ?? i} className="flex flex-col">
            <Person p={x} />
            {x.position && <span className="text-left text-[9px] text-muted">{x.position}</span>}
          </div>
        ))}
        {b.employees.length > MAX_SHOWN && (
          <button type="button" onClick={() => setOpen((v) => !v)} className="text-[10px] font-semibold text-primary hover:underline">
            {open ? t('scheme.less') : t('scheme.more', { n: b.employees.length - MAX_SHOWN })}
          </button>
        )}
      </div>
    </div>
  )
}

function DeptCard({ d, edit, pick }: { d: Dept; edit: Edit; pick: Pick }) {
  const { t } = useTranslation()
  return (
    <div onClick={pick && clickable(() => pick({ kind: 'dept', d }))} className={`w-52 rounded-xl px-3 py-2 text-center text-white shadow-card ${pick ? 'cursor-pointer hover:ring-2 hover:ring-white/70' : ''}`} style={{ background: d.color ?? 'var(--color-primary, #1f3a68)' }}>
      <div className="text-[12px] font-bold uppercase tracking-wide">{d.name}</div>
      <div className="text-[10px] opacity-85">{t('scheme.peopleN', { n: d.headcount })}</div>
      {d.yqm && (
        <p className="mt-1 text-left text-[10px] leading-snug opacity-90">
          <b>{t('scheme.yqm')}:</b> {d.yqm}
        </p>
      )}
      <EditBar edit={edit} kind="dept" dept={d} name={d.name} id={d.id} />
    </div>
  )
}

/** Tashkiliy tuzilma shajarasi (org.xlsx kabi). Bo'lim, lavozim yoki xodim qo'shilganda avtomatik yangilanadi. */
export function SchemeView({ onSelect }: { onSelect?: (n: { kind: 'dept'; d: Dept } | { kind: 'pos'; p: Pos }) => void } = {}) {
  const { t } = useTranslation()
  const canManage = useCan()('org.manage')
  const structures = useQuery({ queryKey: ['org', 'structures'], queryFn: () => api<{ items: OrgStructureRow[] }>('/api/v1/org/structures') })
  const [selected, setSelected] = useState('')
  const defaultId = structures.data?.items.find((x) => x.is_default)?.id
  const structureId = Number(selected) || defaultId
  const q = useQuery({ queryKey: ['org', 'scheme', structureId], queryFn: () => api<Scheme>(`/api/v1/org/scheme${structureId ? `?structure_id=${structureId}` : ''}`), enabled: !!structures.data })
  const [zoom, setZoom] = useState(0.85)
  const box = useRef<HTMLDivElement>(null)
  const inner = useRef<HTMLDivElement>(null)
  const wrap = useRef<HTMLDivElement>(null)
  const [full, setFull] = useState(false)
  const [editing, setEditing] = useState(false)
  const qc = useQueryClient()
  const confirm = useConfirm()
  const toast = useToast()
  const d = q.data

  /** Butun sxemani ko'rinadigan maydonga sig'diradi. */
  const fit = () => {
    const el = box.current
    const tree = inner.current
    if (!el || !tree) return
    const r = tree.getBoundingClientRect()
    const cur = Number(tree.style.zoom || 1) || 1
    const w = r.width / cur
    const h = r.height / cur
    if (!w || !h) return
    const z = Math.min(1, (el.clientWidth - 32) / w, (el.clientHeight - 32) / h)
    setZoom(Math.max(0.15, +z.toFixed(2)))
    el.scrollLeft = 0
    el.scrollTop = 0
  }
  useEffect(() => {
    const id = requestAnimationFrame(() => fit())
    return () => cancelAnimationFrame(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [d, full])
  useEffect(() => {
    const on = () => setFull(document.fullscreenElement === wrap.current)
    document.addEventListener('fullscreenchange', on)
    return () => document.removeEventListener('fullscreenchange', on)
  }, [])
  const toggleFull = () => (document.fullscreenElement ? void document.exitFullscreen() : void wrap.current?.requestFullscreen())

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ['org'] })
    void qc.invalidateQueries({ queryKey: ['recruit'] })
  }
  const fail = (e: unknown) => toast.push({ title: errorText(t, e), tone: 'danger' })
  const edit: Edit = editing
    ? {
        onAdd: async (kind, { dept, pos }) => {
          const name = window.prompt(t(kind === 'dept' ? 'scheme.newDeptName' : 'scheme.newPosName'))?.trim()
          if (!name) return
          try {
            if (kind === 'dept') {
              await send('POST', '/api/v1/org/departments', { name, parent_id: dept?.id ?? pos?.department_id ?? null, reports_to_position_id: pos?.id ?? null, create_default_positions: true })
            } else {
              await send('POST', '/api/v1/org/positions', { name, department_id: dept?.id ?? pos?.department_id ?? null, parent_id: pos?.id ?? null, slots: 1 })
            }
            toast.push({ title: t(kind === 'dept' ? 'scheme.deptAdded' : 'scheme.posAdded', { name }), tone: 'success' })
            refresh()
          } catch (e) {
            fail(e)
          }
        },
        onRemove: async (kind, id, name) => {
          if (!(await confirm({ title: t('common.delete'), body: t(kind === 'dept' ? 'scheme.removeDeptQ' : 'scheme.removePosQ', { name }), danger: true, confirmLabel: t('common.delete') }))) return
          try {
            await send('DELETE', kind === 'dept' ? `/api/v1/org/departments/${id}?detach=true` : `/api/v1/org/positions/${id}`)
            toast.push({ title: t('org.deleted'), tone: 'success' })
            refresh()
          } catch (e) {
            fail(e)
          }
        },
      }
    : null

  const idx = useMemo(() => {
    if (!d) return null
    const deptById = new Map(d.departments.map((x) => [x.id, x]))
    const posById = new Map(d.positions.map((x) => [x.id, x]))
    const childPos = new Map<number, Pos[]>()
    const rootPosOfDept = new Map<number, Pos[]>()
    for (const p of d.positions) {
      if (p.parent_id && posById.has(p.parent_id)) childPos.set(p.parent_id, [...(childPos.get(p.parent_id) ?? []), p])
      else if (p.department_id) rootPosOfDept.set(p.department_id, [...(rootPosOfDept.get(p.department_id) ?? []), p])
    }
    const deptsUnderPos = new Map<number, Dept[]>()
    const deptsUnderDept = new Map<number, Dept[]>()
    const rootDepts: Dept[] = []
    for (const x of d.departments) {
      if (x.reports_to_position_id && posById.has(x.reports_to_position_id)) deptsUnderPos.set(x.reports_to_position_id, [...(deptsUnderPos.get(x.reports_to_position_id) ?? []), x])
      else if (x.parent_id && deptById.has(x.parent_id)) deptsUnderDept.set(x.parent_id, [...(deptsUnderDept.get(x.parent_id) ?? []), x])
      else rootDepts.push(x)
    }
    const general = d.positions.filter((p) => !p.department_id && !p.parent_id)
    return { deptById, childPos, rootPosOfDept, deptsUnderPos, deptsUnderDept, rootDepts, general }
  }, [d])


  if (!d || !idx) return <Skeleton className="h-96" />

  const isLeafPos = (p: Pos) => !(idx.childPos.get(p.id)?.length || idx.deptsUnderPos.get(p.id)?.length)
  // Bolalar: hammasi oxirgi (bargli) lavozim va 3 tadan ko'p bo'lsa — Excel kabi ustun bo'lib pastma-past, aks holda yonma-yon
  const renderKids = (kids: { k: string; n: ReactNode; leaf: boolean }[]): ReactNode => {
    if (!kids.length) return null
    // Oxirgi (bargli) lavozimlar 2 tadan ko'p bo'lsa — Excel kabi bitta ustunda pastma-past; qolganlari yonma-yon
    const leaves = kids.filter((c) => c.leaf)
    const branches = kids.filter((c) => !c.leaf)
    const stack = leaves.length > 2
    const items: { k: string; n: ReactNode }[] = stack
      ? [
          ...branches,
          {
            k: 'leaf-stack',
            n: (
              <div className="leaf-stack">
                {leaves.map((c) => (
                  <div key={c.k}>{c.n}</div>
                ))}
              </div>
            ),
          },
        ]
      : kids
    return (
      <ul>
        {items.map((c) => (
          <li key={c.k}>{c.n}</li>
        ))}
      </ul>
    )
  }

  const renderPos = (p: Pos, seen: Set<number>): ReactNode => {
    if (seen.has(p.id)) return null
    const next = new Set(seen).add(p.id)
    const color = p.department_id ? (idx.deptById.get(p.department_id)?.color ?? null) : null
    const kids = [...(idx.childPos.get(p.id) ?? []).map((c) => ({ k: `p${c.id}`, n: renderPos(c, next), leaf: isLeafPos(c) })), ...(idx.deptsUnderPos.get(p.id) ?? []).map((x) => ({ k: `d${x.id}`, n: renderDept(x, next), leaf: false }))]
    return (
      <>
        <PositionCard p={p} color={color} edit={edit} pick={onSelect} />
        {renderKids(kids)}
      </>
    )
  }

  const renderDept = (x: Dept, seen: Set<number>): ReactNode => {
    const kids = [
      ...(idx.rootPosOfDept.get(x.id) ?? []).map((p) => ({ k: `p${p.id}`, n: renderPos(p, seen), leaf: isLeafPos(p) })),
      ...(idx.deptsUnderDept.get(x.id) ?? []).map((c) => ({ k: `d${c.id}`, n: renderDept(c, seen), leaf: false })),
      ...(d.branches ?? []).filter((b) => b.department_id === x.id).map((b) => ({ k: `b${b.id}`, n: <BranchCard b={b} />, leaf: true })),
    ]
    return (
      <>
        <DeptCard d={x} edit={edit} pick={onSelect} />
        {renderKids(kids)}
      </>
    )
  }

  const deptIds = new Set(d.departments.map((x) => x.id))
  const looseBranches = (d.branches ?? []).filter((b) => !b.department_id || !deptIds.has(b.department_id))
  const tops = [
    ...idx.rootDepts.map((x) => ({ k: `d${x.id}`, n: renderDept(x, new Set()) })),
    ...idx.general.map((p) => ({ k: `p${p.id}`, n: renderPos(p, new Set()) })),
    ...(looseBranches.length
      ? [
          {
            k: 'branches',
            n: (
              <>
                <div className="w-52 rounded-xl bg-orange-500 px-3 py-2 text-center text-white shadow-card">
                  <div className="text-[12px] font-bold uppercase tracking-wide">{t('scheme.branchesNode')}</div>
                  <div className="text-[10px] opacity-85">{t('scheme.branchesN', { n: looseBranches.length })}</div>
                </div>
                {renderKids(looseBranches.map((b) => ({ k: `b${b.id}`, n: <BranchCard b={b} />, leaf: true })))}
              </>
            ),
          },
        ]
      : []),
  ]

  return (
    <div ref={wrap} className={`relative rounded-card border border-border bg-gradient-to-b from-sky-50/60 to-transparent dark:from-sky-950/20 ${full ? 'flex flex-col bg-bg' : ''}`}>
      <div className="flex flex-wrap items-center gap-3 border-b border-border p-3 pr-28">
        <label htmlFor="org-structure" className="text-sm font-medium">{t('org.structureSelect')}</label>
        <Select id="org-structure" className="w-auto min-w-56" value={structureId ? String(structureId) : ''} onChange={(e) => setSelected(e.target.value)}>
          {(structures.data?.items ?? []).map((x) => <option key={x.id} value={x.id}>{x.name}{x.is_default ? ` · ${t('org.defaultStructure')}` : ''}</option>)}
        </Select>
        {canManage && <Link to="/org/structures"><Button variant="outline" className="h-9">{t('org.manageStructures')}</Button></Link>}
        {d.structure?.description && <span className="text-xs text-muted">{d.structure.description}</span>}
      </div>
      <div className="flex flex-wrap items-center justify-end gap-2 border-b border-border px-3 py-2">
      {canManage && (
        <Button variant={editing ? 'primary' : 'outline'} className="h-8" onClick={() => setEditing((v) => !v)}>
          <Pencil className="size-4" />
          {t(editing ? 'scheme.editDone' : 'scheme.edit')}
        </Button>
      )}
      {editing && <span className="text-xs text-muted">{t('scheme.editHint')}</span>}
      <div className="flex items-center gap-1 rounded-control border border-border bg-surface p-1 shadow-card">
        <button type="button" title={t('scheme.fit')} aria-label={t('scheme.fit')} onClick={fit} className="rounded p-1 hover:bg-surface-2">
          <ScanSearch className="size-4" />
        </button>
        <button type="button" aria-label={t('scheme.zoomOut')} onClick={() => setZoom((z) => Math.max(0.15, +(z - 0.1).toFixed(2)))} className="rounded p-1 hover:bg-surface-2">
          <Minus className="size-4" />
        </button>
        <span className="w-10 text-center text-xs tabular-nums">{Math.round(zoom * 100)}%</span>
        <button type="button" aria-label={t('scheme.zoomIn')} onClick={() => setZoom((z) => Math.min(1.4, +(z + 0.1).toFixed(2)))} className="rounded p-1 hover:bg-surface-2">
          <Plus className="size-4" />
        </button>
        <button type="button" aria-label={t('scheme.zoomReset')} onClick={() => setZoom(1)} className="rounded p-1 hover:bg-surface-2">
          <RotateCcw className="size-4" />
        </button>
        <button type="button" title={t('scheme.fullscreen')} aria-label={t('scheme.fullscreen')} onClick={toggleFull} className="rounded p-1 hover:bg-surface-2">
          {full ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}
        </button>
      </div>
      </div>
      <div ref={box} className={`overflow-auto p-4 ${full ? 'flex-1' : ''}`} style={full ? undefined : { height: 'calc(100vh - 230px)', minHeight: 420 }}>
        <div ref={inner} className="org-tree scheme mx-auto w-max origin-top-left" style={{ zoom }}>
          <ul>
            <li>
              <div className="rounded-2xl border border-sky-200 bg-white px-8 py-3 text-center shadow-card dark:border-sky-900 dark:bg-[#141b2b]">
                <div className="text-xl font-extrabold tracking-wide text-[#1f3a68] dark:text-sky-200">{d.company}</div>
                <div className="text-xs text-muted">{t('scheme.company')}</div>
                {edit && (
                  <button type="button" onClick={() => edit.onAdd('dept', {})} className="mt-1 rounded-full bg-primary px-2 py-0.5 text-[11px] text-white">
                    + {t('scheme.addTopDept')}
                  </button>
                )}
              </div>
              {tops.length > 0 && (
                <ul>
                  {tops.map((c) => (
                    <li key={c.k}>{c.n}</li>
                  ))}
                </ul>
              )}
            </li>
          </ul>
        </div>
      </div>
    </div>
  )
}
