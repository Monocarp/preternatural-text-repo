// src/main.tsx
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Archive from './pages/Archive'
import Login from './components/Login'
import Callback from './pages/Callback'
import './index.css' // Tailwind

const queryClient = new QueryClient()

createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}>
    <Router>
      <Routes>
        <Route path="/" element={<Archive />} />
        <Route path="/login" element={<Login />} />
        <Route path="/callback" element={<Callback />} />
        {/* Add /search-curate later */}
      </Routes>
    </Router>
  </QueryClientProvider>
)