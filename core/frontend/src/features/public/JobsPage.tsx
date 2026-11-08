import { useQuery } from '@tanstack/react-query'
import { Briefcase, MapPin } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { api } from '../../lib/api'

interface Job {
  id: number
  title: string
  branch: string | null
  salary_from: number | null
  salary_to: number | null
  requirements: string | null
  code: string
}

const fmt = (n: number) => n.toLocaleString('ru-RU')

/** /jobs: saytdagi ochiq vakansiyalar (kirish shart emas). Har biri "site" havolasi orqali anketaga olib boradi. */
export function JobsPage() {
  const { t } = useTranslation()
  const q = useQuery({ queryKey: ['public-jobs'], queryFn: () => api<{ items: Job[] }>('/api/v1/public/jobs') })
  return (
    <main className="min-h-screen bg-gradient-to-br from-violet-50 via-fuchsia-50 to-amber-50 px-4 py-10 dark:from-[#1b1530] dark:via-[#1d1428] dark:to-[#221c14]">
      <div className="mx-auto flex max-w-3xl flex-col gap-5">
        <header className="text-center">
          <h1 className="text-3xl font-bold text-[#4b1d73] dark:text-violet-200">{t('jobs.title')}</h1>
          <p className="mt-1 text-sm text-[#6b5a80] dark:text-violet-200/70">{t('jobs.subtitle')}</p>
        </header>
        {!q.data ? (
          <div className="h-40 animate-pulse rounded-3xl bg-white/60" />
        ) : q.data.items.length === 0 ? (
          <p className="rounded-3xl bg-white/80 p-8 text-center text-sm text-muted dark:bg-[#1e1a2b]">{t('jobs.empty')}</p>
        ) : (
          q.data.items.map((j) => (
            <a key={j.id} href={`/apply/${j.code}`} className="group flex flex-col gap-2 rounded-3xl border border-violet-100 bg-white/85 p-5 shadow-[0_10px_40px_-25px_rgba(75,29,115,0.45)] transition hover:-translate-y-0.5 dark:border-violet-900/50 dark:bg-[#1e1a2b]/90">
              <div className="flex items-start gap-3">
                <span className="grid size-11 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#4b1d73] to-[#7b2fa8] text-white">
                  <Briefcase className="size-5" />
                </span>
                <div className="min-w-0 flex-1">
                  <h2 className="text-lg font-semibold text-[#2d1247] dark:text-violet-100">{j.title}</h2>
                  <div className="mt-0.5 flex flex-wrap gap-x-4 text-sm text-[#6b5a80] dark:text-violet-200/70">
                    {j.branch && (
                      <span className="flex items-center gap-1">
                        <MapPin className="size-3.5" />
                        {j.branch}
                      </span>
                    )}
                    {(j.salary_from || j.salary_to) && <span className="font-semibold text-emerald-700 dark:text-emerald-400">{[j.salary_from && fmt(j.salary_from), j.salary_to && fmt(j.salary_to)].filter(Boolean).join(' – ')} {t('apply.currency')}</span>}
                  </div>
                </div>
              </div>
              {j.requirements && <p className="line-clamp-3 whitespace-pre-wrap text-sm text-muted">{j.requirements}</p>}
              <span className="self-end rounded-full bg-gradient-to-r from-[#4b1d73] to-[#7b2fa8] px-5 py-2 text-sm font-semibold text-white">{t('jobs.apply')}</span>
            </a>
          ))
        )}
      </div>
    </main>
  )
}
