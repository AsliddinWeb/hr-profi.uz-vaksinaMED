import { useQuery } from '@tanstack/react-query'
import { Settings } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { Kpi } from '../tasks/AnalyticsPage'
import type { AiSettings, AiUsage } from './api'

/** /ai/usage: AI so'rovlari, tokenlar, funksiya va foydalanuvchi bo'yicha, oxirgi so'rovlar. */
export function UsagePage() {
  const { t, i18n } = useTranslation()
  const [days, setDays] = useState('30')
  const q = useQuery({ queryKey: ['ai', 'usage', days], queryFn: () => api<AiUsage>(`/api/v1/ai/usage?days=${days}`), placeholderData: (p) => p })
  const cfg = useQuery({ queryKey: ['ai', 'settings'], queryFn: () => api<AiSettings>('/api/v1/ai/settings') })
  const d = q.data
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5">
      <PageHeader
        title={t('ai.usage.title')}
        subtitle={t('ai.usage.subtitle')}
        actions={
          <Link to="/ai/settings">
            <Button variant="outline">
              <Settings className="size-4" />
              {t('ai.settings.title')}
            </Button>
          </Link>
        }
      />
      <Card className="flex flex-wrap items-center gap-3 p-4 text-sm">
        <Badge tone={cfg.data?.configured && cfg.data.enabled ? 'success' : 'warning'}>{!cfg.data?.configured ? t('ai.usage.noKey') : cfg.data.enabled ? t('ai.usage.on') : t('ai.usage.off')}</Badge>
        {cfg.data && <span className="text-muted">{cfg.data.model} · {t('ai.settings.limit')}: {cfg.data.daily_limit}</span>}
        <Select className="ml-auto w-auto" value={days} onChange={(e) => setDays(e.target.value)} aria-label={t('attendance.dash.period')}>
          {['7', '30', '90'].map((n) => (
            <option key={n} value={n}>
              {t('ai.usage.days', { count: Number(n) })}
            </option>
          ))}
        </Select>
      </Card>
      {!d ? (
        <Skeleton className="h-72" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Kpi tint="lilac" label={t('ai.usage.requests')} value={String(d.requests)} />
            <Kpi label={t('ai.usage.input')} value={d.input_tokens.toLocaleString(i18n.language)} />
            <Kpi label={t('ai.usage.output')} value={d.output_tokens.toLocaleString(i18n.language)} />
            <Kpi tint="rose" label={t('ai.usage.failed')} value={String(d.failed)} />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <Card className="p-5">
              <h2 className="text-[13px] text-muted">{t('ai.usage.byFeature')}</h2>
              <ul className="mt-3 divide-y divide-border text-sm">
                {d.by_feature.map((f) => (
                  <li key={f.feature} className="flex justify-between py-2">
                    <span>{t(`ai.feature.${f.feature}`)}</span>
                    <span className="tabular-nums text-muted">{f.count} · {f.tokens.toLocaleString(i18n.language)}</span>
                  </li>
                ))}
                {d.by_feature.length === 0 && <li className="py-4 text-center text-muted">{t('common.empty')}</li>}
              </ul>
            </Card>
            <Card className="p-5">
              <h2 className="text-[13px] text-muted">{t('ai.usage.byUser')}</h2>
              <ul className="mt-3 divide-y divide-border text-sm">
                {d.by_user.map((u, i) => (
                  <li key={i} className="flex justify-between py-2">
                    <span>{u.name ?? '—'}</span>
                    <span className="tabular-nums text-muted">{u.count} · {u.tokens.toLocaleString(i18n.language)}</span>
                  </li>
                ))}
                {d.by_user.length === 0 && <li className="py-4 text-center text-muted">{t('common.empty')}</li>}
              </ul>
            </Card>
          </div>
          <Card className="overflow-hidden">
            <h2 className="px-5 pt-5 text-[13px] text-muted">{t('ai.usage.recent')}</h2>
            <div className="overflow-x-auto">
              <table className="mt-3 w-full text-left text-sm">
                <thead className="border-y border-border text-xs text-muted">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">{t('calls.when')}</th>
                    <th className="px-5 py-2.5 font-medium">{t('ai.usage.feature')}</th>
                    <th className="hidden px-5 py-2.5 font-medium sm:table-cell">{t('ai.settings.model')}</th>
                    <th className="px-5 py-2.5 text-right font-medium">{t('ai.usage.tokens')}</th>
                    <th className="px-5 py-2.5 font-medium">{t('attendance.statusLabel')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {d.recent.map((r) => (
                    <tr key={r.id}>
                      <td className="px-5 py-2.5 text-muted">{formatDateTime(r.created_at, i18n.language)}</td>
                      <td className="px-5 py-2.5">{t(`ai.feature.${r.feature}`)}</td>
                      <td className="hidden px-5 py-2.5 text-muted sm:table-cell">{r.model}</td>
                      <td className="px-5 py-2.5 text-right">{r.tokens}</td>
                      <td className="px-5 py-2.5">{r.ok ? <Badge tone="success">OK</Badge> : <Badge tone="danger">{r.error ?? 'xato'}</Badge>}</td>
                    </tr>
                  ))}
                  {d.recent.length === 0 && (
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
        </>
      )}
    </div>
  )
}
