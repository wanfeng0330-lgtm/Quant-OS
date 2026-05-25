import { lazy, Suspense } from 'react'
import { Routes, Route } from 'react-router-dom'
import ChatLayout from './components/ChatLayout'

const Chat = lazy(() => import('./pages/Chat'))

function Loading() {
  return (
    <div className="flex items-center justify-center h-screen bg-gray-950">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
    </div>
  )
}

function App() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<ChatLayout />}>
          <Route index element={<Chat />} />
        </Route>
      </Routes>
    </Suspense>
  )
}

export default App
