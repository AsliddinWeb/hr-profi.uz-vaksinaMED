import { ArrowLeft, ArrowRight, ScanFace } from 'lucide-react'
import { useTranslation } from 'react-i18next'

import type { Challenge } from './api'

type Phase = 'idle' | 'preparing' | 'capturing' | 'uploading' | 'done'

/** Joriy qadam bo'yicha ko'rsatma (xodim nuqtai nazaridan: "chapga" = o'zining chap tomoniga). */
export function GuidedCapture({ phase, steps, stepIndex }: { phase: Phase; steps: Challenge['steps']; stepIndex: number }) {
  const { t } = useTranslation()
  if (phase === 'idle' || phase === 'done') return <p className="text-center text-sm text-muted">{t('face.guide.idle')}</p>
  if (phase === 'uploading') return <p className="text-center text-sm font-medium">{t('face.guide.uploading')}</p>
  const step = steps[stepIndex] ?? 'center'
  const Icon = step === 'left' ? ArrowLeft : step === 'right' ? ArrowRight : ScanFace
  return (
    <div className="flex flex-col items-center gap-2" role="status" aria-live="polite">
      <Icon className="size-8 text-primary" />
      <p className="text-center text-lg font-semibold">{t(`face.guide.${step}`)}</p>
      <div className="flex gap-1.5" aria-hidden>
        {steps.map((_, i) => (
          <span key={i} className={'h-1.5 w-10 rounded-full ' + (i < stepIndex ? 'bg-success' : i === stepIndex ? 'bg-primary' : 'bg-surface-2')} />
        ))}
      </div>
      <p className="text-xs text-muted">{phase === 'preparing' ? t('face.guide.prepare') : t('face.guide.hold')}</p>
    </div>
  )
}
