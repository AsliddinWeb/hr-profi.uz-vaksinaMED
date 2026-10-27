import { useTranslation } from 'react-i18next'

import { Badge } from '../../components/ui/Badge'
import { SEV_TONE, type Severity } from './api'

export function SeverityBadge({ severity }: { severity: Severity }) {
  const { t } = useTranslation()
  return <Badge tone={SEV_TONE[severity]}>{t(`pharmacy.severity.${severity}`)}</Badge>
}
