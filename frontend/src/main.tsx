// src/main.tsx
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { StackProvider, StackClientApp } from '@stackframe/react'
import { TooltipProvider } from '@radix-ui/react-tooltip' // New import for TooltipProvider
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

createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <StackProvider app={app}>
      <TooltipProvider> {/* Wrap to provide context for Tooltip components */}
        <Router>
          <Routes>
            <Route path="/" element={<Archive />} />
            <Route path="/archive" element={<Archive />} />
            <Route path="/archive/:path*" element={<Archive />} />
            <Route path="/search-curate" element={<SearchCurate />} />
            <Route path="/login" element={<Login />} />
            <Route path="/callback" element={<Callback />} />
          </Routes>
        </Router>
      </TooltipProvider>
    </StackProvider>
  </QueryClientProvider>
)