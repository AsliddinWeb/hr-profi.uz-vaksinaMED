import { useQuery } from '@tanstack/react-query'
import { CheckCircle2, ScanLine, ShieldAlert, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { ApiError, api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { STATUS_TONE, type VerifyResult } from './api'

/** Ochiq sahifa (kirish shart emas): QR/kod bo'yicha hujjat haqiqiyligini tekshirish va QR skaneri. */
export function VerifyPage() {
  const { t } = useTranslation()
  const { code } = useParams()
  return (
    <div className="mx-auto flex min-h-screen max-w-lg flex-col gap-5 px-4 py-10">
      <div className="flex items-center gap-3">
        <span className="grid size-10 place-items-center rounded-control bg-primary text-primary-fg">
          <ShieldAlert className="size-5" />
        </span>
        <div>
          <h1 className="text-xl font-semibold">{t('letters.verify.title')}</h1>
          <p className="text-sm text-muted">{t('letters.verify.subtitle')}</p>
        </div>
      </div>
      {code ? <Result code={code} /> : <Finder />}
      <Link to="/" className="text-center text-sm text-muted hover:text-text">
        {t('letters.verify.home')}
      </Link>
    </div>
  )
}

function Result({ code }: { code: string }) {
  const { t, i18n } = useTranslation()
  const [hash, setHash] = useState('')
  const q = useQuery({ queryKey: ['verify', code, hash], queryFn: () => api<VerifyResult>(`/api/v1/public/letters/${encodeURIComponent(code)}${hash.trim() ? `?hash=${encodeURIComponent(hash.trim())}` : ''}`), retry: false })
  if (q.error instanceof ApiError) {
    return (
      <Card className="flex flex-col items-center gap-3 p-8 text-center" role="alert">
        <XCircle className="size-14 text-danger" />
        <p className="font-semibold">{q.error.status === 404 ? t('letters.verify.notFound') : t(`errors.${q.error.code}`, { defaultValue: t('errors.unknown'), minutes: 1 })}</p>
        <p className="text-sm text-muted">{t('letters.verify.notFoundHint')}</p>
      </Card>
    )
  }
  const r = q.data
  if (!r) return <Card className="h-40 animate-pulse" />
  const good = r.valid && r.intact
  return (
    <Card className="flex flex-col gap-4 p-6">
      <div className="flex items-center gap-3">
        {good ? <CheckCircle2 className="size-10 text-success" /> : <XCircle className="size-10 text-danger" />}
        <div>
          <p className="text-lg font-semibold">{good ? t('letters.verify.valid') : t('letters.verify.invalid')}</p>
          {!r.intact && <p className="text-sm text-danger">{t('letters.verify.tampered')}</p>}
        </div>
      </div>
      <dl className="grid gap-3 text-sm sm:grid-cols-2">
        <Row label={t('letters.verify.number')} value={r.number} />
        <Row label={t('letters.verify.employee')} value={r.employee} />
        <Row label={t('letters.incident')} value={`${t(`letters.incidents.${r.incident_type}`)} · ${r.incident_date.split('-').reverse().join('.')}`} />
        <Row label={t('letters.verify.signedAt')} value={r.signed_at ? formatDateTime(r.signed_at, i18n.language) : '—'} />
        <div>
          <dt className="text-xs text-muted">{t('attendance.statusLabel')}</dt>
          <dd>
            <Badge tone={STATUS_TONE[r.status]}>{t(`letters.status.${r.status}`)}</Badge>
          </dd>
        </div>
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

interface BarcodeDetectorLike {
  detect(source: HTMLVideoElement): Promise<{ rawValue: string }[]>
}

/** Kodni qo'lda kiritish yoki kamera bilan QR skanerlash (brauzer BarcodeDetector ni qo'llasa). */
function Finder() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)
  const video = useRef<HTMLVideoElement>(null)
  const supported = typeof window !== 'undefined' && 'BarcodeDetector' in window

  const go = (value: string) => {
    const m = value.match(/\/verify\/([\w-]+)/)
    const code = (m ? m[1] : value.trim()).replace(/[^\w-]/g, '')
    if (code) navigate(`/verify/${code}`)
  }

  useEffect(() => {
    if (!scanning) return
    let stream: MediaStream | null = null
    let stop = false
    const Detector = (window as unknown as { BarcodeDetector: new (o: { formats: string[] }) => BarcodeDetectorLike }).BarcodeDetector
    const detector = new Detector({ formats: ['qr_code'] })
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'environment' }, audio: false })
      .then(async (s) => {
        stream = s
        if (!video.current) return
        video.current.srcObject = s
        await video.current.play()
        const tick = async () => {
          if (stop || !video.current) return
          try {
            const found = await detector.detect(video.current)
            if (found[0]) return go(found[0].rawValue)
          } catch {
            /* kadr tayyor emas */
          }
          setTimeout(tick, 300)
        }
        void tick()
      })
      .catch(() => setScanError(t('face.camera.denied')))
    return () => {
      stop = true
      stream?.getTracks().forEach((tr) => tr.stop())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scanning])

  return (
    <Card className="flex flex-col gap-4 p-6">
      {supported && (
        <>
          {scanning ? <video ref={video} playsInline muted className="aspect-square w-full rounded-card bg-black object-cover" aria-label={t('face.camera.label')} /> : null}
          <Button variant="outline" onClick={() => (setScanError(null), setScanning((s) => !s))}>
            <ScanLine className="size-4" />
            {scanning ? t('letters.verify.stopScan') : t('letters.verify.scan')}
          </Button>
          {scanError && <p role="alert" className="text-sm text-danger">{scanError}</p>}
        </>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault()
          go(text)
        }}
        className="flex flex-col gap-2"
      >
        <label htmlFor="code" className="text-sm font-medium">
          {t('letters.verify.enterCode')}
        </label>
        <div className="flex gap-2">
          <Input id="code" value={text} onChange={(e) => setText(e.target.value)} placeholder={t('letters.verify.codePlaceholder')} maxLength={200} />
          <Button type="submit" disabled={!text.trim()}>
            {t('letters.verify.check')}
          </Button>
        </div>
      </form>
      {!supported && <p className="text-xs text-muted">{t('letters.verify.noScanner')}</p>}
    </Card>
  )
}
