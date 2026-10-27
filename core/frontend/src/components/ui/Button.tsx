import type { ButtonHTMLAttributes } from 'react'

import { cn } from '../../lib/cn'

type Tone = 'success' | 'danger' | 'warning' | 'violet' | 'teal' | 'info'

/** Amal turiga qarab rang: yumshoq fon + to'q matn (light/dark'da ham o'qiladi). */
const TONES: Record<Tone, string> = {
  success: 'bg-[color-mix(in_oklab,var(--success)_14%,var(--surface))] text-success hover:bg-[color-mix(in_oklab,var(--success)_24%,var(--surface))]',
  danger: 'bg-[color-mix(in_oklab,var(--danger)_13%,var(--surface))] text-danger hover:bg-[color-mix(in_oklab,var(--danger)_23%,var(--surface))]',
  warning: 'bg-[color-mix(in_oklab,var(--amber)_16%,var(--surface))] text-(--amber) hover:bg-[color-mix(in_oklab,var(--amber)_26%,var(--surface))]',
  violet: 'bg-[color-mix(in_oklab,var(--violet)_14%,var(--surface))] text-(--violet) hover:bg-[color-mix(in_oklab,var(--violet)_24%,var(--surface))]',
  teal: 'bg-[color-mix(in_oklab,var(--teal)_14%,var(--surface))] text-(--teal) hover:bg-[color-mix(in_oklab,var(--teal)_24%,var(--surface))]',
  info: 'bg-[color-mix(in_oklab,var(--info)_14%,var(--surface))] text-info hover:bg-[color-mix(in_oklab,var(--info)_24%,var(--surface))]',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost' | 'outline' | Tone
}

export function Button({ variant = 'primary', className, type = 'button', ...rest }: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex h-9 select-none items-center justify-center gap-2 whitespace-nowrap rounded-control px-3.5 text-[13px] font-medium transition-[background-color,box-shadow,transform,opacity] duration-150 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50',
        variant === 'primary' && 'bg-primary text-primary-fg shadow-[0_1px_2px_color-mix(in_oklab,var(--primary)_40%,transparent)] hover:brightness-110',
        variant !== 'primary' && variant !== 'outline' && variant !== 'ghost' && TONES[variant],
        variant === 'outline' && 'bg-surface text-text shadow-[inset_0_0_0_1px_var(--border-strong)] hover:bg-surface-2',
        variant === 'ghost' && 'text-muted hover:bg-surface-2 hover:text-text',
        '[&_svg]:size-4 [&_svg]:shrink-0',
        className,
      )}
      {...rest}
    />
  )
}
