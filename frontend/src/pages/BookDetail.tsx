import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/react'
import ReactMarkdown from 'react-markdown'
import axios from '../utils/axios'
import SidebarTree from '../components/SidebarTree'

interface Story {
  title: string
  book_slug: string
  book_title?: string
  book_author?: string
  book_year?: string
  pages?: string
  keywords?: string
  start_char: number
  end_char: number
}

const BookDetail = () => {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const [book, setBook] = useState<any>(null)
  const [stories, setStories] = useState<Story[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<'info' | 'text' | 'stories'>('info')
  const [fullText, setFullText] = useState<string>('')
  const [loadingText, setLoadingText] = useState(false)
  const [storyContents, setStoryContents] = useState<Record<string, string>>({})
  const [storyModes, setStoryModes] = useState<Record<string, 'static' | 'book'>>({})
  const textViewerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (slug) {
      loadBook()
    }
  }, [slug])

  const loadBook = async () => {
    try {
      setLoading(true)
      const res = await axios.get(`/books/${slug}`, {
        params: { include_stories: true }
      })
      setBook(res.data)
      setStories(res.data.stories || [])
      setError(null)
    } catch (err) {
      console.error('Error loading book:', err)
      setError('Failed to load book')
    } finally {
      setLoading(false)
    }
  }

  const loadFullText = async () => {
    if (!slug || fullText) return
    
    try {
      setLoadingText(true)
      const res = await axios.get(`/full-text/${slug}`)
      setFullText(res.data.text)
    } catch (err) {
      console.error('Error loading full text:', err)
      setError('Failed to load book text')
    } finally {
      setLoadingText(false)
    }
  }

  const handleViewText = () => {
    setView('text')
    if (!fullText) {
      loadFullText()
    }
  }

  const handleViewStories = () => {
    setView('stories')
  }

  const handleToggleMode = async (story: Story, mode: 'static' | 'book') => {
    try {
      const res = await axios.post('/render-story', {
        title: story.title,
        mode: mode,
        search_query: undefined
      })
      setStoryContents(prev => ({
        ...prev,
        [story.title]: res.data.html
      }))
      setStoryModes(prev => ({
        ...prev,
        [story.title]: mode
      }))
      
      // Auto-scroll to story position in book context mode
      if (mode === 'book') {
        setTimeout(() => {
          const wrapper = document.getElementById(`book-context-${story.title}`)
          const container = wrapper?.querySelector('#book-context-container') as HTMLElement
          const highlight = container?.querySelector('#story-highlight') as HTMLElement
          
          if (container && highlight) {
            const highlightTop = highlight.offsetTop
            const containerHeight = container.clientHeight
            container.scrollTop = highlightTop - (containerHeight / 2) + (highlight.offsetHeight / 2)
          }
        }, 150)
      }
    } catch (err) {
      console.error('Error loading story:', err)
    }
  }

  const handleStoryOpen = async (story: Story) => {
    if (!storyContents[story.title]) {
      await handleToggleMode(story, 'static')
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen">
        <SidebarTree />
        <main className="flex-1 overflow-y-auto bg-gray-900 min-w-0">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
            <div className="text-center py-8">
              <p className="text-gray-400">Loading book...</p>
            </div>
          </div>
        </main>
      </div>
    )
  }

  if (error || !book) {
    return (
      <div className="flex h-screen">
        <SidebarTree />
        <main className="flex-1 overflow-y-auto bg-gray-900 min-w-0">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
            <div className="bg-red-900 border border-red-700 rounded p-4 mb-4 text-center">
              <p className="text-red-200">{error || 'Book not found'}</p>
            </div>
            <div className="text-center">
              <button
                onClick={() => navigate('/book-archive')}
                className="text-blue-400 hover:text-blue-300"
              >
                ← Back to Book Archive
              </button>
            </div>
          </div>
        </main>
      </div>
    )
  }

  return (
    <div className="flex h-screen">
      <SidebarTree />
      <main className="flex-1 overflow-y-auto bg-gray-900 min-w-0">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
          {/* Breadcrumb */}
          <nav className="text-sm text-gray-400 mb-4">
            <button
              onClick={() => navigate('/book-archive')}
              className="hover:text-blue-400"
            >
              Book Archive
            </button>
            <span className="mx-2">›</span>
            <span className="text-white">{book.title}</span>
          </nav>

      {/* Book Header */}
      <div className="mb-6 text-center">
        <h1 className="text-3xl font-bold text-white mb-2">{book.title}</h1>
        {book.author && (
          <p className="text-gray-300 text-lg mb-1">by {book.author}</p>
        )}
        {book.year && (
          <p className="text-gray-500 text-sm mb-3">Published: {book.year}</p>
        )}
        <p className="text-gray-400">
          {book.story_count} {book.story_count === 1 ? 'story' : 'stories'}
        </p>
      </div>

      {/* View Toggle Buttons */}
      <div className="flex justify-center gap-4 mb-6">
        <button
          onClick={handleViewText}
          className={`px-6 py-2 rounded-lg font-medium transition-colors ${
            view === 'text'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          }`}
        >
          View Text
        </button>
        <button
          onClick={handleViewStories}
          className={`px-6 py-2 rounded-lg font-medium transition-colors ${
            view === 'stories'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          }`}
        >
          View Stories
        </button>
      </div>

      {/* Content Area */}
      {view === 'text' && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-6 md:p-10">
          <h2 className="text-xl font-semibold text-white mb-6 text-center">Full Text</h2>
          {loadingText && (
            <div className="text-center py-8">
              <p className="text-gray-400">Loading text...</p>
            </div>
          )}
          {!loadingText && fullText && (
            <div
              ref={textViewerRef}
              className="bg-gray-900 border border-gray-700 rounded-lg p-6 md:p-10 max-h-[75vh] overflow-y-auto"
            >
              <div 
                className="mx-auto text-gray-200"
                style={{ 
                  fontFamily: "'Libre Baskerville', Georgia, 'Times New Roman', serif",
                  maxWidth: '65ch',
                  lineHeight: '1.9',
                  fontSize: '1.05rem'
                }}
              >
                <ReactMarkdown
                  components={{
                    h1: ({children}) => <h1 className="text-2xl font-bold text-white mt-10 mb-6 border-b border-gray-700 pb-3">{children}</h1>,
                    h2: ({children}) => <h2 className="text-xl font-semibold text-white mt-8 mb-4">{children}</h2>,
                    h3: ({children}) => <h3 className="text-lg font-semibold text-gray-100 mt-6 mb-3">{children}</h3>,
                    p: ({children}) => <p className="mb-5 text-gray-200">{children}</p>,
                    blockquote: ({children}) => (
                      <blockquote className="border-l-4 border-blue-500 pl-5 py-2 my-6 italic text-gray-300 bg-gray-800/50 rounded-r">
                        {children}
                      </blockquote>
                    ),
                    strong: ({children}) => <strong className="font-semibold text-white">{children}</strong>,
                    em: ({children}) => <em className="italic text-gray-100">{children}</em>,
                    ul: ({children}) => <ul className="list-disc list-inside mb-5 space-y-2">{children}</ul>,
                    ol: ({children}) => <ol className="list-decimal list-inside mb-5 space-y-2">{children}</ol>,
                    li: ({children}) => <li className="text-gray-200">{children}</li>,
                    hr: () => <hr className="my-8 border-gray-700" />,
                  }}
                >
                  {fullText}
                </ReactMarkdown>
              </div>
            </div>
          )}
        </div>
      )}

      {view === 'stories' && (
        <div className="space-y-3">
          {stories.length === 0 && (
            <div className="text-center py-8">
              <p className="text-gray-400">No stories found in this book.</p>
            </div>
          )}
          {stories.map((story, index) => {
            const currentMode = storyModes[story.title] || 'static'
            const storyContent = storyContents[story.title]
            
            return (
              <Disclosure
                key={`${story.title}-${index}`}
                as="div"
                className="border border-gray-700 rounded-lg shadow-sm hover:shadow-md transition-shadow bg-gray-800 relative"
              >
                <DisclosureButton
                  className="w-full p-4 hover:bg-gray-700"
                  onClick={() => handleStoryOpen(story)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 text-center pr-8">
                      <h3 className="text-lg font-semibold text-white">
                        {story.title}
                      </h3>
                      <div className="mt-1 text-sm text-gray-400">
                        <span className="font-medium">{book?.title || ''}</span>
                        {book?.author && <span className="ml-2">• {book.author}</span>}
                        {book?.year && <span className="ml-2">({book.year})</span>}
                      </div>
                      <div className="mt-0.5 text-xs text-gray-500">
                        {story.pages && <span>Pages: {story.pages}</span>}
                        {story.keywords && (
                          <span className="ml-2">• Keywords: {story.keywords}</span>
                        )}
                      </div>
                    </div>
                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400">▼</span>
                  </div>
                </DisclosureButton>
                <DisclosurePanel className="p-4 pt-0">
                  <div className="mt-4 border-t border-gray-700 pt-4">
                    {storyContent ? (
                      <div className="prose max-w-none prose-invert">
                        <div
                          id={`book-context-${story.title}`}
                          dangerouslySetInnerHTML={{ __html: storyContent }}
                        />
                      </div>
                    ) : (
                      <div className="text-gray-400 text-center py-4">
                        Loading story...
                      </div>
                    )}
                    <div className="mt-4 flex justify-center gap-2">
                      {currentMode === 'static' ? (
                        <button
                          onClick={() => handleToggleMode(story, 'book')}
                          className="px-4 py-2 rounded text-sm bg-blue-600 text-white hover:bg-blue-700"
                        >
                          Book Context
                        </button>
                      ) : (
                        <button
                          onClick={() => handleToggleMode(story, 'static')}
                          className="px-4 py-2 rounded text-sm bg-gray-700 text-gray-200 hover:bg-gray-600"
                        >
                          Static View
                        </button>
                      )}
                    </div>
                  </div>
                </DisclosurePanel>
              </Disclosure>
            )
          })}
        </div>
      )}
        </div>
      </main>
    </div>
  )
}

export default BookDetail
