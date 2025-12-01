import { BrowserRouter, Routes, Route } from 'react-router-dom'
import MobileLayout from './components/MobileLayout'
import ArchivePage from './pages/ArchivePage'
import SearchPage from './pages/SearchPage'
import BooksPage from './pages/BooksPage'
import BookDetailPage from './pages/BookDetailPage'
import AccountPage from './pages/AccountPage'
import StoryReaderPage from './pages/StoryReaderPage'
import CategoryPage from './pages/CategoryPage'
import LoginPage from './pages/LoginPage'
import HandlerPage from './pages/HandlerPage'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Stack Auth handler for OAuth callbacks */}
        <Route path="/handler/*" element={<HandlerPage />} />
        
        {/* Login page */}
        <Route path="/login" element={<LoginPage />} />
        
        <Route element={<MobileLayout />}>
          <Route path="/" element={<ArchivePage />} />
          <Route path="/archive" element={<ArchivePage />} />
          <Route path="/archive/*" element={<CategoryPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/books" element={<BooksPage />} />
          <Route path="/books/:slug" element={<BookDetailPage />} />
          <Route path="/account" element={<AccountPage />} />
        </Route>
        {/* Full-screen reader (no bottom nav) */}
        <Route path="/story/:title" element={<StoryReaderPage />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
