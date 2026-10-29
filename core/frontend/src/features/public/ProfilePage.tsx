import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, Paperclip } from 'lucide-react'
import { useRef, useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useParams } from 'react-router-dom'

import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Field, Input } from '../../components/ui/Input'
import { api, ApiError, send, upload } from '../../lib/api'

interface PublicProfile {
  full_name: string
  fields: Record<string, unknown>
  sources: Record<string, string>
  confirmed_at: string | null
  files: { id: number; filename: string; size: number }[]
  max_files: number
}

/** /profile/:token: nomzod anketasi (kirish shart emas): ma'lumotlarini to'ldiradi, rezyume yuklaydi va birlashgan profilni tasdiqlaydi. */
export function CandidateProfilePage() {
  const { t } = useTranslation()
  const token = useParams().token ?? ''
  const qc = useQueryClient()
  const fileRef = useRef<HTMLInputElement>(null)
  const q = useQuery({ queryKey: ['public-profile', token], queryFn: () => api<PublicProfile>(`/api/v1/public/profile/${token}`), retry: false })
  if (q.error instanceof ApiError) {
    return (
      <main className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-4 py-10">
        <Card className="p-8 text-center" role="alert">
          <p className="font-semibold">{t('recruitCore.public.notFound')}</p>
        </Card>
      </main>
    )
  }
  if (!q.data) return <main className="mx-auto max-w-lg px-4 py-10"><Card className="h-48 animate-pulse" /></main>
  return <ProfileForm key={q.data.confirmed_at ?? 'x'} data={q.data} token={token} onChange={() => void qc.invalidateQueries({ queryKey: ['public-profile', token] })} fileRef={fileRef} />
}

