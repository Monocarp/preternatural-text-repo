// src/pages/SearchCurate.tsx
import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStackApp } from '@stackframe/react'
import apiClient from '../utils/axios'
import SidebarTree from '../components/SidebarTree'

interface SearchResult {
  title: string
  book_slug: string
  pages: string
  keywords: string
  start_char: number
  end_char: number
  score: number
  search_query?: string
}

const SearchCurate = () => {
  const navigate = useNavigate()
  const app = useStackApp()
  const [query, setQuery] = useState('')
  const [sourceFilter, setSourceFilter] = useState('All Sources')
  const [typeFilter, setTypeFilter] = useState('Both')
  const [searchMode, setSearchMode] = useState('Both')
  const [minScore, setMinScore] = useState(0.1)
  const [sources, setSources] = useState<string[]>(['All Sources'])
  const [results, setResults] = useState<SearchResult[]>([])
  const [selectedStory, setSelectedStory] = useState<SearchResult | null>(null)
  const [storyContent, setStoryContent] = useState<string>('')
  const [storyMode, setStoryMode] = useState<'static' | 'book'>('static')
  const [loading, setLoading] = useState(false)
  const [searching, setSearching] = useState(false)
  
  // Boundary editing state
  const [editMode, setEditMode] = useState(false)
  const [fullText, setFullText] = useState<string>('')
  const [editedStart, setEditedStart] = useState<number>(0)
  const [editedEnd, setEditedEnd] = useState<number>(0)
  const [selectingStart, setSelectingStart] = useState(true) // true = selecting start, false = selecting end
  const textContainerRef = useRef<HTMLDivElement>(null)
  
  // Category assignment state
  const [codexTree, setCodexTree] = useState<any>(null)
  const [selectedPath, setSelectedPath] = useState<string[]>([])
  const [currentAssignments, setCurrentAssignments] = useState<string[][]>([])
  const [assigning, setAssigning] = useState(false)

  // Load available sources and codex tree on mount
  useEffect(() => {
    apiClient.get('/sources')
      .then(res => {
        setSources(res.data.sources || ['All Sources'])
      })
      .catch(err => {
        console.error('Error loading sources:', err)
        setSources(['All Sources'])
      })
    
    apiClient.get('/get-tree')
      .then(res => {
        setCodexTree(res.data)
      })
      .catch(err => {
        console.error('Error loading codex tree:', err)
      })
  }, [])
  
  // Load current assignments when story is selected
  useEffect(() => {
    if (!selectedStory || !codexTree) {
      setCurrentAssignments([])
      return
    }
    
    // Find all paths where this story is assigned
    const findAssignments = (node: any, path: string[] = []): string[][] => {
      const assignments: string[][] = []
      
      if (typeof node === 'object' && node !== null) {
        // Check if this node has stories
        if (Array.isArray(node)) {
          if (node.includes(selectedStory.title)) {
            assignments.push([...path])
          }
        } else if (node._stories && Array.isArray(node._stories)) {
          if (node._stories.includes(selectedStory.title)) {
            assignments.push([...path])
          }
        }
        
        // Recursively check children
        for (const [key, value] of Object.entries(node)) {
          if (key !== '_stories') {
            assignments.push(...findAssignments(value, [...path, key]))
          }
        }
      }
      
      return assignments
    }
    
    const assignments = findAssignments(codexTree)
    setCurrentAssignments(assignments)
  }, [selectedStory, codexTree])

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
        min_score: minScore
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
    if (!editMode || !fullText || !textContainerRef.current) return
    
    e.preventDefault()
    const textContainer = textContainerRef.current
    const clickX = e.clientX
    const clickY = e.clientY
    
    // Create a range at the click point
    const range = document.caretRangeFromPoint?.(clickX, clickY)
    if (!range) return
    
    // Calculate character position by walking through text nodes
    let charPos = 0
    const walker = document.createTreeWalker(
      textContainer,
      NodeFilter.SHOW_TEXT,
      null
    )
    
    let node: Node | null
    while ((node = walker.nextNode())) {
      const textNode = node as Text
      if (range.startContainer === textNode) {
        charPos += range.startOffset
        break
      } else if (range.startContainer.contains?.(textNode) || textNode.contains?.(range.startContainer)) {
        // If the range is within this text node's parent, calculate offset
        if (range.startContainer.nodeType === Node.TEXT_NODE) {
          const rangeText = (range.startContainer as Text).textContent || ''
          const beforeRange = textContainer.textContent?.indexOf(rangeText, charPos) || charPos
          charPos = beforeRange + range.startOffset
        } else {
          charPos += textNode.textContent?.length || 0
        }
        break
      } else {
        charPos += textNode.textContent?.length || 0
      }
    }
    
    // Fallback: use textContent if walker didn't find it
    if (charPos === 0 && range.startContainer.nodeType === Node.TEXT_NODE) {
      const allText = textContainer.textContent || ''
      const clickedText = (range.startContainer as Text).textContent || ''
      const index = allText.indexOf(clickedText)
      if (index !== -1) {
        charPos = index + range.startOffset
      }
    }
    
    // Ensure valid range
    charPos = Math.min(Math.max(0, charPos), fullText.length)
    
    if (selectingStart) {
      setEditedStart(charPos)
      setSelectingStart(false) // Switch to selecting end
    } else {
      // Ensure end is after start
      setEditedEnd(Math.max(charPos, editedStart))
      setSelectingStart(true) // Switch back to selecting start for next click
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
  
  // Handle category assignment
  const handleAssignCategory = async () => {
    if (!selectedStory || selectedPath.length === 0) return
    
    setAssigning(true)
    try {
      await apiClient.post('/assign-category', {
        path: selectedPath,
        story: {
          title: selectedStory.title,
          book_slug: selectedStory.book_slug,
          pages: selectedStory.pages,
          keywords: selectedStory.keywords,
          start_char: selectedStory.start_char,
          end_char: selectedStory.end_char
        }
      })
      
      // Reload tree to get updated assignments
      const treeRes = await apiClient.get('/get-tree')
      setCodexTree(treeRes.data)
      
      const assignedPath = selectedPath.join(' > ')
      // Clear selected path
      setSelectedPath([])
      
      // Force re-check of assignments by triggering useEffect
      // The useEffect will run automatically when codexTree changes
      
      alert(`Story assigned to ${assignedPath}`)
    } catch (err: any) {
      console.error('Error assigning category:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to assign categories.')
      } else {
        alert('Failed to assign category. Please try again.')
      }
    } finally {
      setAssigning(false)
    }
  }
  
  // Handle category removal
  const handleRemoveCategory = async (path: string[]) => {
    if (!selectedStory) return
    
    if (!confirm(`Remove "${selectedStory.title}" from ${path.join(' > ')}?`)) {
      return
    }
    
    setAssigning(true)
    try {
      await apiClient.delete('/remove-category', {
        data: {
          path: path,
          title: selectedStory.title
        }
      })
      
      // Reload tree to get updated assignments
      const treeRes = await apiClient.get('/get-tree')
      setCodexTree(treeRes.data)
      
      alert(`Story removed from ${path.join(' > ')}`)
    } catch (err: any) {
      console.error('Error removing category:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to remove categories.')
      } else {
        alert('Failed to remove category. Please try again.')
      }
    } finally {
      setAssigning(false)
    }
  }
  
  // Helper function to get nested options for path selection
  const getPathOptions = (tree: any, currentPath: string[] = []): string[] => {
    if (!tree || typeof tree !== 'object') return []
    
    let node = tree
    for (const level of currentPath) {
      if (node[level]) {
        node = node[level]
      } else {
        return []
      }
    }
    
    // Get keys that are not _stories
    return Object.keys(node).filter(key => key !== '_stories')
  }
  
  // Handle path level selection
  const handlePathLevelChange = (level: number, value: string) => {
    const newPath = selectedPath.slice(0, level)
    if (value) {
      newPath.push(value)
    }
    setSelectedPath(newPath)
  }

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

  return (
    <div className="flex h-screen bg-gray-900 text-white">
      {/* Sidebar Navigation */}
      <SidebarTree />
      
      {/* Main Content Area */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Panel - Search & Results */}
        <div className="w-80 border-r border-gray-700 flex flex-col bg-gray-800">
        <div className="p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold mb-4">Search & Curate</h2>
          
          {/* Search Form */}
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium mb-1">Search Query</label>
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="e.g., demonic possession"
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Source</label>
              <select
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {sources.map((source) => (
                  <option key={source} value={source}>
                    {source}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Type</label>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option>Both</option>
                <option>Story</option>
                <option>Non-Story</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Search Mode</label>
              <select
                value={searchMode}
                onChange={(e) => setSearchMode(e.target.value)}
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="Both">Both (Hybrid)</option>
                <option value="Keywords">Keywords (Exact/Phrase Matches)</option>
                <option value="Semantic">Semantic (Conceptual Similarity)</option>
                <option value="Exact">Exact (Word/Phrase)</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1">Min Score: {minScore.toFixed(2)}</label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={minScore}
                onChange={(e) => setMinScore(parseFloat(e.target.value))}
                className="w-full"
              />
            </div>

            <button
              onClick={handleSearch}
              disabled={searching || !query.trim()}
              className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {searching ? 'Searching...' : 'Search'}
            </button>
          </div>
        </div>

        {/* Results List */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="mb-2 text-sm text-gray-400">
            {results.length} {results.length === 1 ? 'story' : 'stories'} found
          </div>
          <div className="space-y-2">
            {results.map((result, idx) => (
              <button
                key={idx}
                onClick={() => handleSelectStory(result)}
                className={`w-full text-left p-3 rounded border transition-colors ${
                  selectedStory?.title === result.title
                    ? 'bg-blue-600 border-blue-500 text-white'
                    : 'bg-gray-700 border-gray-600 text-gray-200 hover:bg-gray-600'
                }`}
              >
                <div className="font-medium text-sm">{result.title}</div>
                <div className="text-xs text-gray-400 mt-1">
                  {result.book_slug} • Score: {result.score.toFixed(3)}
                </div>
                {result.pages && (
                  <div className="text-xs text-gray-400">Pages: {result.pages}</div>
                )}
              </button>
            ))}
          </div>
          {results.length === 0 && !searching && (
            <div className="text-center text-gray-500 mt-8">
              {query ? 'No results found. Try a different query.' : 'Enter a search query to begin.'}
            </div>
          )}
        </div>
      </div>

      {/* Middle Panel - Story Viewer */}
      <div className="flex-1 flex flex-col bg-gray-900">
        <div className="p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold">Story Viewer</h2>
          {selectedStory && !editMode && (
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
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {loading && !editMode ? (
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
      <div className="w-80 border-l border-gray-700 bg-gray-800 p-4 overflow-y-auto">
        <h2 className="text-lg font-semibold mb-4">Category Assignment</h2>
        
        {!selectedStory ? (
          <div className="text-gray-500 text-sm">
            Select a story from the search results to assign it to a category.
          </div>
        ) : (
          <div className="space-y-4">
            {/* Current Assignments */}
            <div>
              <h3 className="text-sm font-medium mb-2 text-gray-300">Current Assignments</h3>
              {currentAssignments.length === 0 ? (
                <div className="text-sm text-gray-500 italic">Not assigned to any category</div>
              ) : (
                <div className="space-y-2">
                  {currentAssignments.map((path, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-2 bg-gray-700 rounded text-sm"
                    >
                      <span className="text-gray-200">{path.join(' > ')}</span>
                      <button
                        onClick={() => handleRemoveCategory(path)}
                        disabled={assigning}
                        className="px-2 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                      >
                        Remove
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
            
            {/* Assign to Category */}
            <div>
              <h3 className="text-sm font-medium mb-2 text-gray-300">Assign to Category</h3>
              
              {/* Path Selection Dropdowns */}
              <div className="space-y-2 mb-3">
                {codexTree ? (
                  <>
                    {/* Level 1 */}
                    <select
                      value={selectedPath[0] || ''}
                      onChange={(e) => handlePathLevelChange(0, e.target.value)}
                      className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="">Select category...</option>
                      {getPathOptions(codexTree, []).map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                    
                    {/* Level 2 */}
                    {selectedPath.length >= 1 && getPathOptions(codexTree, [selectedPath[0]]).length > 0 && (
                      <select
                        value={selectedPath[1] || ''}
                        onChange={(e) => handlePathLevelChange(1, e.target.value)}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">Select subcategory...</option>
                        {getPathOptions(codexTree, [selectedPath[0]]).map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    )}
                    
                    {/* Level 3 */}
                    {selectedPath.length >= 2 && getPathOptions(codexTree, [selectedPath[0], selectedPath[1]]).length > 0 && (
                      <select
                        value={selectedPath[2] || ''}
                        onChange={(e) => handlePathLevelChange(2, e.target.value)}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">Select subcategory...</option>
                        {getPathOptions(codexTree, [selectedPath[0], selectedPath[1]]).map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    )}
                    
                    {/* Level 4 */}
                    {selectedPath.length >= 3 && getPathOptions(codexTree, [selectedPath[0], selectedPath[1], selectedPath[2]]).length > 0 && (
                      <select
                        value={selectedPath[3] || ''}
                        onChange={(e) => handlePathLevelChange(3, e.target.value)}
                        className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">Select subcategory...</option>
                        {getPathOptions(codexTree, [selectedPath[0], selectedPath[1], selectedPath[2]]).map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    )}
                  </>
                ) : (
                  <div className="text-sm text-gray-500">Loading categories...</div>
                )}
              </div>
              
              {/* Selected Path Display */}
              {selectedPath.length > 0 && (
                <div className="mb-3 p-2 bg-gray-700 rounded text-sm text-gray-300">
                  Selected: <span className="font-medium">{selectedPath.join(' > ')}</span>
                </div>
              )}
              
              {/* Assign Button */}
              <button
                onClick={handleAssignCategory}
                disabled={selectedPath.length === 0 || assigning}
                className="w-full px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {assigning ? 'Assigning...' : 'Assign to Category'}
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

