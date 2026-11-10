import { AlertTriangle, Home, RotateCcw } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { isRouteErrorResponse, useRouteError } from 'react-router-dom'

/** Sahifa ichida kutilmagan xato bo'lsa — butun ilova o'rniga tushunarli xabar va qayta urinish. */
export function RouteError() {
  const { t } = useTranslation()
  const err = useRouteError()
  const detail = isRouteErrorResponse(err) ? `${err.status} ${err.statusText}` : err instanceof Error ? err.message : String(err ?? '')
  if (import.meta.env.DEV) console.error(err)
  return (
    <main className="grid min-h-screen place-items-center bg-bg px-4">
      <div className="flex max-w-md flex-col items-center gap-3 rounded-card border border-border bg-surface p-8 text-center shadow-card">
        <AlertTriangle className="size-10 text-warning" />
        <h1 className="text-lg font-semibold">{t('routeError.title')}</h1>
        <p className="text-sm text-muted">{t('routeError.hint')}</p>
        {detail && <code className="max-w-full truncate rounded bg-surface-2 px-2 py-1 text-xs text-muted">{detail}</code>}
        <div className="mt-2 flex gap-2">
          <button type="button" onClick={() => window.location.reload()} className="inline-flex items-center gap-1.5 rounded-control bg-primary px-4 py-2 text-sm font-semibold text-primary-fg">
            <RotateCcw className="size-4" />
            {t('routeError.retry')}
          </button>
          <a href="/" className="inline-flex items-center gap-1.5 rounded-control border border-border px-4 py-2 text-sm font-semibold">
            <Home className="size-4" />
            {t('routeError.home')}
          </a>
        </div>
      </div>
    </main>
  )
}