function ProfileForm({ data, token, onChange, fileRef }: { data: PublicProfile; token: string; onChange: () => void; fileRef: React.RefObject<HTMLInputElement | null> }) {
  const { t } = useTranslation()
  const f = data.fields
  const str = (k: string) => (f[k] === undefined || f[k] === null ? '' : String(f[k]))
  const arr = (k: string) => (Array.isArray(f[k]) ? (f[k] as string[]).join(', ') : '')
  const [name, setName] = useState(data.full_name)
  const [birth, setBirth] = useState(str('birth_date'))
  const [address, setAddress] = useState(str('address'))
  const [email, setEmail] = useState(str('email'))
  const [region, setRegion] = useState(str('region'))
  const [exp, setExp] = useState(str('experience'))
  const [salary, setSalary] = useState(str('expected_salary'))
  const [langs, setLangs] = useState(arr('languages'))
  const [skills, setSkills] = useState(arr('skills'))
  const [about, setAbout] = useState(str('about'))
  const list = (s: string) => s.split(',').map((x) => x.trim()).filter(Boolean)
  const save = useMutation({
    mutationFn: () => send('PUT', `/api/v1/public/profile/${token}`, { full_name: name, birth_date: birth || null, address: address || null, email: email || null, region: region || null, experience: exp || null, expected_salary: salary ? Number(salary) : null, languages: list(langs), skills: list(skills), about: about || null }),
    onSuccess: onChange,
  })
  const confirm = useMutation({ mutationFn: () => send('POST', `/api/v1/public/profile/${token}/confirm`), onSuccess: onChange })
  const up = useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData()
      fd.append('file', file)
      return upload('POST', `/api/v1/public/profile/${token}/file`, fd)
    },
    onSuccess: onChange,
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'
  return (
    <main className="mx-auto flex min-h-screen max-w-xl flex-col gap-4 px-4 py-8">
      <h1 className="text-xl font-semibold">{t('recruitCore.public.profileTitle')}</h1>
      <p className="text-sm text-muted">{t('recruitCore.public.profileHint')}</p>
      {data.confirmed_at && (
        <Card className="flex items-center gap-3 border-success/40 bg-success/5 p-4 text-sm">
          <CheckCircle2 className="size-6 text-success" />
          {t('recruitCore.public.confirmedDone')}
        </Card>
      )}
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Card className="flex flex-col gap-4 p-5">
          <Field label={t('recruitCore.profile.fields.full_name')}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={250} />}</Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('recruitCore.profile.fields.birth_date')}>{(id) => <Input id={id} type="date" value={birth} onChange={(e) => setBirth(e.target.value)} />}</Field>
            <Field label={t('recruitCore.profile.fields.email')}>{(id) => <Input id={id} type="email" value={email} onChange={(e) => setEmail(e.target.value)} />}</Field>
            <Field label={t('recruitCore.profile.fields.region')}>{(id) => <Input id={id} value={region} onChange={(e) => setRegion(e.target.value)} maxLength={100} />}</Field>
            <Field label={t('recruitCore.profile.fields.address')}>{(id) => <Input id={id} value={address} onChange={(e) => setAddress(e.target.value)} maxLength={300} />}</Field>
            <Field label={t('recruitCore.profile.fields.experience')}>{(id) => <Input id={id} value={exp} onChange={(e) => setExp(e.target.value)} placeholder="3 yil" maxLength={300} />}</Field>
            <Field label={t('recruitCore.profile.fields.expected_salary')}>{(id) => <Input id={id} type="number" min={0} value={salary} onChange={(e) => setSalary(e.target.value)} />}</Field>
            <Field label={t('recruitCore.profile.fields.languages')} hint={t('recruitCore.public.commaHint')}>{(id) => <Input id={id} value={langs} onChange={(e) => setLangs(e.target.value)} />}</Field>
            <Field label={t('recruitCore.profile.fields.skills')} hint={t('recruitCore.public.commaHint')}>{(id) => <Input id={id} value={skills} onChange={(e) => setSkills(e.target.value)} />}</Field>
          </div>
          <Field label={t('recruitCore.profile.fields.about')}>{(id) => <textarea id={id} value={about} onChange={(e) => setAbout(e.target.value)} rows={4} maxLength={2000} className={area} />}</Field>
          <div>
            <Button type="submit" disabled={save.isPending}>
              {t('common.save')}
            </Button>
          </div>
        </Card>
      </form>
      <Card className="flex flex-col gap-3 p-5">
        <h2 className="font-semibold">{t('recruitCore.public.resume')}</h2>
        <p className="text-sm text-muted">{t('recruitCore.public.resumeHint', { n: data.max_files })}</p>
        <ul className="text-sm">
          {data.files.map((x) => (
            <li key={x.id} className="flex items-center gap-2">
              <Paperclip className="size-4 text-muted" />
              {x.filename}
            </li>
          ))}
        </ul>
        <input ref={fileRef} type="file" className="hidden" accept=".pdf,.docx,.png,.jpg,.jpeg" onChange={(e) => e.target.files?.[0] && up.mutate(e.target.files[0])} />
        <div>
          <Button variant="outline" disabled={up.isPending || data.files.length >= data.max_files} onClick={() => fileRef.current?.click()}>
            {t('recruitCore.public.upload')}
          </Button>
        </div>
        {up.isError && <p role="alert" className="text-sm text-danger">{t('recruitCore.public.uploadError')}</p>}
      </Card>
      <Card className="flex flex-col gap-3 p-5">
        <h2 className="font-semibold">{t('recruitCore.public.mergedTitle')}</h2>
        <p className="text-sm text-muted">{t('recruitCore.public.mergedHint')}</p>
        <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-2">
          {Object.entries(data.fields).map(([k, v]) => (
            <div key={k}>
              <dt className="text-xs text-muted">{t(`recruitCore.profile.fields.${k}`, { defaultValue: k })}</dt>
              <dd>{Array.isArray(v) ? v.join(', ') : String(v)}</dd>
            </div>
          ))}
        </dl>
        <div>
          <Button disabled={confirm.isPending || !!data.confirmed_at} onClick={() => confirm.mutate()}>
            {t('recruitCore.public.confirm')}
          </Button>
        </div>
      </Card>
    </main>
  )
}
