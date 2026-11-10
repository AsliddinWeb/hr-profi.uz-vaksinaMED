import { useEffect, useRef, useState } from 'react'

/** Mikrofondan ovoz yozish (MediaRecorder). `maxSec` dan keyin o'zi to'xtaydi. */
export function useVoiceRecorder(maxSec = 180) {
  const [recording, setRecording] = useState(false)
  const [blob, setBlob] = useState<Blob | null>(null)
  const [seconds, setSeconds] = useState(0)
  const [denied, setDenied] = useState(false)
  const rec = useRef<MediaRecorder | null>(null)
  const timer = useRef<number | null>(null)
  const startedAt = useRef(0)

  useEffect(
    () => () => {
      if (timer.current) window.clearInterval(timer.current)
      if (rec.current?.state === 'recording') rec.current.stop()
    },
    [],
  )

  const start = async () => {
    setDenied(false)
    setBlob(null)
    try {
      const st = await navigator.mediaDevices.getUserMedia({ audio: true })
      const chunks: Blob[] = []
      const r = new MediaRecorder(st)
      r.ondataavailable = (e) => e.data.size && chunks.push(e.data)
      r.onstop = () => {
        st.getTracks().forEach((x) => x.stop())
        if (timer.current) window.clearInterval(timer.current)
        setBlob(new Blob(chunks, { type: r.mimeType || 'audio/webm' }))
        setRecording(false)
      }
      startedAt.current = Date.now()
      setSeconds(0)
      timer.current = window.setInterval(() => {
        const s = Math.floor((Date.now() - startedAt.current) / 1000)
        setSeconds(s)
        if (s >= maxSec && r.state === 'recording') r.stop()
      }, 500)
      r.start()
      rec.current = r
      setRecording(true)
    } catch {
      setDenied(true)
    }
  }
  const stop = () => {
    if (rec.current?.state === 'recording') rec.current.stop()
  }
  const reset = () => setBlob(null)
  return { recording, blob, seconds, denied, start, stop, reset }
}

/** Yozilgan ovozni FormData'ga tayyorlaydi (fayl kengaytmasi turiga mos). */
export function voiceForm(blob: Blob, extra: Record<string, string> = {}): FormData {
  const fd = new FormData()
  for (const [k, v] of Object.entries(extra)) fd.append(k, v)
  fd.append('file', blob, blob.type.includes('ogg') ? 'voice.ogg' : blob.type.includes('mp4') ? 'voice.mp4' : 'voice.webm')
  return fd
}
