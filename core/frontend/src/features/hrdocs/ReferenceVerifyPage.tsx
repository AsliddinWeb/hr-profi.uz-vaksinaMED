import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, ShieldCheck, XCircle } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router-dom'

import { Card } from '../../components/ui/Card'
import { ApiError, api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'

interface Verification {
  valid: boolean
  intact: boolean
  number: string
  employee: string
  position: string
  status: 'issued' | 'cancelled'
  issued_at: string
  hash_prefix: string
}

/** QR orqali ish joyi ma'lumotnomasining holatini ochiq tekshirish. */
export function ReferenceVerifyPage() {
  const { t, i18n } = useTranslation()
  const { code = '' } = useParams()
  const q = useQuery({ queryKey: ['verify-reference', code], queryFn: () => api<Verification>(`/api/v1/public/reference/${encodeURIComponent(code)}`), retry: false })
  const item = q.data
  const good = !!item && item.valid && item.intact
  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col gap-5 px-4 py-10">
      <div className="flex items-center gap-3"><span className="grid size-10 place-items-center rounded-control bg-primary text-primary-fg"><ShieldCheck className="size-5" /></span><div><h1 className="text-xl font-semibold">{t('references.verifyTitle')}</h1><p className="text-sm text-muted">{t('references.verifyHint')}</p></div></div>
      {q.error instanceof ApiError ? <Card className="flex flex-col items-center gap-3 p-8 text-center" role="alert"><XCircle className="size-12 text-danger" /><p className="font-semibold">{t('references.notFound')}</p></Card> : !item ? <Card className="h-40 animate-pulse" /> : <Card className="flex flex-col gap-4 p-6">
        <div className="flex items-center gap-3">{good ? <CheckCircle2 className="size-10 text-success" /> : <XCircle className="size-10 text-danger" />}<div><p className="text-lg font-semibold">{t(good ? 'references.valid' : 'references.invalid')}</p>{!item.intact && <p className="text-sm text-danger">{t('references.tampered')}</p>}</div></div>
        <dl className="grid gap-3 text-sm sm:grid-cols-2"><Row label={t('references.number')} value={item.number} /><Row label={t('references.employee')} value={item.employee} /><Row label={t('references.position')} value={item.position} /><Row label={t('references.issuedAt')} value={formatDateTime(item.issued_at, i18n.language)} /><Row label={t('references.statusLabel')} value={t(`references.status.${item.status}`)} /><Row label="SHA-256" value={`${item.hash_prefix}…`} /></dl>
      </Card>}
      <Link to="/" className="text-center text-sm text-muted hover:text-text">{t('letters.verify.home')}</Link>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string }) { return <div><dt className="text-xs text-muted">{label}</dt><dd>{value}</dd></div> }
