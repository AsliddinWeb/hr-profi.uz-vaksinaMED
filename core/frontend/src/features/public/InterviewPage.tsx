import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Mic, Square } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { api, ApiError, send, upload } from '../../lib/api'
import { useVoiceRecorder, voiceForm } from '../../lib/useVoiceRecorder'

interface Q {
  id: string
  kind: 'hard' | 'soft'
  skill: string | null
  text: string
}
interface Pub {
  title: string
  status: string
  questions: Q[]
  answers: Record<string, { text?: string | null; transcript?: string | null }>
  speech: boolean
  submitted: boolean
}

/** /interview/:token: nomzodning AI suhbati — har savolga yozma yoki ovozli javob (Whisper matnga aylantiradi). */
export function InterviewPage() {
  const { t } = useTranslation()
  const token = useParams().token ?? ''
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['public-interview', token], queryFn: () => api<Pub>(`/api/v1/public/interview/${token}`), retry: false })
  const submit = useMutation({ mutationFn: () => send('POST', `/api/v1/public/interview/${token}/submit`), onSuccess: () => void qc.invalidateQueries({ queryKey: ['public-interview', token] }) })
  const d = q.data
  return (
    <main className="min-h-screen bg-gradient-to-br from-violet-50 via-fuchsia-50 to-amber-50 px-4 py-8 dark:from-[#1b1530] dark:via-[#1d1428] dark:to-[#221c14]">
      <div className="mx-auto flex max-w-2xl flex-col gap-4">
        <header className="text-center">
          <h1 className="text-2xl font-bold text-[#4b1d73] dark:text-violet-200">{t('aiiv.publicTitle')}</h1>
          {d && <p className="mt-1 text-sm text-[#6b5a80]">{d.title}</p>}
        </header>
        {q.error instanceof ApiError ? (
          <Box>{t('recruitCore.public.notFound')}</Box>
        ) : !d ? (
          <Box>
            <div className="h-40 animate-pulse rounded-xl bg-violet-100/60" />
          </Box>
        ) : d.submitted || submit.isSuccess ? (
          <Box>
            <div className="flex flex-col items-center gap-2 py-6 text-center">
              <CheckCircle2 className="size-12 text-emerald-500" />
              <p className="text-lg font-semibold">{t('aiiv.thanks')}</p>
              <p className="text-sm text-muted">{t('aiiv.thanksHint')}</p>
            </div>
          </Box>
        ) : (
          <>
            <Box>
              <p className="text-sm text-muted">{d.speech ? t('aiiv.hintVoice') : t('aiiv.hint')}</p>
            </Box>
            {d.questions.map((x, i) => (
              <QuestionCard key={x.id} n={i + 1} q={x} token={token} initial={d.answers[x.id]?.text ?? ''} speech={d.speech} />
            ))}
            {submit.isError && <p className="text-center text-sm text-danger">{t('aiiv.submitError')}</p>}
            <button type="button" disabled={submit.isPending} onClick={() => submit.mutate()} className="self-center rounded-full bg-gradient-to-r from-[#4b1d73] to-[#7b2fa8] px-8 py-3 text-sm font-semibold text-white shadow-lg disabled:opacity-60">
              {t('aiiv.submit')}
            </button>
          </>
        )}
      </div>
    </main>
  )
}

function Box({ children }: { children: React.ReactNode }) {
  return <section className="rounded-3xl border border-violet-100 bg-white/85 p-5 shadow-[0_10px_40px_-20px_rgba(75,29,115,0.35)] dark:border-violet-900/50 dark:bg-[#1e1a2b]/90">{children}</section>
}

function QuestionCard({ n, q, token, initial, speech }: { n: number; q: Q; token: string; initial: string; speech: boolean }) {
  const { t } = useTranslation()
  const [text, setText] = useState(initial)
  const [saved, setSaved] = useState(!!initial)
  const voice = useVoiceRecorder(180)
  const save = useMutation({ mutationFn: (v: string) => send('POST', `/api/v1/public/interview/${token}/answer`, { qid: q.id, text: v }), onSuccess: () => setSaved(true) })
  const sendVoice = useMutation({
    mutationFn: (b: Blob) => upload<{ transcript: string; answers: Record<string, { text?: string | null }> }>('POST', `/api/v1/public/interview/${token}/voice`, voiceForm(b, { qid: q.id })),
    onSuccess: (r) => {
      setText(r.answers[q.id]?.text ?? r.transcript)
      setSaved(true)
      voice.reset()
    },
  })
  return (
    <Box>
      <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-[#8a7a9e]">
        <span>{t('aiiv.question', { n })}</span>
        <span className={q.kind === 'hard' ? 'text-sky-600' : 'text-emerald-600'}>{q.kind === 'hard' ? 'Hard skill' : 'Soft skill'}</span>
      </div>
      <p className="mb-3 font-medium">{q.text}</p>
      <textarea
        rows={4}
        maxLength={4000}
        value={text}
        onChange={(e) => (setText(e.target.value), setSaved(false))}
        onBlur={() => text.trim() && !saved && save.mutate(text.trim())}
        placeholder={t('aiiv.placeholder')}
        className="w-full rounded-control bg-surface px-3 py-2 text-sm shadow-[inset_0_0_0_1px_var(--border-strong)] outline-none focus:ring-2 focus:ring-primary/30"
      />
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
        {speech &&
          (voice.recording ? (
            <button type="button" onClick={voice.stop} className="inline-flex items-center gap-1.5 rounded-full bg-rose-600 px-3 py-1.5 font-semibold text-white">
              <Square className="size-3.5" />
              {t('aiiv.stop', { s: voice.seconds })}
            </button>
          ) : (
            <button type="button" onClick={() => void voice.start()} className="inline-flex items-center gap-1.5 rounded-full border border-violet-200 px-3 py-1.5 font-semibold text-violet-700 dark:border-violet-800 dark:text-violet-300">
              <Mic className="size-3.5" />
              {t('aiiv.record')}
            </button>
          ))}
        {voice.blob && (
          <button type="button" disabled={sendVoice.isPending} onClick={() => voice.blob && sendVoice.mutate(voice.blob)} className="rounded-full bg-violet-700 px-3 py-1.5 font-semibold text-white disabled:opacity-60">
            {sendVoice.isPending ? t('aiiv.transcribing') : t('aiiv.sendVoice')}
          </button>
        )}
        {voice.denied && <span className="text-danger">{t('preboarding.my.micDenied')}</span>}
        {sendVoice.isError && <span className="text-danger">{t('aiiv.voiceError')}</span>}
        <span className="ml-auto text-muted">{save.isPending ? t('aiiv.saving') : saved ? t('aiiv.saved') : ''}</span>
      </div>
    </Box>
  )
}
