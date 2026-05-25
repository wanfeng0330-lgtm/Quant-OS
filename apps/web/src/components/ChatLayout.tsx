import { Outlet } from 'react-router-dom'

export default function ChatLayout() {
  return (
    <div className="h-screen flex flex-col bg-gray-950 text-white">
      {/* Top bar */}
      <header className="h-12 shrink-0 flex items-center justify-between px-4 border-b border-gray-800/80 bg-gray-950/90 backdrop-blur-sm">
        <div className="flex items-center gap-2.5">
          <div className="h-7 w-7 rounded-lg bg-gradient-to-br from-primary-500 to-primary-700 flex items-center justify-center text-xs font-bold shadow-lg shadow-primary-500/20">
            Q
          </div>
          <div>
            <span className="text-sm font-semibold tracking-wide">QuantOS AI</span>
            <span className="ml-2 text-[10px] text-gray-500 font-mono">v0.2.1</span>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[11px] text-gray-500">在线</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
