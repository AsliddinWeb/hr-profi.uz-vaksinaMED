import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

interface BarcodeDetectorLike {
  detect(source: HTMLVideoElement): Promise<{ rawValue: string }[]>
}

/** Ilova ichidagi QR skaner (orqa kamera). Filial QR kodidan tokenni ajratib `onToken` ga beradi. */
export function QrScanner({ onToken }: { onToken: (token: string) => void }) {
  const { t } = useTranslation()
  const video = useRef<HTMLVideoElement>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
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
            const raw = found[0]?.rawValue
            if (raw) {
              const m = raw.match(/[?&]t=([\w.-]+)/)
              if (m) return onToken(m[1])
              setError(t('attendance.panel.qrWrong'))
            }
          } catch {
            /* kadr hali tayyor emas */
          }
          setTimeout(tick, 300)
        }
        void tick()
      })
      .catch(() => setError(t('face.camera.denied')))
    return () => {
      stop = true
      stream?.getTracks().forEach((tr) => tr.stop())
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <div className="flex flex-col gap-2">
      <video ref={video} playsInline muted className="aspect-square w-full rounded-card bg-black object-cover" aria-label={t('face.camera.label')} />
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  )
}
