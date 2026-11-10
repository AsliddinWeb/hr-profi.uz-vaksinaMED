import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bot, Copy, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Input } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { api, send } from '../../lib/api'
import { formatDateTime } from '../../lib/format'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'

interface Iv {
  id: number
  title: string
  status: 'sent' | 'answering' | 'submitted' | 'graded'
  url: string
  questions: { id: string; kind: 'hard' | 'soft'; skill: string | null; text: string }[]
  answers: Record<string, { text?: string | null; transcript?: string | null }>
  scores: Record<string, { score: number; feedback: string }>
  hard_pct: number | null
  soft_pct: number | null
  summary: string | null
  created_at: string
}
const TONE = { sent: 'neutral', answering: 'info', submitted: 'warning', graded: 'success' } as const

/** AI suhbat (hard/soft skill): yaratish, havolani yuborish, javoblar, AI yoki qo'lda baholash. */
export function AiInterviewPanel({ applicationId, employeeId }: { applicationId?: number; employeeId?: number }) {
  const { t, i18n } = useTranslation()
  const toast = useToast()
  const qc = useQueryClient()
  const can = useCan()
  const manage = can('recruit.manage') || can('internship.manage')
  const key = ['ai-interviews', applicationId ?? 0, employeeId ?? 0]
  const qs = applicationId ? `application_id=${applicationId}` : `employee_id=${employeeId}`
  const list = useQuery({ queryKey: key, queryFn: () => api<{ items: Iv[] }>(`/api/v1/ai-interviews?${qs}`) })
  const meta = useQuery({ queryKey: ['ai-interviews', 'meta'], queryFn: () => api<{ ai: boolean; speech: boolean }>('/api/v1/ai-interviews/meta') })
  const refresh = () => void qc.invalidateQueries({ queryKey: key })
  const create = useMutation({
    mutationFn: () => send<Iv>('POST', '/api/v1/ai-interviews', { application_id: applicationId ?? null, employee_id: employeeId ?? null, lang: i18n.language === 'ru' ? 'ru' : 'uz' }),
    onSuccess: refresh,
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const items = list.data?.items ?? []
  return (
    <Card className="flex flex-col gap-3 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <Bot className="size-5 text-primary" />
        <h3 className="font-semibold">{t('aiiv.title')}</h3>
        {meta.data && <Badge tone={meta.data.ai ? 'success' : 'neutral'}>{meta.data.ai ? t('aiiv.aiOn') : t('aiiv.aiOff')}</Badge>}
        {meta.data && <Badge tone={meta.data.speech ? 'success' : 'neutral'}>{meta.data.speech ? t('aiiv.voiceOn') : t('aiiv.voiceOff')}</Badge>}
        {manage && (
          <Button className="ml-auto" disabled={create.isPending} onClick={() => create.mutate()}>
            <Sparkles className="size-4" />
            {t('aiiv.create')}
          </Button>
        )}
      </div>
      <p className="text-xs text-muted">{t('aiiv.hintStaff')}</p>
      {items.length === 0 && <p className="text-sm text-muted">{t('aiiv.none')}</p>}
      {items.map((iv) => (
        <InterviewCard key={iv.id} iv={iv} manage={manage} onChange={refresh} lang={i18n.language} />
      ))}
    </Card>
  )
}

function InterviewCard({ iv, manage, onChange, lang }: { iv: Iv; manage: boolean; onChange: () => void; lang: string }) {
  const { t } = useTranslation()
  const toast = useToast()
  const [open, setOpen] = useState(iv.status === 'graded' || iv.status === 'submitted')
  const [hard, setHard] = useState(String(iv.hard_pct ?? ''))
  const [soft, setSoft] = useState(String(iv.soft_pct ?? ''))
  const grade = useMutation({
    mutationFn: (manual: boolean) => send('POST', `/api/v1/ai-interviews/${iv.id}/grade`, manual ? { hard_pct: Number(hard), soft_pct: Number(soft), summary: null } : undefined),
    onSuccess: onChange,
    onError: (e) => toast.push({ title: errorText(t, e), tone: 'danger' }),
  })
  const link = `${location.origin}${iv.url}`
  return (
    <div className="rounded-control border border-border p-3">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <Badge tone={TONE[iv.status]}>{t(`aiiv.status.${iv.status}`)}</Badge>
        <span className="text-xs text-muted">{formatDateTime(iv.created_at, lang)}</span>
        {iv.hard_pct != null && <Badge tone="info">Hard {iv.hard_pct}%</Badge>}
        {iv.soft_pct != null && <Badge tone="violet">Soft {iv.soft_pct}%</Badge>}
        <button type="button" className="ml-auto text-xs font-semibold text-primary hover:underline" onClick={() => setOpen((v) => !v)}>
          {open ? t('aiiv.hide') : t('aiiv.show')}
        </button>
      </div>
      {(iv.status === 'sent' || iv.status === 'answering') && (
        <div className="mt-2 flex items-center gap-2 rounded-control bg-surface-2 px-2 py-1.5 text-xs">
          <code className="min-w-0 flex-1 truncate">{link}</code>
          <button
            type="button"
            aria-label={t('rdash.copy')}
            onClick={() => {
              void navigator.clipboard?.writeText(link)
              toast.push({ title: t('rdash.copied'), tone: 'success' })
            }}
          >
            <Copy className="size-4" />
          </button>
        </div>
      )}
      {iv.summary && <p className="mt-2 rounded-control bg-primary/5 p-2 text-sm">{iv.summary}</p>}
      {open && (
        <ol className="mt-2 flex flex-col gap-2 text-sm">
          {iv.questions.map((q, i) => {
            const a = iv.answers[q.id]
            const s = iv.scores[q.id]
            return (
              <li key={q.id} className="rounded-control bg-surface-2 p-2">
                <div className="flex items-start gap-2">
                  <span className="text-xs font-semibold text-muted">{i + 1}.</span>
                  <span className="flex-1 font-medium">{q.text}</span>
                  <Badge tone={q.kind === 'hard' ? 'info' : 'violet'}>{q.kind}</Badge>
                  {s && <Badge tone={s.score >= 7 ? 'success' : s.score >= 4 ? 'warning' : 'danger'}>{s.score}/10</Badge>}
                </div>
                <p className="mt-1 whitespace-pre-wrap text-muted">{a?.text || '—'}</p>
                {s?.feedback && <p className="mt-1 text-xs italic">{s.feedback}</p>}
              </li>
            )
          })}
        </ol>
      )}
      {manage && (iv.status === 'submitted' || iv.status === 'graded') && (
        <div className="mt-3 flex flex-wrap items-end gap-2 border-t border-border pt-3">
          <Button variant="outline" disabled={grade.isPending} onClick={() => grade.mutate(false)}>
            <Sparkles className="size-4" />
            {t('aiiv.gradeAi')}
          </Button>
          <span className="text-xs text-muted">{t('aiiv.orManual')}</span>
          <Input className="w-20" type="number" min={0} max={100} value={hard} onChange={(e) => setHard(e.target.value)} aria-label="Hard %" placeholder="Hard %" />
          <Input className="w-20" type="number" min={0} max={100} value={soft} onChange={(e) => setSoft(e.target.value)} aria-label="Soft %" placeholder="Soft %" />
          <Button variant="outline" disabled={grade.isPending || hard === '' || soft === ''} onClick={() => grade.mutate(true)}>
            {t('aiiv.saveManual')}
          </Button>
        </div>
      )}
    </div>
  )
}
