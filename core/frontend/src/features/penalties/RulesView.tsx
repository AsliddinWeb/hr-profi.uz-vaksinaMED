import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { AUTO_TYPES, money, type RuleVersion } from './api'

/** Qoida versiyasining o'qiladigan ko'rinishi. */
export function RulesView({ version, current }: { version: RuleVersion; current?: boolean }) {
  const { t } = useTranslation()
  const c = version.config
  return (
    <Card className="flex flex-col gap-5 p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-semibold">{t('penalties.ruleVersion', { v: version.version })}</h2>
        {current && <Badge tone="success">{t('penalties.rules.current')}</Badge>}
        <Badge tone={c.auto_scan ? 'success' : 'neutral'}>{c.auto_scan ? t('penalties.rules.autoOn') : t('penalties.rules.autoOff')}</Badge>
        <Badge>{t('penalties.rules.windowN', { days: c.window_days })}</Badge>
        <Badge>{t(`penalties.rules.mode.${c.count_mode}`)}</Badge>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">{t('penalties.rules.triggers')}</h3>
        <ul className="grid gap-2 sm:grid-cols-2">
          {AUTO_TYPES.map((k) => (
            <li key={k} className="flex items-center justify-between rounded-control border border-border px-3 py-2 text-sm">
              <span>{t(`letters.incidents.${k}`)}</span>
              <span className="text-muted">{c.triggers[k].enabled ? (c.triggers[k].min_minutes ? t('penalties.rules.fromMin', { m: c.triggers[k].min_minutes }) : t('penalties.rules.on')) : t('penalties.rules.off')}</span>
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium">{t('penalties.rules.steps')}</h3>
        <ol className="divide-y divide-border rounded-control border border-border text-sm">
          {c.steps.map((s) => (
            <li key={s.step} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
              <span>
                <b className="mr-2 tabular-nums">{s.step}.</b>
                {s.label}
              </span>
              <span className="tabular-nums text-muted">
                {s.amount > 0 ? money(s.amount) : t('penalties.noAmount')}
                {s.block_days > 0 && ` · ${t('penalties.blockDays', { count: s.block_days })}`}
              </span>
            </li>
          ))}
        </ol>
      </div>
      {version.note && <p className="text-sm text-muted">{version.note}</p>}
    </Card>
  )
}
