import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus, Trash2 } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Input, Select } from '../../components/ui/Input'
import { Skeleton } from '../../components/ui/Skeleton'
import { useConfirm } from '../../components/ui/confirmContext'
import { useToast } from '../../components/ui/toastContext'
import { api, ApiError, send } from '../../lib/api'
import { NotFound } from '../../pages/NotFound'
import { errorText } from '../auth/errorText'
import { useCan } from '../auth/useAuth'
import { usePositionOptions } from '../org/usePositionOptions'
import { ScorecardPanel } from './EvalParts'
import { RecruitTabs } from './RecruitTabs'
import type { TestBankRow } from './api'

const LIST = '/recruit/tests'

/** /recruit/tests: test banki (IQ, mantiq, lavozim bo'yicha bilim). */
export function TestBankPage() {
  const { t } = useTranslation()
  const manage = useCan()('recruit.manage')
  const q = useQuery({ queryKey: ['recruit', 'tests'], queryFn: () => api<TestBankRow[]>('/api/v1/recruit/tests') })
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-5">
      <PageHeader
        title={t('recruit.title')}
        subtitle={t('recruitEval.bank.subtitle')}
        actions={
          manage && (
            <Link to={`${LIST}/new`}>
              <Button>
                <Plus className="size-4" />
                {t('recruitEval.bank.add')}
              </Button>
            </Link>
          )
        }
      />
      <RecruitTabs />
      {!q.data ? (
        <Skeleton className="h-40" />
      ) : (
        <div className="flex flex-col gap-3">
          {q.data.map((b) => (
            <Link key={b.id} to={`${LIST}/${b.id}/edit`}>
              <Card className="flex flex-wrap items-center justify-between gap-3 p-4 hover:bg-surface-2">
                <div>
                  <div className="font-medium">{b.name}</div>
                  <div className="text-sm text-muted">
                    {t(`recruitEval.tests.kind.${b.kind}`)} · {t('recruitEval.bank.questions', { n: b.question_count })} · {b.time_limit_min} {t('recruitEval.tests.min')} · {t('recruitEval.bank.pass', { n: b.pass_score })}
                  </div>
                </div>
                {!b.is_active && <Badge>{t('duty.inactive')}</Badge>}
              </Card>
            </Link>
          ))}
          {q.data.length === 0 && <Card className="p-8 text-center text-muted">{t('common.empty')}</Card>}
        </div>
      )}
    </div>
  )
}

interface Q {
  id?: string
  text: string
  options: string[]
  correct: number[]
}
const blankQ = (): Q => ({ text: '', options: ['', ''], correct: [] })

/** /recruit/tests/new va /recruit/tests/:id/edit */
export function TestBankFormPage() {
  const { id } = useParams()
  const bid = id ? Number(id) : null
  const q = useQuery({ queryKey: ['recruit', 'test', bid], queryFn: () => api<TestBankRow>(`/api/v1/recruit/tests/${bid}`), enabled: bid !== null, retry: false })
  if (bid === null) return <BankForm bank={null} />
  if (q.isLoading) return <Skeleton className="mx-auto h-96 max-w-3xl" />
  if (q.error instanceof ApiError && q.error.status === 404) return <NotFound />
  return q.data ? <BankForm key={q.data.id} bank={q.data} /> : null
}

