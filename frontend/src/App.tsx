import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Archive from './pages/Archive'
import SearchCurate from './pages/SearchCurate'
import Callback from './pages/Callback'
import Login from './components/Login'
import SidebarTree from './components/SidebarTree'

function App() {
  return (
    <Router>
      <div className="flex h-screen bg-gray-900 text-white">
        <SidebarTree />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Archive />} />
            <Route path="/archive/*" element={<Archive />} />
            <Route path="/search-curate" element={<SearchCurate />} />
            <Route path="/callback" element={<Callback />} />
            <Route path="/login" element={<Login />} />
          </Routes>
        </main>
      </div>
    </Router>
  )
}

export default App