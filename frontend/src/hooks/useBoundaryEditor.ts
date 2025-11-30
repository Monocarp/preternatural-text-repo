// src/hooks/useBoundaryEditor.ts
/**
 * Hook for managing story boundary editing state and logic.
 * 
 * Used by SearchCurate, BookDetail, and Archive for adjusting story start/end positions.
 * 
 * Different behaviors across components:
 * - SearchCurate: Resets to story's original boundaries on cancel
 * - BookDetail: Allows clicking before start to set new start (smarter UX)
 * - Archive: Similar to SearchCurate but tracks the story being edited separately
 */

import { useState, useCallback, useRef } from 'react'
import type { RefObject } from 'react'
import { calculateCharPositionFromClick } from './useTextPositionClick'

interface Story {
  title: string
  book_slug: string
  start_char: number
  end_char: number
  pages?: string
  keywords?: string
}

interface UseBoundaryEditorOptions {
  /** Called when save is triggered (should call API) */
  onSave?: (story: Story, startChar: number, endChar: number) => Promise<void>
  /** Called when boundaries are saved successfully */
  onSaveSuccess?: (story: Story, startChar: number, endChar: number) => void
  /** Called when cancel is triggered */
  onCancel?: () => void
  /** If true, clicking before start sets new start instead of ensuring end >= start */
  smartStartSelection?: boolean
  /** Whether to use stopPropagation on clicks */
  stopPropagation?: boolean
  /** Whether to use indexOf fallback for position calculation */
  useIndexOfFallback?: boolean
}

interface UseBoundaryEditorReturn {
  // State
  isEditing: boolean
  editedStart: number
  editedEnd: number
  selectingStart: boolean
  saving: boolean
  
  // Refs
  textContainerRef: RefObject<HTMLDivElement>
  
  // Actions
  startEditing: (story: Story) => void
  cancelEditing: () => void
  handleTextClick: (e: React.MouseEvent<HTMLDivElement>) => void
  saveBoundaries: () => Promise<void>
  
  // Manual setters (for external control)
  setEditedStart: (pos: number) => void
  setEditedEnd: (pos: number) => void
}

export function useBoundaryEditor(
  fullText: string,
  currentStory: Story | null,
  options: UseBoundaryEditorOptions = {}
): UseBoundaryEditorReturn {
  const {
    onSave,
    onSaveSuccess,
    onCancel,
    smartStartSelection = false,
    stopPropagation = false,
    useIndexOfFallback = true,
  } = options
  
  const [isEditing, setIsEditing] = useState(false)
  const [editedStart, setEditedStart] = useState(0)
  const [editedEnd, setEditedEnd] = useState(0)
  const [selectingStart, setSelectingStart] = useState(true)
  const [saving, setSaving] = useState(false)
  
  const textContainerRef = useRef<HTMLDivElement>(null)
  
  // Start editing with current story's boundaries
  const startEditing = useCallback((story: Story) => {
    setIsEditing(true)
    setEditedStart(story.start_char)
    setEditedEnd(story.end_char)
    setSelectingStart(true)
  }, [])
  
  // Cancel editing
  const cancelEditing = useCallback(() => {
    setIsEditing(false)
    // Reset to original if we have a story
    if (currentStory) {
      setEditedStart(currentStory.start_char)
      setEditedEnd(currentStory.end_char)
    } else {
      setEditedStart(0)
      setEditedEnd(0)
    }
    setSelectingStart(true)
    onCancel?.()
  }, [currentStory, onCancel])
  
  // Handle click on text to set boundary position
  const handleTextClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!isEditing || !fullText) return
    
    const charPos = calculateCharPositionFromClick(
      e,
      textContainerRef,
      fullText.length,
      { stopPropagation, useIndexOfFallback }
    )
    
    if (charPos === null) return
    
    if (selectingStart) {
      setEditedStart(charPos)
      setSelectingStart(false)
    } else {
      if (smartStartSelection && charPos <= editedStart) {
        // BookDetail behavior: treat as new start if clicked before current start
        setEditedStart(charPos)
      } else {
        // SearchCurate/Archive behavior: ensure end >= start
        setEditedEnd(Math.max(charPos, editedStart))
      }
      setSelectingStart(true)
    }
  }, [isEditing, fullText, selectingStart, editedStart, smartStartSelection, stopPropagation, useIndexOfFallback])
  
  // Save boundaries
  const saveBoundaries = useCallback(async () => {
    if (!currentStory || !onSave) return
    
    if (editedEnd <= editedStart) {
      alert('End position must be after start position.')
      return
    }
    
    setSaving(true)
    try {
      await onSave(currentStory, editedStart, editedEnd)
      onSaveSuccess?.(currentStory, editedStart, editedEnd)
      setIsEditing(false)
    } catch (err) {
      console.error('Error saving boundaries:', err)
      throw err // Let caller handle the error display
    } finally {
      setSaving(false)
    }
  }, [currentStory, editedStart, editedEnd, onSave, onSaveSuccess])
  
  return {
    isEditing,
    editedStart,
    editedEnd,
    selectingStart,
    saving,
    textContainerRef,
    startEditing,
    cancelEditing,
    handleTextClick,
    saveBoundaries,
    setEditedStart,
    setEditedEnd,
  }
}
