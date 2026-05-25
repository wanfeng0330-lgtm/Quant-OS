import { useState } from 'react'
import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import EventStream from './EventStream'
import CommandPalette from './CommandPalette'

export default function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [eventStreamOpen, setEventStreamOpen] = useState(false)

  return (
    <div className="min-h-screen overflow-x-hidden bg-gray-50 dark:bg-gray-950">
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className={`min-h-screen transition-all lg:pl-64 ${eventStreamOpen ? 'lg:pr-96' : ''}`}>
        <Header
          onMenuClick={() => setSidebarOpen(true)}
          onEventStreamToggle={() => setEventStreamOpen(v => !v)}
          eventStreamOpen={eventStreamOpen}
        />
        <main className="px-4 pb-24 pt-4 sm:px-6 lg:px-8 lg:pb-8">
          <Outlet />
        </main>
      </div>
      <EventStream open={eventStreamOpen} onClose={() => setEventStreamOpen(false)} />
      <CommandPalette />
    </div>
  )
}
