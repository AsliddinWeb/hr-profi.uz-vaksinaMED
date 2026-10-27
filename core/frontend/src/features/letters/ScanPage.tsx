import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Upload } from 'lucide-react'
import { useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, upload } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import type { LetterDetail } from './api'

/** /letters/:id/scan: qog'ozdagi qo'lda imzolangan nusxani skaner/kamera orqali yuklash (PDF, JPG, PNG). */
export function ScanPage() {
  const { t } = useTranslation()
  const id = Number(useParams().id)
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const input = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const q = useQuery({ queryKey: ['letters', 'one', id], queryFn: () => api<LetterDetail>(`/api/v1/letters/${id}`), retry: false })
  const up = useMutation({
    mutationFn: () => {
      const form = new FormData()
      form.append('file', file as File)
      return upload('POST', `/api/v1/letters/${id}/scan`, form)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['letters'] })
      toast.push({ title: t('letters.scan.uploaded'), tone: 'success' })
      navigate(`/letters/${id}`, { replace: true })
    },
  })
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  const l = q.data
  if (!l) return <Skeleton className="mx-auto h-72 max-w-xl" />
  if (!l.can_scan) return <Navigate to={`/letters/${id}`} replace />

  const pick = (f: File | null) => {
    setFile(f)
    setPreview((old) => {
      if (old) URL.revokeObjectURL(old)
      return f && f.type.startsWith('image/') ? URL.createObjectURL(f) : null
    })
  }

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5">
      <PageHeader title={t('letters.scan.title')} subtitle={`${l.number} · ${l.employee.full_name}`} backTo={`/letters/${id}`} backLabel={l.number} />
      <Card className="flex flex-col gap-4 p-6">
        <p className="text-sm text-muted">{t('letters.scan.hint')}</p>
        <input ref={input} type="file" accept="application/pdf,image/jpeg,image/png" capture="environment" className="sr-only" onChange={(e) => pick(e.target.files?.[0] ?? null)} aria-label={t('letters.scan.choose')} />
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" onClick={() => input.current?.click()}>
            <Camera className="size-4" />
            {t('letters.scan.choose')}
          </Button>
        </div>
        {file && (
          <div className="rounded-control border border-border p-3 text-sm">
            <div className="font-medium">{file.name}</div>
            <div className="text-xs text-muted">{(file.size / 1024).toFixed(0)} KB</div>
            {preview && <img src={preview} alt={t('letters.scan.preview')} className="mt-3 max-h-72 w-full rounded-control object-contain" />}
          </div>
        )}
        {up.isError && (
          <p role="alert" className="text-sm text-danger">
            {errorText(t, up.error)}
          </p>
        )}
        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={() => navigate(`/letters/${id}`)}>
            {t('common.cancel')}
          </Button>
          <Button disabled={!file || up.isPending} onClick={() => up.mutate()}>
            <Upload className="size-4" />
            {t('letters.scan.upload')}
          </Button>
        </div>
      </Card>
    </div>
  )
}
