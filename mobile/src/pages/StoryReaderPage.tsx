import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useSwipeable } from 'react-swipeable'
import { useStore } from '../store'
import apiClient from '../utils/api'

export default function StoryReaderPage() {
  const navigate = useNavigate()
  const { selectedStory } = useStore()
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [viewMode, setViewMode] = useState<'static' | 'book'>('static')

  // Swipe down to close
  const swipeHandlers = useSwipeable({
    onSwipedDown: (eventData) => {
      if (eventData.velocity > 0.5) {
        navigate(-1)
      }
    },
    onSwipedRight: () => {
      navigate(-1)
    },
    trackMouse: false,
    delta: 50,
  })

  useEffect(() => {
    if (selectedStory) {
      loadStoryContent()
    }
  }, [selectedStory, viewMode])

  const loadStoryContent = async () => {
    if (!selectedStory) return

    setLoading(true)
    try {
      const res = await apiClient.post('/render-story', {
        title: selectedStory.title,
        mode: viewMode,
        start_char: selectedStory.start_char,
        end_char: selectedStory.end_char
      })
      setContent(res.data.html)
    } catch (err) {
      console.error('Error loading story:', err)
      setContent('<p class="text-red-400">Failed to load story content</p>')
    } finally {
      setLoading(false)
    }
  }

  const handleBack = () => {
    navigate(-1)
  }

  if (!selectedStory) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center text-gray-400">
          <p>No story selected</p>
          <button
            onClick={() => navigate('/')}
            className="mt-4 text-blue-400"
          >
            Go back
          </button>
        </div>
      </div>
    )
  }

  const bookDisplay = selectedStory.book_title || selectedStory.book_slug?.replace(/_/g, ' ') || 'Unknown Book'

  return (
    <div {...swipeHandlers} className="min-h-screen bg-gray-900 flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-gray-800 border-b border-gray-700 safe-area-top">
        <div className="flex items-center px-2 py-3">
          <button
            onClick={handleBack}
            className="p-2 -ml-2 text-gray-300 hover:text-white"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <div className="flex-1 min-w-0 px-2">
            <h1 className="text-base font-semibold text-white truncate">
              {selectedStory.title}
            </h1>
            <p className="text-xs text-gray-400 truncate">
              {bookDisplay}
              {selectedStory.pages && ` • p.${selectedStory.pages}`}
            </p>
          </div>
        </div>

        {/* View mode toggle */}
        <div className="flex border-t border-gray-700">
          <button
            onClick={() => setViewMode('static')}
            className={`flex-1 py-2 text-sm font-medium transition-colors ${
              viewMode === 'static'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400'
            }`}
          >
            Story
          </button>
          <button
            onClick={() => setViewMode('book')}
            className={`flex-1 py-2 text-sm font-medium transition-colors ${
              viewMode === 'book'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-gray-400'
            }`}
          >
            Book Context
          </button>
        </div>
      </header>

      {/* Content */}
      <div className="flex-1 overflow-y-auto overscroll-contain">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
          </div>
        ) : (
          <div className="px-4 py-6">
            <div
              className="prose prose-invert prose-sm max-w-none"
              style={{
                fontFamily: "'Georgia', 'Times New Roman', serif",
                lineHeight: 1.8
              }}
              dangerouslySetInnerHTML={{ __html: content }}
            />
          </div>
        )}
      </div>

      {/* Bottom safe area */}
      <div className="safe-area-bottom bg-gray-900"></div>
    </div>
  )
}
