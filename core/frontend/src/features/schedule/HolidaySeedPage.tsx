import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { FormFooter, FormSection } from '../../components/ui/Form'
import { Field, Select } from '../../components/ui/Input'
import { useToast } from '../../components/ui/toastContext'
import { send } from '../../lib/api'
import { errorText } from '../auth/errorText'
import { currentYear, FIXED_HOLIDAYS } from './api'

const LIST = '/schedule/holidays'

/** /schedule/holidays/seed: O'zbekistonning qat'iy bayramlarini bir bosishda qo'shish. */
export function HolidaySeedPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const toast = useToast()
  const [params] = useSearchParams()
  const thisYear = currentYear()
  const [year, setYear] = useState(Number(params.get('year')) || thisYear)
  const [yearly, setYearly] = useState(true)

  const run = useMutation({
    mutationFn: () => send<{ created: number; skipped: number }>('POST', '/api/v1/schedule/holidays/seed', { year, yearly }),
    onSuccess: (r) => {
      void qc.invalidateQueries({ queryKey: ['schedule'] })
      toast.push({ title: t('schedule.holidays.seeded', { created: r.created, skipped: r.skipped }), tone: 'success' })
      navigate(LIST)
    },
  })
  const submit = (e: FormEvent) => {
    e.preventDefault()
    run.mutate()
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeader title={t('schedule.holidays.seed')} subtitle={t('schedule.holidays.seedSubtitle')} backTo={LIST} backLabel={t('schedule.holidays.title')} />
      <form onSubmit={submit} className="flex flex-col gap-6">
        <FormSection title={t('schedule.holidays.seedList')} description={t('schedule.holidays.seedHint')}>
          <ul className="divide-y divide-border rounded-control border border-border text-sm">
            {FIXED_HOLIDAYS.map(([md, name]) => (
              <li key={md} className="flex items-center justify-between px-4 py-2.5">
                <span>{name}</span>
                <span className="tabular-nums text-muted">{md.split('-').reverse().join('.')}</span>
              </li>
            ))}
          </ul>
        </FormSection>
        <FormSection title={t('schedule.holidays.seedOptions')}>
          <Field label={t('schedule.holidays.year')}>
            {(id) => (
              <Select id={id} value={year} onChange={(e) => setYear(Number(e.target.value))} className="max-w-40" disabled={yearly}>
                {[thisYear, thisYear + 1, thisYear + 2].map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </Select>
            )}
          </Field>
          <label className="flex items-start gap-2 text-sm">
            <input type="checkbox" className="mt-0.5 size-4" checked={yearly} onChange={(e) => setYearly(e.target.checked)} />
            <span>
              {t('schedule.holidays.repeatYearly')}
              <span className="block text-xs text-muted">{t('schedule.holidays.seedYearlyHint')}</span>
            </span>
          </label>
        </FormSection>
        <FormFooter error={run.isError ? errorText(t, run.error) : null}>
          <Button variant="outline" onClick={() => navigate(LIST)}>
            {t('common.cancel')}
          </Button>
          <Button type="submit" disabled={run.isPending}>
            {t('schedule.holidays.seedRun')}
          </Button>
        </FormFooter>
      </form>
    </div>
  )
}
