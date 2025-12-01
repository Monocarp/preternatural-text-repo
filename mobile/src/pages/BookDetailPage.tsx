import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useSwipeable } from 'react-swipeable'
import apiClient from '../utils/api'
import StoryCard from '../components/StoryCard'
import CategoryPicker from '../components/CategoryPicker'
import { useStore } from '../store'

interface BookDetail {
  id: number
  slug: string
  title: string
  author?: string
  year?: string
  story_count: number
  stories?: Array<{
    title: string
    pages?: string
    keywords?: string  // Already a comma-separated string from DB
    start_char?: number
    end_char?: number
  }>
}

interface UnassignedStory {
  title: string
  book_slug: string
  book_title?: string
  pages?: string
  keywords?: string
  start_char: number
  end_char: number
}

type TabType = 'stories' | 'fulltext' | 'review'

export default function BookDetailPage() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const { setSelectedStory: setStoreSelectedStory } = useStore()
  const [book, setBook] = useState<BookDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabType>('stories')
  const [fullText, setFullText] = useState<string | null>(null)
  const [loadingFullText, setLoadingFullText] = useState(false)
  
  // Review tab state
  const [unassignedStories, setUnassignedStories] = useState<UnassignedStory[]>([])
  const [loadingUnassigned, setLoadingUnassigned] = useState(false)
  const [selectedStory, setSelectedStory] = useState<UnassignedStory | null>(null)
  const [assigning, setAssigning] = useState(false)

  const swipeHandlers = useSwipeable({
    onSwipedRight: () => {
      if (selectedStory) {
        setSelectedStory(null)
      } else {
        navigate(-1)
      }
    },
    trackMouse: false,
    delta: 50,
  })

  useEffect(() => {
    if (slug) {
      loadBook()
    }
  }, [slug])

  const loadBook = async () => {
    setLoading(true)
    try {
      const res = await apiClient.get(`/books/${slug}`, {
        params: { include_stories: true }
      })
      setBook(res.data)
    } catch (err) {
      console.error('Error loading book:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadFullText = async () => {
    if (fullText || !slug) return
    setLoadingFullText(true)
    try {
      const res = await apiClient.get(`/full-text/${slug}`)
      setFullText(res.data.text)
    } catch (err) {
      console.error('Error loading full text:', err)
      setFullText('Failed to load full text.')
    } finally {
      setLoadingFullText(false)
    }
  }

  const loadUnassigned = async () => {
    setLoadingUnassigned(true)
    try {
      const res = await apiClient.get('/get-unassigned')
      // Filter to only this book's stories
      const bookStories = (res.data || []).filter(
        (s: UnassignedStory) => s.book_slug === slug
      )
      setUnassignedStories(bookStories)
    } catch (err) {
      console.error('Error loading unassigned:', err)
    } finally {
      setLoadingUnassigned(false)
    }
  }

  const handleTabChange = (tab: TabType) => {
    setActiveTab(tab)
    if (tab === 'fulltext' && !fullText) {
      loadFullText()
    }
    if (tab === 'review') {
      loadUnassigned()
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
      </div>
    )
  }

  if (!book) {
    return (
      <div className="min-h-screen bg-gray-900 flex flex-col items-center justify-center px-4">
        <p className="text-gray-400 mb-4">Book not found</p>
        <button
          onClick={() => navigate(-1)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg"
        >
          Go Back
        </button>
      </div>
    )
  }

  return (
    <div {...swipeHandlers} className="min-h-full bg-gray-900 pb-20">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-gray-800 border-b border-gray-700 safe-area-top">
        <div className="flex items-center px-4 py-3">
          <button
            onClick={() => selectedStory ? setSelectedStory(null) : navigate(-1)}
            className="text-blue-400 mr-3"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="flex-1 min-w-0">
            <h1 className="text-lg font-bold text-white truncate">
              {selectedStory ? 'Assign Story' : book.title}
            </h1>
            {!selectedStory && (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                {book.author && <span>{book.author}</span>}
                {book.author && book.year && <span className="text-gray-600">•</span>}
                {book.year && <span>{book.year}</span>}
              </div>
            )}
          </div>
        </div>

        {/* Tab buttons - hide when assigning */}
        {!selectedStory && (
          <div className="flex border-t border-gray-700">
            <button
              onClick={() => handleTabChange('stories')}
              className={`flex-1 py-3 text-sm font-medium transition-colors ${
                activeTab === 'stories'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400'
              }`}
            >
              Stories
            </button>
            <button
              onClick={() => handleTabChange('fulltext')}
              className={`flex-1 py-3 text-sm font-medium transition-colors ${
                activeTab === 'fulltext'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400'
              }`}
            >
              Full Text
            </button>
            <button
              onClick={() => handleTabChange('review')}
              className={`flex-1 py-3 text-sm font-medium transition-colors ${
                activeTab === 'review'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-400'
              }`}
            >
              Review
              {unassignedStories.length > 0 && (
                <span className="ml-1 px-1.5 py-0.5 bg-orange-500 text-white text-xs rounded-full">
                  {unassignedStories.length}
                </span>
              )}
            </button>
          </div>
        )}
      </header>

      {/* Content */}
      <div className="px-4 pt-4">
        {/* Assignment modal view */}
        {selectedStory ? (
          <div className="space-y-4">
            {/* Story info card */}
            <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
              <h3 className="text-white font-medium">{selectedStory.title}</h3>
              {selectedStory.pages && (
                <p className="text-sm text-gray-400 mt-1">Pages: {selectedStory.pages}</p>
              )}
              {selectedStory.keywords && (
                <div className="mt-2 flex flex-wrap gap-1">
                  {selectedStory.keywords.split(',').slice(0, 5).map((kw, i) => (
                    <span key={i} className="px-2 py-0.5 bg-gray-700 text-gray-300 text-xs rounded-full">
                      {kw.trim()}
                    </span>
                  ))}
                </div>
              )}
              
              {/* Read story button */}
              <button
                onClick={() => {
                  setStoreSelectedStory({
                    title: selectedStory.title,
                    book_slug: selectedStory.book_slug,
                    book_title: selectedStory.book_title,
                    pages: selectedStory.pages,
                    keywords: selectedStory.keywords,
                    start_char: selectedStory.start_char,
                    end_char: selectedStory.end_char,
                  })
                  navigate(`/story/${encodeURIComponent(selectedStory.title)}`)
                }}
                className="mt-3 w-full py-2 rounded-lg font-medium bg-gray-700 text-gray-300 active:bg-gray-600 text-sm"
              >
                📖 Read Story First
              </button>
            </div>

            {/* Category Picker */}
            <CategoryPicker
              keywords={selectedStory.keywords}
              assigning={assigning}
              onSelect={async (path) => {
                setAssigning(true)
                try {
                  await apiClient.post('/assign-category', {
                    story: {
                      title: selectedStory.title,
                      book_slug: selectedStory.book_slug,
                      start_char: selectedStory.start_char,
                      end_char: selectedStory.end_char,
                      pages: selectedStory.pages,
                      keywords: selectedStory.keywords,
                    },
                    path: path
                  })
                  
                  // Remove from list and clear selection
                  setUnassignedStories(prev => prev.filter(s => s.title !== selectedStory.title))
                  setSelectedStory(null)
                } catch (err) {
                  console.error('Error assigning story:', err)
                  alert('Failed to assign story. Make sure you are logged in as an editor.')
                } finally {
                  setAssigning(false)
                }
              }}
              onCancel={() => setSelectedStory(null)}
            />
          </div>
        ) : activeTab === 'stories' ? (
          // Stories tab
          <>
            {book.stories && book.stories.length > 0 ? (
              <div className="space-y-3">
                {book.stories.map((story, index) => (
                  <StoryCard
                    key={index}
                    story={{
                      title: story.title,
                      book_slug: book.slug,
                      book_title: book.title,
                      book_author: book.author,
                      pages: story.pages,
                      keywords: story.keywords,
                      start_char: story.start_char || 0,
                      end_char: story.end_char || 0,
                    }}
                  />
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-400">
                <p>No stories found in this book</p>
              </div>
            )}
          </>
        ) : activeTab === 'fulltext' ? (
          // Full Text tab
          <>
            {loadingFullText ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
              </div>
            ) : fullText ? (
              <div className="prose prose-invert prose-sm max-w-none">
                <div className="whitespace-pre-wrap text-gray-300 leading-relaxed text-sm font-serif">
                  {fullText}
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-gray-400">
                <p>Loading full text...</p>
              </div>
            )}
          </>
        ) : (
          // Review tab
          <>
            {loadingUnassigned ? (
              <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
              </div>
            ) : unassignedStories.length > 0 ? (
              <div className="space-y-3">
                <p className="text-sm text-gray-400">
                  {unassignedStories.length} unassigned {unassignedStories.length === 1 ? 'story' : 'stories'}
                </p>
                {unassignedStories.map((story, index) => (
                  <button
                    key={index}
                    onClick={() => setSelectedStory(story)}
                    className="w-full bg-gray-800 hover:bg-gray-700 active:bg-gray-600 border border-orange-500/30 rounded-xl p-4 text-left transition-colors"
                  >
                    <h3 className="text-base font-medium text-white">{story.title}</h3>
                    {story.pages && (
                      <p className="text-sm text-gray-400 mt-1">Pages: {story.pages}</p>
                    )}
                    <p className="text-sm text-orange-400 mt-2">Tap to assign →</p>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-400">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mx-auto mb-4 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p>All stories from this book are assigned!</p>
              </div>
            )}
          </>
        )}
      </div>

      {/* Swipe hint */}
      {!selectedStory && (
        <div className="fixed bottom-24 left-4 text-xs text-gray-500">
          ← Swipe right to go back
        </div>
      )}
    </div>
  )
}
