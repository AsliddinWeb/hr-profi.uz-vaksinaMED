import { useCallback, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { ApiError, api, upload } from '../../lib/api'
import { errorText } from '../auth/errorText'
import type { CameraHandle } from './Camera'
import type { Challenge } from './api'

const FRAMES_PER_STEP = 3
const FRAME_GAP_MS = 450
const STEP_PREPARE_MS = 1400

type Phase = 'idle' | 'preparing' | 'capturing' | 'uploading' | 'done'

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))

/**
 * Liveness qadamlarini (markaz -> burilish -> qarama-qarshi burilish) boshqaradi: serverdan challenge oladi,
 * har qadamda xodimga ko'rsatma berib kadrlarni yig'adi va `endpoint` ga yuboradi.
 */
export function useFaceSession<T>(camera: React.RefObject<CameraHandle | null>, purpose: 'enroll' | 'verify', endpoint: string) {
  const { t } = useTranslation()
  const [phase, setPhase] = useState<Phase>('idle')
  const [stepIndex, setStepIndex] = useState(0)
  const [steps, setSteps] = useState<Challenge['steps']>([])
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<T | null>(null)
  const running = useRef(false)

  const run = useCallback(
    async (extra: Record<string, string> = {}) => {
      if (running.current) return
      running.current = true
      setError(null)
      setResult(null)
      try {
        setPhase('preparing')
        const ch = await api<Challenge>('/api/v1/face/challenge', { method: 'POST', body: JSON.stringify({ purpose }) })
        setSteps(ch.steps)
        const blobs: Blob[] = []
        for (let i = 0; i < ch.steps.length; i++) {
          setStepIndex(i)
          setPhase('preparing')
          await sleep(STEP_PREPARE_MS)
          setPhase('capturing')
          for (let k = 0; k < FRAMES_PER_STEP; k++) {
            const b = await camera.current?.capture()
            if (b) blobs.push(b)
            await sleep(FRAME_GAP_MS)
          }
        }
        if (blobs.length < ch.min_frames) throw new Error('camera')
        setPhase('uploading')
        const form = new FormData()
        form.append('challenge_id', ch.id)
        for (const [k, v] of Object.entries(extra)) form.append(k, v)
        blobs.forEach((b, i) => form.append('frames', b, `f${i}.jpg`))
        const res = await upload<T>('POST', endpoint, form)
        setResult(res)
        setPhase('done')
      } catch (e) {
        setPhase('idle')
        if (e instanceof ApiError && e.code === 'liveness_failed') {
          const why = t(`face.liveness.${String(e.extra.reason)}`, { defaultValue: t('face.liveness.challenge_failed') })
          const hint = e.extra.hint ? ` ${t(`face.hint.${String(e.extra.hint)}`, { defaultValue: '' })}` : ''
          setError(why + hint)
        } else if (e instanceof ApiError && e.code === 'face_locked') {
          setError(t('errors.face_locked', { minutes: Math.max(1, Math.ceil(Number(e.extra.retry_after ?? 600) / 60)) }))
        } else if (e instanceof ApiError && e.code === 'outside_geofence') {
          setError(t('errors.outside_geofence', { distance: e.extra.distance, radius: e.extra.radius }))
        } else if (e instanceof Error && e.message === 'camera') {
          setError(t('face.camera.noFrames'))
        } else {
          setError(errorText(t, e))
        }
      } finally {
        running.current = false
      }
    },
    [camera, endpoint, purpose, t],
  )

  return { phase, stepIndex, steps, error, result, run, reset: () => (setPhase('idle'), setResult(null), setError(null)) }
}
