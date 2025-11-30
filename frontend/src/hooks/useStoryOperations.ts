/**
 * Shared hooks for story operations across Archive, BookDetail, and SearchCurate pages.
 * 
 * Centralizes the logic for:
 * - Boundary editing (update start/end character positions)
 * - Title editing
 * - Keywords editing
 * - New story creation
 * - Text position picking (click-to-select character position)
 */

import { useState, useCallback } from 'react'
import type { RefObject } from 'react'
import axios from '../utils/axios'

// ============================================================================
// Types
// ============================================================================

export interface Story {
  title: string
  book_slug: string
  start_char: number
  end_char: number
  keywords?: string
  pages?: string
  [key: string]: any
}

export interface BoundaryEditorState {
  editing: boolean
  editedStart: number
  editedEnd: number
  saving: boolean
  selectingStart: boolean
  fullText: string | null
  loadingFullText: boolean
}

export interface NewStoryState {
  active: boolean
  bookSlug: string
  start: number | null
  end: number | null
  selectingStart: boolean
  title: string
  keywords: string
  pages: string
  adding: boolean
}

// ============================================================================
// useStoryBoundaries - Edit story start/end character positions
// ============================================================================

export interface UseStoryBoundariesOptions {
  onSuccess?: (story: Story, newStart: number, newEnd: number) => void
  onError?: (error: any) => void
}

export function useStoryBoundaries(options: UseStoryBoundariesOptions = {}) {
  const [state, setState] = useState<BoundaryEditorState>({
    editing: false,
    editedStart: 0,
    editedEnd: 0,
    saving: false,
    selectingStart: true,
    fullText: null,
    loadingFullText: false,
  })

  const startEditing = useCallback(async (story: Story) => {
    // First set editing mode and load full text
    setState(prev => ({
      ...prev,
      editing: true,
      editedStart: story.start_char,
      editedEnd: story.end_char,
      saving: false,
      selectingStart: true,
      loadingFullText: true,
    }))
    
    // Load full text from API
    try {
      const res = await axios.get(`/full-text/${story.book_slug}`)
      setState(prev => ({
        ...prev,
        fullText: res.data.text,
        loadingFullText: false,
      }))
    } catch (err) {
      console.error('Error loading full text:', err)
      setState(prev => ({
        ...prev,
        loadingFullText: false,
      }))
    }
  }, [])

  const setEditedStart = useCallback((pos: number) => {
    setState(prev => ({ ...prev, editedStart: pos }))
  }, [])

  const setEditedEnd = useCallback((pos: number) => {
    setState(prev => ({ ...prev, editedEnd: pos }))
  }, [])

  const setSelectingStart = useCallback((selecting: boolean) => {
    setState(prev => ({ ...prev, selectingStart: selecting }))
  }, [])

  const cancel = useCallback(() => {
    setState({
      editing: false,
      editedStart: 0,
      editedEnd: 0,
      saving: false,
      selectingStart: true,
      fullText: null,
      loadingFullText: false,
    })
  }, [])

  const save = useCallback(async (story: Story) => {
    if (state.editedEnd <= state.editedStart) {
      alert('End position must be after start position.')
      return false
    }

    setState(prev => ({ ...prev, saving: true }))
    
    try {
      await axios.post('/update-boundaries', {
        title: story.title,
        book_slug: story.book_slug,
        start_char: state.editedStart,
        end_char: state.editedEnd,
      })

      options.onSuccess?.(story, state.editedStart, state.editedEnd)
      
      setState({
        editing: false,
        editedStart: 0,
        editedEnd: 0,
        saving: false,
        selectingStart: true,
        fullText: null,
        loadingFullText: false,
      })
      
      return true
    } catch (err: any) {
      console.error('Error saving boundaries:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to save boundaries.')
      } else {
        alert('Failed to save boundaries. Please try again.')
      }
      options.onError?.(err)
      setState(prev => ({ ...prev, saving: false }))
      return false
    }
  }, [state.editedStart, state.editedEnd, options])

  return {
    ...state,
    startEditing,
    setEditedStart,
    setEditedEnd,
    setSelectingStart,
    cancel,
    save,
  }
}

// ============================================================================
// useStoryTitle - Edit story title
// ============================================================================

export interface UseStoryTitleOptions {
  onSuccess?: (oldTitle: string, newTitle: string) => void
  onError?: (error: any) => void
}

