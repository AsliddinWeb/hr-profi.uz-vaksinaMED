import { useQuery } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'
import type { FaceEvaluation } from './api'

const pct = (v: number | null) => (v === null ? '—' : `${(v * 100).toFixed(v < 0.01 && v > 0 ? 2 : 1)}%`)

/** /face/evaluation: FAR (yolg'on qabul) va FRR (yolg'on rad) chegara bo'yicha; chegarani tanlash uchun asos. */
export function EvaluationPage() {
  const { t } = useTranslation()
  const ev = useQuery({ queryKey: ['face', 'evaluation'], queryFn: () => api<FaceEvaluation>('/api/v1/face/evaluation') })
  const d = ev.data

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('face.eval.title')} subtitle={t('face.eval.subtitle')} />
      {!d ? (
        <Skeleton className="h-72" />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-4">
            <Stat label={t('face.eval.enrolled')} value={String(d.enrolled_employees)} />
            <Stat label={t('face.eval.impostor')} value={String(d.impostor_pairs)} />
            <Stat label={t('face.eval.genuine')} value={String(d.genuine_attempts)} />
            <Stat label={t('face.eval.current')} value={d.threshold.toFixed(2)} />
          </div>
          {!d.enough_data && (
            <Card tint="sand" className="p-4 text-sm" role="status">
              {t('face.eval.notEnough')}
            </Card>
          )}
          {d.recommended !== null && (
            <Card tint="mint" className="p-4 text-sm" role="status">
              {t('face.eval.recommended', { value: d.recommended.toFixed(2) })}
            </Card>
          )}
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-border text-xs text-muted">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">{t('face.eval.threshold')}</th>
                    <th className="px-5 py-2.5 font-medium">FAR</th>
                    <th className="px-5 py-2.5 font-medium">FRR</th>
                    <th className="px-5 py-2.5" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-border tabular-nums">
                  {d.table.map((r) => (
                    <tr key={r.threshold} className={Math.abs(r.threshold - d.threshold) < 0.001 ? 'bg-primary/5' : ''}>
                      <td className="px-5 py-2.5 font-medium">{r.threshold.toFixed(2)}</td>
                      <td className="px-5 py-2.5">{pct(r.far)}</td>
                      <td className="px-5 py-2.5">{pct(r.frr)}</td>
                      <td className="px-5 py-2.5">
                        {Math.abs(r.threshold - d.threshold) < 0.001 && <Badge tone="success">{t('face.eval.currentBadge')}</Badge>}
                        {d.eer_threshold === r.threshold && <Badge className="ml-1.5">EER</Badge>}
                        {d.recommended === r.threshold && <Badge className="ml-1.5" tone="success">{t('face.eval.recommendedBadge')}</Badge>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
          <Card className="p-5 text-sm text-muted">
            <p>{t('face.eval.how')}</p>
            <p className="mt-2">{t('face.eval.change', { duplicate: d.duplicate_threshold.toFixed(2) })}</p>
          </Card>
        </>
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <Card className="p-5">
      <div className="text-sm text-muted">{label}</div>
      <div className="mt-2 text-3xl font-semibold tabular-nums">{value}</div>
    </Card>
  )
}
