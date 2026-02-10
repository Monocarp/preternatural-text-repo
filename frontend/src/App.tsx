import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import Home from './pages/Home'
import Archive from './pages/Archive'
import SearchCurate from './pages/SearchCurate'
import Callback from './pages/Callback'
import BookArchive from './pages/BookArchive'
import BookDetail from './pages/BookDetail'
import Login from './components/Login'

function App() {
  return (
    <Router>
      <Routes>
        {/* Home page — full screen, no sidebar */}
        <Route path="/" element={<Home />} />

        {/* Main app pages — Archive handles its own sidebar */}
        <Route path="/archive/*" element={<Archive />} />
        <Route path="/search-curate" element={<SearchCurate />} />
        <Route path="/book-archive" element={<BookArchive />} />
        <Route path="/book-archive/:slug" element={<BookDetail />} />
        <Route path="/callback" element={<Callback />} />
        <Route path="/login" element={<Login />} />
      </Routes>
    </Router>
  )
}

export default App