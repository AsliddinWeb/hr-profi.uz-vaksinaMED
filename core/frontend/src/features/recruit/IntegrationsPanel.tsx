import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'

type Item = { key: string; kind: 'api' | 'link'; configured: boolean; provider?: string | null; ok: number; errors: number; last_ok: string | null; last_error: string | null; last_error_text: string | null }
type Data = { days: number; items: Item[]; logs: { at: string; provider: string; action: string; ok: boolean; message: string | null }[] }

/** Integratsiyalar holati va jurnali: Telegram bot/kanal, AI, nomzod havolalari (sayt, hh.uz, OLX...). */
export function IntegrationsPanel() {
  const { t, i18n } = useTranslation()
  const [days, setDays] = useState(7)
  const [onlyErr, setOnlyErr] = useState(false)
  const q = useQuery({ queryKey: ['recruit', 'integrations', days], queryFn: () => api<Data>(`/api/v1/recruit/analytics/integrations?days=${days}`) })
  const d = q.data
  const name = (k: string) => t(`integ.p.${k}`, { defaultValue: t(`ana.src.${k}`, { defaultValue: k }) })
  const state = (x: Item): ['success' | 'danger' | 'warning' | 'neutral', string] => {
    if (!x.configured) return ['neutral', t('integ.off')]
    if (x.kind === 'link') return x.ok ? ['success', t('integ.flowing')] : ['neutral', t('integ.silent')]
    if (x.last_error && (!x.last_ok || x.last_error > x.last_ok)) return ['danger', t('integ.error')]
    if (x.errors) return ['warning', t('integ.partial')]
    return ['success', t('integ.ok')]
  }
  const logs = (d?.logs ?? []).filter((l) => !onlyErr || !l.ok)
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <div className="font-medium">{t('integ.title')}</div>
          <div className="text-xs text-muted">{t('integ.hint')}</div>
        </div>
        <Select className="w-auto" value={days} onChange={(e) => setDays(Number(e.target.value))} aria-label={t('integ.period')}>
          {[1, 7, 30].map((n) => (
            <option key={n} value={n}>
              {t('comp.ov.lastDays', { n })}
            </option>
          ))}
        </Select>
      </div>
      {!d ? (
        <Skeleton className="h-32" />
      ) : (
        <>
          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {d.items.map((x) => {
              const [tone, label] = state(x)
              return (
                <div key={x.key} className="rounded-lg border border-border p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="min-w-0 font-medium leading-tight">{name(x.key)}</span>
                    <Badge tone={tone} className="shrink-0">{label}</Badge>
                  </div>
                  <div className="mt-1 text-xs text-muted">
                    {x.kind === 'link' ? t('integ.applications', { n: x.ok }) : t('integ.counts', { ok: x.ok, err: x.errors })}
                    {x.provider ? ` · ${x.provider}` : ''}
                  </div>
                  {x.last_ok && <div className="text-[11px] text-muted">{t('integ.lastOk', { at: formatDateTime(x.last_ok, i18n.language) })}</div>}
                  {x.last_error && (
                    <div className="truncate text-[11px] text-danger" title={x.last_error_text ?? ''}>
                      {t('integ.lastErr', { at: formatDateTime(x.last_error, i18n.language) })}: {x.last_error_text}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-medium">{t('integ.log')}</div>
            <label className="flex items-center gap-2 text-xs text-muted">
              <input type="checkbox" checked={onlyErr} onChange={(e) => setOnlyErr(e.target.checked)} />
              {t('integ.onlyErrors')}
            </label>
          </div>
          {logs.length === 0 ? (
            <div className="py-4 text-center text-sm text-muted">{t('ana.empty')}</div>
          ) : (
            <div className="max-h-72 overflow-y-auto rounded-lg border border-border">
              <table className="w-full text-xs">
                <tbody>
                  {logs.map((l, i) => (
                    <tr key={`${l.at}-${i}`} className="border-t border-border first:border-t-0">
                      <td className="whitespace-nowrap px-2 py-1.5 text-muted">{formatDateTime(l.at, i18n.language)}</td>
                      <td className="px-2 py-1.5">{name(l.provider)}</td>
                      <td className="px-2 py-1.5 text-muted">{l.action}</td>
                      <td className={clsx('px-2 py-1.5', l.ok ? 'text-success' : 'text-danger')}>{l.ok ? '✓' : `✕ ${l.message ?? ''}`}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </Card>
  )
}
