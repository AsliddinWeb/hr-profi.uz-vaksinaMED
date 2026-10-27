import { useMutation, useQueryClient } from '@tanstack/react-query'
import { RefreshCw, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { useAiStatus } from './useAiStatus'

interface Out {
  text: string
  cached: boolean
  model: string
}

/** "AI xulosa" bloki: tugma bosilganda Claude qisqa xulosa beradi (kesh bor, matn o'zgarsa yangilanadi). AI o'chiq bo'lsa ko'rinmaydi. */
export function AiSummary({ entity, id }: { entity: 'ticket' | 'need' | 'task' | 'candidate'; id: number }) {
  const { t, i18n } = useTranslation()
  const status = useAiStatus().data
  const qc = useQueryClient()
  const [out, setOut] = useState<Out | null>(null)
  const run = useMutation({
    mutationFn: (refresh: boolean) => send<Out>('POST', '/api/v1/ai/summarize', { entity, id, lang: i18n.language === 'ru' ? 'ru' : 'uz', refresh }),
    onSuccess: (r) => {
      setOut(r)
      void qc.invalidateQueries({ queryKey: ['ai', 'status'] })
    },
  })
  if (!status?.enabled || !status.features.summary) return null
  return (
    <Card className="flex flex-col gap-3 border-primary/30 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 font-semibold">
          <Sparkles className="size-4 text-primary" />
          {t('ai.summary.title')}
        </h2>
        {out ? (
          <Button variant="ghost" className="h-8 px-2 text-xs" disabled={run.isPending} onClick={() => run.mutate(true)}>
            <RefreshCw className="size-3.5" />
            {t('ai.summary.refresh')}
          </Button>
        ) : (
          <Button variant="outline" disabled={run.isPending || status.remaining <= 0} onClick={() => run.mutate(false)}>
            {run.isPending ? t('ai.summary.working') : t('ai.summary.run')}
          </Button>
        )}
      </div>
      {out && (
        <>
          <p className="whitespace-pre-wrap text-sm leading-relaxed">{out.text}</p>
          <p className="text-xs text-muted">
            {t('ai.summary.note')} · {out.model}
            {out.cached && ` · ${t('ai.summary.cached')}`}
          </p>
        </>
      )}
      {!out && status.remaining <= 0 && <p className="text-xs text-muted">{t('errors.ai_limit')}</p>}
      {run.isError && (
        <p role="alert" className="text-sm text-danger">
          {errorText(t, run.error)}
        </p>
      )}
    </Card>
  )
}
