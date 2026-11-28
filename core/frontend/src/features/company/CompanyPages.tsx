import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ClipboardList, FileCheck2, Gavel, Scale, type LucideIcon } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Skeleton } from '../../components/ui/Skeleton'
import { Tabs } from '../../components/ui/Tabs'
import { api } from '../../lib/api'
import { useCan } from '../auth/useAuth'
import type { HrDoc } from '../hrdocs/api'
import { DocList, DocPanel, type DocEntry, type DocView } from './DocPanel'
import { SmartCriteria, SmartSummary, StrategySteps, SwotBoard } from './StrategyExtras'

function useDocs() {
  const q = useQuery({ queryKey: ['hrdocs', 'list', ''], queryFn: () => api<{ items: HrDoc[]; pending_ack: number }>('/api/v1/hrdocs'), placeholderData: (p) => p })
  const byKey = useMemo(() => new Map((q.data?.items ?? []).filter((d) => d.key).map((d) => [d.key as string, d])), [q.data])
  return { loading: !q.data, items: q.data?.items ?? [], byKey }
}

interface LinkCard {
  to: string
  title: string
  hint: string
  icon: LucideIcon
  show: boolean
}

function LinkCards({ cards }: { cards: LinkCard[] }) {
  const shown = cards.filter((c) => c.show)
  if (!shown.length) return null
  return (
    <div className="flex flex-col gap-2">
      {shown.map((c) => (
        <Link key={c.to} to={c.to} className="group flex items-center gap-3 rounded-card border border-border bg-surface p-3 transition hover:bg-surface-2">
          <span className="grid size-9 shrink-0 place-items-center rounded-control bg-primary/10 text-primary">
            <c.icon className="size-[18px]" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="block font-medium">{c.title}</span>
            <span className="block text-xs text-muted">{c.hint}</span>
          </span>
          <ArrowRight className="size-4 text-muted transition group-hover:translate-x-0.5" />
        </Link>
      ))}
    </div>
  )
}

function Split({
  entries,
  extra,
  header,
  numbered = false,
  below,
  selectedKey,
  onPick,
  hideList = false,
}: {
  entries: DocEntry[]
  extra?: React.ReactNode
  header?: React.ReactNode
  numbered?: boolean
  /** Tanlangan hujjat ostida qo'shimcha bloklar (masalan strategiya uchun SWOT); faqat «To'liq hujjat» ko'rinishida */
  below?: (key: string | null) => React.ReactNode
  selectedKey?: string
  onPick?: (key: string) => void
  hideList?: boolean
}) {
  const [picked, setPicked] = useState<number | null>(null)
  const [view, setView] = useState<DocView>('all')
  const fromKey = selectedKey ? entries.find((e) => e.doc?.key === selectedKey)?.doc?.id : undefined
  const current = fromKey ?? picked
  const selected = current !== null && entries.some((e) => e.doc?.id === current) ? current : (entries.find((e) => e.doc)?.doc?.id ?? null)
  const entry = entries.find((e) => e.doc?.id === selected)
  const select = (id: number, v: DocView = 'all') => {
    setPicked(id)
    setView(v)
    const key = entries.find((e) => e.doc?.id === id)?.doc?.key
    if (key) onPick?.(key)
  }
  const more = view === 'all' && below ? below(entry?.doc?.key ?? null) : null
  return (
    <div className={hideList ? 'grid items-start gap-5' : 'grid items-start gap-5 lg:grid-cols-[17rem_minmax(0,1fr)]'}>
      {!hideList && (
        <div className="flex flex-col gap-4">
          {header}
          <DocList entries={entries} selected={selected} view={view} onSelect={select} numbered={numbered} />
          {extra}
        </div>
      )}
      <div className={more ? 'flex min-w-0 flex-col gap-5' : 'lg:sticky lg:top-4'}>
        <DocPanel id={selected} label={entry?.label} view={view} onShowAll={() => setView('all')} />
        {more}
      </div>
    </div>
  )
}

