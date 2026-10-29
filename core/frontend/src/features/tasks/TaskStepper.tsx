import clsx from 'clsx'
import { Check } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { STEPS, type Step } from './api'

/** Topshiriq zanjiri: Yangi → Qabul qilingan → Jarayonda → Tekshiruvda → Bajarildi. */
export function TaskStepper({ step, overdue }: { step: Step; overdue?: boolean }) {
  const { t } = useTranslation()
  const cur = STEPS.indexOf(step)
  return (
    <ol className="flex flex-wrap items-center gap-x-1 gap-y-2" aria-label={t('tasks.chain.title')}>
      {STEPS.map((s, i) => {
        const done = i < cur || step === 'done'
        const active = i === cur && step !== 'done'
        return (
          <li key={s} className="flex items-center gap-1">
            <span className={clsx('flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium', done && 'border-success/40 bg-success/10 text-success', active && (overdue ? 'border-danger bg-danger/10 text-danger' : 'border-primary bg-primary/10 text-primary'), !done && !active && 'border-border text-muted')}>
              {done && <Check className="size-3" />}
              {t(`tasks.chain.${s}`)}
            </span>
            {i < STEPS.length - 1 && <span className="text-muted">›</span>}
          </li>
        )
      })}
    </ol>
  )
}
