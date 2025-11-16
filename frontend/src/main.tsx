// src/main.tsx
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { StackProvider, StackClientApp, StackHandler, StackTheme } from '@stackframe/react'
import { TooltipProvider } from '@radix-ui/react-tooltip' // New import for TooltipProvider
import { useLocation } from 'react-router-dom'
import { setStackApp } from './utils/axios'
import Archive from './pages/Archive'
import SearchCurate from './pages/SearchCurate'
import Login from './components/Login'
import Callback from './pages/Callback'
import './index.css' // Tailwind

const queryClient = new QueryClient()

// Load from environment
const projectId = import.meta.env.VITE_STACK_PROJECT_ID
const publishableKey = import.meta.env.VITE_STACK_PUBLISHABLE_CLIENT_KEY

// Create the StackClientApp instance with projectId and tokenStore
const app = new StackClientApp({
  projectId,
  publishableClientKey: publishableKey,
  tokenStore: 'cookie'  // Required for client-side persistence
})

// Register app instance with axios interceptor
setStackApp(app)

// Minimal handler component so Stack can process /handler/* callbacks
function HandlerRoutes() {
  const location = useLocation()
  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <div className="max-w-2xl mx-auto p-6">
        <StackHandler app={app} location={location.pathname} fullPage />
      </div>
    </div>
  )
}

createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <StackProvider app={app}>
      <StackTheme>
        <TooltipProvider> {/* Wrap to provide context for Tooltip components */}
          <Router>
            <Routes>
              {/* StackAuth handler route for OAuth callbacks */}
              <Route path="/handler/*" element={<HandlerRoutes />} />
              
              {/* App routes */}
              <Route path="/" element={<Archive />} />
              <Route path="/archive" element={<Archive />} />
              <Route path="/archive/:path/*" element={<Archive />} />
              <Route path="/search-curate" element={<SearchCurate />} />
              <Route path="/login" element={<Login />} />
              {/* Fallback callback we previously used */}
              <Route path="/callback" element={<Callback />} />
            </Routes>
          </Router>
        </TooltipProvider>
      </StackTheme>
    </StackProvider>
  </QueryClientProvider>
)