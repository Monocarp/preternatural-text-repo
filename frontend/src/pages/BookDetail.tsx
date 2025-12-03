import { useEffect, useState, useRef, useMemo } from 'react'
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

// Color palette for distinguishing stories (alternates to avoid adjacent same colors)
const STORY_COLORS = [
  { bg: 'bg-blue-600/40', border: 'border-blue-500', hover: 'hover:bg-blue-600/60', text: 'text-blue-200' },
  { bg: 'bg-green-600/40', border: 'border-green-500', hover: 'hover:bg-green-600/60', text: 'text-green-200' },
  { bg: 'bg-purple-600/40', border: 'border-purple-500', hover: 'hover:bg-purple-600/60', text: 'text-purple-200' },
  { bg: 'bg-amber-600/40', border: 'border-amber-500', hover: 'hover:bg-amber-600/60', text: 'text-amber-200' },
  { bg: 'bg-cyan-600/40', border: 'border-cyan-500', hover: 'hover:bg-cyan-600/60', text: 'text-cyan-200' },
  { bg: 'bg-rose-600/40', border: 'border-rose-500', hover: 'hover:bg-rose-600/60', text: 'text-rose-200' },
]

const BookDetail = () => {
  const { slug } = useParams<{ slug: string }>()
  const navigate = useNavigate()
  const [book, setBook] = useState<any>(null)
  const [stories, setStories] = useState<Story[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [view, setView] = useState<'info' | 'text' | 'stories' | 'review'>('info')
  const [fullText, setFullText] = useState<string>('')
  const [loadingText, setLoadingText] = useState(false)
  const [storyContents, setStoryContents] = useState<Record<string, string>>({})
  const [storyModes, setStoryModes] = useState<Record<string, 'static' | 'book'>>({})
  const textViewerRef = useRef<HTMLDivElement>(null)
  const reviewContainerRef = useRef<HTMLDivElement>(null)
  
  // Story Review state
  const [selectedStory, setSelectedStory] = useState<Story | null>(null)
  
  // Boundary editing state
  const [editingBoundary, setEditingBoundary] = useState(false)
  const [editedStart, setEditedStart] = useState<number>(0)
  const [editedEnd, setEditedEnd] = useState<number>(0)
  const [selectingStart, setSelectingStart] = useState(true) // true = selecting start, false = selecting end
  const [savingBoundaries, setSavingBoundaries] = useState(false)
  
  // Edit title state
  const [editingTitle, setEditingTitle] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  
  // Edit keywords state
  const [editingKeywords, setEditingKeywords] = useState(false)
  const [editedKeywords, setEditedKeywords] = useState('')
  const [savingKeywords, setSavingKeywords] = useState(false)
  
  // New story state
  const [newStoryMode, setNewStoryMode] = useState(false)
  const [newStoryStart, setNewStoryStart] = useState<number | null>(null)
  const [newStoryEnd, setNewStoryEnd] = useState<number | null>(null)
  const [newStorySelectingStart, setNewStorySelectingStart] = useState(true)
  const [newStoryTitle, setNewStoryTitle] = useState('')
  const [newStoryKeywords, setNewStoryKeywords] = useState('')
  const [newStoryPages, setNewStoryPages] = useState('')
  const [addingStory, setAddingStory] = useState(false)
  
  // Category assignment state
  const [codexTree, setCodexTree] = useState<any>(null)
  const [selectedPath, setSelectedPath] = useState<string[]>([])
  const [currentAssignments, setCurrentAssignments] = useState<string[][]>([])
  const [assigning, setAssigning] = useState(false)
  
  // AI suggestion state
  interface AISuggestion {
    path: string[]
    confidence: number
    reason?: string
    confirmed: boolean
  }
  const [aiSuggestions, setAiSuggestions] = useState<AISuggestion[]>([])
  const [loadingAiSuggestions, setLoadingAiSuggestions] = useState(false)
  const [aiError, setAiError] = useState<string | null>(null)
  const [committingAll, setCommittingAll] = useState(false)

  useEffect(() => {
    if (slug) {
      loadBook()
    }
    // Load codex tree for category assignment
    axios.get('/get-tree')
      .then(res => {
        setCodexTree(res.data)
      })
      .catch(err => {
        console.error('Error loading codex tree:', err)
      })
  }, [slug])

  // Auto-scroll to story position when entering boundary edit mode
  useEffect(() => {
    if (editingBoundary && fullText && reviewContainerRef.current && selectedStory) {
      setTimeout(() => {
        const textContainer = reviewContainerRef.current
        if (!textContainer) return
        
        // Find the highlighted span (the selected region)
        const highlight = textContainer.querySelector('span.bg-yellow-600\\/50') as HTMLElement
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
  }, [editingBoundary, fullText, selectedStory])

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

  // Handle category assignment
  const handleAssignCategory = async () => {
    if (!selectedStory || selectedPath.length === 0) return
    
    setAssigning(true)
    try {
      await axios.post('/assign-category', {
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
      const treeRes = await axios.get('/get-tree')
      setCodexTree(treeRes.data)
      
      const assignedPath = selectedPath.join(' > ')
      // Clear selected path
      setSelectedPath([])
      
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
      await axios.delete('/remove-category', {
        data: {
          path: path,
          title: selectedStory.title
        }
      })
      
      // Reload tree to get updated assignments
      const treeRes = await axios.get('/get-tree')
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

  // AI Category Suggestion handlers
  const handleAutoSuggest = async () => {
    if (!selectedStory || !fullText) return
    
    setLoadingAiSuggestions(true)
    setAiError(null)
    setAiSuggestions([])
    
    try {
      // Extract story text from full text using boundaries
      const storyText = fullText.substring(selectedStory.start_char, selectedStory.end_char)
      
      const res = await axios.post('/ai/suggest-categories', {
        story_title: selectedStory.title,
        story_text: storyText
      })
      
      // Pre-confirm suggestions with confidence >= 0.7
      const suggestions = res.data.suggestions.map((s: any) => ({
        ...s,
        confirmed: s.confidence >= 0.7
      }))
      
      setAiSuggestions(suggestions)
    } catch (err: any) {
      console.error('Error getting AI suggestions:', err)
      const detail = err?.response?.data?.detail
      setAiError(detail || 'Failed to get AI suggestions')
    } finally {
      setLoadingAiSuggestions(false)
    }
  }
  
  const handleToggleSuggestion = (index: number) => {
    setAiSuggestions(prev => prev.map((s, i) => 
      i === index ? { ...s, confirmed: !s.confirmed } : s
    ))
  }
  
  const handleCommitConfirmed = async () => {
    if (!selectedStory) return
    
    const confirmedSuggestions = aiSuggestions.filter(s => s.confirmed)
    if (confirmedSuggestions.length === 0) {
      alert('No suggestions are confirmed. Check the ones you want to assign.')
      return
    }
    
    setCommittingAll(true)
    let successCount = 0
    let errorCount = 0
    
    for (const suggestion of confirmedSuggestions) {
      try {
        await axios.post('/assign-category', {
          path: suggestion.path,
          story: {
            title: selectedStory.title,
            book_slug: selectedStory.book_slug,
            pages: selectedStory.pages,
            keywords: selectedStory.keywords,
            start_char: selectedStory.start_char,
            end_char: selectedStory.end_char
          }
        })
        successCount++
      } catch (err) {
        console.error(`Error assigning ${suggestion.path.join(' > ')}:`, err)
        errorCount++
      }
    }
    
    // Reload tree to get updated assignments
    try {
      const treeRes = await axios.get('/get-tree')
      setCodexTree(treeRes.data)
    } catch (err) {
      console.error('Error reloading tree:', err)
    }
    
    setCommittingAll(false)
    setAiSuggestions([]) // Clear suggestions after commit
    
    if (errorCount === 0) {
      alert(`Successfully assigned ${successCount} categories!`)
    } else {
      alert(`Assigned ${successCount} categories. ${errorCount} failed.`)
    }
  }
  
  // Clear AI suggestions when story changes
  useEffect(() => {
    setAiSuggestions([])
    setAiError(null)
  }, [selectedStory?.title])

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

  const handleViewReview = () => {
    setView('review')
    setSelectedStory(null)
    if (!fullText) {
      loadFullText()
    }
  }

  // Sort stories by start position for review view and assign color indices
  const sortedStories = useMemo(() => {
    return [...stories]
      .sort((a, b) => a.start_char - b.start_char)
      .map((story, idx) => ({
        ...story,
        colorIndex: idx % STORY_COLORS.length
      }))
  }, [stories])

  // Build segments for the review view (text with highlighted story regions)
  const reviewSegments = useMemo(() => {
    if (!fullText || sortedStories.length === 0) return []
    
    const segments: Array<{
      type: 'gap' | 'story'
      start: number
      end: number
      text: string
      story?: typeof sortedStories[0]
      colorIndex?: number
    }> = []
    
    let currentPos = 0
    
    for (const story of sortedStories) {
      // Skip invalid boundaries
      if (story.start_char < 0 || story.end_char <= story.start_char) continue
      
      // Add gap before this story (if any)
      if (story.start_char > currentPos) {
        segments.push({
          type: 'gap',
          start: currentPos,
          end: story.start_char,
          text: fullText.substring(currentPos, story.start_char)
        })
      }
      
      // Add story segment
      const storyStart = Math.max(currentPos, story.start_char)
      const storyEnd = Math.min(fullText.length, story.end_char)
      
      if (storyEnd > storyStart) {
        segments.push({
          type: 'story',
          start: storyStart,
          end: storyEnd,
          text: fullText.substring(storyStart, storyEnd),
          story: story,
          colorIndex: story.colorIndex
        })
        currentPos = storyEnd
      }
    }
    
    // Add final gap after last story (if any)
    if (currentPos < fullText.length) {
      segments.push({
        type: 'gap',
        start: currentPos,
        end: fullText.length,
        text: fullText.substring(currentPos)
      })
    }
    
    return segments
  }, [fullText, sortedStories])

  // Handle clicking on a story in the review view
  const handleStoryClick = (story: Story) => {
    setSelectedStory(selectedStory?.title === story.title ? null : story)
  }

  // Scroll to a story in the review view
  const scrollToStory = (story: Story) => {
    const element = document.getElementById(`review-story-${story.title.replace(/\s+/g, '-')}`)
    if (element && reviewContainerRef.current) {
      const containerRect = reviewContainerRef.current.getBoundingClientRect()
      const elementRect = element.getBoundingClientRect()
      const relativeTop = elementRect.top - containerRect.top + reviewContainerRef.current.scrollTop
      reviewContainerRef.current.scrollTop = relativeTop - 100 // 100px offset from top
    }
  }

  // Enter boundary editing mode
  const handleStartBoundaryEdit = () => {
    if (!selectedStory) return
    setEditingBoundary(true)
    setEditedStart(selectedStory.start_char)
    setEditedEnd(selectedStory.end_char)
    setSelectingStart(true)
  }

  // Cancel boundary editing
  const handleCancelBoundaryEdit = () => {
    setEditingBoundary(false)
    setEditedStart(0)
    setEditedEnd(0)
    setSelectingStart(true)
  }

  // Handle click on text to set boundary position
  const handleBoundaryClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!editingBoundary || !fullText || !reviewContainerRef.current) return
    
    e.preventDefault()
    e.stopPropagation()
    
    const clickX = e.clientX
    const clickY = e.clientY
    
    // Create a range at the click point
    const range = document.caretRangeFromPoint?.(clickX, clickY)
    if (!range) return
    
    // Calculate character position by walking through text nodes
    const textContainer = reviewContainerRef.current
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
          charPos += range.startOffset
        } else {
          charPos += textNode.textContent?.length || 0
        }
        break
      } else {
        charPos += textNode.textContent?.length || 0
      }
    }
    
    // Ensure valid range
    charPos = Math.min(Math.max(0, charPos), fullText.length)
    
    if (selectingStart) {
      setEditedStart(charPos)
      setSelectingStart(false) // Switch to selecting end
    } else {
      // Ensure end is after start
      if (charPos > editedStart) {
        setEditedEnd(charPos)
      } else {
        // If clicked before start, treat as new start
        setEditedStart(charPos)
      }
      setSelectingStart(true) // Switch back to selecting start
    }
  }

  // Save boundary changes
  const handleSaveBoundaries = async () => {
    if (!selectedStory || !slug) return
    
    if (editedEnd <= editedStart) {
      alert('End position must be after start position.')
      return
    }
    
    setSavingBoundaries(true)
    try {
      await axios.post('/update-boundaries', {
        title: selectedStory.title,
        book_slug: slug,
        start_char: editedStart,
        end_char: editedEnd
      })
      
      // Update the story in the local state
      const updatedStories = stories.map(s => 
        s.title === selectedStory.title 
          ? { ...s, start_char: editedStart, end_char: editedEnd }
          : s
      )
      setStories(updatedStories)
      
      // Update selected story
      setSelectedStory({ ...selectedStory, start_char: editedStart, end_char: editedEnd })
      
      // Exit edit mode
      setEditingBoundary(false)
      setEditedStart(0)
      setEditedEnd(0)
      
      alert('Boundaries saved successfully!')
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

  // Build segments for editing mode (shows edited boundaries)
  const editingSegments = useMemo(() => {
    if (!editingBoundary || !fullText || !selectedStory) return []
    
    const segments: Array<{
      type: 'before' | 'selected' | 'after'
      text: string
      start: number
      end: number
    }> = []
    
    // Text before the edited region
    if (editedStart > 0) {
      segments.push({
        type: 'before',
        text: fullText.substring(0, editedStart),
        start: 0,
        end: editedStart
      })
    }
    
    // The edited region
    if (editedEnd > editedStart) {
      segments.push({
        type: 'selected',
        text: fullText.substring(editedStart, editedEnd),
        start: editedStart,
        end: editedEnd
      })
    }
    
    // Text after the edited region
    if (editedEnd < fullText.length) {
      segments.push({
        type: 'after',
        text: fullText.substring(editedEnd),
        start: editedEnd,
        end: fullText.length
      })
    }
    
    return segments
  }, [editingBoundary, fullText, selectedStory, editedStart, editedEnd])

  // Edit title handlers
  const handleStartEditTitle = () => {
    if (!selectedStory) return
    setEditingTitle(true)
    setNewTitle(selectedStory.title)
  }

  const handleSaveTitle = async () => {
    if (!selectedStory || !newTitle.trim() || !slug) return
    
    // Check for duplicate title in same book
    const existingStory = stories.find(s => 
      s.title.toLowerCase() === newTitle.trim().toLowerCase() && 
      s.title !== selectedStory.title
    )
    if (existingStory) {
      alert('A story with this title already exists in this book.')
      return
    }

    try {
      await axios.post('/update-title', {
        old_title: selectedStory.title,
        new_title: newTitle.trim(),
        book_slug: slug
      })

      // Update the story in local state
      const updatedStories = stories.map(s => 
        s.title === selectedStory.title ? { ...s, title: newTitle.trim() } : s
      )
      setStories(updatedStories)
      
      // Update selected story
      setSelectedStory({ ...selectedStory, title: newTitle.trim() })

      // Update story contents key if exists
      if (storyContents[selectedStory.title]) {
        setStoryContents(prev => {
          const updated = { ...prev }
          delete updated[selectedStory.title]
          updated[newTitle.trim()] = prev[selectedStory.title]
          return updated
        })
      }

      setEditingTitle(false)
      setNewTitle('')
      alert('Title updated successfully!')
    } catch (err: any) {
      console.error('Error updating title:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to edit titles.')
      } else {
        alert('Failed to update title. Please try again.')
      }
    }
  }

  const handleCancelEditTitle = () => {
    setEditingTitle(false)
    setNewTitle('')
  }

  // Edit keywords handlers
  const handleStartEditKeywords = () => {
    if (!selectedStory) return
    setEditingKeywords(true)
    setEditedKeywords(selectedStory.keywords || '')
  }

  const handleSaveKeywords = async () => {
    if (!selectedStory || !slug) return
    
    setSavingKeywords(true)
    try {
      await axios.post('/update-keywords', {
        title: selectedStory.title,
        book_slug: slug,
        keywords: editedKeywords.trim()
      })

      // Update the story in local state
      const updatedStories = stories.map(s => 
        s.title === selectedStory.title ? { ...s, keywords: editedKeywords.trim() } : s
      )
      setStories(updatedStories)
      
      // Update selected story
      setSelectedStory({ ...selectedStory, keywords: editedKeywords.trim() })

      setEditingKeywords(false)
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

  const handleCancelEditKeywords = () => {
    setEditingKeywords(false)
    setEditedKeywords('')
  }

  // Delete story handler
  const handleDeleteStory = async () => {
    if (!selectedStory || !slug) return
    
    const confirmDelete = confirm(
      `Are you sure you want to delete "${selectedStory.title}"?\n\n` +
      `This will remove it from:\n` +
      `- Story positions (${slug})\n` +
      `- Database\n` +
      `- Document store\n` +
      `- All category assignments\n` +
      `- Pending queue (if present)\n\n` +
      `This action cannot be undone.`
    )
    
    if (!confirmDelete) return
    
    try {
      const res = await axios.delete(`/delete-story/${encodeURIComponent(selectedStory.title)}`)
      
      if (res.data.status === 'success') {
        alert(`Story "${selectedStory.title}" deleted successfully.`)
        
        // Remove from local state
        setStories(prev => prev.filter(s => s.title !== selectedStory.title))
        setSelectedStory(null)
        
        // Clear story content from state
        setStoryContents(prev => {
          const updated = { ...prev }
          delete updated[selectedStory.title]
          return updated
        })
        setStoryModes(prev => {
          const updated = { ...prev }
          delete updated[selectedStory.title]
          return updated
        })
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

  // New story handlers
  const handleEnterNewStoryMode = () => {
    setNewStoryMode(true)
    setSelectedStory(null)
    setEditingBoundary(false)
    setNewStoryStart(null)
    setNewStoryEnd(null)
    setNewStorySelectingStart(true)
    setNewStoryTitle('')
    setNewStoryKeywords('')
    setNewStoryPages('')
  }

  const handleCancelNewStory = () => {
    setNewStoryMode(false)
    setNewStoryStart(null)
    setNewStoryEnd(null)
    setNewStoryTitle('')
    setNewStoryKeywords('')
    setNewStoryPages('')
  }

  const handleNewStoryTextClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!newStoryMode || !fullText || !reviewContainerRef.current) return
    
    e.preventDefault()
    e.stopPropagation()
    
    const clickX = e.clientX
    const clickY = e.clientY
    
    const range = document.caretRangeFromPoint?.(clickX, clickY)
    if (!range) return
    
    const textContainer = reviewContainerRef.current
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
          charPos += range.startOffset
        } else {
          charPos += textNode.textContent?.length || 0
        }
        break
      } else {
        charPos += textNode.textContent?.length || 0
      }
    }
    
    charPos = Math.min(Math.max(0, charPos), fullText.length)
    
    if (newStorySelectingStart) {
      setNewStoryStart(charPos)
      setNewStorySelectingStart(false)
    } else {
      if (charPos > (newStoryStart || 0)) {
        setNewStoryEnd(charPos)
      } else {
        setNewStoryStart(charPos)
      }
      setNewStorySelectingStart(true)
    }
  }

  const handleAddNewStory = async () => {
    if (!slug || newStoryStart === null || newStoryEnd === null || !newStoryTitle.trim()) return
    
    if (!confirm(`Add new story "${newStoryTitle}" to this book?`)) {
      return
    }
    
    setAddingStory(true)
    try {
      const response = await axios.post('/add-story', {
        book_slug: slug,
        title: newStoryTitle.trim(),
        keywords: newStoryKeywords.trim(),
        pages: newStoryPages.trim(),
        start_char: newStoryStart,
        end_char: newStoryEnd
      })
      
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
        await axios.post('/add-story', {
          book_slug: slug,
          title: newStoryTitle.trim(),
          keywords: newStoryKeywords.trim(),
          pages: newStoryPages.trim(),
          start_char: newStoryStart,
          end_char: newStoryEnd,
          force_overlap: true
        })
      }
      
      alert(`Story "${newStoryTitle}" added successfully and is now searchable!`)
      
      // Add to local state
      const newStory: Story = {
        title: newStoryTitle.trim(),
        book_slug: slug,
        pages: newStoryPages.trim(),
        keywords: newStoryKeywords.trim(),
        start_char: newStoryStart,
        end_char: newStoryEnd
      }
      setStories(prev => [...prev, newStory])
      
      // Exit new story mode
      handleCancelNewStory()
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

  // Build segments for new story mode
  const newStorySegments = useMemo(() => {
    if (!newStoryMode || !fullText) return []
    
    const segments: Array<{
      type: 'before' | 'selected' | 'after'
      text: string
    }> = []
    
    const start = newStoryStart ?? 0
    const end = newStoryEnd ?? start
    
    if (start > 0) {
      segments.push({ type: 'before', text: fullText.substring(0, start) })
    }
    if (end > start) {
      segments.push({ type: 'selected', text: fullText.substring(start, end) })
    }
    if (end < fullText.length) {
      segments.push({ type: 'after', text: fullText.substring(end) })
    }
    
    return segments
  }, [newStoryMode, fullText, newStoryStart, newStoryEnd])

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
      <div className="flex h-screen h-[100dvh] max-h-screen max-w-[100vw] overflow-hidden">
        <SidebarTree />
        <main className="flex-1 overflow-y-auto bg-gray-900 min-w-0 max-w-full">
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
      <div className="flex h-screen h-[100dvh] max-h-screen max-w-[100vw] overflow-hidden">
        <SidebarTree />
        <main className="flex-1 overflow-y-auto bg-gray-900 min-w-0 max-w-full">
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
    <div className="flex h-screen h-[100dvh] max-h-screen max-w-[100vw] overflow-hidden">
      <SidebarTree />
      <main className="flex-1 overflow-y-auto bg-gray-900 min-w-0 max-w-full">
        <div className={`mx-auto px-4 sm:px-6 py-4 sm:py-6 ${view === 'review' ? 'max-w-full' : 'max-w-6xl'}`}>
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
        <button
          onClick={handleViewReview}
          className={`px-6 py-2 rounded-lg font-medium transition-colors ${
            view === 'review'
              ? 'bg-green-600 text-white'
              : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
          }`}
        >
          Story Review
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

      {/* Story Review View */}
      {view === 'review' && (
        <div className="flex gap-3">
          {/* Left column: Text viewer */}
          <div className="flex-1 min-w-0 max-w-[55%] bg-gray-800 border border-gray-700 rounded-lg p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">
                {newStoryMode ? 'Add New Story' : editingBoundary ? 'Editing Boundaries' : 'Text Viewer'}
              </h2>
              <div className="text-xs text-gray-400">
                {newStoryMode ? (
                  <span className={`font-medium ${newStorySelectingStart ? 'text-green-400' : 'text-yellow-400'}`}>
                    Click to set {newStorySelectingStart ? 'START' : 'END'} position
                  </span>
                ) : editingBoundary ? (
                  <span className={`font-medium ${selectingStart ? 'text-blue-400' : 'text-green-400'}`}>
                    Click to set {selectingStart ? 'START' : 'END'} position
                  </span>
                ) : (
                  <>Click highlighted text to select</>
                )}
              </div>
            </div>
            
            {loadingText && (
              <div className="text-center py-8">
                <p className="text-gray-400">Loading text...</p>
              </div>
            )}
            
            {/* Normal review mode - show all story highlights */}
            {!loadingText && fullText && !editingBoundary && !newStoryMode && (
              <div
                ref={reviewContainerRef}
                className="bg-gray-900 border border-gray-700 rounded-lg p-4 max-h-[65vh] overflow-y-auto"
                style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
              >
                <div className="font-mono text-sm leading-relaxed">
                  {reviewSegments.map((segment, idx) => {
                    if (segment.type === 'gap') {
                      return (
                        <span key={idx} className="text-gray-300">
                          {segment.text}
                        </span>
                      )
                    } else {
                      const color = STORY_COLORS[segment.colorIndex!]
                      const isSelected = selectedStory?.title === segment.story?.title
                      return (
                        <span
                          key={idx}
                          id={`review-story-${segment.story?.title.replace(/\s+/g, '-')}`}
                          onClick={() => segment.story && handleStoryClick(segment.story)}
                          className={`
                            cursor-pointer rounded px-0.5 transition-all
                            ${color.bg} ${color.hover}
                            ${isSelected ? `ring-2 ring-white ${color.border} border` : ''}
                          `}
                          title={segment.story?.title}
                        >
                          {segment.text}
                        </span>
                      )
                    }
                  })}
                </div>
              </div>
            )}
            
            {/* Editing mode - show selected region and allow clicking to adjust */}
            {!loadingText && fullText && editingBoundary && (
              <div
                ref={reviewContainerRef}
                onClick={handleBoundaryClick}
                className="bg-gray-900 border-2 border-blue-500 rounded-lg p-4 max-h-[65vh] overflow-y-auto cursor-crosshair"
                style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
              >
                <div className="font-mono text-sm leading-relaxed select-none">
                  {editingSegments.map((segment, idx) => {
                    if (segment.type === 'selected') {
                      return (
                        <span
                          key={idx}
                          className="bg-yellow-600/50 text-yellow-100 rounded px-0.5"
                        >
                          {segment.text}
                        </span>
                      )
                    } else {
                      return (
                        <span key={idx} className="text-gray-300">
                          {segment.text}
                        </span>
                      )
                    }
                  })}
                </div>
              </div>
            )}
            
            {/* New story mode - show selection for new story */}
            {!loadingText && fullText && newStoryMode && (
              <div
                ref={reviewContainerRef}
                onClick={handleNewStoryTextClick}
                className="bg-gray-900 border-2 border-purple-500 rounded-lg p-4 max-h-[65vh] overflow-y-auto cursor-crosshair"
                style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}
              >
                <div className="font-mono text-sm leading-relaxed select-none">
                  {newStorySegments.map((segment, idx) => {
                    if (segment.type === 'selected') {
                      return (
                        <span
                          key={idx}
                          className="bg-purple-600/50 text-purple-100 rounded px-0.5"
                        >
                          {segment.text}
                        </span>
                      )
                    } else {
                      return (
                        <span key={idx} className="text-gray-300">
                          {segment.text}
                        </span>
                      )
                    }
                  })}
                </div>
              </div>
            )}
            
            {!loadingText && !fullText && (
              <div className="text-center py-8">
                <p className="text-gray-400">No text available for this book.</p>
              </div>
            )}
          </div>
          
          {/* Middle column: Stories + Details */}
          <div className="w-72 xl:w-80 2xl:w-96 flex-shrink-0">
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 sticky top-4 max-h-[85vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-white">Stories ({sortedStories.length})</h3>
                {!newStoryMode && !editingBoundary && (
                  <button
                    onClick={handleEnterNewStoryMode}
                    className="px-2 py-1 text-xs bg-purple-600 hover:bg-purple-700 text-white rounded transition-colors"
                  >
                    + New
                  </button>
                )}
              </div>
              
              {/* Story list - compact when story selected */}
              <div className={`overflow-y-auto space-y-1 ${selectedStory ? 'max-h-32' : 'max-h-[50vh]'}`}>
                {sortedStories.map((story) => {
                  const color = STORY_COLORS[story.colorIndex]
                  const isSelected = selectedStory?.title === story.title
                  return (
                    <button
                      key={story.title}
                      onClick={() => {
                        handleStoryClick(story)
                        scrollToStory(story)
                      }}
                      className={`
                        w-full text-left px-2 py-1.5 rounded text-xs transition-colors
                        ${isSelected ? `${color.bg} ${color.border} border` : 'hover:bg-gray-700'}
                      `}
                    >
                      <div className={`font-medium truncate ${isSelected ? color.text : 'text-gray-200'}`}>
                        {story.title}
                      </div>
                      <div className="text-xs text-gray-500 truncate">
                        {story.pages && `p.${story.pages}`}
                        {story.pages && ' • '}
                        {(story.end_char - story.start_char).toLocaleString()} chars
                      </div>
                    </button>
                  )
                })}
              </div>
              
              {/* New story controls */}
              {newStoryMode && (
                <div className="mt-3 p-3 bg-gray-700 rounded-lg border-2 border-purple-500">
                  <h4 className="font-semibold text-purple-400 mb-2 text-sm">New Story</h4>
                  <div className="space-y-2 mb-3">
                    <input
                      type="text"
                      value={newStoryTitle}
                      onChange={(e) => setNewStoryTitle(e.target.value)}
                      placeholder="Story title *"
                      className="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 rounded text-sm text-white placeholder-gray-500"
                    />
                    <input
                      type="text"
                      value={newStoryKeywords}
                      onChange={(e) => setNewStoryKeywords(e.target.value)}
                      placeholder="Keywords (optional)"
                      className="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 rounded text-sm text-white placeholder-gray-500"
                    />
                    <input
                      type="text"
                      value={newStoryPages}
                      onChange={(e) => setNewStoryPages(e.target.value)}
                      placeholder="Pages (optional)"
                      className="w-full px-2 py-1.5 bg-gray-800 border border-gray-600 rounded text-sm text-white placeholder-gray-500"
                    />
                  </div>
                  
                  <div className="text-xs space-y-2 mb-3">
                    <div className={`p-2 rounded ${newStorySelectingStart ? 'bg-green-900/50 border border-green-500' : 'bg-gray-800'}`}>
                      <p className="text-gray-400">Start Position:</p>
                      <p className="text-white font-mono">{newStoryStart?.toLocaleString() ?? '—'}</p>
                      {newStorySelectingStart && <p className="text-green-400 text-xs mt-1">← Click text to set</p>}
                    </div>
                    <div className={`p-2 rounded ${!newStorySelectingStart ? 'bg-yellow-900/50 border border-yellow-500' : 'bg-gray-800'}`}>
                      <p className="text-gray-400">End Position:</p>
                      <p className="text-white font-mono">{newStoryEnd?.toLocaleString() ?? '—'}</p>
                      {!newStorySelectingStart && <p className="text-yellow-400 text-xs mt-1">← Click text to set</p>}
                    </div>
                  </div>
                  
                  <div className="flex gap-2">
                    <button
                      onClick={handleAddNewStory}
                      disabled={addingStory || !newStoryTitle.trim() || newStoryStart === null || newStoryEnd === null || newStoryEnd <= newStoryStart}
                      className="flex-1 px-3 py-1.5 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white text-sm font-medium rounded transition-colors"
                    >
                      {addingStory ? 'Adding...' : 'Add Story'}
                    </button>
                    <button
                      onClick={handleCancelNewStory}
                      disabled={addingStory}
                      className="flex-1 px-3 py-1.5 bg-gray-600 hover:bg-gray-500 text-white text-sm font-medium rounded transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
              
              {/* Boundary editing controls */}
              {selectedStory && editingBoundary && (
                <div className="mt-3 p-3 bg-gray-700 rounded-lg border-2 border-blue-500">
                  <h4 className="font-semibold text-blue-400 mb-2 text-sm">Editing Boundaries</h4>
                  <p className="text-xs text-gray-300 mb-2 truncate" title={selectedStory.title}>{selectedStory.title}</p>
                  
                  <div className="text-xs space-y-2 mb-3">
                    <div className={`p-2 rounded ${selectingStart ? 'bg-blue-900/50 border border-blue-500' : 'bg-gray-800'}`}>
                      <p className="text-gray-400">Start Position:</p>
                      <p className="text-white font-mono">{editedStart.toLocaleString()}</p>
                      {selectingStart && <p className="text-blue-400 text-xs mt-1">← Click text to set</p>}
                    </div>
                    <div className={`p-2 rounded ${!selectingStart ? 'bg-green-900/50 border border-green-500' : 'bg-gray-800'}`}>
                      <p className="text-gray-400">End Position:</p>
                      <p className="text-white font-mono">{editedEnd.toLocaleString()}</p>
                      {!selectingStart && <p className="text-green-400 text-xs mt-1">← Click text to set</p>}
                    </div>
                    <div className="p-2 bg-gray-800 rounded">
                      <p className="text-gray-400">Selection Length:</p>
                      <p className="text-white font-mono">
                        {editedEnd > editedStart 
                          ? (editedEnd - editedStart).toLocaleString() + ' chars'
                          : '—'}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex gap-2">
                    <button
                      onClick={handleSaveBoundaries}
                      disabled={savingBoundaries || editedEnd <= editedStart}
                      className="flex-1 px-3 py-1.5 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white text-sm font-medium rounded transition-colors"
                    >
                      {savingBoundaries ? 'Saving...' : 'Save'}
                    </button>
                    <button
                      onClick={handleCancelBoundaryEdit}
                      disabled={savingBoundaries}
                      className="flex-1 px-3 py-1.5 bg-gray-600 hover:bg-gray-500 text-white text-sm font-medium rounded transition-colors"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
              
              {/* Selected story details */}
              {selectedStory && !editingBoundary && !newStoryMode && (
                <div className="mt-3 p-3 bg-gray-700 rounded-lg border border-green-600">
                  <h4 className="text-xs font-medium text-gray-400 mb-1">Selected Story</h4>
                  {editingTitle ? (
                    <div className="mb-2">
                      <input
                        type="text"
                        value={newTitle}
                        onChange={(e) => setNewTitle(e.target.value)}
                        className="w-full px-2 py-1 bg-gray-800 border border-gray-600 rounded text-sm text-white"
                        autoFocus
                      />
                      <div className="flex gap-2 mt-2">
                        <button
                          onClick={handleSaveTitle}
                          className="flex-1 px-2 py-1 bg-green-600 hover:bg-green-700 text-white text-xs rounded"
                        >
                          Save
                        </button>
                        <button
                          onClick={handleCancelEditTitle}
                          className="flex-1 px-2 py-1 bg-gray-600 hover:bg-gray-500 text-white text-xs rounded"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <h4 className="font-semibold text-green-400 mb-2 text-sm">{selectedStory.title}</h4>
                  )}
                  <div className="text-xs text-gray-300 space-y-1">
                    {selectedStory.pages && <p>Pages: {selectedStory.pages}</p>}
                    {editingKeywords ? (
                      <div className="space-y-1">
                        <p className="text-gray-400">Keywords:</p>
                        <input
                          type="text"
                          value={editedKeywords}
                          onChange={(e) => setEditedKeywords(e.target.value)}
                          placeholder="ghost, haunting, supernatural"
                          className="w-full px-2 py-1 bg-gray-800 border border-gray-600 rounded text-white text-xs"
                        />
                        <div className="flex gap-1">
                          <button
                            onClick={handleSaveKeywords}
                            disabled={savingKeywords}
                            className="flex-1 px-2 py-1 bg-green-600 hover:bg-green-700 text-white text-xs rounded disabled:opacity-50"
                          >
                            {savingKeywords ? '...' : 'Save'}
                          </button>
                          <button
                            onClick={handleCancelEditKeywords}
                            className="flex-1 px-2 py-1 bg-gray-600 hover:bg-gray-500 text-white text-xs rounded"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1">
                        <p className="flex-1 truncate">Keywords: {selectedStory.keywords || <span className="italic text-gray-500">none</span>}</p>
                        <button
                          onClick={handleStartEditKeywords}
                          className="px-1.5 py-0.5 bg-gray-600 text-white rounded hover:bg-gray-500 text-xs flex-shrink-0"
                        >
                          ✎
                        </button>
                      </div>
                    )}
                    <p>Chars: {selectedStory.start_char.toLocaleString()} – {selectedStory.end_char.toLocaleString()}</p>
                    <p>Length: {(selectedStory.end_char - selectedStory.start_char).toLocaleString()}</p>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button
                      onClick={handleStartBoundaryEdit}
                      className="flex-1 px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded transition-colors"
                    >
                      Edit Bounds
                    </button>
                    {!editingTitle && (
                      <button
                        onClick={handleStartEditTitle}
                        className="flex-1 px-2 py-1 bg-amber-600 hover:bg-amber-700 text-white text-xs font-medium rounded transition-colors"
                      >
                        Edit Title
                      </button>
                    )}
                    <button
                      onClick={handleDeleteStory}
                      className="px-2 py-1 bg-red-600 hover:bg-red-700 text-white text-xs font-medium rounded transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              )}
              
              {/* Color legend */}
              <div className="mt-3 pt-3 border-t border-gray-700">
                <p className="text-xs text-gray-500 mb-2">Color Legend</p>
                <div className="flex flex-wrap gap-1">
                  {STORY_COLORS.map((color, idx) => (
                    <div
                      key={idx}
                      className={`w-3 h-3 rounded ${color.bg} ${color.border} border`}
                      title={`Story color ${idx + 1}`}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>
          
          {/* Right column: Category Assignment */}
          <div className="w-72 xl:w-80 2xl:w-96 flex-shrink-0">
            <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 sticky top-4 max-h-[85vh] overflow-y-auto">
              <h3 className="text-sm font-semibold text-white mb-3">Category Assignment</h3>
              
              {!selectedStory ? (
                <div className="text-center py-8 text-gray-500">
                  <p className="text-sm">Select a story to assign categories</p>
                </div>
              ) : (
                <>
                  {/* Current Assignments */}
                  <div className="mb-4">
                    <p className="text-xs text-gray-400 mb-2">Current Assignments:</p>
                    {currentAssignments.length === 0 ? (
                      <p className="text-xs text-gray-500 italic">Not assigned to any category</p>
                    ) : (
                      <div className="space-y-2">
                        {currentAssignments.map((path, idx) => (
                          <div
                            key={idx}
                            className="p-2 bg-gray-700 rounded text-xs"
                            title={path.join(' > ')}
                          >
                            <div className="flex items-start justify-between gap-1">
                              <div className="flex-1 min-w-0 text-gray-200">
                                {path.join(' › ')}
                              </div>
                              <button
                                onClick={() => handleRemoveCategory(path)}
                                disabled={assigning}
                                className="px-1.5 py-0.5 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex-shrink-0"
                              >
                                ×
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                  
                  {/* AI Suggestions Section */}
                  <div className="mb-4 p-3 bg-gradient-to-br from-purple-900/30 to-blue-900/30 rounded-lg border border-purple-500/50">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">🤖</span>
                      <h4 className="text-sm font-medium text-purple-300">AI Category Suggestions</h4>
                    </div>
                    
                    <button
                      onClick={handleAutoSuggest}
                      disabled={loadingAiSuggestions || !fullText}
                      className="w-full px-3 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white text-sm font-medium rounded transition-colors mb-3"
                    >
                      {loadingAiSuggestions ? (
                        <span className="flex items-center justify-center gap-2">
                          <span className="animate-spin">⏳</span> Analyzing story...
                        </span>
                      ) : (
                        '✨ Auto-Suggest Categories'
                      )}
                    </button>
                    
                    {aiError && (
                      <div className="p-2 bg-red-900/50 border border-red-500 rounded text-xs text-red-200 mb-3">
                        {aiError}
                      </div>
                    )}
                    
                    {aiSuggestions.length > 0 && (
                      <div className="space-y-2">
                        {aiSuggestions.map((suggestion, idx) => (
                          <label
                            key={idx}
                            className={`flex items-start gap-2 p-2 rounded cursor-pointer transition-colors ${
                              suggestion.confirmed 
                                ? 'bg-green-900/40 border border-green-500' 
                                : 'bg-gray-800 border border-gray-600 hover:border-gray-500'
                            }`}
                          >
                            <input
                              type="checkbox"
                              checked={suggestion.confirmed}
                              onChange={() => handleToggleSuggestion(idx)}
                              className="mt-0.5 rounded border-gray-500 text-green-500 focus:ring-green-500"
                            />
                            <div className="flex-1 min-w-0">
                              <div className="text-xs text-gray-200 mb-1">
                                {suggestion.path.join(' › ')}
                              </div>
                              <div className="flex items-center gap-2 text-xs">
                                <span className={`px-1.5 py-0.5 rounded ${
                                  suggestion.confidence >= 0.8 ? 'bg-green-600 text-white' :
                                  suggestion.confidence >= 0.5 ? 'bg-yellow-600 text-white' :
                                  'bg-gray-600 text-gray-200'
                                }`}>
                                  {Math.round(suggestion.confidence * 100)}%
                                </span>
                                {suggestion.reason && (
                                  <span className="text-gray-400 truncate" title={suggestion.reason}>
                                    {suggestion.reason}
                                  </span>
                                )}
                              </div>
                            </div>
                          </label>
                        ))}
                        
                        <button
                          onClick={handleCommitConfirmed}
                          disabled={committingAll || aiSuggestions.filter(s => s.confirmed).length === 0}
                          className="w-full mt-3 px-3 py-2 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed text-white text-sm font-medium rounded transition-colors"
                        >
                          {committingAll ? (
                            <span className="flex items-center justify-center gap-2">
                              <span className="animate-spin">⏳</span> Committing...
                            </span>
                          ) : (
                            `✓ Commit ${aiSuggestions.filter(s => s.confirmed).length} Confirmed`
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                  
                  {/* Manual Assignment */}
                  <div className="border-t border-gray-700 pt-3">
                    <p className="text-xs text-gray-400 mb-2">Manual Assignment:</p>
                    <div className="space-y-1.5 mb-2">
                      {codexTree ? (
                        <>
                          {/* Level 1 */}
                          <select
                            value={selectedPath[0] || ''}
                            onChange={(e) => handlePathLevelChange(0, e.target.value)}
                            className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
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
                              className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
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
                              className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
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
                              className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                            >
                              <option value="">Select subcategory...</option>
                              {getPathOptions(codexTree, [selectedPath[0], selectedPath[1], selectedPath[2]]).map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          )}
                          
                          {/* Level 5+ */}
                          {selectedPath.length >= 4 && getPathOptions(codexTree, selectedPath.slice(0, 4)).length > 0 && (
                            <select
                              value={selectedPath[4] || ''}
                              onChange={(e) => handlePathLevelChange(4, e.target.value)}
                              className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                            >
                              <option value="">Select subcategory...</option>
                              {getPathOptions(codexTree, selectedPath.slice(0, 4)).map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          )}
                          
                          {selectedPath.length >= 5 && getPathOptions(codexTree, selectedPath.slice(0, 5)).length > 0 && (
                            <select
                              value={selectedPath[5] || ''}
                              onChange={(e) => handlePathLevelChange(5, e.target.value)}
                              className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                            >
                              <option value="">Select subcategory...</option>
                              {getPathOptions(codexTree, selectedPath.slice(0, 5)).map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          )}
                          
                          {selectedPath.length >= 6 && getPathOptions(codexTree, selectedPath.slice(0, 6)).length > 0 && (
                            <select
                              value={selectedPath[6] || ''}
                              onChange={(e) => handlePathLevelChange(6, e.target.value)}
                              className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                            >
                              <option value="">Select subcategory...</option>
                              {getPathOptions(codexTree, selectedPath.slice(0, 6)).map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          )}
                          
                          {selectedPath.length >= 7 && getPathOptions(codexTree, selectedPath.slice(0, 7)).length > 0 && (
                            <select
                              value={selectedPath[7] || ''}
                              onChange={(e) => handlePathLevelChange(7, e.target.value)}
                              className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                            >
                              <option value="">Select subcategory...</option>
                              {getPathOptions(codexTree, selectedPath.slice(0, 7)).map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          )}
                        </>
                      ) : (
                        <p className="text-xs text-gray-500">Loading categories...</p>
                      )}
                    </div>
                    
                    {/* Selected Path Display */}
                    {selectedPath.length > 0 && (
                      <div className="mb-2 p-2 bg-gray-700 rounded text-xs text-gray-200">
                        {selectedPath.join(' › ')}
                      </div>
                    )}
                    
                    {/* Assign Button */}
                    <button
                      onClick={handleAssignCategory}
                      disabled={selectedPath.length === 0 || assigning}
                      className="w-full px-3 py-1.5 bg-green-600 text-white rounded text-sm hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                      {assigning ? 'Assigning...' : 'Assign Manually'}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
        </div>
      </main>
    </div>
  )
}

export default BookDetail
