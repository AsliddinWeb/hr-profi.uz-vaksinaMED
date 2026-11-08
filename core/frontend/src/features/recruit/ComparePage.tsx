import { useQuery } from '@tanstack/react-query'
import { Check, X } from 'lucide-react'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { money, STAGE_TONE, type Stage } from './api'

interface Cmp {
  id: number
  full_name: string
  phone: string | null
  age: number | null
  address: string | null
  source: string | null
  skills: string[]
  experience: string | number | null
  expected_salary: number | string | null
  languages: string | string[] | null
  education: string | null
  profile_confirmed: boolean
  resume_excerpt: string | null
  files: { id: number; name: string }[]
  application: {
    id: number
    vacancy_id: number
    stage: Stage
    rating: number | null
    match_score: number | null
    experience_level: string | null
    hard_skill: number | null
    soft_skill: number | null
    bg_status: string | null
    interview_at: string | null
    offer_status: string | null
    ai: string | null
  } | null
  tests: { score: number | null; status: string }[]
}

const txt = (v: unknown): string => (v === null || v === undefined || v === '' ? '—' : Array.isArray(v) ? v.join(', ') || '—' : String(v))

/** /recruit/compare?ids=1,2,3: 2-10 nomzod rezyumesini yonma-yon solishtirish; eng yaxshi qiymat yashil bilan belgilanadi. */
export function ComparePage() {
  const { t, i18n } = useTranslation()
  const [sp] = useSearchParams()
  const ids = sp.get('ids') ?? ''
  const vac = sp.get('vacancy_id')
  const q = useQuery({ queryKey: ['recruit', 'compare', ids, vac], queryFn: () => api<{ items: Cmp[] }>(`/api/v1/recruit/compare?ids=${encodeURIComponent(ids)}${vac ? `&vacancy_id=${vac}` : ''}`), enabled: !!ids, retry: false })
  const items = q.data?.items ?? []
  const best = (get: (c: Cmp) => number | null | undefined) => {
    const vals = items.map(get).filter((x): x is number => typeof x === 'number')
    return vals.length > 1 ? Math.max(...vals) : null
  }
  const testMax = (c: Cmp) => (c.tests.length ? Math.max(...c.tests.map((x) => x.score ?? 0)) : null)
  const num = (get: (c: Cmp) => number | null | undefined, fmt: (n: number) => string = String) => {
    const b = best(get)
    return (c: Cmp) => {
      const v = get(c)
      if (typeof v !== 'number') return '—'
      return <span className={v === b ? 'font-bold text-emerald-600' : ''}>{fmt(v)}</span>
    }
  }
  const rows: [string, (c: Cmp) => ReactNode][] = [
    [t('rcmp.stage'), (c) => (c.application ? <Badge tone={STAGE_TONE[c.application.stage]}>{t(`recruit.stage.${c.application.stage}`)}</Badge> : '—')],
    [t('rcmp.match'), num((c) => c.application?.match_score, (n) => `${n}%`)],
    [t('rcmp.rating'), num((c) => c.application?.rating, (n) => `${n}/5`)],
    [t('rcmp.hard'), num((c) => c.application?.hard_skill)],
    [t('rcmp.soft'), num((c) => c.application?.soft_skill)],
    [t('rcmp.test'), num(testMax, (n) => `${Math.round(n)}%`)],
    [t('rcmp.age'), (c) => txt(c.age)],
    [t('rcmp.experience'), (c) => txt(c.experience ?? c.application?.experience_level)],
    [t('rcmp.education'), (c) => txt(c.education)],
    [t('rcmp.languages'), (c) => txt(c.languages)],
    [t('rcmp.salary'), (c) => (typeof c.expected_salary === 'number' ? money(c.expected_salary) : txt(c.expected_salary))],
    [t('rcmp.skills'), (c) => (c.skills.length ? <div className="flex flex-wrap gap-1">{c.skills.slice(0, 10).map((s) => <Badge key={s}>{s}</Badge>)}</div> : '—')], // prettier-ignore
    [t('rcmp.source'), (c) => (c.source ? t(`recruit.source.${c.source}`, { defaultValue: c.source }) : '—')],
    [t('rcmp.address'), (c) => txt(c.address)],
    [t('rcmp.bg'), (c) => txt(c.application?.bg_status)],
    [t('rcmp.interview'), (c) => (c.application?.interview_at ? formatDateTime(c.application.interview_at, i18n.language) : '—')],
    [t('rcmp.confirmed'), (c) => (c.profile_confirmed ? <Check className="size-4 text-emerald-600" /> : <X className="size-4 text-muted" />)],
    [t('rcmp.ai'), (c) => <span className="line-clamp-4 text-xs">{txt(c.application?.ai)}</span>],
    [t('rcmp.resume'), (c) => <span className="line-clamp-6 whitespace-pre-wrap text-xs text-muted">{txt(c.resume_excerpt)}</span>],
    [
      t('rcmp.files'),
      (c) =>
        c.files.length ? (
          <ul className="flex flex-col gap-0.5 text-xs">
            {c.files.map((f) => (
              <li key={f.id} className="truncate">
                {f.name}
              </li>
            ))}
          </ul>
        ) : (
          '—'
        ),
    ],
  ]
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4">
      <PageHeader title={t('rcmp.title')} subtitle={t('rcmp.subtitle')} backTo="/recruit/candidates" backLabel={t('nav.sub.recruit')} />
      {!ids ? (
        <Card className="p-8 text-center text-sm text-muted">{t('rcmp.pick')}</Card>
      ) : q.isError ? (
        <Card className="p-8 text-center text-sm text-danger">{errorText(t, q.error)}</Card>
      ) : !q.data ? (
        <Skeleton className="h-96" />
      ) : (
        <Card className="overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] table-fixed text-left text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="sticky left-0 z-10 w-40 bg-surface px-4 py-3 text-xs font-medium text-muted" />
                  {items.map((c) => (
                    <th key={c.id} className="w-56 px-4 py-3 align-top">
                      <Link to={`/recruit/candidates/${c.id}`} className="font-semibold text-primary hover:underline">
                        {c.full_name}
                      </Link>
                      <div className="text-xs font-normal tabular-nums text-muted">{c.phone ?? ''}</div>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {rows.map(([label, render]) => (
                  <tr key={label}>
                    <th className="sticky left-0 z-10 bg-surface px-4 py-2.5 align-top text-xs font-medium text-muted">{label}</th>
                    {items.map((c) => (
                      <td key={c.id} className="px-4 py-2.5 align-top">
                        {render(c)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  )
}
