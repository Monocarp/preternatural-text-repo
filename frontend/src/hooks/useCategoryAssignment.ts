// src/hooks/useCategoryAssignment.ts
/**
 * Hook for managing category assignment state and operations.
 * 
 * Used by SearchCurate and BookDetail for assigning stories to codex tree categories.
 * Archive doesn't have category assignment in the UI (it's view-only from assigned categories).
 * 
 * Features:
 * - Loads and caches codex tree
 * - Finds current assignments for a story
 * - Multi-level path selection (up to 8 levels deep)
 * - Assign/remove operations with error handling
 * - AI-suggested categories based on keywords matching category names
 */

import { useState, useCallback, useEffect, useMemo } from 'react'
import axios from '../utils/axios'

export interface Story {
  title: string
  book_slug: string
  start_char: number
  end_char: number
  keywords?: string
  pages?: string
}

interface UseCategoryAssignmentOptions {
  /** Called after successful assignment */
  onAssignSuccess?: (path: string[]) => void
  /** Called after successful removal */
  onRemoveSuccess?: (path: string[]) => void
  /** Called on any error */
  onError?: (error: any, operation: 'assign' | 'remove') => void
}

interface UseCategoryAssignmentReturn {
  // State
  codexTree: any
  selectedPath: string[]
  currentAssignments: string[][]
  suggestedCategories: string[][]
  assigning: boolean
  loading: boolean
  
  // Actions
  loadTree: () => Promise<void>
  setSelectedPath: (path: string[]) => void
  handlePathLevelChange: (level: number, value: string) => void
  assignCategory: () => Promise<void>
  assignToPath: (path: string[]) => Promise<void>
  removeCategory: (path: string[]) => Promise<void>
  
  // Helpers
  getPathOptions: (currentPath?: string[]) => string[]
}

/**
 * Find all paths where a story title appears in the codex tree.
 */
function findAssignmentsInTree(tree: any, title: string, path: string[] = []): string[][] {
  const assignments: string[][] = []
  
  if (typeof tree === 'object' && tree !== null) {
    // Check if this node has stories array
    if (Array.isArray(tree)) {
      if (tree.includes(title)) {
        assignments.push([...path])
      }
    } else if (tree._stories && Array.isArray(tree._stories)) {
      if (tree._stories.includes(title)) {
        assignments.push([...path])
      }
    }
    
    // Recursively check children
    for (const [key, value] of Object.entries(tree)) {
      if (key !== '_stories') {
        assignments.push(...findAssignmentsInTree(value, title, [...path, key]))
      }
    }
  }
  
  return assignments
}

/**
 * Get available child keys at a path in the tree (excluding _stories).
 */
function getOptionsAtPath(tree: any, path: string[]): string[] {
  if (!tree || typeof tree !== 'object') return []
  
  let node = tree
  for (const level of path) {
    if (node[level]) {
      node = node[level]
    } else {
      return []
    }
  }
  
  return Object.keys(node).filter(key => key !== '_stories')
}

/**
 * Generate category suggestions based on keywords matching category names.
 * Uses a scoring system similar to the mobile app.
 */
function generateSuggestions(tree: any, keywords: string | undefined): string[][] {
  if (!keywords || !tree || Object.keys(tree).length === 0) return []

  const keywordList = keywords.toLowerCase().split(',').map(k => k.trim()).filter(Boolean)
  if (keywordList.length === 0) return []
  
  const matches: Array<{ path: string[]; score: number }> = []

  // Recursive function to find all paths and score them
  const findPaths = (node: any, path: string[]) => {
    for (const key of Object.keys(node)) {
      if (key === '_stories') continue
      
      const currentPath = [...path, key]
      const keyLower = key.toLowerCase()
      
      // Score based on keyword matches
      let score = 0
      for (const kw of keywordList) {
        // Exact or contains match
        if (keyLower.includes(kw) || kw.includes(keyLower)) {
          score += 2
        }
        // Partial word match
        const kwWords = kw.split(/\s+/)
        const keyWords = keyLower.split(/\s+/)
        for (const kWord of keyWords) {
          for (const kwWord of kwWords) {
            if (kWord.includes(kwWord) || kwWord.includes(kWord)) {
              score += 1
            }
          }
        }
      }

      if (score > 0) {
        matches.push({ path: currentPath, score })
      }

      // Recurse into children
      const child = node[key]
      if (child && typeof child === 'object' && !Array.isArray(child)) {
        findPaths(child, currentPath)
      }
    }
  }

  findPaths(tree, [])

  // Sort by score and take top 5
  return matches
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)
    .map(m => m.path)
}

