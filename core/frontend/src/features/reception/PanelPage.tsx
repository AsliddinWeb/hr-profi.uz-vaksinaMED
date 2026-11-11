import { BookUser, Coffee, FilePlus2, LifeBuoy, PackagePlus } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'

import { PageHeader } from '../../components/layout/PageHeader'
import { Button } from '../../components/ui/Button'
import { useCan } from '../auth/useAuth'
import { DeskPanel } from '../home/DeskPanel'

/** /reception/panel: Resepshin — hamma soha bo'yicha xodim ishi va umumiy nazorat bitta joyda. */
export function PanelPage() {
  const { t } = useTranslation()
  const can = useCan()
  const actions = [
    { to: '/reception/new', icon: BookUser, key: 'guest', ok: can('reception.own') || can('reception.desk') || can('reception.read') },
    { to: '/reception/coffee', icon: Coffee, key: 'coffee', ok: true },
    { to: '/answers/new', icon: FilePlus2, key: 'request', ok: can('answers.request') },
    { to: '/helpdesk/new', icon: LifeBuoy, key: 'ticket', ok: ['helpdesk.own', 'helpdesk.work', 'helpdesk.read', 'helpdesk.manage'].some(can) },
    { to: '/needs/new', icon: PackagePlus, key: 'need', ok: ['needs.own', 'needs.work', 'needs.dispatch', 'needs.manage'].some(can) },
  ].filter((a) => a.ok)
  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6">
      <PageHeader title={t('desk.title')} subtitle={t('desk.subtitle')} />
      <div className="flex flex-wrap gap-2">
        {actions.map(({ to, icon: Icon, key }) => (
          <Link key={key} to={to}>
            <Button variant="outline">
              <Icon className="size-4" />
              {t(`desk.action.${key}`)}
            </Button>
          </Link>
        ))}
      </div>
      <DeskPanel />
    </div>
  )
}
