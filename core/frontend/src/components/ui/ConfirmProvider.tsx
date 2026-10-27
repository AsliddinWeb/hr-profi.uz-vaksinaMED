import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react'
import { useTranslation } from 'react-i18next'

import { Button } from './Button'
import { ConfirmContext, type ConfirmFn, type ConfirmOptions } from './confirmContext'

/**
 * Halokatli amallarni (o'chirish, parolni tiklash) tasdiqlash uchun kichik dialog.
 * Yaratish/tahrirlash uchun ISHLATILMAYDI: ular alohida sahifada.
 */
export function ConfirmProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation()
  const ref = useRef<HTMLDialogElement>(null)
  const resolver = useRef<((v: boolean) => void) | null>(null)
  const [opts, setOpts] = useState<ConfirmOptions | null>(null)

  const confirm: ConfirmFn = useCallback(
    (o) =>
      new Promise<boolean>((resolve) => {
        resolver.current?.(false)
        resolver.current = resolve
        setOpts(o)
      }),
    [],
  )

  useEffect(() => {
    if (opts && ref.current && !ref.current.open) ref.current.showModal()
  }, [opts])

  const finish = (value: boolean) => {
    resolver.current?.(value)
    resolver.current = null
    ref.current?.close()
    setOpts(null)
  }

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <dialog
        ref={ref}
        onCancel={(e) => {
          e.preventDefault()
          finish(false)
        }}
        className="m-auto w-[min(26rem,calc(100vw-2rem))] rounded-card bg-surface p-0 text-text shadow-pop backdrop:bg-black/40 backdrop:backdrop-blur-[2px]"
      >
        {opts && (
          <div className="p-6">
            <h2 className="text-base font-medium tracking-tight">{opts.title}</h2>
            {opts.body && <p className="mt-2 text-sm text-muted">{opts.body}</p>}
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="outline" onClick={() => finish(false)}>
                {opts.cancelLabel ?? t('common.cancel')}
              </Button>
              <Button
                onClick={() => finish(true)}
                className={opts.danger ? 'bg-danger text-white hover:opacity-90' : undefined}
                autoFocus
              >
                {opts.confirmLabel ?? t('common.confirm')}
              </Button>
            </div>
          </div>
        )}
      </dialog>
    </ConfirmContext.Provider>
  )
}
