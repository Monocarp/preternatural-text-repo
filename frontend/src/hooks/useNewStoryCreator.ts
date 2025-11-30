// src/hooks/useNewStoryCreator.ts
/**
 * Hook for creating new stories with text boundary selection.
 * 
 * Used by SearchCurate, BookDetail, and Archive.
 * 
 * Key differences between implementations:
 * - SearchCurate: Uses selectedStory.book_slug, shared textContainerRef with boundary editing
 * - BookDetail: Uses route param slug, uses reviewContainerRef
 * - Archive: Requires explicit bookSlug to be set, separate textContainerRef
 * 
 * This hook is flexible enough to accommodate all three patterns.
 */

import { useState, useCallback, useRef, useMemo } from 'react'
import type { RefObject } from 'react'
import axios from '../utils/axios'
import { calculateCharPositionFromClick } from './useTextPositionClick'

interface UseNewStoryCreatorOptions {
  /** Called after successful creation */
  onSuccess?: (response: any) => void
  /** Called on error */
  onError?: (error: any) => void
  /** Whether to use stopPropagation on text clicks */
  stopPropagation?: boolean
  /** Whether to use indexOf fallback for position calculation */
  useIndexOfFallback?: boolean
}

interface UseNewStoryCreatorReturn {
  // State
  isActive: boolean
  bookSlug: string
  start: number | null
  end: number | null
  selectingStart: boolean
  title: string
  keywords: string
  pages: string
  adding: boolean
  fullText: string
  loadingFullText: boolean
  
  // Refs
  textContainerRef: RefObject<HTMLDivElement | null>
  
  // Computed
  canAdd: boolean
  previewText: string
  
  // Actions
  startCreating: (bookSlug: string) => Promise<void>
  handleTextClick: (e: React.MouseEvent<HTMLDivElement>) => void
  setTitle: (title: string) => void
  setKeywords: (keywords: string) => void
  setPages: (pages: string) => void
  addStory: (forceOverlap?: boolean) => Promise<boolean>
  cancel: () => void
  
  // Manual position setters (for external control)
  setStart: (pos: number | null) => void
  setEnd: (pos: number | null) => void
}

export function useNewStoryCreator(
  options: UseNewStoryCreatorOptions = {}
): UseNewStoryCreatorReturn {
  const { onSuccess, onError, stopPropagation = false, useIndexOfFallback = true } = options
  
  // Main state
  const [isActive, setIsActive] = useState(false)
  const [bookSlug, setBookSlug] = useState('')
  const [start, setStart] = useState<number | null>(null)
  const [end, setEnd] = useState<number | null>(null)
  const [selectingStart, setSelectingStart] = useState(true)
  const [title, setTitle] = useState('')
  const [keywords, setKeywords] = useState('')
  const [pages, setPages] = useState('')
  const [adding, setAdding] = useState(false)
  
  // Full text state
  const [fullText, setFullText] = useState('')
  const [loadingFullText, setLoadingFullText] = useState(false)
  
  const textContainerRef = useRef<HTMLDivElement>(null)
  
  // Can add if we have all required fields
  const canAdd = useMemo(() => {
    return isActive && 
           bookSlug !== '' && 
           start !== null && 
           end !== null && 
           end > start && 
           title.trim() !== ''
  }, [isActive, bookSlug, start, end, title])
  
  // Preview text (first 100 chars of selection)
  const previewText = useMemo(() => {
    if (!fullText || start === null || end === null) return ''
    return fullText.substring(start, Math.min(start + 100, end)) + '...'
  }, [fullText, start, end])
  
  // Start creating a new story
  const startCreating = useCallback(async (slug: string) => {
    setIsActive(true)
    setBookSlug(slug)
    setStart(null)
    setEnd(null)
    setSelectingStart(true)
    setTitle('')
    setKeywords('')
    setPages('')
    
    // Load full text for the book
    setLoadingFullText(true)
    try {
      const res = await axios.get(`/full-text/${slug}`)
      setFullText(res.data.text)
    } catch (err) {
      console.error('Error loading full text:', err)
      setIsActive(false)
      onError?.(err)
    } finally {
      setLoadingFullText(false)
    }
  }, [onError])
  
  // Handle text click to select position
  const handleTextClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!isActive || !fullText) return
    
    const charPos = calculateCharPositionFromClick(
      e,
      textContainerRef,
      fullText.length,
      { stopPropagation, useIndexOfFallback }
    )
    
    if (charPos === null) return
    
    if (selectingStart) {
      setStart(charPos)
      setSelectingStart(false)
    } else {
      // Ensure end is after start
      setEnd(Math.max(charPos, start || 0))
      setSelectingStart(true)
    }
  }, [isActive, fullText, selectingStart, start, stopPropagation, useIndexOfFallback])
  
  // Cancel creation
  const cancel = useCallback(() => {
    setIsActive(false)
    setBookSlug('')
    setStart(null)
    setEnd(null)
    setSelectingStart(true)
    setTitle('')
    setKeywords('')
    setPages('')
    setFullText('')
  }, [])
  
  // Add the story
  const addStory = useCallback(async (forceOverlap = false): Promise<boolean> => {
    if (!canAdd) return false
    
    const bookName = bookSlug.replace(/_/g, ' ')
    if (!forceOverlap && !confirm(`Add new story "${title}" to ${bookName}?`)) {
      return false
    }
    
    setAdding(true)
    try {
      const response = await axios.post('/add-story', {
        book_slug: bookSlug,
        title: title.trim(),
        keywords: keywords.trim(),
        pages: pages.trim(),
        start_char: start,
        end_char: end,
        force_overlap: forceOverlap,
      })
      
      // Check if overlap warning was returned
      if (response.data?.status === 'overlap_warning' && !forceOverlap) {
        const overlaps = response.data.overlaps || []
        const overlapMsg = overlaps
          .map((o: any) => `  • ${o.title} (${o.overlap_percent}% overlap)`)
          .join('\n')
        const confirmMsg = `Warning: This story overlaps with existing stories:\n\n${overlapMsg}\n\nAdd anyway?`
        
        if (!confirm(confirmMsg)) {
          setAdding(false)
          return false
        }
        
        // Retry with force
        return addStory(true)
      }
      
      // Success
      onSuccess?.(response.data)
      cancel()
      alert(`Story "${title}" added successfully and is now searchable!`)
      return true
    } catch (err: any) {
      console.error('Error adding story:', err)
      const status = err?.response?.status
      const errorDetail = err?.response?.data?.detail || err?.response?.data?.message || 'Unknown error'
      
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to add stories.')
      } else if (status === 400) {
        alert(`Bad request: ${errorDetail}`)
      } else {
        alert(`Failed to add story: ${errorDetail}`)
      }
      onError?.(err)
      return false
    } finally {
      setAdding(false)
    }
  }, [canAdd, bookSlug, title, keywords, pages, start, end, onSuccess, onError, cancel])
  
  return {
    isActive,
    bookSlug,
    start,
    end,
    selectingStart,
    title,
    keywords,
    pages,
    adding,
    fullText,
    loadingFullText,
    textContainerRef,
    canAdd,
    previewText,
    startCreating,
    handleTextClick,
    setTitle,
    setKeywords,
    setPages,
    addStory,
    cancel,
    setStart,
    setEnd,
  }
}
