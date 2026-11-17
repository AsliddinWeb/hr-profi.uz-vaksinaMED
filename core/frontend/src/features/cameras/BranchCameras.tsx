import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Card } from '../../components/ui/Card'
import { Input, Select } from '../../components/ui/Input'
import { Pagination } from '../../components/ui/Pagination'
import { Skeleton } from '../../components/ui/Skeleton'
import { api } from '../../lib/api'

type Row = { id: number; name: string; number: number | null; total: number; online: number; offline: number; unknown: number; ip: number; webcam: number; phone: number }

/** Har bir filialda nechta kamera bor (1000+ filial): jami / onlayn / oflayn, turlari; kamerasi yo'q filiallar. */
export function BranchCameras({ onOpen }: { onOpen: (branchId: number) => void }) {
  const { t } = useTranslation()
  const [q, setQ] = useState('')
  const [only, setOnly] = useState('')
  const [page, setPage] = useState(1)
  const params = new URLSearchParams({ page: String(page), size: '50' })
  if (q) params.set('q', q)
  if (only) params.set('only', only)
  const d = useQuery({ queryKey: ['cameras', 'by-branch', params.toString()], queryFn: () => api<{ items: Row[]; total: number; without_cameras: number }>(`/api/v1/cameras/by-branch?${params}`), placeholderData: (p) => p })
  return (
    <div className="flex flex-col gap-3">
      <Card className="grid grid-cols-1 gap-2 p-3 sm:grid-cols-3">
        <Input value={q} onChange={(e) => (setQ(e.target.value), setPage(1))} placeholder={t('cam.branchSearch')} aria-label={t('cam.branchSearch')} />
        <Select value={only} onChange={(e) => (setOnly(e.target.value), setPage(1))} aria-label={t('cam.status')}>
          <option value="">{t('cam.allBranches')}</option>
          <option value="offline">{t('cam.onlyOffline')}</option>
          <option value="none">{t('cam.onlyNone')}</option>
        </Select>
        <div className="flex items-center text-xs text-muted">{d.data ? t('cam.branchesCount', { n: d.data.total, none: d.data.without_cameras }) : ''}</div>
      </Card>
      {!d.data ? (
        <Skeleton className="h-64" />
      ) : (
        <Card className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-muted">
              <tr>
                {[t('cam.branch'), t('cam.total'), t('cam.st.online'), t('cam.st.offline'), t('cam.kinds.ip'), t('cam.kinds.webcam'), t('cam.kinds.phone')].map((h) => (
                  <th key={h} className="px-3 py-2 font-medium">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {d.data.items.map((r) => (
                <tr key={r.id} className="cursor-pointer border-t border-border hover:bg-surface-2" onClick={() => onOpen(r.id)}>
                  <td className="px-3 py-2">
                    {r.number ? <span className="text-muted">№{r.number} · </span> : null}
                    {r.name}
                  </td>
                  <td className={clsx('px-3 py-2 font-mono', !r.total && 'text-warning')}>{r.total || t('cam.noCameras')}</td>
                  <td className="px-3 py-2 font-mono text-success">{r.online || '—'}</td>
                  <td className={clsx('px-3 py-2 font-mono', r.offline ? 'font-semibold text-danger' : 'text-muted')}>{r.offline || '—'}</td>
                  <td className="px-3 py-2 font-mono">{r.ip || '—'}</td>
                  <td className="px-3 py-2 font-mono">{r.webcam || '—'}</td>
                  <td className="px-3 py-2 font-mono">{r.phone || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="p-3">
            <Pagination page={page} size={50} total={d.data.total} onPage={setPage} />
          </div>
        </Card>
      )}
    </div>
  )
}