function BankForm({ bank }: { bank: TestBankRow | null }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const confirm = useConfirm()
  const positions = usePositionOptions()
  const [name, setName] = useState(bank?.name ?? '')
  const [kind, setKind] = useState<TestBankRow['kind']>(bank?.kind ?? 'logic')
  const [pos, setPos] = useState(String(bank?.position_id ?? ''))
  const [limit, setLimit] = useState(String(bank?.time_limit_min ?? 20))
  const [pass, setPass] = useState(String(bank?.pass_score ?? 60))
  const [active, setActive] = useState(bank?.is_active ?? true)
  const [qs, setQs] = useState<Q[]>(bank?.questions?.length ? bank.questions : [blankQ()])
  const [delErr, setDelErr] = useState<string | null>(null)
  const patch = (i: number, p: Partial<Q>) => setQs(qs.map((x, j) => (j === i ? { ...x, ...p } : x)))
  const save = useMutation({
    mutationFn: () => {
      const body = { name, kind, position_id: kind === 'position' && pos ? Number(pos) : null, time_limit_min: Number(limit), pass_score: Number(pass), is_active: active, questions: qs }
      return bank ? send('PUT', `/api/v1/recruit/tests/${bank.id}`, body) : send('POST', '/api/v1/recruit/tests', body)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['recruit'] })
      toast.push({ title: t('common.saved'), tone: 'success' })
      navigate(LIST)
    },
  })
  const remove = useMutation({
    mutationFn: () => send('DELETE', `/api/v1/recruit/tests/${bank?.id}`),
    onSuccess: () => (void qc.invalidateQueries({ queryKey: ['recruit'] }), navigate(LIST)),
    onError: (e) => setDelErr(errorText(t, e)),
  })
  const valid = name.trim().length >= 2 && qs.every((x) => x.text.trim() && x.options.every((o) => o.trim()) && x.correct.length > 0)
  const submit = (e: FormEvent) => {
    e.preventDefault()
    save.mutate()
  }
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <PageHeader title={bank ? t('recruitEval.bank.edit') : t('recruitEval.bank.add')} subtitle={bank?.name} backTo={LIST} backLabel={t('recruit.tabs.tests')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('recruitEval.bank.main')}>
          <Field label={t('recruitEval.bank.name')}>{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} required minLength={2} maxLength={160} autoFocus />}</Field>
          <div className="grid gap-4 sm:grid-cols-4">
            <Field label={t('recruitEval.bank.kind')}>
              {(id) => (
                <Select id={id} value={kind} onChange={(e) => setKind(e.target.value as typeof kind)}>
                  {(['iq', 'logic', 'position'] as const).map((k) => (
                    <option key={k} value={k}>
                      {t(`recruitEval.tests.kind.${k}`)}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
            <Field label={t('recruitEval.bank.limit')}>{(id) => <Input id={id} type="number" min={1} max={240} value={limit} onChange={(e) => setLimit(e.target.value)} />}</Field>
            <Field label={t('recruitEval.bank.passLabel')}>{(id) => <Input id={id} type="number" min={1} max={100} value={pass} onChange={(e) => setPass(e.target.value)} />}</Field>
            {kind === 'position' && (
              <Field label={t('recruitEval.bank.position')}>
                {(id) => (
                  <Select id={id} value={pos} onChange={(e) => setPos(e.target.value)}>
                    <option value="">—</option>
                    {positions.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.label}
                      </option>
                    ))}
                  </Select>
                )}
              </Field>
            )}
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4" checked={active} onChange={(e) => setActive(e.target.checked)} />
            {t('duty.activeLabel')}
          </label>
        </FormSection>
        <FormSection title={t('recruitEval.bank.questionsTitle')} description={t('recruitEval.bank.questionsHint')}>
          <ol className="flex flex-col gap-4">
            {qs.map((x, i) => (
              <li key={x.id ?? `n${i}`}>
                <Card tint="sand" className="flex flex-col gap-3 p-4">
                  <div className="flex items-center gap-2">
                    <span className="grid size-7 shrink-0 place-items-center rounded-full bg-surface text-xs font-semibold">{i + 1}</span>
                    <Input value={x.text} onChange={(e) => patch(i, { text: e.target.value })} maxLength={500} placeholder={t('recruitEval.bank.qText')} aria-label={t('recruitEval.bank.qText')} />
                    <Button variant="ghost" className="h-9 px-2 text-danger" disabled={qs.length === 1} onClick={() => setQs(qs.filter((_, j) => j !== i))} aria-label={t('common.delete')}>
                      <Trash2 className="size-4" />
                    </Button>
                  </div>
                  <ul className="flex flex-col gap-2">
                    {x.options.map((o, k) => (
                      <li key={k} className="flex items-center gap-2">
                        <input type="checkbox" className="size-4" checked={x.correct.includes(k)} onChange={(e) => patch(i, { correct: e.target.checked ? [...x.correct, k].sort() : x.correct.filter((c) => c !== k) })} aria-label={t('recruitEval.bank.correct')} />
                        <Input value={o} onChange={(e) => patch(i, { options: x.options.map((y, m) => (m === k ? e.target.value : y)) })} maxLength={200} placeholder={t('recruitEval.bank.option', { n: k + 1 })} aria-label={t('recruitEval.bank.option', { n: k + 1 })} />
                        {x.options.length > 2 && (
                          <Button variant="ghost" className="h-9 px-2" onClick={() => patch(i, { options: x.options.filter((_, m) => m !== k), correct: x.correct.filter((c) => c !== k).map((c) => (c > k ? c - 1 : c)) })} aria-label={t('common.delete')}>
                            <Trash2 className="size-4" />
                          </Button>
                        )}
                      </li>
                    ))}
                  </ul>
                  {x.options.length < 6 && (
                    <div>
                      <Button variant="outline" className="h-8" onClick={() => patch(i, { options: [...x.options, ''] })}>
                        <Plus className="size-4" />
                        {t('recruitEval.bank.addOption')}
                      </Button>
                    </div>
                  )}
                </Card>
              </li>
            ))}
          </ol>
          <div>
            <Button variant="outline" onClick={() => setQs([...qs, blankQ()])} disabled={qs.length >= 100}>
              <Plus className="size-4" />
              {t('recruitEval.bank.addQuestion')}
            </Button>
          </div>
        </FormSection>
        <FormFooter error={save.isError ? errorText(t, save.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={save.isPending || !valid}>
            {t('common.save')}
          </Button>
        </FormFooter>
      </form>
      {bank && (
        <FormSection title={t('org.dangerZone')} description={t('recruitEval.bank.deleteHint')} danger>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="outline"
              className="text-danger"
              onClick={async () => {
                if (await confirm({ title: t('common.delete'), body: t('org.deleteConfirm', { name: bank.name }), danger: true, confirmLabel: t('common.delete') })) {
                  setDelErr(null)
                  remove.mutate()
                }
              }}
            >
              <Trash2 className="size-4" />
              {t('common.delete')}
            </Button>
            {delErr && <span className="text-sm text-danger">{delErr}</span>}
          </div>
        </FormSection>
      )}
    </div>
  )
}

/** /recruit/applications/:id/scorecard: faqat baholash huquqi bor suhbatdosh (mudir, koordinator) uchun yengil sahifa. */
export function ScorecardPage() {
  const id = Number(useParams().id)
  const { t } = useTranslation()
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5">
      <PageHeader title={t('recruitEval.score.title')} subtitle={t('recruitEval.score.pageHint')} />
      <ScorecardPanel appId={id} />
    </div>
  )
}
