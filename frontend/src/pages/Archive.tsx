// src/pages/Archive.tsx
import { useEffect, useMemo, useState, useRef } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/react'
import axios from 'axios'
import { useStore } from '../store'
import SidebarTree from '../components/SidebarTree'
import { decodeRoutePath, encodePathSegmentsForRoute } from '../utils/path'
import { useStackApp } from '@stackframe/react'

const Archive = () => {
  const location = useLocation()
  const { path = '' } = useParams<{ path?: string }>()
  const navigate = useNavigate()
  const app = useStackApp()
  
  // Extract path from location.pathname to ensure we detect URL changes
  // React Router's :path* might not trigger useParams updates properly
  const pathFromLocation = useMemo(() => {
    const match = location.pathname.match(/^\/archive\/(.+)$/)
    return match ? match[1] : ''
  }, [location.pathname])
  const { stories, loadStories, loading, error } = useStore()
  const [storyContents, setStoryContents] = useState<Record<string, string>>({})
  const [storyModes, setStoryModes] = useState<Record<string, 'static' | 'book'>>({})
  const [editingTitle, setEditingTitle] = useState<string | null>(null)
  const [newTitle, setNewTitle] = useState('')

  // New story mode state
  const [newStoryMode, setNewStoryMode] = useState(false)
  const [newStoryBookSlug, setNewStoryBookSlug] = useState<string>('')
  const [newStoryStart, setNewStoryStart] = useState<number | null>(null)
  const [newStoryEnd, setNewStoryEnd] = useState<number | null>(null)
  const [newStorySelectingStart, setNewStorySelectingStart] = useState(true)
  const [newStoryTitle, setNewStoryTitle] = useState('')
  const [newStoryKeywords, setNewStoryKeywords] = useState('')
  const [newStoryPages, setNewStoryPages] = useState('')
  const [addingStory, setAddingStory] = useState(false)
  const [fullText, setFullText] = useState<string>('')
  const textContainerRef = useRef<HTMLDivElement>(null)

  const decodedPath = useMemo(() => {
    // Use pathFromLocation instead of useParams path - React Router's :path* doesn't update reliably
    const pathToUse = pathFromLocation || path
    console.log('Archive: location.pathname =', location.pathname)
    console.log('Archive: pathFromLocation =', pathFromLocation)
    console.log('Archive: path param from useParams =', path)
    console.log('Archive: using path =', pathToUse)
    const decoded = decodeRoutePath(pathToUse)
    console.log('Archive: decoded path segments =', decoded)
    console.log('Archive: decoded length =', decoded.length)
    return decoded
  }, [pathFromLocation, path, location.pathname])
  const isUnassigned =
    decodedPath.length === 1 && decodedPath[0].toLowerCase() === 'unassigned'

  // Load stories based on URL path
  useEffect(() => {
    if (isUnassigned) {
      // Load unassigned stories
      axios.get('/api/get-unassigned')
        .then(res => {
          useStore.getState().setStories(res.data)
          useStore.getState().selectedPath = ['unassigned']
        })
        .catch(err => console.error('Error loading unassigned:', err))
    } else if (decodedPath.length > 0) {
      // Load stories for the category path (only if we have a path)
      loadStories(decodedPath)
    } else {
      // Root archive - don't load stories, just show empty state
      useStore.getState().setStories([])
      useStore.getState().selectedPath = []
    }
  }, [decodedPath, isUnassigned, loadStories, location.pathname])

  // Handle title editing
  const handleEditTitle = (story: any) => {
    setEditingTitle(story.title)
    setNewTitle(story.title)
  }

  const handleSaveTitle = async (story: any) => {
    if (!newTitle.trim() || newTitle === story.title) {
      setEditingTitle(null)
      return
    }

    // Check if title already exists in this book
    const existingStory = stories.find(s => 
      s.title.toLowerCase() === newTitle.trim().toLowerCase() && 
      s.book_slug === story.book_slug && 
      s.title !== story.title
    )
    if (existingStory) {
      alert('A story with this title already exists in this book.')
      return
    }

    try {
      const user = await app.getUser()
      if (!user) {
        alert('You must be logged in to edit titles.')
        return
      }

      await axios.post('/api/update-title', {
        old_title: story.title,
        new_title: newTitle.trim(),
        book_slug: story.book_slug
      })

      // Update the story in the store
      const updatedStories = stories.map(s => 
        s.title === story.title ? { ...s, title: newTitle.trim() } : s
      )
      useStore.getState().setStories(updatedStories)

      // Update story contents key
      if (storyContents[story.title]) {
        setStoryContents(prev => {
          const updated = { ...prev }
          delete updated[story.title]
          updated[newTitle.trim()] = prev[story.title]
          return updated
        })
      }

      // Update story modes key
      if (storyModes[story.title]) {
        setStoryModes(prev => {
          const updated = { ...prev }
          delete updated[story.title]
          updated[newTitle.trim()] = prev[story.title]
          return updated
        })
      }

      setEditingTitle(null)
      setNewTitle('')
    } catch (err: any) {
      console.error('Error updating title:', err)
      alert('Failed to update title. Please try again.')
    }
  }

  const handleCancelEdit = () => {
    setEditingTitle(null)
    setNewTitle('')
  }

  // Delete story
  const handleDeleteStory = async (story: any) => {
    const confirmDelete = confirm(`Are you sure you want to delete "${story.title}"?\n\nThis will remove it from:\n- Story positions (${story.book_slug})\n- Database\n- Document store\n- All category assignments\n- Pending queue (if present)\n\nThis action cannot be undone.`)
    
    if (!confirmDelete) return
    
    try {
      const user = await app.getUser()
      if (!user) {
        alert('You must be logged in to delete stories.')
        return
      }
      
      const token = await app.getAuthJson()
      const accessToken = token?.accessToken
      
      const res = await axios.delete(`/api/delete-story/${encodeURIComponent(story.title)}`, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      })
      
      if (res.data.status === 'success') {
        alert(`Story "${story.title}" deleted successfully.`)
        
        // Refresh the current view
        if (isUnassigned) {
          const unassignedRes = await axios.get('/api/get-unassigned')
          useStore.getState().setStories(unassignedRes.data)
        } else if (decodedPath.length > 0) {
          loadStories(decodedPath)
        }
        
        // Clear story content from state
        setStoryContents(prev => {
          const updated = { ...prev }
          delete updated[story.title]
          return updated
        })
        setStoryModes(prev => {
          const updated = { ...prev }
          delete updated[story.title]
          return updated
        })
        
        // Notify pending badge to refresh
        window.dispatchEvent(new Event('pendingStoriesChanged'))
      }
    } catch (err: any) {
      console.error('Error deleting story:', err)
      const errorMsg = err.response?.data?.detail || 'Failed to delete story.'
      alert(errorMsg)
    }
  }

  // Load story content when toggling modes
  const handleToggleMode = async (story: any, mode: 'static' | 'book') => {
    try {
      const res = await axios.post('/api/render-story', {
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
      useStore.getState().selectStory({ ...story, html: res.data.html, mode })
      
      // Auto-scroll to story position in book context mode
      if (mode === 'book') {
        // Wait for DOM to update, then scroll within the scrollable container
        setTimeout(() => {
          const wrapper = document.getElementById(`book-context-${story.title}`)
          const container = wrapper?.querySelector('#book-context-container') as HTMLElement
          const highlight = container?.querySelector('#story-highlight') as HTMLElement
          
          if (container && highlight) {
            // Calculate the position of the highlight relative to the container
            const highlightTop = highlight.offsetTop
            const containerHeight = container.clientHeight
            // Scroll to center the highlight in the container
            container.scrollTop = highlightTop - (containerHeight / 2) + (highlight.offsetHeight / 2)
          }
        }, 150)
      }
    } catch (err) {
      console.error('Error loading story:', err)
    }
  }

  // Enter new story mode
  const handleEnterNewStoryMode = async (bookSlug: string) => {
    setNewStoryMode(true)
    setNewStoryBookSlug(bookSlug)
    setEditingTitle(null) // Exit title editing if active
    try {
      // Load full text for the book
      const res = await axios.get(`/api/full-text/${bookSlug}`)
      setFullText(res.data.text)
      setNewStoryStart(null)
      setNewStoryEnd(null)
      setNewStorySelectingStart(true)
      setNewStoryTitle('')
      setNewStoryKeywords('')
      setNewStoryPages('')
    } catch (err) {
      console.error('Error loading full text:', err)
      setNewStoryMode(false)
    }
  }

  // Handle text click for new story selection
  const handleNewStoryTextClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!newStoryMode || !fullText || !textContainerRef.current) return
    
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
    
    if (newStorySelectingStart) {
      setNewStoryStart(charPos)
      setNewStorySelectingStart(false) // Switch to selecting end
    } else {
      // Ensure end is after start
      setNewStoryEnd(Math.max(charPos, newStoryStart || 0))
      setNewStorySelectingStart(true) // Switch back to selecting start for next click
    }
  }

  // Cancel new story mode
  const handleCancelNewStory = () => {
    setNewStoryMode(false)
    setFullText('')
    setNewStoryBookSlug('')
    setNewStoryStart(null)
    setNewStoryEnd(null)
    setNewStoryTitle('')
    setNewStoryKeywords('')
    setNewStoryPages('')
  }

  // Add new story
  const handleAddNewStory = async () => {
    if (!newStoryBookSlug || newStoryStart === null || newStoryEnd === null || !newStoryTitle.trim()) return
    
    if (!confirm(`Add new story "${newStoryTitle}" to ${newStoryBookSlug.replace(/_/g, ' ')}?`)) {
      return
    }
    
    setAddingStory(true)
    try {
      const response = await axios.post('/api/add-story', {
        book_slug: newStoryBookSlug,
        title: newStoryTitle.trim(),
        keywords: newStoryKeywords.trim(),
        pages: newStoryPages.trim(),
        start_char: newStoryStart,
        end_char: newStoryEnd
      })
      
      console.log('Add story response:', response.data)
      
      // Check if overlap warning was returned
      if (response.data?.status === 'overlap_warning') {
        const overlaps = response.data.overlaps || []
        const overlapMsg = overlaps.map((o: any) => `  • ${o.title} (${o.overlap_percent}% overlap)`).join('\n')
        const confirmMsg = `Warning: This story overlaps with existing stories:\n\n${overlapMsg}\n\nAdd anyway?`
        
        if (!confirm(confirmMsg)) {
          setAddingStory(false)
          return
        }
        
        // Retry with force_overlap flag
        const retryResponse = await axios.post('/api/add-story', {
          book_slug: newStoryBookSlug,
          title: newStoryTitle.trim(),
          keywords: newStoryKeywords.trim(),
          pages: newStoryPages.trim(),
          start_char: newStoryStart,
          end_char: newStoryEnd,
          force_overlap: true
        })
        
        const pendingCount = retryResponse.data?.pending_count || 1
        alert(`Story "${newStoryTitle}" added successfully! ${pendingCount} stories pending reindexing.`)
      } else {
        // Success - no overlaps
        const pendingCount = response.data?.pending_count || 1
        alert(`Story "${newStoryTitle}" added successfully! ${pendingCount} stories pending reindexing.`)
      }
      
      // Trigger a custom event to notify PendingStoriesBadge to refresh
      window.dispatchEvent(new CustomEvent('pendingStoriesChanged'))
      
      // Exit new story mode
      setNewStoryMode(false)
      setFullText('')
      setNewStoryBookSlug('')
      setNewStoryStart(null)
      setNewStoryEnd(null)
      setNewStoryTitle('')
      setNewStoryKeywords('')
      setNewStoryPages('')
      
      // Reload stories to include the new one (though it won't be immediately searchable)
      if (isUnassigned) {
        axios.get('/api/get-unassigned')
          .then(res => {
            useStore.getState().setStories(res.data)
          })
          .catch(err => console.error('Error reloading unassigned:', err))
      } else if (decodedPath.length > 0) {
        loadStories(decodedPath)
      }
    } catch (err: any) {
      console.error('Error adding story:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to add stories.')
      } else if (status === 409) {
        alert('This story overlaps with an existing story. Please adjust the boundaries.')
      } else {
        alert('Failed to add story. Please try again.')
      }
    } finally {
      setAddingStory(false)
    }
  }

  // Load static view when story panel is opened
  const handleStoryOpen = async (story: any) => {
    // Only load if we don't already have content for this story
    if (!storyContents[story.title]) {
      await handleToggleMode(story, 'static')
    }
  }

  // Get page title from path
  const getPageTitle = () => {
    if (decodedPath.length === 0) return 'Story Archive'
    if (isUnassigned) return 'Unassigned Stories'
    return decodedPath[decodedPath.length - 1]
  }

  // Get breadcrumb path
  const getBreadcrumb = () => {
    if (decodedPath.length === 0) return ['Story Archive']
    if (isUnassigned) return ['Story Archive', 'Unassigned']
    return ['Story Archive', ...decodedPath]
  }

  return (
    <div className="flex h-screen">
      <SidebarTree />
      <main className="flex-1 overflow-y-auto bg-gray-900">
        <div className="max-w-4xl mx-auto px-6 py-6">
          <div className="mb-6">
            <nav className="text-sm text-gray-400 mb-2 text-center">
              {getBreadcrumb().map((part, idx) => (
                <span key={idx}>
                  {idx > 0 && ' > '}
                  <button
                    onClick={() => {
                      if (idx === 0) {
                        navigate('/archive')
                      } else {
                        // idx 1 = first category (decodedPath[0]), idx 2 = second category (decodedPath[0:2]), etc.
                        const targetSegments = decodedPath.slice(0, idx)
                        if (targetSegments.length > 0) {
                          const encoded = encodePathSegmentsForRoute(targetSegments)
                          navigate(`/archive/${encoded}`)
                        } else {
                          navigate('/archive')
                        }
                      }
                    }}
                    className="hover:text-blue-400"
                  >
                    {part}
                  </button>
                </span>
              ))}
            </nav>
            <h1 className="text-3xl font-bold text-white text-center">{getPageTitle()}</h1>
            {stories.length > 0 && (
              <p className="text-gray-300 mt-2 text-center">{stories.length} {stories.length === 1 ? 'story' : 'stories'}</p>
            )}
          </div>

          {newStoryMode && (
            <div className="mb-6 p-4 bg-gray-800 rounded-lg border border-purple-700">
              <div className="text-center mb-4">
                <h2 className="text-xl font-semibold text-white mb-2">Add New Story</h2>
                <p className="text-gray-300">Adding to: <span className="font-medium text-purple-400">{newStoryBookSlug.replace(/_/g, ' ')}</span></p>
              </div>
              
              <div className="text-sm text-gray-300 mb-4 text-center">
                {newStorySelectingStart ? (
                  <span>Click to set <strong className="text-green-400">START</strong> position for new story</span>
                ) : (
                  <span>Click to set <strong className="text-yellow-400">END</strong> position for new story</span>
                )}
              </div>
              
              {/* Story Details Form */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div>
                  <label className="block text-sm font-medium mb-1 text-gray-300">Story Title *</label>
                  <input
                    type="text"
                    value={newStoryTitle}
                    onChange={(e) => setNewStoryTitle(e.target.value)}
                    placeholder="Enter story title"
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1 text-gray-300">Keywords</label>
                  <input
                    type="text"
                    value={newStoryKeywords}
                    onChange={(e) => setNewStoryKeywords(e.target.value)}
                    placeholder="e.g., ghost, haunting, supernatural"
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1 text-gray-300">Pages</label>
                  <input
                    type="text"
                    value={newStoryPages}
                    onChange={(e) => setNewStoryPages(e.target.value)}
                    placeholder="e.g., 45-52"
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>
              </div>
              
              <div className="flex justify-center gap-2 mb-4">
                <button
                  onClick={handleAddNewStory}
                  disabled={!newStoryTitle.trim() || newStoryStart === null || newStoryEnd === null || addingStory}
                  className="px-6 py-2 rounded text-sm bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {addingStory ? 'Adding...' : 'Add Story'}
                </button>
                <button
                  onClick={handleCancelNewStory}
                  className="px-6 py-2 rounded text-sm bg-gray-700 text-gray-200 hover:bg-gray-600 transition-colors"
                >
                  Cancel
                </button>
              </div>
              
              {newStoryStart !== null && newStoryEnd !== null && (
                <div className="text-xs text-gray-400 text-center">
                  Start: {newStoryStart.toLocaleString()} | End: {newStoryEnd.toLocaleString()} | Length: {(newStoryEnd - newStoryStart).toLocaleString()} chars
                </div>
              )}
            </div>
          )}

        {loading && (
          <div className="text-center py-8">
            <p className="text-gray-400">Loading stories...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-900 border border-red-700 rounded p-4 mb-4 text-center">
            <p className="text-red-200">Error: {error}</p>
          </div>
        )}

        {!loading && !error && stories.length === 0 && (
          <div className="text-center py-8">
            <p className="text-gray-400">No stories found in this category.</p>
          </div>
        )}

          {!loading && stories.length > 0 && (
            <div className="space-y-3">
            {stories.map((story: any, index: number) => {
              const currentMode = storyModes[story.title] || 'static'
              const storyContent = storyContents[story.title]
              
              return (
                <Disclosure 
                  key={`${story.book_slug}-${story.title}-${index}`} 
                  as="div" 
                  className="border border-gray-700 rounded-lg shadow-sm hover:shadow-md transition-shadow bg-gray-800 relative"
                >
                  <DisclosureButton 
                    className="w-full p-4 hover:bg-gray-700"
                    onClick={() => handleStoryOpen(story)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 text-center pr-8">
                        {editingTitle === story.title ? (
                          <div className="flex items-center justify-center gap-2" onClick={(e) => e.stopPropagation()}>
                            <input
                              type="text"
                              value={newTitle}
                              onChange={(e) => setNewTitle(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') handleSaveTitle(story)
                                if (e.key === 'Escape') handleCancelEdit()
                                e.stopPropagation()
                              }}
                              onClick={(e) => e.stopPropagation()}
                              className="flex-1 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-lg font-semibold"
                              autoFocus
                              placeholder="Press Enter to save, Escape to cancel"
                            />
                          </div>
                        ) : (
                          <h3 className="text-lg font-semibold text-white">{story.title}</h3>
                        )}
                        <div className="mt-1 text-sm text-gray-400">
                          <span className="font-medium">{story.book_title || story.book_slug.replace(/_/g, ' ')}</span>
                          {story.book_author && <span className="ml-2">• {story.book_author}</span>}
                          {story.book_year && <span className="ml-2">({story.book_year})</span>}
                        </div>
                        <div className="mt-0.5 text-xs text-gray-500">
                          {story.pages && <span>Pages: {story.pages}</span>}
                          {story.keywords && <span className="ml-2">• Keywords: {story.keywords}</span>}
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
                        <div className="text-gray-400 text-center py-4">Loading story...</div>
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
                        <button
                          onClick={() => handleEnterNewStoryMode(story.book_slug)}
                          className="px-4 py-2 rounded text-sm bg-purple-600 text-white hover:bg-purple-700"
                        >
                          Add New Story
                        </button>
                        {editingTitle === story.title ? (
                          <>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleSaveTitle(story) }}
                              className="px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700 text-sm"
                            >
                              Save
                            </button>
                            <button
                              onClick={(e) => { e.stopPropagation(); handleCancelEdit() }}
                              className="px-2 py-1 bg-gray-600 text-white rounded hover:bg-gray-700 text-sm"
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleEditTitle(story) }}
                            className="px-2 py-1 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                          >
                            Edit Title
                          </button>
                        )}
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDeleteStory(story) }}
                          className="px-4 py-2 rounded text-sm bg-red-600 text-white hover:bg-red-700"
                        >
                          Delete Story
                        </button>
                      </div>
                    </div>
                  </DisclosurePanel>
                </Disclosure>
              )
            })}
          </div>
        )}

          {newStoryMode && fullText && (
            <div className="mt-6">
              {newStoryStart !== null && newStoryEnd !== null && (
                <div className="mb-4 p-3 bg-gray-800 rounded border border-gray-700">
                  <div className="text-sm text-gray-300 mb-2">
                    <span className="inline-block w-32">New Story Range:</span>
                    <span className="text-green-400">{newStoryStart.toLocaleString()}</span>
                    <span className="mx-2">to</span>
                    <span className="text-yellow-400">{newStoryEnd.toLocaleString()}</span>
                  </div>
                  <div className="text-xs text-gray-400">
                    Preview: {fullText.substring(newStoryStart, Math.min(newStoryStart + 100, newStoryEnd))}...
                  </div>
                </div>
              )}
              <div
                ref={textContainerRef}
                onClick={handleNewStoryTextClick}
                className="bg-gray-800 border border-gray-700 rounded p-4 cursor-text select-none font-mono text-sm leading-relaxed max-h-96 overflow-y-auto"
                style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
              >
                {newStoryStart !== null && newStoryEnd !== null ? (
                  <>
                    {fullText.substring(0, newStoryStart)}
                    <span className="bg-green-600 bg-opacity-50 text-green-200 px-1 rounded">
                      {fullText.substring(newStoryStart, newStoryEnd)}
                    </span>
                    <span className="bg-yellow-600 bg-opacity-30 text-yellow-200">
                      {fullText.substring(newStoryEnd)}
                    </span>
                  </>
                ) : newStoryStart !== null ? (
                  <>
                    {fullText.substring(0, newStoryStart)}
                    <span className="bg-green-600 bg-opacity-50 text-green-200 px-1 rounded">
                      {fullText.substring(newStoryStart)}
                    </span>
                  </>
                ) : (
                  fullText
                )}
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default Archive