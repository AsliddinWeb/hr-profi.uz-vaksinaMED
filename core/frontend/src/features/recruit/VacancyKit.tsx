import { useQuery } from '@tanstack/react-query'
import { Copy, Send } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { Skeleton } from '../../components/ui/Skeleton'
import { useToast } from '../../components/ui/toastContext'
import { api } from '../../lib/api'
import { formatDateTime } from '../../lib/format'

type Kit = {
  vacancy: { id: number; title: string; status: string; openings: number; hired: number; found: boolean; recruiter: string | null; deadline: string | null; days_open: number | null }
  competencies: { by_category: Record<string, { name: string; level: number | null; mandatory: boolean }[]>; duties: string[]; questions: string[]; min_experience: number | null }
  links: { id: number; url: string; label: string | null; channel: string | null; clicks: number; applications: number; active: boolean }[]
  stats: { total: number; by_stage: Record<string, number>; today: number; with_resume: number }
  resumes: { application_id: number; candidate_id: number; name: string; phone: string | null; stage: string; applied_at: string; has_resume: boolean; anketa: boolean }[]
  activity: { at: string; actor: string | null; action: string; to: string | null; candidate: string }[]
}
const CATS = ['hard', 'soft', 'management', 'knowledge', 'experience']

function useKit(id: number) {
  return useQuery({ queryKey: ['recruit', 'kit', id], queryFn: () => api<Kit>(`/api/v1/recruit/vacancies/${id}/kit`), refetchInterval: 30_000 })
}

/** Vakansiya holati: qidirilmoqda / topildi va rezyumelar soni. */
export function KitStats({ id }: { id: number }) {
  const { t } = useTranslation()
  const k = useKit(id).data
  if (!k) return <Skeleton className="h-20" />
  const cards: [string, string | number, string][] = [
    ['state', t(k.vacancy.found ? 'vkit.found' : k.vacancy.status === 'open' ? 'vkit.searching' : `recruit.vacancy.status.${k.vacancy.status}`), k.vacancy.found ? 'text-success' : 'text-primary'],
    ['resumes', k.stats.total, 'text-text'],
    ['withResume', k.stats.with_resume, 'text-text'],
    ['today', k.stats.today, 'text-primary'],
    ['hired', `${k.vacancy.hired}/${k.vacancy.openings}`, 'text-success'],
    ['daysOpen', k.vacancy.days_open ?? '—', 'text-muted'],
  ]
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {cards.map(([key, v, tone]) => (
        <Card key={key} className="p-4">
          <div className="text-xs text-muted">{t(`vkit.k.${key}`)}</div>
          <div className={`mt-1.5 font-mono text-xl font-medium ${tone}`}>{v}</div>
        </Card>
      ))}
    </div>
  )
}