export function useStoryTitle(options: UseStoryTitleOptions = {}) {
  const [editing, setEditing] = useState(false)
  const [newTitle, setNewTitle] = useState('')
  const [saving, setSaving] = useState(false)

  const startEditing = useCallback((currentTitle: string) => {
    setEditing(true)
    setNewTitle(currentTitle)
  }, [])

  const cancel = useCallback(() => {
    setEditing(false)
    setNewTitle('')
  }, [])

  const save = useCallback(async (
    story: Story,
    existingTitles: string[] = []
  ) => {
    const trimmedTitle = newTitle.trim()
    
    if (!trimmedTitle) {
      alert('Title cannot be empty.')
      return false
    }

    // Check for duplicate title
    const isDuplicate = existingTitles.some(
      t => t.toLowerCase() === trimmedTitle.toLowerCase() && t !== story.title
    )
    if (isDuplicate) {
      alert('A story with this title already exists in this book.')
      return false
    }

    setSaving(true)
    
    try {
      await axios.post('/update-title', {
        old_title: story.title,
        new_title: trimmedTitle,
        book_slug: story.book_slug,
      })

      options.onSuccess?.(story.title, trimmedTitle)
      
      setEditing(false)
      setNewTitle('')
      setSaving(false)
      
      return true
    } catch (err: any) {
      console.error('Error updating title:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to edit titles.')
      } else {
        alert('Failed to update title. Please try again.')
      }
      options.onError?.(err)
      setSaving(false)
      return false
    }
  }, [newTitle, options])

  return {
    editing,
    newTitle,
    saving,
    setNewTitle,
    startEditing,
    cancel,
    save,
  }
}

// ============================================================================
// useStoryKeywords - Edit story keywords
// ============================================================================

export interface UseStoryKeywordsOptions {
  onSuccess?: (story: Story, keywords: string) => void
  onError?: (error: any) => void
}

export function useStoryKeywords(options: UseStoryKeywordsOptions = {}) {
  const [editing, setEditing] = useState(false)
  const [editedKeywords, setEditedKeywords] = useState('')
  const [saving, setSaving] = useState(false)

  const startEditing = useCallback((currentKeywords: string) => {
    setEditing(true)
    setEditedKeywords(currentKeywords || '')
  }, [])

  const cancel = useCallback(() => {
    setEditing(false)
    setEditedKeywords('')
  }, [])

  const save = useCallback(async (story: Story) => {
    setSaving(true)
    
    try {
      await axios.post('/update-keywords', {
        title: story.title,
        book_slug: story.book_slug,
        keywords: editedKeywords.trim(),
      })

      options.onSuccess?.(story, editedKeywords.trim())
      
      setEditing(false)
      setEditedKeywords('')
      setSaving(false)
      
      return true
    } catch (err: any) {
      console.error('Error updating keywords:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to edit keywords.')
      } else {
        alert('Failed to update keywords. Please try again.')
      }
      options.onError?.(err)
      setSaving(false)
      return false
    }
  }, [editedKeywords, options])

  return {
    editing,
    editedKeywords,
    saving,
    setEditedKeywords,
    startEditing,
    cancel,
    save,
  }
}

// ============================================================================
// useNewStoryCreator - Create new stories
// ============================================================================

export interface UseNewStoryCreatorOptions {
  onSuccess?: (story: any) => void
  onError?: (error: any) => void
}

