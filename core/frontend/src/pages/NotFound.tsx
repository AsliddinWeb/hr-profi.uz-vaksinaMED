import { Link } from 'react-router-dom'
import { useTranslation } from 'react-i18next'

export function NotFound() {
  const { t } = useTranslation()
  return (
    <div className="mx-auto mt-24 max-w-md text-center">
      <div className="text-6xl font-semibold text-muted">404</div>
      <h1 className="mt-4 text-xl font-semibold">{t('notFound.title')}</h1>
      <Link to="/" className="mt-6 inline-block text-sm font-medium text-primary underline">
        {t('notFound.back')}
      </Link>
    </div>
  )
}
