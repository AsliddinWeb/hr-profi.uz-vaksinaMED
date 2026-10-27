import type { ReactNode } from 'react'

import { cn } from '../../lib/cn'
import { Card } from './Card'

/** Forma bo'limi: sarlavha + izoh + maydonlar. */
export function FormSection({
  title,
  description,
  children,
  danger,
  className,
}: {
  title: string
  description?: string
  children: ReactNode
  danger?: boolean
  className?: string
}) {
  return (
    <Card className={cn('@container p-6', danger && 'shadow-[inset_0_0_0_1px_color-mix(in_oklab,var(--danger)_35%,transparent)]', className)}>
      {/* Keng sahifada: chapda nom va izoh, o'ngda maydonlar; tor joyda ustma-ust */}
      <div className="@3xl:grid @3xl:grid-cols-[13rem_minmax(0,1fr)] @3xl:gap-10">
        <div>
          <h2 className={cn('text-[15px] font-medium tracking-tight', danger && 'text-danger')}>{title}</h2>
          {description && <p className="mt-1 text-[13px] leading-relaxed text-muted">{description}</p>}
        </div>
        <div className="mt-5 flex flex-col gap-4 @3xl:mt-0">{children}</div>
      </div>
    </Card>
  )
}

/** Sahifa tagida suzuvchi amallar paneli (Bekor qilish / Saqlash). */
export function FormFooter({ children, error }: { children: ReactNode; error?: ReactNode }) {
  return (
    <div className="sticky bottom-4 z-10 mt-2 flex flex-wrap items-center justify-end gap-3 rounded-2xl bg-surface/90 px-4 py-3 shadow-pop backdrop-blur">
      {error && (
        <p role="alert" className="mr-auto text-sm text-danger">
          {error}
        </p>
      )}
      {children}
    </div>
  )
}
