import { useState } from 'react'
import { Outlet } from 'react-router-dom'

import { IncomingCalls } from '../../features/calls/IncomingCalls'
import { useRealtime } from '../../features/notifications/useRealtime'
import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

export function AppShell() {
  const [open, setOpen] = useState(false)
  useRealtime()
  return (
    <div className="flex min-h-full bg-bg">
      <a href="#main" className="sr-only z-50 rounded-control bg-surface px-3 py-2 text-sm shadow-pop focus:not-sr-only focus:fixed focus:left-3 focus:top-3">
        Skip to content
      </a>
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onMenu={() => setOpen(true)} />
        <IncomingCalls />
        <main id="main" className="flex-1 px-4 pb-12 pt-1 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
