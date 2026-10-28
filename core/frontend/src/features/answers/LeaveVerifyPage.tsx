import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, ShieldAlert, XCircle } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { ApiError, api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'

interface LeaveVerify {
  valid: boolean
  intact: boolean
  number: string
  employee: string
  status: string
  kind: 'day' | 'hourly'
  start_date: string
  end_date: string
  start_time: string | null
  end_time: string | null
  decided_level: 'coordinator' | 'hr' | null
  decided_at: string | null
  hash_prefix: string
  hash_match: boolean | null
}

/** /verify/leave/:code: ochiq sahifa (kirish shart emas): javob olish bildirgisining haqiqiyligini tekshirish. */
export function LeaveVerifyPage() {
  const { t, i18n } = useTranslation()
  const { code = '' } = useParams()
  const [hash, setHash] = useState('')
  const q = useQuery({ queryKey: ['verify-leave', code, hash], queryFn: () => api<LeaveVerify>(`/api/v1/public/leave/${encodeURIComponent(code)}${hash.trim() ? `?hash=${encodeURIComponent(hash.trim())}` : ''}`), retry: false })
  const r = q.data
  const good = !!r && r.valid && r.intact
  const when = r ? r.start_date.split('-').reverse().join('.') + (r.kind === 'hourly' && r.start_time ? ` ${r.start_time}–${r.end_time}` : r.end_date !== r.start_date ? ` – ${r.end_date.split('-').reverse().join('.')}` : '') : ''
  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col gap-5 px-4 py-10">
      <div className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-control bg-primary text-primary-fg">
          <ShieldAlert className="size-5" />
        </span>
        <div>
          <h1 className="text-xl font-semibold">{t('answers.verify.title')}</h1>
          <p className="text-sm text-muted">{t('answers.verify.subtitle')}</p>
        </div>
      </div>
      {q.error instanceof ApiError ? (
        <Card className="flex flex-col items-center gap-3 p-8 text-center" role="alert">
          <XCircle className="size-14 text-danger" />
          <p className="font-semibold">{q.error.status === 404 ? t('letters.verify.notFound') : t('errors.unknown')}</p>
          <p className="text-sm text-muted">{t('letters.verify.notFoundHint')}</p>
        </Card>
      ) : !r ? (
        <Card className="h-40 animate-pulse" />
      ) : (
        <Card className="flex flex-col gap-4 p-6">
          <div className="flex items-center gap-3">
            {good ? <CheckCircle2 className="size-10 text-success" /> : <XCircle className="size-10 text-danger" />}
            <div>
              <p className="text-lg font-semibold">{good ? t('answers.verify.valid') : t('answers.verify.invalid')}</p>
              {!r.intact && <p className="text-sm text-danger">{t('letters.verify.tampered')}</p>}
              {r.status !== 'approved' && <p className="text-sm text-danger">{t('answers.verify.notApproved')}</p>}
            </div>
          </div>
          <dl className="grid gap-3 text-sm sm:grid-cols-2">
            <Row label={t('letters.verify.number')} value={r.number} />
            <Row label={t('letters.verify.employee')} value={r.employee} />
            <Row label={t('answers.verify.period')} value={`${when} · ${t(`answersReport.kind.${r.kind}`)}`} />
            <Row label={t('answers.verify.decided')} value={`${r.decided_level ? t(`answersReport.level.${r.decided_level}`) + ' · ' : ''}${r.decided_at ? formatDateTime(r.decided_at, i18n.language) : '—'}`} />
            <Row label="SHA-256" value={`${r.hash_prefix}…`} mono />
          </dl>
          <div className="border-t border-border pt-4">
            <label className="text-sm font-medium" htmlFor="hash">
              {t('letters.verify.compare')}
            </label>
            <Input id="hash" className="mt-1.5 font-mono" value={hash} onChange={(e) => setHash(e.target.value)} placeholder={t('letters.verify.comparePlaceholder')} maxLength={64} />
            {r.hash_match !== null && (
              <p role="status" className={'mt-2 text-sm font-medium ' + (r.hash_match ? 'text-success' : 'text-danger')}>
                {r.hash_match ? t('letters.verify.hashMatch') : t('letters.verify.hashMismatch')}
              </p>
            )}
          </div>
          <p className="text-xs text-muted">{t('letters.verify.privacy')}</p>
        </Card>
      )}
      <Link to="/" className="text-center text-sm text-muted hover:text-text">
        {t('letters.verify.home')}
      </Link>
    </div>
  )
}

function Row({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className={mono ? 'font-mono' : ''}>{value}</dd>
    </div>
  )
}
