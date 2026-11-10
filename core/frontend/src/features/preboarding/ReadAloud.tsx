import { useMutation, useQuery } from '@tanstack/react-query'
import { Mic, Square, Volume2 } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { api, upload } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { useVoiceRecorder, voiceForm } from '../../lib/useVoiceRecorder'
import { errorText } from '../auth/errorText'

interface Result {
  accuracy: number
  missed: string[]
  transcript: string
  attempts: number
}

/** Stajyor bosqich matnini ovoz chiqarib o'qiydi: Whisper matnga aylantiradi, aniqlik foizi va o'qilmagan so'zlar. */
export function ReadAloudBox({ stageId, text }: { stageId: number; text: string }) {
  const { t } = useTranslation()
  const voice = useVoiceRecorder(300)
  const check = useMutation({
    mutationFn: (b: Blob) => upload<Result>('POST', `/api/v1/preboarding/my/stages/${stageId}/read-aloud?seconds=${voice.seconds}`, voiceForm(b)),
    onSuccess: () => voice.reset(),
  })
  if (text.trim().split(/\s+/).length < 5) return null
  const r = check.data
  const tone = !r ? '' : r.accuracy >= 85 ? 'text-emerald-600' : r.accuracy >= 60 ? 'text-amber-600' : 'text-rose-600'
  return (
    <Card className="flex flex-col gap-2 p-4">
      <div className="flex items-center gap-2">
        <Volume2 className="size-4 text-primary" />
        <h4 className="text-sm font-semibold">{t('readAloud.title')}</h4>
      </div>
      <p className="text-xs text-muted">{t('readAloud.hint')}</p>
      <div className="flex flex-wrap items-center gap-2">
        {voice.recording ? (
          <Button onClick={voice.stop} className="bg-rose-600 text-white hover:bg-rose-700">
            <Square className="size-4" />
            {t('readAloud.stop', { s: voice.seconds })}
          </Button>
        ) : (
          <Button variant="outline" onClick={() => void voice.start()} disabled={check.isPending}>
            <Mic className="size-4" />
            {r ? t('readAloud.again') : t('readAloud.start')}
          </Button>
        )}
        {voice.blob && (
          <Button disabled={check.isPending} onClick={() => voice.blob && check.mutate(voice.blob)}>
            {check.isPending ? t('readAloud.checking') : t('readAloud.check')}
          </Button>
        )}
        {voice.denied && <span className="text-xs text-danger">{t('preboarding.my.micDenied')}</span>}
      </div>
      {check.isError && <p className="text-xs text-danger">{errorText(t, check.error)}</p>}
      {r && (
        <div className="rounded-control bg-surface-2 p-3 text-sm">
          <div className={`text-2xl font-bold ${tone}`}>{r.accuracy}%</div>
          <div className="text-xs text-muted">{t('readAloud.attempt', { n: r.attempts })}</div>
          {r.missed.length > 0 && (
            <p className="mt-1 text-xs">
              <b>{t('readAloud.missed')}:</b> {r.missed.join(', ')}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}

/** HR: yo'nalish bo'yicha o'qish natijalari. */
export function ReadAloudResults({ trackId }: { trackId: number }) {
  const { t, i18n } = useTranslation()
  const q = useQuery({ queryKey: ['preboarding', 'read-aloud', trackId], queryFn: () => api<{ items: { employee: string; stage: string; best: number; attempts: number; last_at: string }[] }>(`/api/v1/preboarding/tracks/${trackId}/read-aloud`) })
  const items = q.data?.items ?? []
  return (
    <Card className="flex flex-col gap-2 p-5">
      <h3 className="text-sm font-semibold">{t('readAloud.results')}</h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted">{t('readAloud.noResults')}</p>
      ) : (
        <table className="w-full text-sm">
          <thead className="text-xs text-muted">
            <tr>
              <th className="py-1 text-left font-medium">{t('readAloud.employee')}</th>
              <th className="py-1 text-left font-medium">{t('readAloud.stage')}</th>
              <th className="py-1 text-right font-medium">{t('readAloud.best')}</th>
              <th className="py-1 text-right font-medium">{t('readAloud.attempts')}</th>
              <th className="py-1 text-right font-medium">{t('readAloud.last')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((x) => (
              <tr key={`${x.employee}-${x.stage}`}>
                <td className="py-1.5">{x.employee}</td>
                <td className="py-1.5 text-muted">{x.stage}</td>
                <td className={`py-1.5 text-right font-semibold ${x.best >= 85 ? 'text-emerald-600' : x.best >= 60 ? 'text-amber-600' : 'text-rose-600'}`}>{x.best}%</td>
                <td className="py-1.5 text-right tabular-nums">{x.attempts}</td>
                <td className="py-1.5 text-right text-xs text-muted">{formatDateTime(x.last_at, i18n.language)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  )
}