const STRATEGY_PATH: Record<string, string> = { goal: 'goal', mission: 'mission', strategies: 'strategies', smart: 'smart', values: 'values', slogan: 'slogan' }
const STRATEGY_ORDER = ['goal', 'mission', 'strategies', 'smart', 'values', 'slogan'] as const

export function StrategyPage() {
  const { t } = useTranslation()
  const { key } = useParams()
  const { loading, byKey } = useDocs()
  const entries: DocEntry[] = STRATEGY_ORDER.map((k) => ({ label: t(`company.strategy.items.${k}`), doc: byKey.get(k) }))
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-5">
      <PageHeader title={t('company.strategy.title')} subtitle={t('company.strategy.subtitle')} />
      {loading ? (
        <Skeleton className="h-96" />
      ) : (
        <Split
          hideList
          entries={entries}
          selectedKey={STRATEGY_PATH[key ?? 'goal']}
          below={(key) =>
            key === 'strategies' ? (
              <>
                <StrategySteps />
                <SwotBoard />
              </>
            ) : key === 'smart' ? (
              <>
                <SmartCriteria />
                <SmartSummary />
              </>
            ) : null
          }
        />
      )}
    </div>
  )
}

export function CompanyRulesPage() {
  const { t } = useTranslation()
  const can = useCan()
  const { loading, items, byKey } = useDocs()
  const [tab, setTab] = useState<'charter' | 'internal'>('charter')
  const charter: DocEntry[] = [{ label: t('company.rules.charter'), doc: byKey.get('charter') }, ...items.filter((d) => d.category === 'process' && (d.has_body || d.has_file || d.media.length > 0)).map((d) => ({ label: d.title, doc: d }))]
  const internal: DocEntry[] = [{ label: t('company.rules.internal'), doc: byKey.get('internal_rules') }]
  const penalties = can('penalties.read') || can('penalties.own') || can('penalties.manage')
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader title={t('company.rules.title')} subtitle={t('company.rules.subtitle')} />
      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          { key: 'charter', label: t('company.rules.charter') },
          { key: 'internal', label: t('company.rules.internal') },
        ]}
      />
      {loading ? (
        <Skeleton className="h-96" />
      ) : tab === 'charter' ? (
        <Split key="charter" entries={charter} header={<p className="text-sm text-muted">{t('company.rules.charterHint')}</p>} />
      ) : (
        <Split
          key="internal"
          entries={internal}
          extra={
            <LinkCards
              cards={[
                { to: '/penalties/rules', title: t('company.rules.penaltyRules'), hint: t('company.rules.penaltyRulesHint'), icon: Scale, show: can('penalties.read') || can('penalties.manage') },
                { to: '/penalties', title: t('company.rules.penalties'), hint: t('company.rules.penaltiesHint'), icon: Gavel, show: penalties },
              ]}
            />
          }
        />
      )}
    </div>
  )
}

export function CompanyDutiesPage() {
  const { t } = useTranslation()
  const can = useCan()
  const { loading, byKey } = useDocs()
  const entries: DocEntry[] = [{ label: t('company.duties.title'), doc: byKey.get('job_duties') }]
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-5">
      <PageHeader title={t('company.duties.title')} subtitle={t('company.duties.subtitle')} />
      {loading ? (
        <Skeleton className="h-96" />
      ) : (
        <Split
          entries={entries}
          extra={
            <LinkCards
              cards={[
                { to: '/org/duties', title: t('company.duties.byPosition'), hint: t('company.duties.byPositionHint'), icon: ClipboardList, show: can('org.read') },
                { to: '/checklists/duty', title: t('company.duties.checklists'), hint: t('company.duties.checklistsHint'), icon: FileCheck2, show: can('duty.read') || can('duty.manage') },
              ]}
            />
          }
        />
      )}
    </div>
  )
}
