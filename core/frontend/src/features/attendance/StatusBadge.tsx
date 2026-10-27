import { useTranslation } from 'react-i18next'

import { TONES, type Status } from './api'

export function StatusBadge({ status }: { status: Status }) {
  const { t } = useTranslation()
  return <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${TONES[status]}`}>{t(`attendance.status.${status}`)}</span>
}
