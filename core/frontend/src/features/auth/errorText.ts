import type { TFunction } from 'i18next'

import { ApiError } from '../../lib/api'

/** ApiError -> foydalanuvchiga ko'rinadigan matn (errors.<code>, bo'lmasa umumiy). */
export function errorText(t: TFunction, e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === 'too_many_attempts') {
      const mins = Math.max(1, Math.ceil(Number(e.extra.retry_after ?? 60) / 60))
      return t('errors.too_many_attempts', { minutes: mins })
    }
    const key = `errors.${e.code}`
    const text = t(key)
    return text === key ? t('errors.unknown') : text
  }
  return t('errors.network')
}

/** 422 `validation`: maydon bo'yicha xatolar `{ phone: "Telefon noto'g'ri" }` ko'rinishida. */
export function fieldErrors(t: TFunction, e: unknown): Record<string, string> {
  if (!(e instanceof ApiError) || e.code !== 'validation') return {}
  const fields = (e.extra.fields ?? []) as { field: string; code: string }[]
  const out: Record<string, string> = {}
  for (const { field, code } of fields) {
    const key = `errors.fields.${code}`
    const text = t(key)
    out[field] = text === key ? t('errors.invalidValue') : text
  }
  return out
}
