import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

export interface CameraHandle {
  /** Joriy kadrni JPEG sifatida oladi (eni <= 640). */
  capture: () => Promise<Blob | null>
}

/** Old kamera (selfi) oqimi. Preview ko'zguli (xodim o'zini ko'zguda ko'rgandek), yuboriladigan kadr esa asl. */
export const Camera = forwardRef<CameraHandle, { onReady?: (ready: boolean) => void }>(function Camera({ onReady }, ref) {
  const { t } = useTranslation()
  const video = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState<string | null>(() => (typeof navigator.mediaDevices?.getUserMedia === 'function' ? null : 'unsupported'))

  useEffect(() => {
    let stream: MediaStream | null = null
    let cancelled = false
    if (typeof navigator.mediaDevices?.getUserMedia !== 'function') return
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false })
      .then((s) => {
        if (cancelled) return s.getTracks().forEach((tr) => tr.stop())
        stream = s
        if (video.current) {
          video.current.srcObject = s
          void video.current.play()
        }
        onReady?.(true)
      })
      .catch((e: DOMException) => {
        setError(e.name === 'NotAllowedError' ? 'denied' : 'unavailable')
        onReady?.(false)
      })
    return () => {
      cancelled = true
      stream?.getTracks().forEach((tr) => tr.stop())
    }
  }, [onReady])

  useImperativeHandle(ref, () => ({
    capture: () =>
      new Promise((resolve) => {
        const v = video.current
        if (!v || !v.videoWidth) return resolve(null)
        const scale = Math.min(1, 640 / v.videoWidth)
        const c = document.createElement('canvas')
        c.width = Math.round(v.videoWidth * scale)
        c.height = Math.round(v.videoHeight * scale)
        c.getContext('2d')?.drawImage(v, 0, 0, c.width, c.height)
        c.toBlob((b) => resolve(b), 'image/jpeg', 0.85)
      }),
  }))

  if (error) {
    return (
      <div role="alert" className="grid aspect-[4/3] place-items-center rounded-card bg-surface-2 p-6 text-center text-sm text-danger">
        {t(`face.camera.${error}`)}
      </div>
    )
  }
  return <video ref={video} playsInline muted className="aspect-[4/3] w-full -scale-x-100 rounded-card bg-black object-cover" aria-label={t('face.camera.label')} />
})