export function useCategoryAssignment(
  selectedStory: Story | null,
  options: UseCategoryAssignmentOptions = {}
): UseCategoryAssignmentReturn {
  const { onAssignSuccess, onRemoveSuccess, onError } = options
  
  const [codexTree, setCodexTree] = useState<any>(null)
  const [selectedPath, setSelectedPath] = useState<string[]>([])
  const [assigning, setAssigning] = useState(false)
  const [loading, setLoading] = useState(false)
  
  // Load codex tree
  const loadTree = useCallback(async () => {
    setLoading(true)
    try {
      const res = await axios.get('/get-tree')
      setCodexTree(res.data)
    } catch (err) {
      console.error('Error loading codex tree:', err)
      onError?.(err, 'assign')
    } finally {
      setLoading(false)
    }
  }, [onError])
  
  // Load tree on mount
  useEffect(() => {
    if (!codexTree) {
      loadTree()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  
  // Find current assignments when story or tree changes
  const currentAssignments = useMemo(() => {
    if (!selectedStory || !codexTree) return []
    return findAssignmentsInTree(codexTree, selectedStory.title)
  }, [selectedStory, codexTree])
  
  // Generate suggested categories based on keywords
  const suggestedCategories = useMemo(() => {
    if (!selectedStory || !codexTree) return []
    return generateSuggestions(codexTree, selectedStory.keywords)
  }, [selectedStory, codexTree])
  
  // Handle path level selection (cascading dropdowns)
  const handlePathLevelChange = useCallback((level: number, value: string) => {
    setSelectedPath(prev => {
      const newPath = prev.slice(0, level)
      if (value) {
        newPath.push(value)
      }
      return newPath
    })
  }, [])
  
  // Get options for a given path level
  const getPathOptions = useCallback((currentPath: string[] = []) => {
    return getOptionsAtPath(codexTree, currentPath)
  }, [codexTree])
  
  // Assign story to category
  const assignCategory = useCallback(async () => {
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
      
      const assignedPath = [...selectedPath]
      setSelectedPath([])
      
      onAssignSuccess?.(assignedPath)
      alert(`Story assigned to ${assignedPath.join(' > ')}`)
    } catch (err: any) {
      console.error('Error assigning category:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to assign categories.')
      } else {
        alert('Failed to assign category. Please try again.')
      }
      onError?.(err, 'assign')
    } finally {
      setAssigning(false)
    }
  }, [selectedStory, selectedPath, onAssignSuccess, onError])
  
  // Remove story from category
  const removeCategory = useCallback(async (path: string[]) => {
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
      
      onRemoveSuccess?.(path)
      alert(`Story removed from ${path.join(' > ')}`)
    } catch (err: any) {
      console.error('Error removing category:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to remove categories.')
      } else {
        alert('Failed to remove category. Please try again.')
      }
      onError?.(err, 'remove')
    } finally {
      setAssigning(false)
    }
  }, [selectedStory, onRemoveSuccess, onError])
  
  // Assign story to a specific path (used by suggestions)
  const assignToPath = useCallback(async (path: string[]) => {
    if (!selectedStory || path.length === 0) return
    
    setAssigning(true)
    try {
      await axios.post('/assign-category', {
        path: path,
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
      
      onAssignSuccess?.(path)
      alert(`Story assigned to ${path.join(' > ')}`)
    } catch (err: any) {
      console.error('Error assigning category:', err)
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor to assign categories.')
      } else {
        alert('Failed to assign category. Please try again.')
      }
      onError?.(err, 'assign')
    } finally {
      setAssigning(false)
    }
  }, [selectedStory, onAssignSuccess, onError])
  
  return {
    codexTree,
    selectedPath,
    currentAssignments,
    suggestedCategories,
    assigning,
    loading,
    loadTree,
    setSelectedPath,
    handlePathLevelChange,
    assignCategory,
    assignToPath,
    removeCategory,
    getPathOptions,
  }
}
