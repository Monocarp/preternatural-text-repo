import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import apiClient from '../utils/api'
import StoryCard from '../components/StoryCard'
import CategoryPicker from '../components/CategoryPicker'
import StoryReviewTab from '../components/StoryReviewTab'

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

interface AiSuggestion {
  path: string[]
  confidence: number
  reason?: string
  confirmed: boolean
}

type TabType = 'stories' | 'fulltext' | 'review'

export default function BookDetailPage() {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const [book, setBook] = useState<BookDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabType>('stories')
  const [fullText, setFullText] = useState<string | null>(null)
  const [loadingFullText, setLoadingFullText] = useState(false)
  
  // Review tab state
  const [unassignedStories, setUnassignedStories] = useState<UnassignedStory[]>([])
  const [selectedStory, setSelectedStory] = useState<UnassignedStory | null>(null)
  const [assigning, setAssigning] = useState(false)
  
  // AI suggestion state
  const [aiSuggestions, setAiSuggestions] = useState<AiSuggestion[]>([])
  const [loadingAi, setLoadingAi] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)
  const [committingAll, setCommittingAll] = useState(false)
  const [showAiPanel, setShowAiPanel] = useState(false)

  // Inline preview state
  const [previewHtml, setPreviewHtml] = useState<string | null>(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [previewMode, setPreviewMode] = useState<'story' | 'context'>('story')
  const [showPreview, setShowPreview] = useState(false)
  const previewRef = useRef<HTMLDivElement>(null)

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
    try {
      const res = await apiClient.get('/get-unassigned')
      // Filter to only this book's stories
      const bookStories = (res.data || []).filter(
        (s: UnassignedStory) => s.book_slug === slug
      )
      setUnassignedStories(bookStories)
    } catch (err) {
      console.error('Error loading unassigned:', err)
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

  // Reset AI state and preview when story changes
  useEffect(() => {
    setAiSuggestions([])
    setAiError(null)
    setShowAiPanel(false)
    setPreviewHtml(null)
    setShowPreview(false)
    setPreviewMode('story')
  }, [selectedStory?.title])

  // After context preview loads, scroll to the highlighted story
  useEffect(() => {
    if (previewHtml && previewMode === 'context' && previewRef.current) {
      // Small delay to let dangerouslySetInnerHTML render
      const timer = setTimeout(() => {
        const container = previewRef.current
        const highlight = container?.querySelector('#story-highlight') as HTMLElement | null
        if (container && highlight) {
          // Calculate offset relative to scrollable container and scroll there
          container.scrollTop = highlight.offsetTop - container.offsetTop - 20
        }
      }, 100)
      return () => clearTimeout(timer)
    }
  }, [previewHtml, previewMode])

  // Load inline preview content
  const loadPreview = async (mode: 'story' | 'context') => {
    if (!selectedStory) return
    setLoadingPreview(true)
    setPreviewMode(mode)
    setShowPreview(true)
    try {
      const res = await apiClient.post('/render-story', {
        title: selectedStory.title,
        mode: mode === 'context' ? 'book' : 'static',
        start_char: selectedStory.start_char,
        end_char: selectedStory.end_char,
      })
      let html = res.data.html
      // Strip backend's fixed-height scroll container so mobile's own container controls scrolling
      if (mode === 'context') {
        html = html.replace(/height:\s*500px;\s*/g, '')
        html = html.replace(/overflow-y:\s*scroll;\s*/g, '')
      }
      setPreviewHtml(html)
    } catch (err) {
      console.error('Error loading preview:', err)
      setPreviewHtml('<p class="text-red-400">Failed to load story content</p>')
    } finally {
      setLoadingPreview(false)
    }
  }

  // Advance to next unassigned story (or clear if none left)
  const advanceToNext = (justAssignedTitle: string) => {
    const remaining = unassignedStories.filter(s => s.title !== justAssignedTitle)
    setUnassignedStories(remaining)
    if (remaining.length > 0) {
      setSelectedStory(remaining[0])
    } else {
      setSelectedStory(null)
    }
    setAiSuggestions([])
    setShowAiPanel(false)
  }

  const handleAutoSuggest = async () => {
    if (!selectedStory || !fullText) {
      // Load full text first if not loaded
      if (!fullText && slug) {
        setLoadingFullText(true)
        try {
          const res = await apiClient.get(`/full-text/${slug}`)
          setFullText(res.data.text)
        } catch (err) {
          console.error('Error loading full text:', err)
          setAiError('Failed to load story text')
          return
        } finally {
          setLoadingFullText(false)
        }
      }
    }
    
    const text = fullText
    if (!text || !selectedStory) return
    
    // Extract story text using character boundaries
    const storyText = text.slice(selectedStory.start_char, selectedStory.end_char)
    
    setLoadingAi(true)
    setAiError(null)
    setShowAiPanel(true)
    
    try {
      const res = await apiClient.post('/ai/suggest-categories', {
        story_title: selectedStory.title,
        story_text: storyText.slice(0, 15000) // Limit to ~15k chars
      })
      
      const suggestions = (res.data.suggestions || []).map((s: { path: string[]; confidence: number; reason?: string }) => ({
        ...s,
        confirmed: s.confidence >= 0.7 // Auto-confirm high confidence
      }))
      
      setAiSuggestions(suggestions)
    } catch (err: any) {
      console.error('Error getting AI suggestions:', err)
      const detail = err.response?.data?.detail || err.message || 'Unknown error'
      setAiError(`Failed: ${detail}`)
    } finally {
      setLoadingAi(false)
    }
  }

  const handleToggleSuggestion = (idx: number) => {
    setAiSuggestions(prev => prev.map((s, i) => 
      i === idx ? { ...s, confirmed: !s.confirmed } : s
    ))
  }

  const handleCommitConfirmed = async () => {
    if (!selectedStory) return
    
    const confirmed = aiSuggestions.filter(s => s.confirmed)
    if (confirmed.length === 0) return
    
    setCommittingAll(true)
    
    try {
      // Commit each confirmed suggestion
      for (const suggestion of confirmed) {
        await apiClient.post('/assign-category', {
          story: {
            title: selectedStory.title,
            book_slug: selectedStory.book_slug,
            start_char: selectedStory.start_char,
            end_char: selectedStory.end_char,
            pages: selectedStory.pages,
            keywords: selectedStory.keywords,
          },
          path: suggestion.path
        })
      }
      
      // Advance to next unassigned story
      advanceToNext(selectedStory.title)
    } catch (err) {
      console.error('Error committing categories:', err)
      setAiError('Failed to save categories. Make sure you are logged in as an editor.')
    } finally {
      setCommittingAll(false)
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
    <div className="min-h-full bg-gray-900 pb-20">
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
              {selectedStory ? selectedStory.title : book.title}
            </h1>
            {selectedStory ? (
              <p className="text-sm text-gray-400 truncate">Assign to category</p>
            ) : (
              <div className="flex items-center gap-2 text-sm text-gray-400">
                {book.author && <span>{book.author}</span>}
                {book.author && book.year && <span className="text-gray-600">•</span>}
                {book.year && <span>{book.year}</span>}
              </div>
            )}
          </div>
          {/* Skip button when assigning */}
          {selectedStory && unassignedStories.length > 1 && (
            <button
              onClick={() => {
                const idx = unassignedStories.findIndex(s => s.title === selectedStory.title)
                const next = unassignedStories[(idx + 1) % unassignedStories.length]
                setSelectedStory(next)
              }}
              className="text-gray-400 active:text-white ml-2 px-2 py-1 text-sm"
            >
              Skip →
            </button>
          )}
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
      <div className={activeTab === 'review' && !selectedStory ? '' : 'px-4 pt-4'}>
        {/* Assignment modal view */}
        {selectedStory ? (
          <div className="space-y-4">
            {/* Progress indicator */}
            {unassignedStories.length > 0 && (
              <div className="flex items-center justify-between text-xs text-gray-400">
                <span>
                  Story {unassignedStories.findIndex(s => s.title === selectedStory.title) + 1} of {unassignedStories.length}
                </span>
                <div className="flex gap-1">
                  {unassignedStories.map((s, i) => (
                    <div
                      key={i}
                      className={`w-2 h-2 rounded-full ${
                        s.title === selectedStory.title ? 'bg-blue-400' : 'bg-gray-600'
                      }`}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Story info card with inline preview */}
            <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
              <div className="p-4">
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

                {/* Preview toggle buttons */}
                <div className="mt-3 flex gap-2">
                  <button
                    onClick={() => showPreview && previewMode === 'story' ? setShowPreview(false) : loadPreview('story')}
                    className={`flex-1 py-2 rounded-lg font-medium text-sm transition-colors ${
                      showPreview && previewMode === 'story'
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-700 text-gray-300 active:bg-gray-600'
                    }`}
                  >
                    {loadingPreview && previewMode === 'story' ? '⏳' : '📖'} Story Text
                  </button>
                  <button
                    onClick={() => showPreview && previewMode === 'context' ? setShowPreview(false) : loadPreview('context')}
                    className={`flex-1 py-2 rounded-lg font-medium text-sm transition-colors ${
                      showPreview && previewMode === 'context'
                        ? 'bg-amber-600 text-white'
                        : 'bg-gray-700 text-gray-300 active:bg-gray-600'
                    }`}
                  >
                    {loadingPreview && previewMode === 'context' ? '⏳' : '🔍'} In Context
                  </button>
                </div>
              </div>

              {/* Expandable inline preview */}
              {showPreview && (
                <div className="border-t border-gray-700">
                  {loadingPreview ? (
                    <div className="flex items-center justify-center py-8">
                      <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-400"></div>
                    </div>
                  ) : previewHtml ? (
                    <div className="relative">
                      <div
                        ref={previewRef}
                        className="max-h-64 overflow-y-auto px-4 py-3"
                        style={{ overscrollBehavior: 'contain' }}
                      >
                        <div
                          className="prose prose-invert prose-sm max-w-none text-sm"
                          style={{ fontFamily: "'Georgia', 'Times New Roman', serif", lineHeight: 1.7 }}
                          dangerouslySetInnerHTML={{ __html: previewHtml }}
                        />
                      </div>
                      {/* Fade-out gradient at bottom */}
                      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-8 bg-gradient-to-t from-gray-800 to-transparent" />
                    </div>
                  ) : null}
                  <div className="px-4 py-2 bg-gray-800/80 text-center">
                    <span className="text-xs text-gray-500">
                      {previewMode === 'story' ? 'Story text only' : 'Story highlighted in book context'} • Scroll to read
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* AI Suggestions Panel */}
            <div className="bg-gradient-to-br from-purple-900/40 to-blue-900/40 rounded-xl p-4 border border-purple-500/50">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-xl">🤖</span>
                <h4 className="text-white font-medium">AI Category Suggestions</h4>
              </div>
              
              <button
                onClick={handleAutoSuggest}
                disabled={loadingAi}
                className="w-full py-3 bg-purple-600 hover:bg-purple-500 active:bg-purple-700 disabled:bg-gray-600 text-white rounded-lg font-medium transition-colors mb-3"
              >
                {loadingAi ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="animate-spin">⏳</span> Analyzing story...
                  </span>
                ) : (
                  '✨ Auto-Suggest Categories'
                )}
              </button>
              
              {aiError && (
                <div className="p-3 bg-red-900/50 border border-red-500 rounded-lg text-sm text-red-200 mb-3">
                  {aiError}
                </div>
              )}
              
              {aiSuggestions.length > 0 && (
                <div className="space-y-2">
                  {aiSuggestions.map((suggestion, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleToggleSuggestion(idx)}
                      className={`w-full text-left p-3 rounded-lg transition-colors ${
                        suggestion.confirmed 
                          ? 'bg-green-900/50 border-2 border-green-500' 
                          : 'bg-gray-800 border border-gray-600'
                      }`}
                    >
                      <div className="flex items-start gap-2">
                        <div className={`w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 ${
                          suggestion.confirmed 
                            ? 'bg-green-500 border-green-500' 
                            : 'border-gray-500'
                        }`}>
                          {suggestion.confirmed && (
                            <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                            </svg>
                          )}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="text-sm text-white mb-1">
                            {suggestion.path.join(' → ')}
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 text-xs rounded ${
                              suggestion.confidence >= 0.8 ? 'bg-green-600 text-white' :
                              suggestion.confidence >= 0.5 ? 'bg-yellow-600 text-white' :
                              'bg-gray-600 text-gray-200'
                            }`}>
                              {Math.round(suggestion.confidence * 100)}%
                            </span>
                            {suggestion.reason && (
                              <span className="text-xs text-gray-400 truncate">{suggestion.reason}</span>
                            )}
                          </div>
                        </div>
                      </div>
                    </button>
                  ))}
                  
                  <button
                    onClick={handleCommitConfirmed}
                    disabled={committingAll || aiSuggestions.filter(s => s.confirmed).length === 0}
                    className="w-full mt-3 py-3 bg-green-600 hover:bg-green-500 active:bg-green-700 disabled:bg-gray-600 text-white rounded-lg font-medium transition-colors"
                  >
                    {committingAll ? (
                      <span className="flex items-center justify-center gap-2">
                        <span className="animate-spin">⏳</span> Saving...
                      </span>
                    ) : (
                      `✓ Commit ${aiSuggestions.filter(s => s.confirmed).length} Selected`
                    )}
                  </button>
                </div>
              )}
              
              {!showAiPanel && aiSuggestions.length === 0 && !loadingAi && (
                <p className="text-sm text-gray-400 text-center">
                  Tap above to get AI-powered category suggestions
                </p>
              )}
            </div>

            {/* Divider */}
            <div className="flex items-center gap-3 text-gray-500 text-sm">
              <div className="flex-1 h-px bg-gray-700"></div>
              <span>or browse manually</span>
              <div className="flex-1 h-px bg-gray-700"></div>
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
                  
                  // Advance to next unassigned story
                  advanceToNext(selectedStory.title)
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
          // Review tab – full-text viewer with story highlighting
          <StoryReviewTab
            slug={book.slug}
            stories={(book.stories || []).map((s: any) => ({
              title: s.title,
              book_slug: book.slug,
              pages: s.pages,
              keywords: s.keywords,
              start_char: s.start_char ?? 0,
              end_char: s.end_char ?? 0,
            }))}
            onStoriesChange={(updated) => {
              setBook({ ...book, stories: updated, story_count: updated.length })
            }}
          />
        )}
      </div>

    </div>
  )
}
