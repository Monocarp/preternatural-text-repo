// src/hooks/useKeywordsEditor.ts
/**
 * Hook for inline keywords editing.
 * 
 * Used by SearchCurate, BookDetail, and Archive for editing story keywords.
 * All implementations are essentially identical.
 */

import { useState, useCallback } from 'react'
import { useStackApp } from '@stackframe/react'
import axios from '../utils/axios'

export interface Story {
  title: string
  book_slug: string
  keywords?: string
}

interface UseKeywordsEditorOptions {
  /** Called after successful save with new keywords */
  onSaveSuccess?: (story: Story, newKeywords: string) => void
  /** Called on error */
  onError?: (error: any) => void
}

interface UseKeywordsEditorReturn {
  // State
  isEditing: boolean
  editedKeywords: string
  saving: boolean
  
  // Actions
  startEditing: (story: Story) => void
  setEditedKeywords: (keywords: string) => void
  saveKeywords: (story: Story) => Promise<void>
  cancelEditing: () => void
}

export function useKeywordsEditor(
  options: UseKeywordsEditorOptions = {}
): UseKeywordsEditorReturn {
  const { onSaveSuccess, onError } = options
  const app = useStackApp()
  
  const [isEditing, setIsEditing] = useState(false)
  const [editedKeywords, setEditedKeywords] = useState('')
  const [saving, setSaving] = useState(false)
  
  const startEditing = useCallback((story: Story) => {
    setIsEditing(true)
    setEditedKeywords(story.keywords || '')
  }, [])
  
  const cancelEditing = useCallback(() => {
    setIsEditing(false)
    setEditedKeywords('')
  }, [])
  
  const saveKeywords = useCallback(async (story: Story) => {
    if (!story) return
    
    setSaving(true)
    try {
      const user = await app.getUser()
      if (!user) {
        alert('You must be logged in to edit keywords.')
        setSaving(false)
        return
      }
      
      await axios.post('/update-keywords', {
        title: story.title,
        book_slug: story.book_slug,
        keywords: editedKeywords.trim()
      })
      
      onSaveSuccess?.(story, editedKeywords.trim())
      setIsEditing(false)
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
      onError?.(err)
    } finally {
      setSaving(false)
    }
  }, [app, editedKeywords, onSaveSuccess, onError])
  
  return {
    isEditing,
    editedKeywords,
    saving,
    startEditing,
    setEditedKeywords,
    saveKeywords,
    cancelEditing,
  }
}
