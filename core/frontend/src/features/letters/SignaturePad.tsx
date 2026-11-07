import { Eraser } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../../components/ui/Button'

/** Imzo chizish maydoni (sichqoncha, barmoq, stilus). Saqlanganda shaffof fonli PNG (data URL) qaytaradi. */
export function SignaturePad({ onSave, onCancel, busy }: { onSave: (png: string) => void; onCancel: () => void; busy?: boolean }) {
  const { t } = useTranslation()
  const canvas = useRef<HTMLCanvasElement>(null)
  const drawing = useRef(false)
  const last = useRef<{ x: number; y: number } | null>(null)
  const [length, setLength] = useState(0)

  useEffect(() => {
    const c = canvas.current
    if (!c) return
    const ratio = window.devicePixelRatio || 1
    const { width, height } = c.getBoundingClientRect()
    c.width = Math.round(width * ratio)
    c.height = Math.round(height * ratio)
    const ctx = c.getContext('2d')
    if (!ctx) return
    ctx.scale(ratio, ratio)
    ctx.lineWidth = 2.2
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.strokeStyle = '#1e3a8a'
  }, [])

  const point = (e: React.PointerEvent<HTMLCanvasElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    return { x: e.clientX - r.left, y: e.clientY - r.top }
  }
  const down = (e: React.PointerEvent<HTMLCanvasElement>) => {
    e.currentTarget.setPointerCapture(e.pointerId)
    drawing.current = true
    last.current = point(e)
  }
  const move = (e: React.PointerEvent<HTMLCanvasElement>) => {
    if (!drawing.current || !last.current) return
    const ctx = e.currentTarget.getContext('2d')
    const p = point(e)
    if (!ctx) return
    ctx.beginPath()
    ctx.moveTo(last.current.x, last.current.y)
    ctx.lineTo(p.x, p.y)
    ctx.stroke()
    setLength((l) => l + Math.hypot(p.x - last.current!.x, p.y - last.current!.y))
    last.current = p
  }
  const up = () => {
    drawing.current = false
    last.current = null
  }
  const clear = () => {
    const c = canvas.current
    c?.getContext('2d')?.clearRect(0, 0, c.width, c.height)
    setLength(0)
  }
  const enough = length > 60

  return (
    <div className="flex flex-col gap-3">
      <div>
        <div className="text-sm font-semibold">{t('autoLetter.sign.padTitle')}</div>
        <p className="text-xs text-muted">{t('autoLetter.sign.padHint')}</p>
      </div>
      <canvas
        ref={canvas}
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerLeave={up}
        aria-label={t('autoLetter.sign.padTitle')}
        className="h-44 w-full cursor-crosshair touch-none rounded-control border-2 border-dashed border-border bg-white"
      />
      <div className="flex flex-wrap gap-2">
        <Button type="button" variant="outline" onClick={clear} disabled={!length || busy}>
          <Eraser className="size-4" />
          {t('autoLetter.sign.clear')}
        </Button>
        <Button type="button" variant="outline" onClick={onCancel} disabled={busy}>
          {t('common.cancel')}
        </Button>
        <Button type="button" className="ml-auto" disabled={!enough || busy} onClick={() => canvas.current && onSave(canvas.current.toDataURL('image/png'))}>
          {t('autoLetter.sign.save')}
        </Button>
      </div>
    </div>
  )
}
