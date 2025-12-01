// mobile/src/pages/HandlerPage.tsx
// Stack Auth handler for OAuth callbacks
import { useLocation } from 'react-router-dom'
import { StackHandler } from '@stackframe/react'
import { stackApp } from '../main'

export default function HandlerPage() {
  const location = useLocation()
  
  return (
    <div className="min-h-screen bg-gray-900 flex items-center justify-center p-6">
      <div className="bg-gray-800 p-6 rounded-xl w-full max-w-sm">
        <StackHandler app={stackApp} location={location.pathname} fullPage />
      </div>
    </div>
  )
}
