import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Timer } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { api, ApiError, send } from '../../lib/api'

interface PublicTest {
  name: string
  kind: string
  time_limit_min: number
  question_count: number
  status: 'assigned' | 'started' | 'submitted' | 'expired'
  deadline_at: string | null
  questions?: { id: string; text: string; options: string[]; multiple: boolean }[]
}

function Remaining({ deadline, onEnd }: { deadline: string; onEnd: () => void }) {
  const [left, setLeft] = useState(() => Math.max(0, Math.floor((new Date(deadline).getTime() - Date.now()) / 1000)))
  useEffect(() => {
    const id = setInterval(() => setLeft(Math.max(0, Math.floor((new Date(deadline).getTime() - Date.now()) / 1000))), 1000)
    return () => clearInterval(id)
  }, [deadline])
  useEffect(() => {
    if (left === 0) onEnd()
  }, [left, onEnd])
  const m = String(Math.floor(left / 60)).padStart(2, '0')
  const s = String(left % 60).padStart(2, '0')
  return (
    <span className={'inline-flex items-center gap-1.5 font-mono text-lg ' + (left < 60 ? 'text-danger' : '')}>
      <Timer className="size-5" />
      {m}:{s}
    </span>
  )
}

/** /test/:token: nomzod testi (kirish shart emas): vaqt cheklovi serverda hisoblanadi, natija nomzodga ko'rsatilmaydi. */
export function TestPage() {
  const { t } = useTranslation()
  const token = useParams().token ?? ''
  const qc = useQueryClient()
  const q = useQuery({ queryKey: ['public-test', token], queryFn: () => api<PublicTest>(`/api/v1/public/test/${token}`), retry: false })
  const [answers, setAnswers] = useState<Record<string, number[]>>({})
  const refresh = () => void qc.invalidateQueries({ queryKey: ['public-test', token] })
  const start = useMutation({ mutationFn: () => send('POST', `/api/v1/public/test/${token}/start`), onSuccess: refresh })
  const submit = useMutation({ mutationFn: () => send('POST', `/api/v1/public/test/${token}/submit`, { answers }), onSuccess: refresh, onError: refresh })
  if (q.error instanceof ApiError) {
    return (
      <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-4 py-10">
        <Card className="p-8 text-center" role="alert">
          <p className="font-semibold">{t('recruitCore.public.notFound')}</p>
        </Card>
      </main>
    )
  }
  const d = q.data
  if (!d) return <main className="mx-auto max-w-lg px-4 py-10"><Card className="h-48 animate-pulse" /></main>
  const toggle = (qid: string, idx: number, multiple: boolean) => {
    const cur = answers[qid] ?? []
    setAnswers({ ...answers, [qid]: multiple ? (cur.includes(idx) ? cur.filter((x) => x !== idx) : [...cur, idx].sort()) : [idx] })
  }
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 px-4 py-8">
      <h1 className="text-xl font-semibold">{d.name}</h1>
      {d.status === 'assigned' && (
        <Card className="flex flex-col gap-3 p-5">
          <p className="text-sm">{t('recruitEval.public.intro', { n: d.question_count, m: d.time_limit_min })}</p>
          <p className="text-sm text-muted">{t('recruitEval.public.rules')}</p>
          <div>
            <Button disabled={start.isPending} onClick={() => start.mutate()}>
              {t('recruitEval.public.start')}
            </Button>
          </div>
        </Card>
      )}
      {d.status === 'started' && d.questions && d.deadline_at && (
        <>
          <Card className="sticky top-2 z-10 flex items-center justify-between p-3">
            <Remaining deadline={d.deadline_at} onEnd={() => submit.mutate()} />
            <span className="text-sm text-muted">{t('recruitEval.public.answered', { a: Object.keys(answers).length, n: d.questions.length })}</span>
          </Card>
          {d.questions.map((qq, i) => (
            <Card key={qq.id} className="flex flex-col gap-3 p-5">
              <div className="font-medium">
                {i + 1}. {qq.text}
              </div>
              {qq.multiple && <p className="text-xs text-muted">{t('recruitEval.public.multi')}</p>}
              <div className="flex flex-col gap-2">
                {qq.options.map((o, k) => (
                  <label key={k} className="flex cursor-pointer items-center gap-3 rounded-xl border border-border px-3 py-2 text-sm hover:bg-surface-2">
                    <input type={qq.multiple ? 'checkbox' : 'radio'} name={qq.id} className="size-4" checked={(answers[qq.id] ?? []).includes(k)} onChange={() => toggle(qq.id, k, qq.multiple)} />
                    {o}
                  </label>
                ))}
              </div>
            </Card>
          ))}
          <div>
            <Button disabled={submit.isPending} onClick={() => submit.mutate()}>
              {t('recruitEval.public.submit')}
            </Button>
          </div>
        </>
      )}
      {d.status === 'submitted' && <Card className="p-6 text-sm">{t('recruitEval.public.done')}</Card>}
      {d.status === 'expired' && <Card className="p-6 text-sm text-danger">{t('recruitEval.public.expired')}</Card>}
    </main>
  )
}