/** Rekruter uchun «Xodim qidirish»: kompetensiyalar, nomzod havolalari (yuborish), kelgan rezyumelar va solishtirish. */
export function RecruiterSearch({ id }: { id: number }) {
  const { t, i18n } = useTranslation()
  const toast = useToast()
  const k = useKit(id).data
  if (!k) return <Skeleton className="h-64" />
  const cats = CATS.filter((c) => k.competencies.by_category[c]?.length)
  const copy = (url: string) => void navigator.clipboard.writeText(url).then(() => toast.push({ title: t('vkit.copied'), tone: 'success' }))
  const ids = k.resumes.map((r) => r.candidate_id).slice(0, 10).join(',')
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="flex flex-col gap-3 p-5">
        <div className="font-semibold">{t('vkit.compTitle')}</div>
        {cats.length === 0 && <div className="text-sm text-muted">{t('vkit.noComps')}</div>}
        {k.competencies.min_experience ? <div className="text-sm">{t('vkit.minExp', { n: k.competencies.min_experience })}</div> : null}
        {cats.map((c) => (
          <div key={c} className="flex flex-col gap-1">
            <div className="text-xs text-muted">{t(`comp.cat.${c}`)}</div>
            <div className="flex flex-wrap gap-1.5">
              {k.competencies.by_category[c].map((x) => (
                <Badge key={x.name} tone={x.mandatory ? 'danger' : 'warning'}>
                  {x.name}
                  {x.level ? ` · L${x.level}` : ''}
                </Badge>
              ))}
            </div>
          </div>
        ))}
        {k.competencies.questions.length > 0 && (
          <div className="text-sm">
            <div className="text-xs text-muted">{t('vkit.questions')}</div>
            <ul className="list-disc pl-5">
              {k.competencies.questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          </div>
        )}
      </Card>
      <Card className="flex flex-col gap-3 p-5">
        <div className="font-semibold">{t('vkit.linksTitle')}</div>
        <div className="text-xs text-muted">{t('vkit.linksHint')}</div>
        {k.links.length === 0 && (
          <div className="text-sm text-muted">
            {t('vkit.noLinks')}{' '}
            <Link to={`/recruit/vacancies/${id}/promo`} className="text-primary hover:underline">
              {t('vkit.makeLink')}
            </Link>
          </div>
        )}
        {k.links.map((l) => (
          <div key={l.id} className="flex flex-col gap-1.5 rounded-lg border border-border p-3 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span className="font-medium">{l.label || l.channel}</span>
              <span className="text-xs text-muted">{t('vkit.linkStats', { c: l.clicks, a: l.applications })}</span>
            </div>
            <div className="truncate font-mono text-xs text-muted">{l.url}</div>
            <div className="flex flex-wrap gap-1.5">
              <Button variant="outline" className="h-8" onClick={() => copy(l.url)}>
                <Copy className="size-3.5" />
                {t('vkit.copy')}
              </Button>
              <a href={`https://t.me/share/url?url=${encodeURIComponent(l.url)}&text=${encodeURIComponent(k.vacancy.title)}`} target="_blank" rel="noreferrer">
                <Button variant="outline" className="h-8">
                  <Send className="size-3.5" />
                  Telegram
                </Button>
              </a>
              <a href={`https://wa.me/?text=${encodeURIComponent(`${k.vacancy.title} ${l.url}`)}`} target="_blank" rel="noreferrer">
                <Button variant="outline" className="h-8">
                  WhatsApp
                </Button>
              </a>
            </div>
          </div>
        ))}
      </Card>
      <Card className="flex flex-col gap-3 p-5 lg:col-span-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="font-semibold">{t('vkit.resumesTitle', { n: k.stats.total })}</div>
          {k.resumes.length > 1 && (
            <Link to={`/recruit/compare?ids=${ids}&vacancy_id=${id}`}>
              <Button variant="outline" className="h-8">
                {t('vkit.compare')}
              </Button>
            </Link>
          )}
        </div>
        {k.resumes.length === 0 && <div className="text-sm text-muted">{t('vkit.noResumes')}</div>}
        <div className="divide-y divide-border">
          {k.resumes.map((r) => (
            <Link key={r.application_id} to={`/recruit/applications/${r.application_id}`} className="flex flex-wrap items-center gap-2 py-2 text-sm hover:bg-surface-2">
              <span className="min-w-40 flex-1 font-medium">{r.name}</span>
              <span className="text-xs text-muted">{formatDateTime(r.applied_at, i18n.language)}</span>
              {r.has_resume && <Badge tone="info">{t('vkit.hasResume')}</Badge>}
              {r.anketa && <Badge tone="success">{t('vkit.anketa')}</Badge>}
              <Badge>{t(`recruit.stage.${r.stage}`)}</Badge>
            </Link>
          ))}
        </div>
      </Card>
    </div>
  )
}

/** HR uchun nazorat: rekruter faoliyati (kim, qachon, nima qildi). */
export function RecruiterActivity({ id }: { id: number }) {
  const { t, i18n } = useTranslation()
  const k = useKit(id).data
  if (!k) return null
  return (
    <Card className="flex flex-col gap-2 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="font-semibold">{t('vkit.activityTitle')}</div>
        <div className="text-sm text-muted">
          {t('recruit.vacancy.recruiter')}: {k.vacancy.recruiter ?? '—'}
        </div>
      </div>
      {k.activity.length === 0 && <div className="text-sm text-muted">{t('vkit.noActivity')}</div>}
      {k.activity.map((a, i) => (
        <div key={i} className="flex flex-wrap gap-2 text-sm">
          <span className="w-32 shrink-0 text-xs text-muted">{formatDateTime(a.at, i18n.language)}</span>
          <span className="font-medium">{a.actor ?? t('vkit.system')}</span>
          <span className="text-muted">
            {t(`vkit.act.${a.action}`, { defaultValue: a.action })}
            {a.to ? ` → ${t(`recruit.stage.${a.to}`, { defaultValue: a.to })}` : ''}: {a.candidate}
          </span>
        </div>
      ))}
    </Card>
  )
}
