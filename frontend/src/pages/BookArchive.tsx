import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import axios from '../utils/axios'
import SidebarTree from '../components/SidebarTree'

interface Book {
  id: number
  slug: string
  title: string
  author?: string
  year?: string
  story_count: number
}

const BookArchive = () => {
  const [books, setBooks] = useState<Book[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    loadBooks()
  }, [])

  const loadBooks = async () => {
    try {
      setLoading(true)
      const res = await axios.get('/books')
      setBooks(res.data)
      setError(null)
    } catch (err) {
      console.error('Error loading books:', err)
      setError('Failed to load books')
    } finally {
      setLoading(false)
    }
  }

  const handleBookClick = (slug: string) => {
    navigate(`/book-archive/${slug}`)
  }

  return (
    <div className="flex h-screen h-[100dvh] max-h-screen max-w-[100vw] overflow-hidden">
      <SidebarTree />
      <main className="flex-1 overflow-y-auto bg-gray-900 min-w-0 max-w-full">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
          <div className="mb-6">
        <h1 className="text-3xl font-bold text-white text-center">Book Archive</h1>
        <p className="text-gray-300 mt-2 text-center">
          Browse books and their stories
        </p>
      </div>

      {loading && (
        <div className="text-center py-8">
          <p className="text-gray-400">Loading books...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-900 border border-red-700 rounded p-4 mb-4 text-center">
          <p className="text-red-200">Error: {error}</p>
        </div>
      )}

      {!loading && !error && books.length === 0 && (
        <div className="text-center py-8">
          <p className="text-gray-400">No books found.</p>
        </div>
      )}

      {!loading && books.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {books.map((book) => (
            <button
              key={book.id}
              onClick={() => handleBookClick(book.slug)}
              className="bg-gray-800 border border-gray-700 rounded-lg p-6 hover:bg-gray-700 hover:border-gray-600 transition-all text-left"
            >
              <h3 className="text-xl font-semibold text-white mb-2">
                {book.title}
              </h3>
              {book.author && (
                <p className="text-gray-400 text-sm mb-1">
                  {book.author}
                </p>
              )}
              {book.year && (
                <p className="text-gray-500 text-xs mb-3">
                  Published: {book.year}
                </p>
              )}
              <div className="flex items-center justify-between pt-3 border-t border-gray-700">
                <span className="text-sm text-gray-400">
                  {book.story_count} {book.story_count === 1 ? 'story' : 'stories'}
                </span>
                <span className="text-blue-400 text-sm">View →</span>
              </div>
            </button>
          ))}
        </div>
      )}
        </div>
      </main>
    </div>
  )
}

export default BookArchive