export function useNewStoryCreator(options: UseNewStoryCreatorOptions = {}) {
  const [state, setState] = useState<NewStoryState>({
    active: false,
    bookSlug: '',
    start: null,
    end: null,
    selectingStart: true,
    title: '',
    keywords: '',
    pages: '',
    adding: false,
  })
  const [fullText, setFullText] = useState('')

  const startCreating = useCallback(async (bookSlug: string) => {
    setState(prev => ({
      ...prev,
      active: true,
      bookSlug,
      start: null,
      end: null,
      selectingStart: true,
      title: '',
      keywords: '',
      pages: '',
    }))

    try {
      const res = await axios.get(`/full-text/${bookSlug}`)
      setFullText(res.data.text)
    } catch (err) {
      console.error('Error loading full text:', err)
      setState(prev => ({ ...prev, active: false }))
    }
  }, [])

  const setStart = useCallback((pos: number | null) => {
    setState(prev => ({ ...prev, start: pos }))
  }, [])

  const setEnd = useCallback((pos: number | null) => {
    setState(prev => ({ ...prev, end: pos }))
  }, [])

  const setSelectingStart = useCallback((selecting: boolean) => {
    setState(prev => ({ ...prev, selectingStart: selecting }))
  }, [])

  const setTitle = useCallback((title: string) => {
    setState(prev => ({ ...prev, title }))
  }, [])

  const setKeywords = useCallback((keywords: string) => {
    setState(prev => ({ ...prev, keywords }))
  }, [])

  const setPages = useCallback((pages: string) => {
    setState(prev => ({ ...prev, pages }))
  }, [])

  const cancel = useCallback(() => {
    setState({
      active: false,
      bookSlug: '',
      start: null,
      end: null,
      selectingStart: true,
      title: '',
      keywords: '',
      pages: '',
      adding: false,
    })
    setFullText('')
  }, [])

  const canAdd = state.start !== null && 
                 state.end !== null && 
                 state.title.trim() !== '' &&
                 state.end > state.start

  const add = useCallback(async (forceAdd = false) => {
    if (!canAdd) return false

    const bookName = state.bookSlug.replace(/_/g, ' ')
    if (!forceAdd && !confirm(`Add new story "${state.title}" to ${bookName}?`)) {
      return false
    }

    setState(prev => ({ ...prev, adding: true }))

    try {
      const response = await axios.post('/add-story', {
        book_slug: state.bookSlug,
        title: state.title.trim(),
        keywords: state.keywords.trim(),
        pages: state.pages.trim(),
        start_char: state.start,
        end_char: state.end,
      })

      // Handle overlap warning
      if (response.data?.status === 'overlap_warning') {
        const overlaps = response.data.overlaps || []
        const overlapMsg = overlaps
          .map((o: any) => `  • ${o.title} (${o.overlap_percent}% overlap)`)
          .join('\n')
        const confirmMsg = `Warning: This story overlaps with existing stories:\n\n${overlapMsg}\n\nAdd anyway?`

        if (!confirm(confirmMsg)) {
          setState(prev => ({ ...prev, adding: false }))
          return false
        }

        // Force add with overlap
        const forceResponse = await axios.post('/add-story', {
          book_slug: state.bookSlug,
          title: state.title.trim(),
          keywords: state.keywords.trim(),
          pages: state.pages.trim(),
          start_char: state.start,
          end_char: state.end,
  force_overlap: true,
        })
        
        options.onSuccess?.(forceResponse.data)
      } else {:', err)
      console.error('Error response datar?.esponse?.data
        options.onSuccess?.(response.datas
      const errorDetail = err?.response?.data?.detail || err?.response?.data?.mes)age || 'Unknown error'
      }
)
      } else if (status === 400) {
        alert(`Bad request: ${errorDetail}`
      // Reset state
      setState`{:${rrorDl}`
        active: false,
        bookSlug: '',
        start: null,
        end: null,
        selectingStart: true,
        title: '',
        keywords: '',
        pages: '',
        adding: false,
      })
      setFullText('')

      alert('Story added successfully!')
      return true
    } catch (err: any) {
      console.error('Error adding story:', err)
      console.error('Error response data:', err?.response?.data)
      const status = err?.response?.status
      const errorDetail = err?.response?.data?.detail || err?.response?.data?.message || 'Unknown error'
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to add stories.')
      } else if (status === 400) {
        alert(`Bad request: ${errorDetail}`)
      } else {
        alert(`Failed to add story: ${errorDetail}`)
      }
      options.onError?.(err)
      setState(prev => ({ ...prev, adding: false }))
      return false
    }
  }, [state, canAdd, options])

  return {
    ...state,
    fullText,
    canAdd,
    startCreating,
    setStart,
    setEnd,
    setSelectingStart,
    setTitle,
    setKeywords,
    setPages,
    cancel,
    add,
  }
}

// ============================================================================
// useTextPositionPicker - Click-to-select character position in text
// ============================================================================

export interface TextPositionPickerOptions {
  onPositionSelected?: (pos: number) => void
}

/**
 * Calculates character position from a click event on a text container.
 * Used for boundary editing and new story selection.
 */
export function calculateCharacterPosition(
  e: React.MouseEvent<HTMLDivElement>,
  textContainerRef: RefObject<HTMLDivElement>,
  fullText: string
): number | null {
  if (!textContainerRef.current || !fullText) return null

  const textContainer = textContainerRef.current
  const clickX = e.clientX
  const clickY = e.clientY

  // Create a range at the click point
  const range = document.caretRangeFromPoint?.(clickX, clickY)
  if (!range) return null

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
    } else if (
      range.startContainer.contains?.(textNode) ||
      textNode.contains?.(range.startContainer)
    ) {
      if (range.startContainer.nodeType === Node.TEXT_NODE) {
        const rangeText = (range.startContainer as Text).textContent || ''
        const beforeRange =
          textContainer.textContent?.indexOf(rangeText, charPos) || charPos
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
  return Math.min(Math.max(0, charPos), fullText.length)
}

/**
 * Hook for handling text position selection.
 * Returns a click handler that calculates and returns the character position.
 */
export function useTextPositionPicker(
  textContainerRef: RefObject<HTMLDivElement>,
  fullText: string,
  options: TextPositionPickerOptions = {}
) {
  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      e.preventDefault()
      const pos = calculateCharacterPosition(e, textContainerRef, fullText)
      if (pos !== null) {
        options.onPositionSelected?.(pos)
      }
      return pos
    },
    [textContainerRef, fullText, options]
  )

  return { handleClick, calculatePosition: calculateCharacterPosition }
}

// ============================================================================
// useFullTextLoader - Load book full text for editing/creating
// ============================================================================

export function useFullTextLoader() {
  const [fullText, setFullText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async (bookSlug: string) => {
    setLoading(true)
    setError(null)
    try {
      const res = await axios.get(`/full-text/${bookSlug}`)
      setFullText(res.data.text)
      return res.data.text
    } catch (err) {
      console.error('Error loading full text:', err)
      setError('Failed to load book text')
      return null
    } finally {
      setLoading(false)
    }
  }, [])

  const clear = useCallback(() => {
    setFullText('')
    setError(null)
  }, [])

  return { fullText, loading, error, load, clear }
}
