// src/pages/SearchCurate.tsx
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStackApp } from '@stackframe/react'
import apiClient from '../utils/axios'
import SidebarTree from '../components/SidebarTree'
import {
  useCategoryAssignment,
  useKeywordsEditor,
  useNewStoryCreator,
  calculateCharPositionFromClick
} from '../hooks'

interface SearchResult {
  title: string
  book_slug: string
  pages: string
  keywords: string
  start_char: number
  end_char: number
  score: number
  search_query?: string
  book_title?: string
  book_author?: string
  book_year?: string
}

const SearchCurate = () => {
  const navigate = useNavigate()
  const app = useStackApp()
  const [query, setQuery] = useState('')
  const [sourceFilter, setSourceFilter] = useState('All Sources')
  const [typeFilter, setTypeFilter] = useState('Both')
  const [searchMode, setSearchMode] = useState('Both')
  const [minScore, setMinScore] = useState(0.1)
  const [assignmentFilter, setAssignmentFilter] = useState('all')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [subcategoryFilter, setSubcategoryFilter] = useState('')
  const [sources, setSources] = useState<string[]>(['All Sources'])
  const [categories, setCategories] = useState<string[]>([])
  const [subcategories, setSubcategories] = useState<Record<string, string[]>>({})
  const [results, setResults] = useState<SearchResult[]>([])
  const [selectedStory, setSelectedStory] = useState<SearchResult | null>(null)
  const [storyContent, setStoryContent] = useState<string>('')
  const [storyMode, setStoryMode] = useState<'static' | 'book'>('static')
  const [loading, setLoading] = useState(false)
  const [searching, setSearching] = useState(false)
  
  // Collapsible filters state - auto-collapse on smaller screens
  const [filtersExpanded, setFiltersExpanded] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerHeight > 800
    }
    return true
  })
  
  // Boundary editing - kept as local state since hook needs fullText which is loaded async
  // The hook's value proposition is limited here due to the async fullText loading pattern
  const [editMode, setEditMode] = useState(false)
  const [fullText, setFullText] = useState<string>('')
  const [editedStart, setEditedStart] = useState<number>(0)
  const [editedEnd, setEditedEnd] = useState<number>(0)
  const [selectingStart, setSelectingStart] = useState(true)
  const textContainerRef = useRef<HTMLDivElement>(null)
  
  // Category assignment - using custom hook
  const categoryAssignment = useCategoryAssignment(selectedStory)

  // New story creation - using custom hook
  const newStoryCreator = useNewStoryCreator()

  // Keywords editing - using custom hook
  const keywordsEditor = useKeywordsEditor({
    onSaveSuccess: (_story, newKeywords) => {
      // Update local selected story state
      if (selectedStory) {
        const updatedStory = { ...selectedStory, keywords: newKeywords }
        setSelectedStory(updatedStory)
        // Update in results list
        setResults(prev => prev.map(r =>
          r.title === selectedStory.title && r.book_slug === selectedStory.book_slug
            ? { ...r, keywords: newKeywords }
            : r
        ))
      }
    }
  })

  // Load available sources on mount
  useEffect(() => {
    apiClient.get('/sources')
      .then(res => {
        setSources(res.data.sources || ['All Sources'])
      })
      .catch(err => {
        console.error('Error loading sources:', err)
        setSources(['All Sources'])
      })
  }, [])

  // Load available categories on mount
  useEffect(() => {
    apiClient.get('/categories')
      .then(res => {
        // Sort categories alphabetically
        const sortedCategories = (res.data.categories || []).sort((a: string, b: string) => a.localeCompare(b))
        // Sort subcategories alphabetically for each category
        const sortedSubcategories: Record<string, string[]> = {}
        for (const [cat, subs] of Object.entries(res.data.subcategories || {})) {
          sortedSubcategories[cat] = (subs as string[]).sort((a, b) => a.localeCompare(b))
        }
        setCategories(sortedCategories)
        setSubcategories(sortedSubcategories)
      })
      .catch(err => {
        console.error('Error loading categories:', err)
        setCategories([])
        setSubcategories({})
      })
  }, [])
  
  // Current assignments now handled by categoryAssignment hook

  // Handle search
  const handleSearch = async () => {
    if (!query.trim()) return
    
    setSearching(true)
    try {
      const res = await apiClient.post('/search', {
        query: query.trim(),
        source_filter: sourceFilter,
        type_filter: typeFilter,
        search_mode: searchMode,
        top_k: 1000,
        min_score: minScore,
        assignment_filter: assignmentFilter,
        category_filter: categoryFilter || null,
        subcategory_filter: subcategoryFilter || null
      })
      setResults(res.data.results || [])
      if (res.data.results && res.data.results.length > 0) {
        setSelectedStory(null) // Clear selection when new search
        setStoryContent('')
      }
    } catch (err) {
      console.error('Search error:', err)
      setResults([])
    } finally {
      setSearching(false)
    }
  }

  // Handle story selection
  const handleSelectStory = async (story: SearchResult) => {
    setSelectedStory(story)
    setEditMode(false) // Exit edit mode when selecting new story
    newStoryCreator.cancel() // Exit new story mode when selecting existing story
    setLoading(true)
    try {
      const res = await apiClient.post('/render-story', {
        title: story.title,
        mode: 'static',
        search_query: story.search_query
      })
      setStoryContent(res.data.html)
      setStoryMode('static')
      // Initialize edited boundaries with current story boundaries
      setEditedStart(story.start_char)
      setEditedEnd(story.end_char)
    } catch (err) {
      console.error('Error loading story:', err)
      setStoryContent('Error loading story.')
    } finally {
      setLoading(false)
    }
  }

  // Enter boundary editing mode
  const handleAdjustBoundaries = async () => {
    if (!selectedStory) return
    
    setLoading(true)
    setEditMode(true)
    try {
      // Load full text
      const res = await apiClient.get(`/full-text/${selectedStory.book_slug}`)
      setFullText(res.data.text)
      setEditedStart(selectedStory.start_char)
      setEditedEnd(selectedStory.end_char)
      setSelectingStart(true)
    } catch (err) {
      console.error('Error loading full text:', err)
      setEditMode(false)
    } finally {
      setLoading(false)
    }
  }

  // Auto-scroll to original boundaries when entering edit mode
  useEffect(() => {
    if (editMode && fullText && textContainerRef.current && selectedStory) {
      // Wait for DOM to update, then scroll to the start position
      setTimeout(() => {
        const textContainer = textContainerRef.current
        if (!textContainer) return
        
        // Find the scrollable parent (the div with overflow-y-auto)
        let scrollableParent: HTMLElement | null = textContainer.parentElement
        while (scrollableParent && !scrollableParent.classList.contains('overflow-y-auto')) {
          scrollableParent = scrollableParent.parentElement
        }
        
        // Find the marker element at the start position
        const startMarker = textContainer.querySelector('#boundary-start-marker') as HTMLElement
        if (startMarker) {
          if (scrollableParent) {
            // Calculate position using getBoundingClientRect for accurate positioning
            const markerRect = startMarker.getBoundingClientRect()
            const parentRect = scrollableParent.getBoundingClientRect()
            const relativeTop = markerRect.top - parentRect.top + scrollableParent.scrollTop
            const parentHeight = scrollableParent.clientHeight
            // Center the marker in the viewport
            scrollableParent.scrollTop = relativeTop - (parentHeight / 2) + (markerRect.height / 2)
          } else {
            // Fallback to scrollIntoView if no scrollable parent found
            startMarker.scrollIntoView({ behavior: 'smooth', block: 'center' })
          }
        }
      }, 150)
    }
  }, [editMode, fullText, selectedStory])

  // Handle click on text to set boundary
  const handleTextClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!editMode || !fullText) return
    
    const charPos = calculateCharPositionFromClick(e, textContainerRef, fullText.length, {
      useIndexOfFallback: true
    })
    
    if (charPos === null) return
    
    if (selectingStart) {
      setEditedStart(charPos)
      setSelectingStart(false)
    } else {
      setEditedEnd(Math.max(charPos, editedStart))
      setSelectingStart(true)
    }
  }

  // Cancel boundary editing
  const handleCancelEdit = () => {
    if (selectedStory) {
      setEditedStart(selectedStory.start_char)
      setEditedEnd(selectedStory.end_char)
    }
    setEditMode(false)
    setFullText('')
  }

  const handleDeleteStory = async () => {
    if (!selectedStory) return
    
    const confirmDelete = confirm(`Are you sure you want to delete "${selectedStory.title}"?\n\nThis will remove it from:\n- Story positions (${selectedStory.book_slug})\n- Database\n- Document store\n- All category assignments\n- Pending queue (if present)\n\nThis action cannot be undone.`)
    
    if (!confirmDelete) return
    
    try {
      const res = await apiClient.delete(`/delete-story/${encodeURIComponent(selectedStory.title)}`)
      
      if (res.data.status === 'success') {
        alert(`Story "${selectedStory.title}" deleted successfully.`)
        
        // Remove from search results
        setResults(prev => prev.filter(r => r.title !== selectedStory.title))
        
        // Clear selected story
        setSelectedStory(null)
        setStoryContent('')
        
        // Refresh tree
        categoryAssignment.loadTree()
      }
    } catch (err: any) {
      console.error('Error deleting story:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to delete stories.')
      } else {
        const errorMsg = err.response?.data?.detail || 'Failed to delete story.'
        alert(errorMsg)
      }
    }
  }

  // Keywords editing now handled by keywordsEditor hook

  // Category assignment now handled by categoryAssignment hook

  // Save boundary changes (persist to backend)
  const handleSaveBoundaries = async () => {
    if (!selectedStory) return
    
    setLoading(true)
    try {
      // Check if user is authenticated (apiClient will automatically add token via interceptor)
      const user = await app.getUser()
      if (!user) {
        const shouldLogin = confirm('You must be logged in to save boundaries. Would you like to log in now?')
        if (shouldLogin) {
          // Save current location so we can return after login
          sessionStorage.setItem('returnTo', window.location.pathname + window.location.search)
          navigate('/login')
        }
        setLoading(false)
        return
      }
      
      // First, persist the boundaries to the backend (token added automatically by interceptor)
      await apiClient.post('/update-boundaries', {
        title: selectedStory.title,
        book_slug: selectedStory.book_slug,
        start_char: editedStart,
        end_char: editedEnd
      })
      
      // Update the selected story with new boundaries
      const updatedStory = {
        ...selectedStory,
        start_char: editedStart,
        end_char: editedEnd
      }
      setSelectedStory(updatedStory)
      
      // Reload the story view with new boundaries
      const res = await apiClient.post('/render-story', {
        title: selectedStory.title,
        mode: storyMode,
        search_query: selectedStory.search_query,
        start_char: editedStart,
        end_char: editedEnd
      })
      setStoryContent(res.data.html)
    } catch (err) {
      console.error('Error saving boundaries:', err)
      alert('Failed to save boundaries. Please try again.')
    } finally {
      setLoading(false)
      setEditMode(false)
      setFullText('')
    }
  }



  // Toggle between static and book context
  const handleToggleMode = async (mode: 'static' | 'book') => {
    if (!selectedStory) return
    
    setLoading(true)
    try {
      const res = await apiClient.post('/render-story', {
        title: selectedStory.title,
        mode: mode,
        search_query: selectedStory.search_query,
        start_char: selectedStory.start_char,
        end_char: selectedStory.end_char
      })
      setStoryContent(res.data.html)
      setStoryMode(mode)
      
      // Auto-scroll for book context mode
      if (mode === 'book') {
        setTimeout(() => {
          const wrapper = document.getElementById(`book-context-${selectedStory.title}`)
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
    } finally {
      setLoading(false)
    }
  }

  // Enter new story mode
  const handleEnterNewStoryMode = async () => {
    if (!selectedStory) return
    setEditMode(false) // Exit edit mode if active
    await newStoryCreator.startCreating(selectedStory.book_slug)
  }

  // New story text click handled by newStoryCreator.handleTextClick

  // Cancel and add new story handled by newStoryCreator.cancel() and newStoryCreator.addStory()

  return (
    <div className="flex h-screen h-[100dvh] max-h-screen max-w-[100vw] overflow-hidden bg-gray-900 text-white">
      {/* Sidebar Navigation */}
      <SidebarTree />
      
      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden min-w-0 max-w-full">
        {/* Left Panel - Search & Results */}
        <div className="w-[22vw] min-w-[260px] max-w-[350px] border-r border-gray-700 flex flex-col bg-gray-800 flex-shrink-0 overflow-hidden">
        <div className="p-3 border-b border-gray-700 flex-shrink-0">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-base font-semibold">Search & Curate</h2>
            <button
              onClick={() => setFiltersExpanded(!filtersExpanded)}
              className="text-xs text-gray-400 hover:text-white px-2 py-1 rounded bg-gray-700 hover:bg-gray-600"
            >
              {filtersExpanded ? 'Hide Filters' : 'Show Filters'}
            </button>
          </div>
          
          {/* Search Query - Always visible */}
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="Search stories..."
              className="flex-1 px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-sm text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSearch}
              disabled={searching || !query.trim()}
              className="px-3 py-1.5 bg-blue-600 text-white rounded text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {searching ? '...' : 'Go'}
            </button>
          </div>
          
          {/* Collapsible Filters */}
          {filtersExpanded && (
            <div className="mt-3 space-y-2">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium mb-1 text-gray-400">Source</label>
                  <select
                    value={sourceFilter}
                    onChange={(e) => setSourceFilter(e.target.value)}
                    className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    {sources.map((source) => (
                      <option key={source} value={source}>
                        {source}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium mb-1 text-gray-400">Type</label>
                  <select
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                    className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option>Both</option>
                    <option>Story</option>
                    <option>Non-Story</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium mb-1 text-gray-400">Search Mode</label>
                  <select
                    value={searchMode}
                    onChange={(e) => setSearchMode(e.target.value)}
                    className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="Both">Hybrid</option>
                    <option value="Keywords">Keywords</option>
                    <option value="Semantic">Semantic</option>
                    <option value="Exact">Exact</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium mb-1 text-gray-400">Assignment</label>
                  <select
                    value={assignmentFilter}
                    onChange={(e) => setAssignmentFilter(e.target.value)}
                    className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="all">All</option>
                    <option value="assigned">Assigned</option>
                    <option value="unassigned">Unassigned</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="block text-xs font-medium mb-1 text-gray-400">Category</label>
                  <select
                    value={categoryFilter}
                    onChange={(e) => {
                      setCategoryFilter(e.target.value)
                      setSubcategoryFilter('') // Reset subcategory when category changes
                    }}
                    className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500"
                  >
                    <option value="">All Categories</option>
                    {categories.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium mb-1 text-gray-400">Subcategory</label>
                  <select
                    value={subcategoryFilter}
                    onChange={(e) => setSubcategoryFilter(e.target.value)}
                    disabled={!categoryFilter}
                    className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <option value="">All Subcategories</option>
                    {categoryFilter && subcategories[categoryFilter]?.map((subcat) => (
                      <option key={subcat} value={subcat}>
                        {subcat}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium mb-1 text-gray-400">Min Score: {minScore.toFixed(2)}</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={minScore}
                  onChange={(e) => setMinScore(parseFloat(e.target.value))}
                  className="w-full h-1"
                />
              </div>
            </div>
          )}
        </div>

        {/* Results List */}
        <div className="flex-1 overflow-y-auto p-2">
          <div className="mb-1 text-xs text-gray-400 px-1">
            {results.length} {results.length === 1 ? 'story' : 'stories'} found
          </div>
          <div className="space-y-1">
            {results.map((result, idx) => (
              <button
                key={`${result.book_slug}-${result.title}-${idx}`}
                onClick={() => handleSelectStory(result)}
                className={`w-full text-left p-2 rounded border transition-colors ${
                  selectedStory?.title === result.title && selectedStory?.book_slug === result.book_slug
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-gray-700 border-gray-600 text-gray-200 hover:bg-gray-600'
                }`}
              >
                <div className="font-medium text-sm leading-tight">{result.title}</div>
                <div className="text-xs text-gray-400 mt-0.5 truncate">
                  {result.book_title || (result.book_slug ? result.book_slug.replace(/_/g, ' ') : 'Unknown Book')}
                </div>
                <div className="text-xs text-gray-500">
                  p.{result.pages} • {result.score.toFixed(2)}
                </div>
              </button>
            ))}
          </div>
          {results.length === 0 && !searching && (
            <div className="text-center text-gray-500 text-sm mt-4 px-2">
              {query ? 'No results found.' : 'Enter a query to search.'}
            </div>
          )}
        </div>
      </div>

      {/* Middle Panel - Story Viewer */}
      <div className="flex-1 flex flex-col bg-gray-900 min-w-0 overflow-hidden">
        <div className="p-4 border-b border-gray-700 flex-shrink-0">
          <h2 className="text-lg font-semibold">Story Viewer</h2>
          {selectedStory && !editMode && !newStoryCreator.isActive && (
            <div className="mt-2 flex gap-2 flex-wrap">
              <button
                onClick={() => handleToggleMode('static')}
                className={`px-4 py-2 rounded text-sm transition-colors ${
                  storyMode === 'static'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-200 hover:bg-gray-600'
                }`}
              >
                Static View
              </button>
              <button
                onClick={() => handleToggleMode('book')}
                className={`px-4 py-2 rounded text-sm transition-colors ${
                  storyMode === 'book'
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-200 hover:bg-gray-600'
                }`}
              >
                Book Context
              </button>
              <button
                onClick={handleAdjustBoundaries}
                className="px-4 py-2 rounded text-sm bg-green-600 text-white hover:bg-green-700 transition-colors"
              >
                Adjust Boundaries
              </button>
              <button
                onClick={handleEnterNewStoryMode}
                className="px-4 py-2 rounded text-sm bg-purple-600 text-white hover:bg-purple-700 transition-colors"
              >
                Add New Story
              </button>
              <button
                onClick={handleDeleteStory}
                className="px-4 py-2 rounded text-sm bg-red-600 text-white hover:bg-red-700 transition-colors"
              >
                Delete Story
              </button>
            </div>
          )}
          {editMode && (
            <div className="mt-2 space-y-2">
              <div className="text-sm text-gray-300">
                {selectingStart ? (
                  <span>Click to set <strong className="text-blue-400">START</strong> position</span>
                ) : (
                  <span>Click to set <strong className="text-red-400">END</strong> position</span>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleSaveBoundaries}
                  className="px-4 py-2 rounded text-sm bg-green-600 text-white hover:bg-green-700 transition-colors"
                >
                  Save Boundaries
                </button>
                <button
                  onClick={handleCancelEdit}
                  className="px-4 py-2 rounded text-sm bg-gray-700 text-gray-200 hover:bg-gray-600 transition-colors"
                >
                  Cancel
                </button>
              </div>
              <div className="text-xs text-gray-400">
                Start: {editedStart.toLocaleString()} | End: {editedEnd.toLocaleString()} | Length: {(editedEnd - editedStart).toLocaleString()} chars
              </div>
            </div>
          )}
          {newStoryCreator.isActive && (
            <div className="mt-2 space-y-3">
              <div className="text-sm text-gray-300">
                {newStoryCreator.selectingStart ? (
                  <span>Click to set <strong className="text-green-400">START</strong> position for new story</span>
                ) : (
                  <span>Click to set <strong className="text-yellow-400">END</strong> position for new story</span>
                )}
              </div>
              
              {/* Story Details Form */}
              <div className="grid grid-cols-1 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1 text-gray-300">Story Title *</label>
                  <input
                    type="text"
                    value={newStoryCreator.title}
                    onChange={(e) => newStoryCreator.setTitle(e.target.value)}
                    placeholder="Enter story title"
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1 text-gray-300">Keywords</label>
                  <input
                    type="text"
                    value={newStoryCreator.keywords}
                    onChange={(e) => newStoryCreator.setKeywords(e.target.value)}
                    placeholder="e.g., ghost, haunting, supernatural"
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1 text-gray-300">Pages</label>
                  <input
                    type="text"
                    value={newStoryCreator.pages}
                    onChange={(e) => newStoryCreator.setPages(e.target.value)}
                    placeholder="e.g., 45-52"
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              </div>
              
              <div className="flex gap-2">
                <button
                  onClick={() => newStoryCreator.addStory()}
                  disabled={!newStoryCreator.canAdd || newStoryCreator.adding}
                  className="px-4 py-2 rounded text-sm bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {newStoryCreator.adding ? 'Adding...' : 'Add Story'}
                </button>
                <button
                  onClick={newStoryCreator.cancel}
                  className="px-4 py-2 rounded text-sm bg-gray-700 text-gray-200 hover:bg-gray-600 transition-colors"
                >
                  Cancel
                </button>
              </div>
              
              {newStoryCreator.start !== null && newStoryCreator.end !== null && (
                <div className="text-xs text-gray-400">
                  Start: {newStoryCreator.start.toLocaleString()} | End: {newStoryCreator.end.toLocaleString()} | Length: {(newStoryCreator.end - newStoryCreator.start).toLocaleString()} chars
                </div>
              )}
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {loading && !editMode && !newStoryCreator.isActive ? (
            <div className="flex items-center justify-center h-full text-gray-400">
              Loading story...
            </div>
          ) : editMode && fullText ? (
            <div className="h-full">
              <div className="mb-4 p-3 bg-gray-800 rounded border border-gray-700">
                <div className="text-sm text-gray-300 mb-2">
                  <span className="inline-block w-32">Selected Range:</span>
                  <span className="text-blue-400">{editedStart.toLocaleString()}</span>
                  <span className="mx-2">to</span>
                  <span className="text-red-400">{editedEnd.toLocaleString()}</span>
                </div>
                <div className="text-xs text-gray-400">
                  Preview: {fullText.substring(editedStart, Math.min(editedStart + 100, editedEnd))}...
                </div>
              </div>
              <div
                ref={textContainerRef}
                onClick={handleTextClick}
                className="bg-gray-800 border border-gray-700 rounded p-4 cursor-text select-none font-mono text-sm leading-relaxed"
                style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
              >
                {fullText.substring(0, editedStart)}
                <span id="boundary-start-marker" className="bg-blue-600 bg-opacity-50 text-blue-200 px-1 rounded">
                  {fullText.substring(editedStart, editedEnd)}
                </span>
                <span className="bg-red-600 bg-opacity-30 text-red-200">
                  {fullText.substring(editedEnd)}
                </span>
              </div>
            </div>
          ) : newStoryCreator.isActive && newStoryCreator.fullText ? (
            <div className="h-full">
              {newStoryCreator.start !== null && newStoryCreator.end !== null && (
                <div className="mb-4 p-3 bg-gray-800 rounded border border-gray-700">
                  <div className="text-sm text-gray-300 mb-2">
                    <span className="inline-block w-32">New Story Range:</span>
                    <span className="text-green-400">{newStoryCreator.start.toLocaleString()}</span>
                    <span className="mx-2">to</span>
                    <span className="text-yellow-400">{newStoryCreator.end.toLocaleString()}</span>
                  </div>
                  <div className="text-xs text-gray-400">
                    Preview: {newStoryCreator.fullText.substring(newStoryCreator.start, Math.min(newStoryCreator.start + 100, newStoryCreator.end))}...
                  </div>
                </div>
              )}
              <div
                ref={newStoryCreator.textContainerRef}
                onClick={newStoryCreator.handleTextClick}
                className="bg-gray-800 border border-gray-700 rounded p-4 cursor-text select-none font-mono text-sm leading-relaxed"
                style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
              >
                {newStoryCreator.start !== null && newStoryCreator.end !== null ? (
                  <>
                    {newStoryCreator.fullText.substring(0, newStoryCreator.start)}
                    <span className="bg-green-600 bg-opacity-50 text-green-200 px-1 rounded">
                      {newStoryCreator.fullText.substring(newStoryCreator.start, newStoryCreator.end)}
                    </span>
                    <span className="bg-yellow-600 bg-opacity-30 text-yellow-200">
                      {newStoryCreator.fullText.substring(newStoryCreator.end)}
                    </span>
                  </>
                ) : newStoryCreator.start !== null ? (
                  <>
                    {newStoryCreator.fullText.substring(0, newStoryCreator.start)}
                    <span className="bg-green-600 bg-opacity-50 text-green-200 px-1 rounded">
                      {newStoryCreator.fullText.substring(newStoryCreator.start)}
                    </span>
                  </>
                ) : (
                  newStoryCreator.fullText
                )}
              </div>
            </div>
          ) : selectedStory ? (
            <div className="prose max-w-none prose-invert">
              <div
                id={`book-context-${selectedStory.title}`}
                dangerouslySetInnerHTML={{ __html: storyContent }}
              />
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              Select a story from the search results to view it here.
            </div>
          )}
        </div>
      </div>

      {/* Right Panel - Category Assignment */}
      <div className="w-[18vw] min-w-[220px] max-w-[300px] border-l border-gray-700 bg-gray-800 p-3 overflow-y-auto flex-shrink-0 hidden lg:block">
        <h2 className="text-base font-semibold mb-3">Story Details</h2>
        
        {!selectedStory ? (
          <div className="text-gray-500 text-xs">
            Select a story to view and edit details.
          </div>
        ) : (
          <div className="space-y-3">
            {/* Keywords Section */}
            <div>
              <h3 className="text-xs font-medium mb-1.5 text-gray-300">Keywords</h3>
              {keywordsEditor.isEditing ? (
                <div className="space-y-2">
                  <input
                    type="text"
                    value={keywordsEditor.editedKeywords}
                    onChange={(e) => keywordsEditor.setEditedKeywords(e.target.value)}
                    placeholder="e.g., ghost, haunting, supernatural"
                    className="w-full px-2 py-1.5 bg-gray-700 border border-gray-600 rounded text-white text-xs placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
                  />
                  <div className="flex gap-1">
                    <button
                      onClick={() => keywordsEditor.saveKeywords(selectedStory)}
                      disabled={keywordsEditor.saving}
                      className="flex-1 px-2 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {keywordsEditor.saving ? 'Saving...' : 'Save'}
                    </button>
                    <button
                      onClick={keywordsEditor.cancelEditing}
                      className="flex-1 px-2 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs text-gray-400 flex-1">
                    {selectedStory.keywords || <span className="italic">No keywords</span>}
                  </p>
                  <button
                    onClick={() => keywordsEditor.startEditing(selectedStory)}
                    className="px-2 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors flex-shrink-0"
                  >
                    Edit
                  </button>
                </div>
              )}
            </div>

            {/* Current Assignments */}
            <div>
              <h3 className="text-xs font-medium mb-1.5 text-gray-300">Category Assignments</h3>
              {categoryAssignment.currentAssignments.length === 0 ? (
                <div className="text-xs text-gray-500 italic">Not assigned</div>
              ) : (
                <div className="space-y-1">
                  {categoryAssignment.currentAssignments.map((path: string[], idx: number) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-1.5 bg-gray-700 rounded text-xs"
                    >
                      <span className="text-gray-200 truncate flex-1 mr-1">{path.join(' > ')}</span>
                      <button
                        onClick={() => categoryAssignment.removeCategory(path)}
                        disabled={categoryAssignment.assigning}
                        className="px-1.5 py-0.5 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {/* Assign to Category */}
            <div>
              <h3 className="text-xs font-medium mb-1.5 text-gray-300">Assign to Category</h3>
              
              {/* AI Suggested Categories */}
              {categoryAssignment.suggestedCategories.length > 0 && (
                <div className="mb-3">
                  <div className="flex items-center gap-1.5 mb-1.5">
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-3.5 w-3.5 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                    </svg>
                    <span className="text-xs text-gray-400">Suggested</span>
                  </div>
                  <div className="space-y-1">
                    {categoryAssignment.suggestedCategories.map((path, idx) => (
                      <button
                        key={idx}
                        onClick={() => categoryAssignment.assignToPath(path)}
                        disabled={categoryAssignment.assigning}
                        className="w-full text-left px-2 py-1.5 bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/30 rounded text-xs text-gray-200 hover:from-yellow-500/20 hover:to-orange-500/20 disabled:opacity-50 transition-colors"
                      >
                        {path.join(' → ')}
                      </button>
                    ))}
                  </div>
                  <div className="flex items-center gap-2 mt-2 text-gray-500 text-xs">
                    <div className="flex-1 h-px bg-gray-700"></div>
                    <span>or browse</span>
                    <div className="flex-1 h-px bg-gray-700"></div>
                  </div>
                </div>
              )}
              
              {/* Path Selection Dropdowns */}
              <div className="space-y-1.5 mb-2">
                {categoryAssignment.codexTree ? (
                  <>
                    {/* Level 1 */}
                    <select
                      value={categoryAssignment.selectedPath[0] || ''}
                      onChange={(e) => categoryAssignment.handlePathLevelChange(0, e.target.value)}
                      className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                    >
                      <option value="">Select category...</option>
                      {categoryAssignment.getPathOptions([]).map((option: string) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                    
                    {/* Level 2 */}
                    {categoryAssignment.selectedPath.length >= 1 && categoryAssignment.getPathOptions([categoryAssignment.selectedPath[0]]).length > 0 && (
                      <select
                        value={categoryAssignment.selectedPath[1] || ''}
                        onChange={(e) => categoryAssignment.handlePathLevelChange(1, e.target.value)}
                        className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        <option value="">Select subcategory...</option>
                        {categoryAssignment.getPathOptions([categoryAssignment.selectedPath[0]]).map((option: string) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    )}
                    
                    {/* Level 3 */}
                    {categoryAssignment.selectedPath.length >= 2 && categoryAssignment.getPathOptions([categoryAssignment.selectedPath[0], categoryAssignment.selectedPath[1]]).length > 0 && (
                      <select
                        value={categoryAssignment.selectedPath[2] || ''}
                        onChange={(e) => categoryAssignment.handlePathLevelChange(2, e.target.value)}
                        className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        <option value="">Select subcategory...</option>
                        {categoryAssignment.getPathOptions([categoryAssignment.selectedPath[0], categoryAssignment.selectedPath[1]]).map((option: string) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    )}
                    
                    {/* Level 4 */}
                    {categoryAssignment.selectedPath.length >= 3 && categoryAssignment.getPathOptions([categoryAssignment.selectedPath[0], categoryAssignment.selectedPath[1], categoryAssignment.selectedPath[2]]).length > 0 && (
                      <select
                        value={categoryAssignment.selectedPath[3] || ''}
                        onChange={(e) => categoryAssignment.handlePathLevelChange(3, e.target.value)}
                        className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        <option value="">Select subcategory...</option>
                        {categoryAssignment.getPathOptions([categoryAssignment.selectedPath[0], categoryAssignment.selectedPath[1], categoryAssignment.selectedPath[2]]).map((option: string) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    )}
                    
                    {/* Level 5 */}
                    {categoryAssignment.selectedPath.length >= 4 && categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 4)).length > 0 && (
                      <select
                        value={categoryAssignment.selectedPath[4] || ''}
                        onChange={(e) => categoryAssignment.handlePathLevelChange(4, e.target.value)}
                        className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        <option value="">Select subcategory...</option>
                        {categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 4)).map((option: string) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    )}
                    
                    {/* Level 6 */}
                    {categoryAssignment.selectedPath.length >= 5 && categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 5)).length > 0 && (
                      <select
                        value={categoryAssignment.selectedPath[5] || ''}
                        onChange={(e) => categoryAssignment.handlePathLevelChange(5, e.target.value)}
                        className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        <option value="">Select subcategory...</option>
                        {categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 5)).map((option: string) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    )}
                    
                    {/* Level 7 */}
                    {categoryAssignment.selectedPath.length >= 6 && categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 6)).length > 0 && (
                      <select
                        value={categoryAssignment.selectedPath[6] || ''}
                        onChange={(e) => categoryAssignment.handlePathLevelChange(6, e.target.value)}
                        className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        <option value="">Select subcategory...</option>
                        {categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 6)).map((option: string) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    )}
                    
                    {/* Level 8 */}
                    {categoryAssignment.selectedPath.length >= 7 && categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 7)).length > 0 && (
                      <select
                        value={categoryAssignment.selectedPath[7] || ''}
                        onChange={(e) => categoryAssignment.handlePathLevelChange(7, e.target.value)}
                        className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                      >
                        <option value="">Select subcategory...</option>
                        {categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 7)).map((option: string) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    )}
                  </>
                ) : (
                  <div className="text-xs text-gray-500">Loading categories...</div>
                )}
              </div>
              
              {/* Selected Path Display */}
              {categoryAssignment.selectedPath.length > 0 && (
                <div className="mb-2 p-1.5 bg-gray-700 rounded text-xs text-gray-300 truncate">
                  <span className="font-medium">{categoryAssignment.selectedPath.join(' > ')}</span>
                </div>
              )}
              
              {/* Assign Button */}
              <button
                onClick={categoryAssignment.assignCategory}
                disabled={categoryAssignment.selectedPath.length === 0 || categoryAssignment.assigning}
                className="w-full px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {categoryAssignment.assigning ? 'Assigning...' : 'Assign'}
              </button>
            </div>
          </div>
        )}
      </div>
      </div>
    </div>
  )
}

export default SearchCurate

