import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Pencil } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../../components/layout/PageHeader'
import { Badge } from '../../../components/ui/Badge'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { FormFooter, FormSection } from '../../../components/ui/Form'
import { Field, Input } from '../../../components/ui/Input'
import { Skeleton } from '../../../components/ui/Skeleton'
import { useToast } from '../../../components/ui/toastContext'
import { api, send } from '../../../lib/api'
import { errorText } from '../../auth/errorText'
import { useCan } from '../../auth/useAuth'
import { RecruitTabs } from '../RecruitTabs'

interface Row {
  position_id: number
  position: string
  filled: boolean
  competencies: string[]
}
interface Req {
  position_id: number
  position: string
  requirements: string | null
  competencies: string[]
  ad_template: string | null
}

/** /recruit/requirements: lavozimlar bo'yicha talab, kompetensiya va e'lon shabloni. */
export function RequirementsPage() {
  const { t } = useTranslation()
  const manage = useCan()('recruit.manage')
  const q = useQuery({ queryKey: ['recruit', 'requirements'], queryFn: () => api<Row[]>('/api/v1/recruit/requirements') })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader title={t('recruit.title')} subtitle={t('recruitSources.reqHint')} />
      <RecruitTabs />
      {!q.data ? (
        <Skeleton className="h-48" />
      ) : (
        <Card className="overflow-hidden">
          <ul className="divide-y divide-border text-sm">
            {q.data.map((r) => (
              <li key={r.position_id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
                <div>
                  <span className="font-medium">{r.position}</span>
                  <div className="mt-1 flex flex-wrap gap-1">{r.competencies.map((c) => <Badge key={c}>{c}</Badge>)}</div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={r.filled ? 'success' : 'neutral'}>{r.filled ? t('recruitSources.filled') : t('recruitSources.notFilled')}</Badge>
                  {manage && (
                    <Link to={`/recruit/requirements/${r.position_id}/edit`}>
                      <Button variant="outline" className="h-8">
                        <Pencil className="size-4" />
                      </Button>
                    </Link>
                  )}
                </div>
              </li>
            ))}
            {q.data.length === 0 && <li className="px-5 py-10 text-center text-muted">{t('common.empty')}</li>}
          </ul>
        </Card>
      )}
    </div>
  )
}

/** /recruit/requirements/:positionId/edit */
export function RequirementFormPage() {
  const pid = Number(useParams().positionId)
  const q = useQuery({ queryKey: ['recruit', 'requirement', pid], queryFn: () => api<Req>(`/api/v1/recruit/requirements/${pid}`) })
  if (!q.data) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  return <ReqForm key={pid} req={q.data} />
}

function ReqForm({ req }: { req: Req }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [requirements, setRequirements] = useState(req.requirements ?? '')
  const [competencies, setCompetencies] = useState(req.competencies.join(', '))
  const [template, setTemplate] = useState(req.ad_template ?? '')
  const save = useMutation({
    mutationFn: () => send('PUT', `/api/v1/recruit/requirements/${req.position_id}`, { requirements: requirements || null, competencies: competencies.split(',').map((x) => x.trim()).filter(Boolean), ad_template: template || null }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['recruit'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate('/recruit/requirements')
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  const area = 'w-full rounded-control border border-border bg-surface px-3 py-2 text-sm'
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={req.position} subtitle={t('recruitSources.reqEdit')} backTo="/recruit/requirements" backLabel={t('recruit.tabs.requirements')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('recruitSources.reqTitle')}>
          <Field label={t('recruitSources.reqText')}>{(id) => <textarea id={id} value={requirements} onChange={(e) => setRequirements(e.target.value)} rows={5} maxLength={4000} className={area} />}</Field>
          <Field label={t('recruitSources.competencies')} hint={t('recruitSources.competenciesHint')}>{(id) => <Input id={id} value={competencies} onChange={(e) => setCompetencies(e.target.value)} />}</Field>
        </FormSection>
        <FormSection title={t('recruitSources.template')} description={t('recruitSources.templateHint')}>
          <Field label={t('recruitSources.template')}>{(id) => <textarea id={id} value={template} onChange={(e) => setTemplate(e.target.value)} rows={7} maxLength={4000} className={area + ' font-mono'} />}</Field>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate('/recruit/requirements')}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
