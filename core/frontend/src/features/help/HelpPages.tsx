import { ArrowRight, ChevronRight } from 'lucide-react'
import { useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Card } from '../../components/ui/Card'
import { getExtensionNavItems, type NavItem } from '../../extensions/registry'
import { coreNav } from '../../nav'
import { PROCESS_INFO, FLOWS } from '../../lib/processInfo'
import { useCan } from '../auth/useAuth'
import { useMeta } from '../meta/useMeta'

function useVisibleNav(): NavItem[] {
  const can = useCan()
  const { data: meta } = useMeta()
  const enabled = (m?: string) => !m || !meta || meta.modules.includes(m)
  return [...coreNav, ...getExtensionNavItems()].filter((i) => enabled(i.module) && (!i.permission || can(i.permission)) && (!i.anyPermission || i.anyPermission.some(can)))
}

/** /help: kompaniyadagi asosiy bog'langan jarayonlar va har bir bo'lim nima qilishi. */
export function HelpPage() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const nav = useVisibleNav()
  const groups = useMemo(() => {
    const out: { group: string; items: NavItem[] }[] = []
    for (const it of nav) {
      const g = it.group ?? 'main'
      const last = out[out.length - 1]
      if (last && last.group === g) last.items.push(it)
      else out.push({ group: g, items: [it] })
    }
    return out
  }, [nav])
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader title={t('help.title')} subtitle={t('help.subtitle')} />
      <h2 className="text-lg font-semibold">{t('help.flowsTitle')}</h2>
      {FLOWS.map((f) => (
        <Card key={f.key} className="flex flex-col gap-3 p-5">
          <h3 className="font-semibold">{f.title[lang]}</h3>
          <ol className="flex flex-wrap items-center gap-2 text-sm">
            {f.chain.map((s, n) => (
              <li key={`${s.to}-${n}`} className="flex items-center gap-2">
                <Link to={s.to} className="rounded-full border border-border bg-surface-2 px-3 py-1.5 font-medium hover:border-primary hover:text-primary">
                  <span className="mr-1 text-xs text-muted">{n + 1}.</span>
                  {s.label[lang]}
                </Link>
                {n < f.chain.length - 1 && <ArrowRight className="size-4 text-muted" />}
              </li>
            ))}
          </ol>
        </Card>
      ))}
      <h2 className="mt-2 text-lg font-semibold">{t('help.sectionsTitle')}</h2>
      {groups.map((g) => (
        <Card key={g.group} className="overflow-hidden">
          <div className="border-b border-border px-5 py-3 font-semibold">{t(`nav.group.${g.group}`, { defaultValue: g.group })}</div>
          <ul className="divide-y divide-border">
            {g.items.map((it) => (
              <li key={it.id}>
                <Link to={it.to} className="flex items-start gap-3 px-5 py-3 hover:bg-surface-2">
                  {it.icon ? <it.icon className="mt-0.5 size-4 shrink-0 text-primary" /> : <ChevronRight className="mt-0.5 size-4 shrink-0 text-primary" />}
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium">{it.label[lang]}</span>
                    {PROCESS_INFO[it.to] && <span className="block text-xs text-muted">{PROCESS_INFO[it.to].what[lang]}</span>}
                  </span>
                  <ChevronRight className="mt-0.5 size-4 text-muted" />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      ))}
    </div>
  )
}

/** /hub/:sub: menyu papkasining bosh sahifasi — ichidagi bo'limlar va ular nima qilishi. */
export function SubHubPage() {
  const { t, i18n } = useTranslation()
  const lang = i18n.language === 'ru' ? 'ru' : 'uz'
  const sub = useParams().sub ?? ''
  const items = useVisibleNav().filter((i) => i.sub === sub)
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-4">
      <PageHeader title={t(`nav.sub.${sub}`, { defaultValue: sub })} subtitle={t(`help.subHint.${sub}`, { defaultValue: '' }) || undefined} />
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((x) => (
          <Link key={x.id} to={x.to} className="group flex flex-col gap-3 rounded-card border border-border bg-surface p-4 shadow-card transition hover:-translate-y-0.5 hover:shadow-pop">
            <span className="grid size-11 place-items-center rounded-control bg-primary/10 text-primary">
              {x.icon ? <x.icon className="size-5" /> : <ChevronRight className="size-5" />}
            </span>
            <div>
              <div className="flex items-center gap-1 font-semibold">
                {x.label[lang]}
                <ChevronRight className="size-4 text-muted transition group-hover:translate-x-0.5" />
              </div>
              {PROCESS_INFO[x.to] && <p className="mt-0.5 text-xs text-muted">{PROCESS_INFO[x.to].what[lang]}</p>}
            </div>
          </Link>
        ))}
        {items.length === 0 && <Card className="p-8 text-center text-sm text-muted sm:col-span-2 lg:col-span-3">{t('help.noAccess')}</Card>}
      </div>
    </div>
  )
}
