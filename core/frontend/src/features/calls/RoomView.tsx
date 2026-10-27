import { Mic, MicOff, MonitorUp, MonitorX, PhoneOff, Video, VideoOff } from 'lucide-react'
import type { Participant, Room } from 'livekit-client'
import { useEffect, useRef, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from '../../components/ui/Button'
import { initials } from '../../lib/format'
import { durationText, livekitUrl, type TokenResp } from './api'

type LK = typeof import('livekit-client')

function Tile({ p, lk, big }: { p: Participant; lk: LK; big?: boolean }) {
  const video = useRef<HTMLVideoElement>(null)
  const audio = useRef<HTMLDivElement>(null)
  const { Track } = lk
  const cam = p.getTrackPublication(Track.Source.Camera)
  const screen = p.getTrackPublication(Track.Source.ScreenShare)
  const shown = screen?.track && !screen.isMuted ? screen : cam?.track && !cam.isMuted ? cam : undefined
  const mic = p.getTrackPublication(Track.Source.Microphone)
  const track = shown?.track
  const micTrack = p.isLocal ? undefined : mic?.track
  useEffect(() => {
    const el = video.current
    if (!track || !el) return
    track.attach(el)
    return () => {
      track.detach(el)
    }
  }, [track])
  useEffect(() => {
    const box = audio.current
    if (!micTrack || !box) return
    const el = micTrack.attach()
    box.appendChild(el)
    return () => {
      micTrack.detach(el)
      el.remove()
    }
  }, [micTrack])
  const muted = !mic || mic.isMuted
  return (
    <div className={'relative overflow-hidden rounded-card bg-surface-2 ' + (big ? 'aspect-video' : 'aspect-video') + (p.isSpeaking ? ' ring-2 ring-primary' : '')}>
      {track ? <video ref={video} autoPlay playsInline muted className={'size-full ' + (screen?.track && shown === screen ? 'object-contain' : 'object-cover')} /> : (
        <div className="grid size-full place-items-center">
          <span className="grid size-16 place-items-center rounded-full bg-primary/20 text-xl font-semibold text-primary">{initials(p.name || p.identity)}</span>
        </div>
      )}
      <div ref={audio} className="hidden" />
      <div className="absolute inset-x-0 bottom-0 flex items-center justify-between bg-gradient-to-t from-black/60 to-transparent px-3 py-2 text-xs text-white">
        <span className="truncate">{p.name || p.identity}{p.isLocal ? ' (siz)' : ''}</span>
        {muted && <MicOff className="size-3.5 shrink-0" aria-label="muted" />}
      </div>
    </div>
  )
}

/** Faol qo'ng'iroq: video setkasi, mikrofon / kamera / ekran ulashish, chiqish. */
export function RoomView({ tok, startedAt, canEnd, banner, onLeave, onEnd }: { tok: TokenResp; startedAt: number; canEnd: boolean; banner?: string; onLeave: () => void; onEnd: () => void }) {
  const { t } = useTranslation()
  const [lk, setLk] = useState<LK | null>(null)
  const [room, setRoom] = useState<Room | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [, setTick] = useState(0)
  const [secs, setSecs] = useState(0)
  const [micOn, setMicOn] = useState(false)
  const [camOn, setCamOn] = useState(false)
  const [shareOn, setShareOn] = useState(false)
  const [note, setNote] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    let r: Room | null = null
    void (async () => {
      const mod = await import('livekit-client')
      if (!alive) return
      setLk(mod)
      r = new mod.Room({ adaptiveStream: true, dynacast: true })
      const bump = () => setTick((n) => n + 1)
      const ev = mod.RoomEvent
      for (const e of [ev.ParticipantConnected, ev.ParticipantDisconnected, ev.TrackSubscribed, ev.TrackUnsubscribed, ev.TrackMuted, ev.TrackUnmuted, ev.LocalTrackPublished, ev.LocalTrackUnpublished, ev.ActiveSpeakersChanged]) r.on(e, bump)
      r.on(ev.Disconnected, () => alive && setError(t('calls.room.disconnected')))
      try {
        await r.connect(livekitUrl(tok), tok.token)
        if (!alive) return void r.disconnect()
        setRoom(r)
        try {
          await r.localParticipant.setMicrophoneEnabled(true)
          setMicOn(true)
        } catch {
          setNote(t('calls.room.noMic'))
        }
        if (tok.media === 'video') {
          try {
            await r.localParticipant.setCameraEnabled(true)
            setCamOn(true)
          } catch {
            setNote(t('calls.room.noCamera'))
          }
        }
        bump()
      } catch {
        if (alive) setError(t('calls.room.connectFailed'))
      }
    })()
    return () => {
      alive = false
      void r?.disconnect()
    }
  }, [tok, t])

  useEffect(() => {
    const id = setInterval(() => setSecs(Math.max(0, Math.floor((Date.now() - startedAt) / 1000))), 1000)
    return () => clearInterval(id)
  }, [startedAt])

  const toggle = async (kind: 'mic' | 'cam' | 'share') => {
    if (!room) return
    setNote(null)
    try {
      if (kind === 'mic') setMicOn(await room.localParticipant.setMicrophoneEnabled(!micOn).then(() => !micOn))
      if (kind === 'cam') setCamOn(await room.localParticipant.setCameraEnabled(!camOn).then(() => !camOn))
      if (kind === 'share') setShareOn(await room.localParticipant.setScreenShareEnabled(!shareOn).then(() => !shareOn))
    } catch {
      setNote(t(kind === 'mic' ? 'calls.room.noMic' : kind === 'cam' ? 'calls.room.noCamera' : 'calls.room.noShare'))
    }
  }

  const all: Participant[] = room ? [room.localParticipant, ...Array.from(room.remoteParticipants.values())] : []
  const sharing = lk ? all.find((p) => p.getTrackPublication(lk.Track.Source.ScreenShare)?.track) : undefined
  const others = sharing ? all.filter((p) => p !== sharing) : all
  const cols = others.length <= 1 ? 'grid-cols-1 sm:grid-cols-2' : others.length <= 4 ? 'grid-cols-2' : 'grid-cols-2 lg:grid-cols-3'

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between text-sm text-muted">
        <span>{error ?? banner ?? (room ? t('calls.room.connected', { count: all.length }) : t('calls.room.connecting'))}</span>
        <span className="tabular-nums">{durationText(secs)}</span>
      </div>
      {note && <p role="status" className="rounded-control bg-warning/10 px-3 py-2 text-sm">{note}</p>}
      {lk && room && (
        <>
          {sharing && (
            <div className="max-w-4xl">
              <Tile p={sharing} lk={lk} big />
            </div>
          )}
          <div className={'grid gap-3 ' + (sharing ? 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-4' : cols)}>
            {others.map((p) => (
              <Tile key={p.identity} p={p} lk={lk} />
            ))}
          </div>
        </>
      )}
      <div className="sticky bottom-3 flex flex-wrap items-center justify-center gap-2 rounded-card border border-border bg-surface/95 p-3 shadow-card backdrop-blur">
        <Button variant={micOn ? 'outline' : 'primary'} onClick={() => void toggle('mic')} disabled={!room} aria-pressed={micOn} aria-label={micOn ? t('calls.room.muteMic') : t('calls.room.unmuteMic')}>
          {micOn ? <Mic className="size-4" /> : <MicOff className="size-4" />}
        </Button>
        <Button variant={camOn ? 'outline' : 'primary'} onClick={() => void toggle('cam')} disabled={!room} aria-pressed={camOn} aria-label={camOn ? t('calls.room.camOff') : t('calls.room.camOn')}>
          {camOn ? <Video className="size-4" /> : <VideoOff className="size-4" />}
        </Button>
        <Button variant="outline" onClick={() => void toggle('share')} disabled={!room} aria-pressed={shareOn}>
          {shareOn ? <MonitorX className="size-4" /> : <MonitorUp className="size-4" />}
          {shareOn ? t('calls.room.stopShare') : t('calls.room.share')}
        </Button>
        <Button variant="outline" className="text-danger" onClick={onLeave}>
          <PhoneOff className="size-4" />
          {t('calls.room.leave')}
        </Button>
        {canEnd && (
          <Button className="bg-danger text-white hover:bg-danger/90" onClick={onEnd}>
            {t('calls.room.endAll')}
          </Button>
        )}
      </div>
    </div>
  )
}
