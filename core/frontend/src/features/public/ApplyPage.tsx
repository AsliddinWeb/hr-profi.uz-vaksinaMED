import { useMutation, useQuery } from '@tanstack/react-query'
import { CheckCircle2, FileUp, PencilLine } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field, Input } from '../../components/ui/Input'
import { api, ApiError, send, upload } from '../../lib/api'

type Comp = { name: string; level: number | null; mandatory: boolean }
interface Info {
  title: string
  branch: string | null
  salary_from: number | null
  salary_to: number | null
  requirements: string | null
  competencies?: Record<string, Comp[]>
  duties?: string[]
  min_experience?: number | null
}
const CAT_ORDER = ['hard', 'soft', 'management', 'knowledge', 'experience']

/** /apply/:code: ommaviy ariza sahifasi (kirish shart emas). Ikki yo'l: qo'lda to'ldirish yoki rezyume yuklash (ma'lumotlar fayldan avtomatik olinadi). */
export function ApplyPage() {
  const { t } = useTranslation()
  const code = useParams().code ?? ''
  const q = useQuery({ queryKey: ['public-apply', code], queryFn: () => api<Info>(`/api/v1/public/apply/${code}`), retry: false })
  const [mode, setMode] = useState<'manual' | 'resume'>('manual')
  const [name, setName] = useState('')
  const [phone, setPhone] = useState('+998')
  const [note, setNote] = useState('')
  const [trap, setTrap] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [found, setFound] = useState<string[] | null>(null)
  const after = (r: { ok: boolean; profile_url?: string }) => {
    // yangi nomzod: to'liq anketa sahifasiga (rezyumedan to'lgan maydonlar u yerda tayyor turadi)
    if (r?.profile_url?.startsWith('/profile/')) window.location.assign(r.profile_url)
  }
  const sendIt = useMutation({
    mutationFn: () => {
      if (mode === 'resume' && file) {
        const fd = new FormData()
        fd.append('file', file)
        fd.append('full_name', name)
        fd.append('phone', phone)
        if (note) fd.append('note', note)
        if (trap) fd.append('website', trap)
        return upload<{ ok: boolean; profile_url?: string }>('POST', `/api/v1/public/apply/${code}/resume`, fd)
      }
      return send<{ ok: boolean; profile_url?: string }>('POST', `/api/v1/public/apply/${code}`, { full_name: name, phone, note: note || null, website: trap || null })
    },
    onSuccess: after,
  })
  const parse = useMutation({
    mutationFn: (f: File) => {
      const fd = new FormData()
      fd.append('file', f)
      return upload<{ full_name: string | null; phone: string | null; email: string | null; found: string[] }>('POST', `/api/v1/public/apply/${code}/parse`, fd)
    },
    onSuccess: (r) => {
      if (r.full_name && !name.trim()) setName(r.full_name)
      if (r.phone && phone.length < 8) setPhone(r.phone)
      setFound(r.found)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    sendIt.mutate()
  }
  const money = (n: number) => n.toLocaleString('ru-RU')
  const failed = q.error instanceof ApiError
  const errOf = (e: unknown) =>
    e instanceof ApiError ? (e.code === 'phone_invalid' ? t('apply.phoneInvalid') : e.code === 'too_many_attempts' ? t('apply.tooMany') : e.code === 'unsupported_file' ? t('apply.badFile') : e.code === 'file_too_large' ? t('apply.bigFile') : t('apply.error')) : null
  const err = errOf(sendIt.error) ?? errOf(parse.error)
  const comps = q.data?.competencies ?? {}
  const cats = CAT_ORDER.filter((c) => comps[c]?.length)
  const pill = (on: boolean) => `flex flex-1 items-center justify-center gap-2 rounded-control border px-3 py-3 text-sm font-medium transition ${on ? 'border-primary bg-primary/10 text-primary' : 'border-border text-muted hover:bg-surface-2'}`

  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col justify-center gap-4 px-4 py-10">
      {failed ? (
        <Card className="p-6 text-center">{t('apply.closed')}</Card>
      ) : !q.data ? null : sendIt.isSuccess ? (
        <Card className="flex flex-col items-center gap-3 p-8 text-center">
          <CheckCircle2 className="size-12 text-success" />
          <p className="text-lg font-semibold">{t('apply.thanks')}</p>
          <p className="text-sm text-muted">{t('apply.thanksHint')}</p>
        </Card>
      ) : (
        <Card className="flex flex-col gap-4 p-6">
          <div>
            <h1 className="text-xl font-semibold">{q.data.title}</h1>
            {q.data.branch && <p className="text-sm text-muted">{q.data.branch}</p>}
            {(q.data.salary_from || q.data.salary_to) && (
              <p className="mt-1 text-sm">
                {t('apply.salary')}: {[q.data.salary_from && money(q.data.salary_from), q.data.salary_to && money(q.data.salary_to)].filter(Boolean).join(' – ')} {t('apply.currency')}
              </p>
            )}
          </div>
          {(cats.length > 0 || (q.data.duties?.length ?? 0) > 0) && (
            <div className="flex flex-col gap-2 rounded-lg bg-surface-2 p-3 text-sm">
              <div className="font-medium">{t('apply.whatWeNeed')}</div>
              {q.data.min_experience ? <div className="text-muted">{t('apply.minExp', { n: q.data.min_experience })}</div> : null}
              {cats.map((c) => (
                <div key={c}>
                  <span className="text-xs text-muted">{t(`apply.cat.${c}`)}: </span>
                  {comps[c].map((x) => x.name).join(', ')}
                </div>
              ))}
              {q.data.duties && q.data.duties.length > 0 && (
                <ul className="list-disc pl-5 text-muted">
                  {q.data.duties.slice(0, 8).map((d, i) => (
                    <li key={i}>{d}</li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {cats.length === 0 && q.data.requirements && <p className="whitespace-pre-wrap text-sm text-muted">{q.data.requirements}</p>}
          <div className="flex gap-2">
            <button type="button" className={pill(mode === 'manual')} onClick={() => setMode('manual')}>
              <PencilLine className="size-4" />
              {t('apply.manual')}
            </button>
            <button type="button" className={pill(mode === 'resume')} onClick={() => setMode('resume')}>
              <FileUp className="size-4" />
              {t('apply.withResume')}
            </button>
          </div>
          <form onSubmit={submit} className="flex flex-col gap-4">
            {mode === 'resume' && (
              <div className="flex flex-col gap-2 rounded-lg border border-dashed border-border p-4 text-sm">
                <div className="text-muted">{t('apply.resumeHint')}</div>
                <input
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={(e) => {
                    const f = e.target.files?.[0] ?? null
                    setFile(f)
                    setFound(null)
                    if (f) parse.mutate(f)
                  }}
                  aria-label={t('apply.withResume')}
                />
                {parse.isPending && <div className="text-muted">{t('apply.reading')}</div>}
                {found && <div className="text-success">{found.length ? t('apply.filledFromResume') : t('apply.fillRest')}</div>}
              </div>
            )}
            <Field label={t('apply.name')}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required minLength={3} maxLength={250} autoComplete="name" />}</Field>
            <Field label={t('apply.phone')}>{(id) => <Input id={id} type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required autoComplete="tel" />}</Field>
            <Field label={t('apply.note')}>{(id) => <textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} rows={3} maxLength={1000} className="w-full rounded-control border border-border bg-surface px-3 py-2 text-sm" />}</Field>
            <div aria-hidden className="absolute -left-[9999px]">
              <input tabIndex={-1} autoComplete="off" value={trap} onChange={(e) => setTrap(e.target.value)} name="website" />
            </div>
            {err && <p role="alert" className="text-sm text-danger">{err}</p>}
            <p className="text-xs text-muted">{t(mode === 'resume' ? 'apply.nextResume' : 'apply.nextManual')}</p>
            <Button type="submit" className="h-12 text-base" disabled={sendIt.isPending || name.trim().length < 3 || phone.length < 7 || (mode === 'resume' && !file)}>
              {t('apply.submit')}
            </Button>
          </form>
        </Card>
      )}
    </main>
  )
}
