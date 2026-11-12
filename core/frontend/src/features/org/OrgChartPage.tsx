import { useQuery } from '@tanstack/react-query'
import { ChevronDown, ChevronRight, Pencil, TriangleAlert } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { initials } from '../../lib/format'
import { useCan } from '../auth/useAuth'
import { type DepartmentNode, type OrgTree } from './api'
import { InsightCharts, InsightKpis, InsightTabs, InsightsLoading } from './OrgInsights'
import { useInsights } from './orgInsightsApi'
import { OrgSidePanel, type PanelKey, type Selected } from './OrgSidePanel'
import { SchemeView } from './SchemeView'

const AUTO_EXPAND_DEPTH = 2

export function OrgChartPage() {
  const { t, i18n } = useTranslation()
  const can = useCan()
  const [view, setView] = useState<'scheme' | 'tree' | 'list'>('scheme')
  const [panel, setPanel] = useState<PanelKey | null>(null)
  const [picked, setPicked] = useState<Selected>(null)
  const [selected, setSelected] = useState<DepartmentNode | null>(null)
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set())

  const tree = useQuery({ queryKey: ['org', 'tree'], queryFn: () => api<OrgTree>('/api/v1/org/tree') })

  const toggle = (id: number) =>
    setCollapsed((s) => {
      const n = new Set(s)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })

  const data = tree.data
  const scroller = useRef<HTMLDivElement>(null)

  // Keng daraxtni boshida markazga keltiramiz (ildiz ko'rinsin)
  useEffect(() => {
    const el = scroller.current
    if (el && view === 'tree') el.scrollLeft = Math.max(0, (el.scrollWidth - el.clientWidth) / 2)
  }, [data, view])
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'

  return (
    <div className="mx-auto flex max-w-[110rem] flex-col gap-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{t('org.chartTitle')}</h1>
          <p className="mt-1 text-sm text-muted">{t('org.chartSubtitle')}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex rounded-control bg-(--seg-bg) p-0.5 text-[13px]">
            {(['scheme', 'tree', 'list'] as const).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={view === v ? 'rounded-lg bg-(--seg-on) px-3 py-1.5 font-medium text-text shadow-card' : 'rounded-lg px-3 py-1.5 text-muted transition-colors hover:text-text'}
              >
                {t(`org.view.${v}`)}
              </button>
            ))}
          </div>
          {(['departments', 'positions', 'duties', 'structures', 'branches'] as const).map((k) => (
            <Button key={k} variant={panel === k ? 'primary' : 'outline'} onClick={() => setPanel(k)}>
              {k === 'departments' && <Pencil className="size-4" />}
              {t(`org.panel.${k}`)}
            </Button>
          ))}
        </div>
      </div>

      <CompanyOverview />

      {tree.isLoading && <Skeleton className="h-64" />}

      {data && data.roots.length === 0 && (
        <Card className="p-10 text-center text-muted">
          <p>{t('org.emptyTree')}</p>
          {can('org.manage') && (
            <Link to="/org/departments" className="mt-3 inline-block font-medium text-primary underline">
              {t('org.addFirst')}
            </Link>
          )}
        </Card>
      )}

      {data && data.roots.length > 0 && view === 'scheme' && (
        <SchemeView
          onSelect={(n) => {
            setPicked(n.kind === 'dept' ? { kind: 'dept', d: n.d } : { kind: 'pos', p: n.p })
            setPanel('node')
          }}
        />
      )}
      <OrgSidePanel open={panel} onClose={() => setPanel(null)} selected={picked} onSelect={setPanel} />

      {data && data.roots.length > 0 && view !== 'scheme' && (
        <div className="flex flex-col gap-5">
          <Card className="p-6">
            <div ref={scroller} className="overflow-x-auto pb-2">
            {view === 'tree' ? (
              <div className="org-tree min-w-max">
                <ul>
                  <li>
                    <div className="rounded-card bg-primary px-6 py-4 text-center text-primary-fg shadow-card">
                      <div className="text-base font-semibold">{data.company}</div>
                      {data.leadership.length > 0 && (
                        <div className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1 text-xs opacity-90">
                          {data.leadership.map((l) => (
                            <span key={l.id}>
                              {lang === 'ru' ? l.role_name_ru : l.role_name_uz}: <b>{l.full_name}</b>
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                    <ul>
                      {data.roots.map((n) => (
                        <TreeNode key={n.id} node={n} depth={1} collapsed={collapsed} onToggle={toggle} selected={selected?.id} onSelect={setSelected} />
                      ))}
                    </ul>
                  </li>
                </ul>
              </div>
            ) : (
              <ul className="flex flex-col gap-1">
                {data.roots.map((n) => (
                  <ListNode key={n.id} node={n} depth={0} selected={selected?.id} onSelect={setSelected} />
                ))}
              </ul>
            )}
            </div>
          </Card>

          <DetailPanel node={selected} canManage={can('org.manage')} />
        </div>
      )}
    </div>
  )

  function TreeNode({
    node,
    depth,
    collapsed,
    onToggle,
    selected,
    onSelect,
  }: {
    node: DepartmentNode
    depth: number
    collapsed: Set<number>
    onToggle: (id: number) => void
    selected?: number
    onSelect: (n: DepartmentNode) => void
  }) {
    // Chuqurroq qatlamlar boshida yig'ilgan (foydalanuvchi ochadi)
    const isCollapsed = collapsed.has(node.id) !== (depth > AUTO_EXPAND_DEPTH && !collapsed.has(-node.id))
    return (
      <li>
        <NodeCard node={node} selected={selected === node.id} onSelect={() => onSelect(node)} />
        {node.children.length > 0 && (
          <>
            <button
              onClick={() => (depth > AUTO_EXPAND_DEPTH ? onToggle(-node.id) : onToggle(node.id))}
              className="mt-1 grid size-6 place-items-center rounded-full border border-border bg-surface text-muted hover:text-text"
              aria-label={isCollapsed ? t('org.expand') : t('org.collapse')}
            >
              {isCollapsed ? <ChevronRight className="size-3.5" /> : <ChevronDown className="size-3.5" />}
            </button>
            {!isCollapsed && (
              <ul>
                {node.children.map((c) => (
                  <TreeNode key={c.id} node={c} depth={depth + 1} collapsed={collapsed} onToggle={onToggle} selected={selected} onSelect={onSelect} />
                ))}
              </ul>
            )}
          </>
        )}
      </li>
    )
  }
}

function NodeCard({ node, selected, onSelect }: { node: DepartmentNode; selected: boolean; onSelect: () => void }) {
  const { t } = useTranslation()
  const color = node.color ?? 'var(--primary)'
  return (
    <button
      onClick={onSelect}
      className={
        'relative w-52 overflow-hidden rounded-card border bg-surface p-3 text-left shadow-card transition ' +
        (selected ? 'border-primary ring-2 ring-primary/30 ' : 'border-border hover:border-primary/50 ') +
        (node.is_active ? '' : 'opacity-60')
      }
    >
      <span className="absolute inset-y-0 left-0 w-1.5" style={{ background: color }} />
      <div className="pl-2">
        <div className="truncate text-sm font-semibold">{node.name}</div>
        {node.head ? (
          <div className="mt-1.5 flex items-center gap-2">
            <span className="grid size-6 shrink-0 place-items-center rounded-full bg-surface-2 text-[10px] font-semibold">{initials(node.head.full_name)}</span>
            <span className="truncate text-xs text-muted">{node.head.full_name}</span>
          </div>
        ) : (
          <div className="mt-1.5 flex items-center gap-1.5 text-xs text-warning">
            <TriangleAlert className="size-3.5" />
            {t('org.noHead')}
          </div>
        )}
        <div className="mt-2 flex gap-2 text-[11px] text-muted">
          <span>{t('org.positionsCount', { count: node.positions })}</span>
          <span>{t('orgx.peopleShort', { n: node.employees ?? 0 })}</span>
          {node.branches > 0 && <span>· {t('org.branchesCount', { count: node.branches })}</span>}
        </div>
      </div>
    </button>
  )
}

function ListNode({
  node,
  depth,
  selected,
  onSelect,
}: {
  node: DepartmentNode
  depth: number
  selected?: number
  onSelect: (n: DepartmentNode) => void
}) {
  return (
    <li>
      <div style={{ marginLeft: depth * 20 }} className="mb-1">
        <NodeCardWide node={node} selected={selected === node.id} onSelect={() => onSelect(node)} />
      </div>
      {node.children.length > 0 && (
        <ul>
          {node.children.map((c) => (
            <ListNode key={c.id} node={c} depth={depth + 1} selected={selected} onSelect={onSelect} />
          ))}
        </ul>
      )}
    </li>
  )
}

function NodeCardWide({ node, selected, onSelect }: { node: DepartmentNode; selected: boolean; onSelect: () => void }) {
  const { t } = useTranslation()
  return (
    <button
      onClick={onSelect}
      className={
        'flex w-full items-center gap-3 rounded-control border px-3 py-2.5 text-left text-sm ' +
        (selected ? 'border-primary bg-primary/5' : 'border-border bg-surface hover:bg-surface-2')
      }
    >
      <span className="size-3 shrink-0 rounded-full" style={{ background: node.color ?? 'var(--primary)' }} />
      <span className="min-w-0 flex-1 truncate font-medium">{node.name}</span>
      <span className="hidden truncate text-xs text-muted sm:block">{node.head?.full_name ?? t('org.noHead')}</span>
    </button>
  )
}

function CompanyOverview() {
  const q = useInsights(null)
  if (!q.data) return <InsightsLoading />
  return (
    <div className="flex flex-col gap-4">
      <InsightKpis d={q.data} />
      <InsightCharts d={q.data} />
    </div>
  )
}

function DetailPanel({ node, canManage }: { node: DepartmentNode | null; canManage: boolean }) {
  const { t } = useTranslation()
  const q = useInsights(node?.id ?? null)
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold">{node ? node.name : t('orgx.allCompany')}</h2>
          <p className="mt-0.5 text-sm text-muted">
            {node ? (
              <>
                {t(`org.kinds.${node.kind}`)} · {t('org.head')}: {node.head?.full_name ?? <span className="text-warning">{t('org.noHead')}</span>}
                {node.branches > 0 && <> · {t('branches.title')}: {node.branches}</>}
              </>
            ) : (
              t('org.selectHint')
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {node && !node.is_active && <Badge tone="warning">{t('users.blocked')}</Badge>}
          {node && canManage && (
            <Link to={`/org/departments/${node.id}/edit`}>
              <Button variant="outline">
                <Pencil className="size-4" />
                {t('common.edit')}
              </Button>
            </Link>
          )}
        </div>
      </div>
      {!q.data ? (
        <InsightsLoading />
      ) : (
        <>
          {node && <InsightKpis d={q.data} />}
          <InsightTabs key={node?.id ?? 'all'} d={q.data} />
        </>
      )}
    </Card>
  )
}
