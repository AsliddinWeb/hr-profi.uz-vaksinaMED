import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ClipboardCheck, ExternalLink, Paperclip, Upload } from 'lucide-react'
import { useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { Field, Input, Select } from '../../components/ui/Input'
import { api, ApiError, send, upload } from '../../lib/api'
import { cn } from '../../lib/cn'

type Anketa = Record<string, string | number | null>
interface PublicProfile {
  full_name: string
  phone: string | null
  fields: Record<string, unknown>
  sources: Record<string, string>
  confirmed_at: string | null
  files: { id: number; filename: string; size: number }[]
  max_files: number
  anketa: Anketa
  tests: { url: string; status: string; vacancy: string }[]
}

const STEPS = ['personal', 'education', 'experience', 'extra', 'motivation', 'documents', 'knowledge', 'submit'] as const
type Step = (typeof STEPS)[number]

/** /profile/:token: nomzodning 8 bosqichli onlayn anketasi (qog'ozsiz ariza). Ma'lumotlar nomzodlar bazasiga va vakansiya zayafkasiga tushadi. */
export function CandidateProfilePage() {
  const { t } = useTranslation()
  const token = useParams().token ?? ''
  const q = useQuery({ queryKey: ['public-profile', token], queryFn: () => api<PublicProfile>(`/api/v1/public/profile/${token}`), retry: false })
  return (
    <main className="min-h-screen bg-gradient-to-br from-violet-50 via-fuchsia-50 to-amber-50 px-4 py-8 dark:from-[#1b1530] dark:via-[#1d1428] dark:to-[#221c14]">
      <div className="mx-auto flex max-w-3xl flex-col gap-5">
        <header className="text-center">
          <h1 className="text-2xl font-bold text-[#4b1d73] dark:text-violet-200">{t('anketa.title')}</h1>
          <p className="mt-1 text-sm text-[#6b5a80] dark:text-violet-200/70">{t('anketa.subtitle')}</p>
        </header>
        {q.error instanceof ApiError ? (
          <Shell>
            <p className="text-center font-semibold">{t('recruitCore.public.notFound')}</p>
          </Shell>
        ) : !q.data ? (
          <Shell>
            <div className="h-48 animate-pulse rounded-xl bg-violet-100/60" />
          </Shell>
        ) : (
          <Wizard data={q.data} token={token} />
        )}
      </div>
    </main>
  )
}

function Shell({ children }: { children: ReactNode }) {
  return <section className="rounded-3xl border border-violet-100 bg-white/85 p-6 shadow-[0_10px_40px_-20px_rgba(75,29,115,0.35)] backdrop-blur dark:border-violet-900/50 dark:bg-[#1e1a2b]/90 sm:p-8">{children}</section>
}

function Wizard({ data, token }: { data: PublicProfile; token: string }) {
  const { t } = useTranslation()
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const f = data.fields
  const s = (k: string) => (f[k] === undefined || f[k] === null ? '' : String(f[k]))
  const [step, setStep] = useState(0)
  const [name, setName] = useState(data.full_name)
  const [birth, setBirth] = useState(s('birth_date'))
  const [address, setAddress] = useState(s('address'))
  const [email, setEmail] = useState(s('email'))
  const [langs, setLangs] = useState(Array.isArray(f.languages) ? (f.languages as string[]).join(', ') : '')
  const [a, setA] = useState<Anketa>(() => ({ ...data.anketa }))
  const [done, setDone] = useState(!!data.confirmed_at)
  const val = (k: string) => (a[k] === null || a[k] === undefined ? '' : String(a[k]))
  const set = (k: string) => (e: { target: { value: string } }) => setA((p) => ({ ...p, [k]: e.target.value }))
  const [today] = useState(() => Date.now())
  const age = birth ? Math.floor((today - new Date(birth).getTime()) / (365.25 * 864e5)) : null
  const refresh = () => void qc.invalidateQueries({ queryKey: ['public-profile', token] })

  const save = useMutation({
    mutationFn: () =>
      send('PUT', `/api/v1/public/profile/${token}`, {
        full_name: name, birth_date: birth || null, address: address || null, email: email || null, region: null, experience: null, expected_salary: null,
        languages: langs.split(',').map((x) => x.trim()).filter(Boolean), skills: [], about: val('motivation') || null, anketa: a,
      }), // prettier-ignore
  })
  const confirm = useMutation({ mutationFn: () => send('POST', `/api/v1/public/profile/${token}/confirm`), onSuccess: () => (setDone(true), refresh()) })
  const up = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return upload('POST', `/api/v1/public/profile/${token}/file`, fd)
    },
    onSuccess: refresh,
  })
  const next = async () => {
    if (step === 0 && name.trim().length < 2) return
    if (step <= 4) await save.mutateAsync()
    setStep((x) => Math.min(STEPS.length - 1, x + 1))
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  const cur: Step = STEPS[step]
  const pick = (k: string, opts: string[]) => (
    <Field label={t(`anketa.f.${k}`)}>
      {(id) => (
        <Select id={id} value={val(k)} onChange={set(k)}>
          <option value="">—</option>
          {opts.map((o) => (
            <option key={o} value={t(`anketa.o.${o}`)}>
              {t(`anketa.o.${o}`)}
            </option>
          ))}
        </Select>
      )}
    </Field>
  )
  const text = (k: string, extra: Partial<React.InputHTMLAttributes<HTMLInputElement>> = {}) => (
    <Field label={t(`anketa.f.${k}`)}>{(id) => <Input id={id} value={val(k)} onChange={set(k)} maxLength={300} {...extra} />}</Field>
  )

  if (done) {
    return (
      <Shell>
        <div className="flex flex-col items-center gap-3 py-6 text-center">
          <CheckCircle2 className="size-14 text-emerald-500" />
          <h2 className="text-xl font-bold text-[#4b1d73] dark:text-violet-200">{t('anketa.doneTitle')}</h2>
          <p className="max-w-md text-sm text-muted">{t('anketa.doneHint')}</p>
          <button type="button" className="mt-2 text-sm font-semibold text-violet-700 underline dark:text-violet-300" onClick={() => (setDone(false), setStep(0))}>
            {t('anketa.edit')}
          </button>
        </div>
      </Shell>
    )
  }

  return (
    <>
      <div>
        <div className="flex justify-between text-sm text-[#6b5a80] dark:text-violet-200/70">
          <span>{t('anketa.stepOf', { n: step + 1, total: STEPS.length })}</span>
          <span>{t(`anketa.s.${cur}`)}</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-violet-100 dark:bg-violet-950">
          <div className="h-full rounded-full bg-gradient-to-r from-[#5b2a86] to-[#8e44ad] transition-all" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
        </div>
        <ol className="mt-3 hidden grid-cols-8 gap-1 sm:grid">
          {STEPS.map((k, i) => (
            <li key={k}>
              <button type="button" disabled={i > step} onClick={() => setStep(i)} className="flex w-full flex-col items-center gap-1 text-[11px]">
                <span className={cn('size-2.5 rounded-full', i <= step ? 'bg-[#5b2a86]' : 'bg-violet-200 dark:bg-violet-900')} />
                <span className={cn(i === step ? 'font-semibold text-[#4b1d73] dark:text-violet-200' : 'text-[#8a7a9e]')}>{t(`anketa.s.${k}`)}</span>
              </button>
            </li>
          ))}
        </ol>
      </div>

      <Shell>
        <h2 className="text-2xl font-bold text-[#4b1d73] dark:text-violet-200">{t(`anketa.h.${cur}`)}</h2>
        <p className="mb-5 mt-1 text-sm text-muted">{t(`anketa.d.${cur}`)}</p>
        <div className="flex flex-col gap-4">
          {cur === 'personal' && (
            <>
              <Field label={`${t('anketa.f.full_name')} *`}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} placeholder={t('anketa.ph.full_name')} required maxLength={250} />}</Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={t('anketa.f.birth_date')}>{(id) => <Input id={id} type="date" value={birth} onChange={(e) => setBirth(e.target.value)} />}</Field>
                <Field label={t('anketa.f.age')}>{(id) => <Input id={id} value={age !== null && age > 0 ? String(age) : ''} readOnly placeholder={t('anketa.ph.age')} />}</Field>
              </div>
              <Field label={t('anketa.f.address')}>{(id) => <Input id={id} value={address} onChange={(e) => setAddress(e.target.value)} placeholder={t('anketa.ph.address')} maxLength={300} />}</Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label={`${t('anketa.f.phone')} *`}>{(id) => <Input id={id} value={data.phone ?? ''} readOnly />}</Field>
                <Field label={t('anketa.f.email')}>{(id) => <Input id={id} type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email@example.com" />}</Field>
              </div>
            </>
          )}
          {cur === 'education' && (
            <>
              {text('education_place')}
              <div className="grid gap-4 sm:grid-cols-2">
                {text('graduation_year', { inputMode: 'numeric', maxLength: 4 })}
                {text('specialty')}
              </div>
              {text('diploma_no')}
            </>
          )}
          {cur === 'experience' && (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                {text('last_job')}
                {text('last_position')}
              </div>
              {text('experience_years', { inputMode: 'decimal', placeholder: '3' })}
              {text('leave_reason')}
            </>
          )}
          {cur === 'extra' && (
            <>
              <div className="grid gap-4 sm:grid-cols-2">
                {pick('computer_skill', ['good', 'mid', 'low'])}
                {pick('pharm_software', ['yes', 'no'])}
                {pick('gmp_certificate', ['have', 'nothave'])}
                {pick('drug_knowledge', ['high', 'mid', 'basic'])}
              </div>
              <Field label={t('anketa.f.languages')} hint={t('recruitCore.public.commaHint')}>{(id) => <Input id={id} value={langs} onChange={(e) => setLangs(e.target.value)} placeholder={t('anketa.ph.languages')} />}</Field>
              {text('personal_qualities')}
            </>
          )}
          {cur === 'motivation' && (
            <>
              <Field label={t('anketa.f.motivation')}>
                {(id) => <textarea id={id} rows={4} maxLength={500} value={val('motivation')} onChange={set('motivation')} className="w-full rounded-control bg-surface px-3 py-2 text-sm shadow-[inset_0_0_0_1px_var(--border-strong)] outline-none focus:ring-2 focus:ring-primary/30" />}
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                {pick('shift', ['morning', 'evening', 'rotating', 'any'])}
                {text('salary_text', { placeholder: t('anketa.ph.salary') })}
              </div>
            </>
          )}
          {cur === 'documents' && (
            <>
              <ul className="flex flex-col gap-2 text-sm">
                {data.files.map((x) => (
                  <li key={x.id} className="flex items-center gap-2 rounded-xl bg-violet-50 px-3 py-2 dark:bg-violet-950/40">
                    <Paperclip className="size-4 text-violet-600" />
                    <span className="truncate">{x.filename}</span>
                  </li>
                ))}
                {data.files.length === 0 && <li className="text-muted">{t('anketa.noFiles')}</li>}
              </ul>
              <input ref={fileRef} type="file" className="hidden" accept=".pdf,.docx,.png,.jpg,.jpeg" onChange={(e) => e.target.files?.[0] && up.mutate(e.target.files[0])} />
              <button
                type="button"
                disabled={up.isPending || data.files.length >= data.max_files}
                onClick={() => fileRef.current?.click()}
                className="flex items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-violet-200 px-4 py-6 text-sm font-semibold text-violet-700 hover:bg-violet-50 disabled:opacity-50 dark:border-violet-800 dark:text-violet-300 dark:hover:bg-violet-950/40"
              >
                <Upload className="size-5" />
                {t('anketa.upload', { n: data.max_files })}
              </button>
              {up.isError && <p role="alert" className="text-sm text-danger">{t('recruitCore.public.uploadError')}</p>}
            </>
          )}
          {cur === 'knowledge' &&
            (data.tests.length ? (
              data.tests.map((x) => (
                <a key={x.url} href={x.url} className="flex items-center gap-3 rounded-2xl border border-violet-100 p-4 hover:bg-violet-50 dark:border-violet-900 dark:hover:bg-violet-950/40">
                  <ClipboardCheck className="size-6 text-violet-600" />
                  <span className="flex-1">
                    <span className="block font-semibold">{x.vacancy}</span>
                    <span className="text-xs text-muted">{t(`anketa.test.${x.status}`, { defaultValue: x.status })}</span>
                  </span>
                  <ExternalLink className="size-4 text-muted" />
                </a>
              ))
            ) : (
              <p className="rounded-2xl bg-violet-50 p-4 text-sm text-[#6b5a80] dark:bg-violet-950/40 dark:text-violet-200/80">{t('anketa.noTest')}</p>
            ))}
          {cur === 'submit' && (
            <dl className="grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
              {[
                ['full_name', name],
                ['phone', data.phone],
                ['email', email],
                ['address', address],
                ['specialty', val('specialty')],
                ['education_place', val('education_place')],
                ['last_job', [val('last_job'), val('last_position')].filter(Boolean).join(' / ')],
                ['experience_years', val('experience_years')],
                ['shift', val('shift')],
                ['salary_text', val('salary_text')],
                ['documents', String(data.files.length)],
              ].map(([k, v]) => (
                <div key={k}>
                  <dt className="text-[11px] uppercase tracking-wide text-[#8a7a9e]">{t(`anketa.f.${k}`)}</dt>
                  <dd className="font-medium">{v || '—'}</dd>
                </div>
              ))}
            </dl>
          )}
          {save.isError && <p role="alert" className="text-sm text-danger">{t('anketa.saveError')}</p>}
        </div>
      </Shell>

      <div className="flex items-center justify-between">
        <button type="button" disabled={step === 0} onClick={() => setStep((x) => Math.max(0, x - 1))} className="rounded-full border border-violet-200 px-6 py-3 text-sm font-semibold text-violet-800 disabled:opacity-40 dark:border-violet-800 dark:text-violet-200">
          {t('anketa.back')}
        </button>
        {cur === 'submit' ? (
          <button type="button" disabled={confirm.isPending} onClick={() => confirm.mutate()} className="rounded-full bg-gradient-to-r from-[#4b1d73] to-[#7b2fa8] px-7 py-3 text-sm font-semibold text-white shadow-lg disabled:opacity-60">
            {t('anketa.send')}
          </button>
        ) : (
          <button type="button" disabled={save.isPending || (step === 0 && name.trim().length < 2)} onClick={() => void next()} className="rounded-full bg-gradient-to-r from-[#4b1d73] to-[#7b2fa8] px-7 py-3 text-sm font-semibold text-white shadow-lg disabled:opacity-60">
            {t('anketa.next')}
          </button>
        )}
      </div>
    </>
  )
}
