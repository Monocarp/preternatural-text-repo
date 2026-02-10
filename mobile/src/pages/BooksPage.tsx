import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import apiClient from '../utils/api'

interface Book {
  slug: string
  title: string
  author?: string
  year?: string
  story_count: number
}

export default function BooksPage() {
  const navigate = useNavigate()
  const [books, setBooks] = useState<Book[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadBooks()
  }, [])

  const loadBooks = async () => {
    setLoading(true)
    try {
      const res = await apiClient.get('/books')
      // API returns array directly, not wrapped in {books: [...]}
      setBooks(Array.isArray(res.data) ? res.data : [])
    } catch (err) {
      console.error('Error loading books:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleBookTap = (book: Book) => {
    // For now, navigate to a placeholder
    // Later this will open the book detail view
    navigate(`/books/${book.slug}`)
  }

  return (
    <div className="min-h-full bg-gray-900 pb-4">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-gray-800 border-b border-gray-700 px-4 py-3 safe-area-top">
        <h1 className="text-xl font-bold text-white text-center">Book Archive</h1>
        <p className="text-xs text-gray-400 text-center mt-0.5">Fae & Forgotten</p>
      </header>

      {/* Content */}
      <div className="px-4 pt-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
          </div>
        ) : books.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p>No books found</p>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-gray-400">{books.length} books</p>
            {books.map((book) => (
              <button
                key={book.slug}
                onClick={() => handleBookTap(book)}
                className="w-full bg-gray-800 hover:bg-gray-700 active:bg-gray-600 border border-gray-700 rounded-xl p-4 text-left transition-colors"
              >
                <h3 className="text-base font-medium text-white">
                  {book.title}
                </h3>
                <div className="mt-1 flex items-center gap-2 text-sm text-gray-400">
                  {book.author && <span>{book.author}</span>}
                  {book.author && book.year && <span className="text-gray-600">•</span>}
                  {book.year && <span>{book.year}</span>}
                </div>
                <div className="mt-2 text-sm text-blue-400">
                  {book.story_count} {book.story_count === 1 ? 'story' : 'stories'}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
