import clsx from 'clsx'

import { initials } from '../../lib/format'

/** Xodim rasmi (API orqali, ruxsat bilan). Rasm bo'lmasa bosh harflar. `v` — yangilangan rasmni ko'rsatish uchun. */
export function Avatar({
  id,
  name,
  hasPhoto,
  size = 40,
  v,
  className,
}: {
  id: number
  name: string
  hasPhoto: boolean
  size?: number
  v?: number
  className?: string
}) {
  const style = { width: size, height: size, fontSize: size * 0.36 }
  if (hasPhoto) {
    return (
      <img
        src={`/api/v1/employees/${id}/photo${v ? `?v=${v}` : ''}`}
        alt=""
        loading="lazy"
        style={style}
        className={clsx('shrink-0 rounded-[30%] object-cover', className)}
      />
    )
  }
  return (
    <span style={style} className={clsx('grid shrink-0 place-items-center rounded-[30%] bg-surface-3 font-medium text-muted', className)}>
      {initials(name)}
    </span>
  )
}
