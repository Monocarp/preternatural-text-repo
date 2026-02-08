// src/pages/Archive.tsx
import { useEffect, useMemo, useState, useRef } from 'react'
import { useParams, useNavigate, useLocation, useSearchParams } from 'react-router-dom'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/react'
import axios from '../utils/axios'
import { useStore } from '../store'
import SidebarTree from '../components/SidebarTree'
import { SubcategoryFilter } from '../components/SubcategoryFilter'
import { BookFilter } from '../components/BookFilter'
import { decodeRoutePath, encodePathSegmentsForRoute, encodePathSegmentsForApi } from '../utils/path'
import { useStackApp } from '@stackframe/react'
import { useCategoryAssignment } from '../hooks'

const Archive = () => {
  const location = useLocation()
  const { path = '' } = useParams<{ path?: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const app = useStackApp()
  
  // Extract path from location.pathname to ensure we detect URL changes
  // React Router's :path* might not trigger useParams updates properly
  const pathFromLocation = useMemo(() => {
    const match = location.pathname.match(/^\/archive\/(.+)$/)
    return match ? match[1] : ''
  }, [location.pathname])
  const { stories, loadStories, loading, error, tree, loadTree } = useStore()
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

  // Boundary editing state
  const [editingBoundaries, setEditingBoundaries] = useState<string | null>(null) // story title being edited
  const [editingBoundariesStory, setEditingBoundariesStory] = useState<any>(null)
  const [editedStart, setEditedStart] = useState<number>(0)
  const [editedEnd, setEditedEnd] = useState<number>(0)
  const [boundarySelectingStart, setBoundarySelectingStart] = useState(true)
  const [savingBoundaries, setSavingBoundaries] = useState(false)
  const boundaryTextContainerRef = useRef<HTMLDivElement>(null)

  // Keywords editing state
  const [editingKeywords, setEditingKeywords] = useState<string | null>(null) // story title being edited
  const [editedKeywords, setEditedKeywords] = useState('')
  const [savingKeywords, setSavingKeywords] = useState(false)

  // Category assignment state - track which story panel is expanded for assignment
  const [expandedStoryForCategory, setExpandedStoryForCategory] = useState<any>(null)
  
  // Book filter state for unassigned stories
  const [books, setBooks] = useState<any[]>([])
  const [selectedBookSlug, setSelectedBookSlug] = useState<string | null>(null)
  
  // Use the category assignment hook
  const categoryAssignment = useCategoryAssignment(expandedStoryForCategory)

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

  // Subcategory filter state from URL
  const selectedSubcats = useMemo(() => {
    const subcatsParam = searchParams.get('subcats')
    return subcatsParam ? subcatsParam.split(',').filter(s => s.trim()) : []
  }, [searchParams])

  // Extract subcategory names from tree for current path
  const subcategoryNames = useMemo(() => {
    if (!tree || Object.keys(tree).length === 0 || decodedPath.length === 0) return []
    
    // Navigate to current node in tree
    let node = tree
    for (const part of decodedPath) {
      if (!node || typeof node !== 'object' || !(part in node)) return []
      node = node[part]
    }
    
    // Get child keys excluding '_stories'
    if (!node || typeof node !== 'object') return []
    // If node is an array (legacy leaf format), it has no children
    if (Array.isArray(node)) return []
    return Object.keys(node).filter(k => k !== '_stories').sort()
  }, [tree, decodedPath])

  // Load tree if not loaded
  useEffect(() => {
    if (!tree || Object.keys(tree).length === 0) {
      loadTree()
    }
  }, [tree, loadTree])

  // Load books when viewing unassigned stories
  useEffect(() => {
    if (isUnassigned) {
      axios.get('/books')
        .then(res => {
          setBooks(res.data)
        })
        .catch(err => console.error('Error loading books:', err))
    }
  }, [isUnassigned])

  // Load stories based on URL path (with optional subcategory filter or book filter)
  useEffect(() => {
    if (isUnassigned) {
      // Load unassigned stories with optional book filter
      const bookParam = selectedBookSlug ? `?book_slug=${selectedBookSlug}` : ''
      axios.get(`/get-unassigned${bookParam}`)
        .then(res => {
          useStore.getState().setStories(res.data)
          useStore.getState().selectedPath = ['unassigned']
        })
        .catch(err => console.error('Error loading unassigned:', err))
    } else if (decodedPath.length > 0) {
      // Load stories for the category path (with optional subcategory filter)
      const pathStr = encodePathSegmentsForApi(decodedPath)
      const subcatsParam = selectedSubcats.length > 0 ? `?subcats=${selectedSubcats.join(',')}` : ''
      const url = `/get-stories/${pathStr}${subcatsParam}`
      
      axios.get(url)
        .then(res => {
          useStore.getState().setStories(res.data)
          useStore.getState().selectedPath = decodedPath
        })
        .catch(err => console.error('Error loading stories:', err))
    } else {
      // Root archive - don't load stories, just show empty state
      useStore.getState().setStories([])
      useStore.getState().selectedPath = []
    }
  }, [decodedPath, isUnassigned, selectedSubcats, selectedBookSlug, location.pathname])

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

      await axios.post('/update-title', {
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
      
      const res = await axios.delete(`/delete-story/${encodeURIComponent(story.title)}`, {
        headers: { 'Authorization': `Bearer ${accessToken}` }
      })
      
      if (res.data.status === 'success') {
        alert(`Story "${story.title}" deleted successfully.`)
        
        // Refresh the current view
        if (isUnassigned) {
          const unassignedRes = await axios.get('/get-unassigned')
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
      }
    } catch (err: any) {
      console.error('Error deleting story:', err)
      const errorMsg = err.response?.data?.detail || 'Failed to delete story.'
      alert(errorMsg)
    }
  }

  // Keywords editing handlers
  const handleEditKeywords = (story: any) => {
    setEditingKeywords(story.title)
    setEditedKeywords(story.keywords || '')
  }

  const handleSaveKeywords = async (story: any) => {
    if (!story) return
    
    setSavingKeywords(true)
    try {
      const user = await app.getUser()
      if (!user) {
        alert('You must be logged in to edit keywords.')
        setSavingKeywords(false)
        return
      }

      await axios.post('/update-keywords', {
        title: story.title,
        book_slug: story.book_slug,
        keywords: editedKeywords.trim()
      })

      // Update in store
      const updatedStories = stories.map(s => 
        s.title === story.title ? { ...s, keywords: editedKeywords.trim() } : s
      )
      useStore.getState().setStories(updatedStories)

      setEditingKeywords(null)
      setEditedKeywords('')
      alert('Keywords updated successfully!')
    } catch (err: any) {
      console.error('Error updating keywords:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to edit keywords.')
      } else {
        alert('Failed to update keywords. Please try again.')
      }
    } finally {
      setSavingKeywords(false)
    }
  }

  const handleCancelKeywordsEdit = () => {
    setEditingKeywords(null)
    setEditedKeywords('')
  }

  // Load story content when toggling modes
  const handleToggleMode = async (story: any, mode: 'static' | 'book') => {
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

  // Enter boundary editing mode for a story
  const handleAdjustBoundaries = async (story: any) => {
    setEditingBoundaries(story.title)
    setEditingBoundariesStory(story)
    setEditedStart(story.start_char)
    setEditedEnd(story.end_char)
    setBoundarySelectingStart(true)
    setEditingTitle(null) // Exit title editing if active
    setNewStoryMode(false) // Exit new story mode if active
    
    try {
      const res = await axios.get(`/full-text/${story.book_slug}`)
      setFullText(res.data.text)
    } catch (err) {
      console.error('Error loading full text:', err)
      setEditingBoundaries(null)
      setEditingBoundariesStory(null)
    }
  }

  // Auto-scroll to story position when entering boundary edit mode
  useEffect(() => {
    if (editingBoundaries && fullText && boundaryTextContainerRef.current && editingBoundariesStory) {
      setTimeout(() => {
        const textContainer = boundaryTextContainerRef.current
        if (!textContainer) return
        
        // Find the highlighted span (the story content)
        const highlight = textContainer.querySelector('span.bg-blue-600') as HTMLElement
        if (highlight) {
          // Scroll the container to center the highlight
          const containerRect = textContainer.getBoundingClientRect()
          const highlightRect = highlight.getBoundingClientRect()
          const relativeTop = highlightRect.top - containerRect.top + textContainer.scrollTop
          const containerHeight = textContainer.clientHeight
          textContainer.scrollTop = relativeTop - (containerHeight / 2) + (highlightRect.height / 2)
        }
      }, 150)
    }
  }, [editingBoundaries, fullText, editingBoundariesStory])

  // Handle click on text to set boundary position
  const handleBoundaryTextClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!editingBoundaries || !fullText || !boundaryTextContainerRef.current) return
    
    e.preventDefault()
    const textContainer = boundaryTextContainerRef.current
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
    
    if (boundarySelectingStart) {
      setEditedStart(charPos)
      setBoundarySelectingStart(false) // Switch to selecting end
    } else {
      // Ensure end is after start
      setEditedEnd(Math.max(charPos, editedStart))
      setBoundarySelectingStart(true) // Switch back to selecting start for next click
    }
  }

  // Save boundary changes
  const handleSaveBoundaries = async () => {
    if (!editingBoundariesStory) return
    
    const user = await app.getUser()
    if (!user) {
      alert('You must be logged in to save boundaries.')
      return
    }
    
    setSavingBoundaries(true)
    try {
      await axios.post('/update-boundaries', {
        title: editingBoundariesStory.title,
        book_slug: editingBoundariesStory.book_slug,
        start_char: editedStart,
        end_char: editedEnd
      })
      
      // Reload the story content with new boundaries
      const currentMode = storyModes[editingBoundariesStory.title] || 'static'
      const res = await axios.post('/render-story', {
        title: editingBoundariesStory.title,
        mode: currentMode,
        start_char: editedStart,
        end_char: editedEnd
      })
      
      setStoryContents(prev => ({
        ...prev,
        [editingBoundariesStory.title]: res.data.html
      }))
      
      // Update story in the stories list
      const updatedStories = stories.map(s => 
        s.title === editingBoundariesStory.title 
          ? { ...s, start_char: editedStart, end_char: editedEnd }
          : s
      )
      useStore.getState().setStories(updatedStories)
      
      alert('Boundaries saved successfully!')
      
      // Exit edit mode
      setEditingBoundaries(null)
      setEditingBoundariesStory(null)
      setFullText('')
    } catch (err: any) {
      console.error('Error saving boundaries:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to save boundaries.')
      } else {
        alert('Failed to save boundaries. Please try again.')
      }
    } finally {
      setSavingBoundaries(false)
    }
  }

  // Cancel boundary editing
  const handleCancelBoundaryEdit = () => {
    setEditingBoundaries(null)
    setEditingBoundariesStory(null)
    setFullText('')
    setEditedStart(0)
    setEditedEnd(0)
  }

  // Enter new story mode
  const handleEnterNewStoryMode = async (bookSlug: string) => {
    setNewStoryMode(true)
    setNewStoryBookSlug(bookSlug)
    setEditingTitle(null) // Exit title editing if active
    try {
      // Load full text for the book
      const res = await axios.get(`/full-text/${bookSlug}`)
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
    
    // Debug: log the request payload
    const payload = {
      book_slug: newStoryBookSlug,
      title: newStoryTitle.trim(),
      keywords: newStoryKeywords.trim(),
      pages: newStoryPages.trim(),
      start_char: newStoryStart,
      end_char: newStoryEnd,
      force_overlap: false
    }
    console.log('Add story request payload:', payload)
    
    try {
      const response = await axios.post('/add-story', payload)
      
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
        const forcePayload = { ...payload, force_overlap: true }
        console.log('Retry with force_overlap:', forcePayload)
        await axios.post('/add-story', forcePayload)
        
        alert(`Story "${newStoryTitle}" added successfully and is now searchable!`)
      } else {
        // Success - no overlaps
        alert(`Story "${newStoryTitle}" added successfully and is now searchable!`)
      }
      
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
        axios.get('/get-unassigned')
          .then(res => {
            useStore.getState().setStories(res.data)
          })
          .catch(err => console.error('Error reloading unassigned:', err))
      } else if (decodedPath.length > 0) {
        loadStories(decodedPath)
      }
    } catch (err: any) {
      console.error('Error adding story:', err)
      console.error('Error response data:', err?.response?.data)
      const status = err?.response?.status
      const errorDetail = err?.response?.data?.detail || err?.response?.data?.message || 'Unknown error'
      
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to add stories.')
      } else if (status === 409) {
        alert('This story overlaps with an existing story. Please adjust the boundaries.')
      } else if (status === 400) {
        alert(`Bad request: ${errorDetail}`)
      } else {
        alert(`Failed to add story: ${errorDetail}`)
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
    <div className="flex h-screen h-[100dvh] max-h-screen max-w-[100vw] overflow-hidden">
      <SidebarTree />
      <main className="flex-1 overflow-y-auto bg-gray-900 min-w-0 max-w-full">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
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
          </div>

          {/* Subcategory Filter */}
          {!isUnassigned && decodedPath.length > 0 && (
            <SubcategoryFilter
              subcategories={subcategoryNames}
              selectedSubcats={selectedSubcats}
              onFilterChange={(selected) => {
                if (selected.length === 0) {
                  // Remove subcats param entirely
                  searchParams.delete('subcats')
                } else {
                  searchParams.set('subcats', selected.join(','))
                }
                setSearchParams(searchParams)
              }}
            />
          )}

          {/* Book Filter for Unassigned Stories */}
          {isUnassigned && (
            <BookFilter
              books={books}
              selectedBookSlug={selectedBookSlug}
              onFilterChange={setSelectedBookSlug}
            />
          )}

          {stories.length > 0 && (
            <p className="text-gray-300 mb-4 text-center">{stories.length} {stories.length === 1 ? 'story' : 'stories'}</p>
          )}

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
                          <span className="font-medium">{story.book_title || (story.book_slug ? story.book_slug.replace(/_/g, ' ') : 'Unknown Book')}</span>
                          {story.book_author && <span className="ml-2">• {story.book_author}</span>}
                          {story.book_year && <span className="ml-2">({story.book_year})</span>}
                        </div>
                        <div className="mt-0.5 text-xs text-gray-500">
                          {story.pages && <span>Pages: {story.pages}</span>}
                          {editingKeywords === story.title ? (
                            <span className="ml-2 inline-flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                              • Keywords:
                              <input
                                type="text"
                                value={editedKeywords}
                                onChange={(e) => setEditedKeywords(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') { e.stopPropagation(); handleSaveKeywords(story) }
                                  if (e.key === 'Escape') { e.stopPropagation(); handleCancelKeywordsEdit() }
                                }}
                                className="px-1.5 py-0.5 bg-gray-700 border border-gray-600 rounded text-white text-xs w-48"
                                autoFocus
                                placeholder="ghost, haunting, supernatural"
                              />
                              <span
                                role="button"
                                tabIndex={0}
                                onClick={(e) => { e.stopPropagation(); handleSaveKeywords(story) }}
                                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); handleSaveKeywords(story) } }}
                                className={`px-1.5 py-0.5 bg-green-600 text-white rounded hover:bg-green-700 text-xs cursor-pointer ${savingKeywords ? 'opacity-50 pointer-events-none' : ''}`}
                              >
                                ✓
                              </span>
                              <span
                                role="button"
                                tabIndex={0}
                                onClick={(e) => { e.stopPropagation(); handleCancelKeywordsEdit() }}
                                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); handleCancelKeywordsEdit() } }}
                                className="px-1.5 py-0.5 bg-gray-600 text-white rounded hover:bg-gray-700 text-xs cursor-pointer"
                              >
                                ✕
                              </span>
                            </span>
                          ) : (
                            <span className="ml-2 inline-flex items-center gap-1">
                              • Keywords: {story.keywords || <span className="italic">none</span>}
                              <span
                                role="button"
                                tabIndex={0}
                                onClick={(e) => { e.stopPropagation(); handleEditKeywords(story) }}
                                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); handleEditKeywords(story) } }}
                                className="ml-1 px-1 py-0.5 bg-gray-600 text-white rounded hover:bg-gray-700 text-xs cursor-pointer"
                              >
                                ✎
                              </span>
                            </span>
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
                        <button
                          onClick={(e) => { e.stopPropagation(); handleAdjustBoundaries(story) }}
                          className="px-4 py-2 rounded text-sm bg-green-600 text-white hover:bg-green-700"
                        >
                          Adjust Boundaries
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
                      
                      {/* Category Assignment Section */}
                      <div className="mt-4 pt-4 border-t border-gray-700">
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            if (expandedStoryForCategory?.title === story.title) {
                              setExpandedStoryForCategory(null)
                            } else {
                              setExpandedStoryForCategory(story)
                            }
                          }}
                          className="w-full flex items-center justify-between px-3 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm text-gray-200 transition-colors"
                        >
                          <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                            </svg>
                            Assign to Category
                          </span>
                          <span className="text-gray-400">
                            {expandedStoryForCategory?.title === story.title ? '▲' : '▼'}
                          </span>
                        </button>
                        
                        {expandedStoryForCategory?.title === story.title && (
                          <div className="mt-3 p-3 bg-gray-750 rounded border border-gray-600">
                            {/* Current Assignments */}
                            {categoryAssignment.currentAssignments.length > 0 && (
                              <div className="mb-3">
                                <p className="text-xs text-gray-400 mb-1">Currently assigned to:</p>
                                <div className="flex flex-wrap gap-1">
                                  {categoryAssignment.currentAssignments.map((pathArr, idx) => (
                                    <span
                                      key={idx}
                                      className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-900/50 text-blue-300 rounded text-xs"
                                    >
                                      {pathArr.join(' > ')}
                                      <button
                                        onClick={(e) => {
                                          e.stopPropagation()
                                          categoryAssignment.removeCategory(pathArr)
                                        }}
                                        className="ml-1 text-blue-400 hover:text-red-400"
                                        title="Remove from this category"
                                      >
                                        ×
                                      </button>
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                            
                            {/* Category Selection Dropdowns */}
                            <div className="space-y-2">
                              <p className="text-xs text-gray-400">Select category path:</p>
                              <div className="flex flex-wrap gap-2">
                                {/* Level 0 - Root categories */}
                                <select
                                  value={categoryAssignment.selectedPath[0] || ''}
                                  onChange={(e) => categoryAssignment.handlePathLevelChange(0, e.target.value)}
                                  className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                                  onClick={(e) => e.stopPropagation()}
                                >
                                  <option value="">Select category...</option>
                                  {categoryAssignment.getPathOptions([]).map((opt) => (
                                    <option key={opt} value={opt}>{opt}</option>
                                  ))}
                                </select>
                                
                                {/* Level 1 */}
                                {categoryAssignment.selectedPath[0] && categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 1)).length > 0 && (
                                  <select
                                    value={categoryAssignment.selectedPath[1] || ''}
                                    onChange={(e) => categoryAssignment.handlePathLevelChange(1, e.target.value)}
                                    className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <option value="">Select subcategory...</option>
                                    {categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 1)).map((opt) => (
                                      <option key={opt} value={opt}>{opt}</option>
                                    ))}
                                  </select>
                                )}
                                
                                {/* Level 2 */}
                                {categoryAssignment.selectedPath[1] && categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 2)).length > 0 && (
                                  <select
                                    value={categoryAssignment.selectedPath[2] || ''}
                                    onChange={(e) => categoryAssignment.handlePathLevelChange(2, e.target.value)}
                                    className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <option value="">Select...</option>
                                    {categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 2)).map((opt) => (
                                      <option key={opt} value={opt}>{opt}</option>
                                    ))}
                                  </select>
                                )}
                                
                                {/* Level 3 */}
                                {categoryAssignment.selectedPath[2] && categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 3)).length > 0 && (
                                  <select
                                    value={categoryAssignment.selectedPath[3] || ''}
                                    onChange={(e) => categoryAssignment.handlePathLevelChange(3, e.target.value)}
                                    className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <option value="">Select...</option>
                                    {categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 3)).map((opt) => (
                                      <option key={opt} value={opt}>{opt}</option>
                                    ))}
                                  </select>
                                )}
                                
                                {/* Level 4 */}
                                {categoryAssignment.selectedPath[3] && categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 4)).length > 0 && (
                                  <select
                                    value={categoryAssignment.selectedPath[4] || ''}
                                    onChange={(e) => categoryAssignment.handlePathLevelChange(4, e.target.value)}
                                    className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <option value="">Select...</option>
                                    {categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 4)).map((opt) => (
                                      <option key={opt} value={opt}>{opt}</option>
                                    ))}
                                  </select>
                                )}
                                
                                {/* Level 5 */}
                                {categoryAssignment.selectedPath[4] && categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 5)).length > 0 && (
                                  <select
                                    value={categoryAssignment.selectedPath[5] || ''}
                                    onChange={(e) => categoryAssignment.handlePathLevelChange(5, e.target.value)}
                                    className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <option value="">Select...</option>
                                    {categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 5)).map((opt) => (
                                      <option key={opt} value={opt}>{opt}</option>
                                    ))}
                                  </select>
                                )}
                                
                                {/* Level 6 */}
                                {categoryAssignment.selectedPath[5] && categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 6)).length > 0 && (
                                  <select
                                    value={categoryAssignment.selectedPath[6] || ''}
                                    onChange={(e) => categoryAssignment.handlePathLevelChange(6, e.target.value)}
                                    className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <option value="">Select...</option>
                                    {categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 6)).map((opt) => (
                                      <option key={opt} value={opt}>{opt}</option>
                                    ))}
                                  </select>
                                )}
                                
                                {/* Level 7 */}
                                {categoryAssignment.selectedPath[6] && categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 7)).length > 0 && (
                                  <select
                                    value={categoryAssignment.selectedPath[7] || ''}
                                    onChange={(e) => categoryAssignment.handlePathLevelChange(7, e.target.value)}
                                    className="px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-sm"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <option value="">Select...</option>
                                    {categoryAssignment.getPathOptions(categoryAssignment.selectedPath.slice(0, 7)).map((opt) => (
                                      <option key={opt} value={opt}>{opt}</option>
                                    ))}
                                  </select>
                                )}
                              </div>
                              
                              {/* Assign Button */}
                              {categoryAssignment.selectedPath.length > 0 && (
                                <div className="flex items-center gap-2 mt-2">
                                  <span className="text-xs text-gray-400">
                                    Path: {categoryAssignment.selectedPath.join(' > ')}
                                  </span>
                                  <button
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      categoryAssignment.assignCategory()
                                    }}
                                    disabled={categoryAssignment.assigning}
                                    className="px-3 py-1 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50"
                                  >
                                    {categoryAssignment.assigning ? 'Assigning...' : 'Assign'}
                                  </button>
                                </div>
                              )}
                            </div>
                          </div>
                        )}
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

          {/* Boundary Editing Panel */}
          {editingBoundaries && fullText && editingBoundariesStory && (
            <div className="mt-6 p-4 bg-gray-800 rounded-lg border border-green-700">
              <div className="text-center mb-4">
                <h2 className="text-xl font-semibold text-white mb-2">Adjust Story Boundaries</h2>
                <p className="text-gray-300">Editing: <span className="font-medium text-green-400">{editingBoundariesStory.title}</span></p>
              </div>
              
              <div className="text-sm text-gray-300 mb-4 text-center">
                {boundarySelectingStart ? (
                  <span>Click to set <strong className="text-blue-400">START</strong> position</span>
                ) : (
                  <span>Click to set <strong className="text-red-400">END</strong> position</span>
                )}
              </div>
              
              <div className="flex justify-center gap-2 mb-4">
                <button
                  onClick={handleSaveBoundaries}
                  disabled={savingBoundaries}
                  className="px-6 py-2 rounded text-sm bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {savingBoundaries ? 'Saving...' : 'Save Boundaries'}
                </button>
                <button
                  onClick={handleCancelBoundaryEdit}
                  className="px-6 py-2 rounded text-sm bg-gray-700 text-gray-200 hover:bg-gray-600 transition-colors"
                >
                  Cancel
                </button>
              </div>
              
              <div className="text-xs text-gray-400 text-center mb-4">
                Start: {editedStart.toLocaleString()} | End: {editedEnd.toLocaleString()} | Length: {(editedEnd - editedStart).toLocaleString()} chars
              </div>
              
              <div
                ref={boundaryTextContainerRef}
                onClick={handleBoundaryTextClick}
                className="bg-gray-900 border border-gray-700 rounded p-4 cursor-text select-none font-mono text-sm leading-relaxed max-h-96 overflow-y-auto"
                style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
              >
                {fullText.substring(0, editedStart)}
                <span className="bg-blue-600 bg-opacity-50 text-blue-200 px-1 rounded">
                  {fullText.substring(editedStart, editedEnd)}
                </span>
                <span className="text-gray-400">
                  {fullText.substring(editedEnd)}
                </span>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

export default Archive