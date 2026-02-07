// frontend/src/components/CategoryManager.tsx
/**
 * CategoryManager component for creating and deleting categories.
 * 
 * Provides UI for editors to:
 * - Create new categories/subcategories
 * - Delete existing categories (with confirmation)
 * - View category info (story count, children)
 */

import { useState, useEffect, useRef } from 'react'
import axios from '../utils/axios'
import { encodePathSegmentsForApi } from '../utils/path'

interface CategoryManagerProps {
  /** Current path segments of the selected category (empty for root) */
  currentPath: string[]
  /** Category name at the current path (null for root) */
  categoryName: string | null
  /** Whether the user is an editor */
  isEditor: boolean
  /** Callback when tree should be refreshed */
  onTreeChange: () => void
  /** Position of the popup (for positioning near click) */
  position?: { x: number; y: number }
  /** Close callback */
  onClose: () => void
}

interface CategoryInfo {
  exists: boolean
  has_children?: boolean
  has_stories?: boolean
  story_count?: number
  child_count?: number
}

type Mode = 'view' | 'create' | 'delete'

export default function CategoryManager({
  currentPath,
  categoryName,
  isEditor,
  onTreeChange,
  position,
  onClose,
}: CategoryManagerProps) {
  const [mode, setMode] = useState<Mode>('view')
  const [newCategoryName, setNewCategoryName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [categoryInfo, setCategoryInfo] = useState<CategoryInfo | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const popupRef = useRef<HTMLDivElement>(null)

  // Load category info on mount
  useEffect(() => {
    if (currentPath.length > 0) {
      loadCategoryInfo()
    } else {
      // Root level - just show create option
      setCategoryInfo({ exists: true, has_children: true, has_stories: false })
    }
  }, [currentPath])

  // Close on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        onClose()
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [onClose])

  // Close on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onClose])

  const loadCategoryInfo = async () => {
    try {
      const encodedPath = encodePathSegmentsForApi(currentPath)
      const res = await axios.get(`/category-info/${encodedPath}`)
      setCategoryInfo(res.data)
    } catch (err) {
      console.error('Failed to load category info:', err)
      setCategoryInfo({ exists: false })
    }
  }

  const handleCreate = async () => {
    if (!newCategoryName.trim()) {
      setError('Category name cannot be empty')
      return
    }

    setLoading(true)
    setError(null)

    try {
      await axios.post('/create-category', {
        parent_path: currentPath,
        name: newCategoryName.trim(),
      })
      
      setNewCategoryName('')
      setMode('view')
      onTreeChange()
      onClose()
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to create category'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const handleDelete = async () => {
    if (currentPath.length === 0) {
      setError('Cannot delete root level')
      return
    }

    // Require typing category name for confirmation
    if (deleteConfirm !== categoryName) {
      setError(`Type "${categoryName}" to confirm deletion`)
      return
    }

    setLoading(true)
    setError(null)

    try {
      const res = await axios.delete('/delete-category', {
        data: { path: currentPath },
      })
      
      const { affected_stories, had_children } = res.data
      
      // Show summary
      let message = `Deleted "${categoryName}"`
      if (affected_stories?.length > 0) {
        message += `. ${affected_stories.length} stories unassigned from this category.`
      }
      if (had_children) {
        message += ' All subcategories were also deleted.'
      }
      
      console.log(message)
      setMode('view')
      onTreeChange()
      onClose()
    } catch (err: any) {
      const message = err.response?.data?.detail || 'Failed to delete category'
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  const popupStyle: React.CSSProperties = position
    ? {
        position: 'fixed',
        left: Math.min(position.x, window.innerWidth - 320),
        top: Math.min(position.y, window.innerHeight - 300),
        zIndex: 1000,
      }
    : {}

  return (
    <div
      ref={popupRef}
      className="bg-gray-800 border border-gray-600 rounded-lg shadow-xl p-4 w-72"
      style={popupStyle}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3 pb-2 border-b border-gray-700">
        <h3 className="text-sm font-semibold text-white">
          {mode === 'view' && 'Category Options'}
          {mode === 'create' && 'Create Subcategory'}
          {mode === 'delete' && 'Delete Category'}
        </h3>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white p-1 rounded hover:bg-gray-700"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Current path display */}
      <div className="text-xs text-gray-400 mb-3">
        {currentPath.length > 0 ? (
          <span className="break-words">
            Path: {currentPath.join(' → ')}
          </span>
        ) : (
          <span>Root level (top-level categories)</span>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div className="bg-red-900/50 border border-red-700 text-red-300 px-3 py-2 rounded text-sm mb-3">
          {error}
        </div>
      )}

      {/* View Mode - Show options */}
      {mode === 'view' && isEditor && (
        <div className="space-y-2">
          {/* Category info */}
          {categoryInfo && categoryInfo.exists && currentPath.length > 0 && (
            <div className="text-xs text-gray-400 mb-3 p-2 bg-gray-700/50 rounded">
              <div>Stories: {categoryInfo.story_count || 0}</div>
              <div>Subcategories: {categoryInfo.child_count || 0}</div>
            </div>
          )}

          <button
            onClick={() => setMode('create')}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700 rounded transition-colors"
          >
            <svg className="w-4 h-4 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            Add Subcategory
          </button>

          {currentPath.length > 0 && (
            <button
              onClick={() => setMode('delete')}
              className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700 rounded transition-colors"
            >
              <svg className="w-4 h-4 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete This Category
            </button>
          )}
        </div>
      )}

      {/* Create Mode */}
      {mode === 'create' && isEditor && (
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-gray-400 mb-1">New category name</label>
            <input
              type="text"
              value={newCategoryName}
              onChange={(e) => setNewCategoryName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleCreate()}
              placeholder="Enter category name..."
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm placeholder-gray-400 focus:outline-none focus:border-blue-500"
              autoFocus
              disabled={loading}
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => {
                setMode('view')
                setNewCategoryName('')
                setError(null)
              }}
              className="flex-1 px-3 py-2 text-sm text-gray-300 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={loading || !newCategoryName.trim()}
              className="flex-1 px-3 py-2 text-sm text-white bg-green-600 hover:bg-green-500 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Creating...' : 'Create'}
            </button>
          </div>
        </div>
      )}

      {/* Delete Mode */}
      {mode === 'delete' && isEditor && (
        <div className="space-y-3">
          {categoryInfo && (categoryInfo.story_count || 0) > 0 && (
            <div className="bg-yellow-900/50 border border-yellow-700 text-yellow-300 px-3 py-2 rounded text-xs">
              ⚠️ This category has {categoryInfo.story_count} stories assigned.
              They will be unassigned from this category.
            </div>
          )}

          {categoryInfo && (categoryInfo.child_count || 0) > 0 && (
            <div className="bg-yellow-900/50 border border-yellow-700 text-yellow-300 px-3 py-2 rounded text-xs">
              ⚠️ This category has {categoryInfo.child_count} subcategories.
              All will be deleted.
            </div>
          )}

          <div>
            <label className="block text-xs text-gray-400 mb-1">
              Type "<span className="text-red-400">{categoryName}</span>" to confirm:
            </label>
            <input
              type="text"
              value={deleteConfirm}
              onChange={(e) => setDeleteConfirm(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleDelete()}
              placeholder="Type category name..."
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white text-sm placeholder-gray-400 focus:outline-none focus:border-red-500"
              autoFocus
              disabled={loading}
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={() => {
                setMode('view')
                setDeleteConfirm('')
                setError(null)
              }}
              className="flex-1 px-3 py-2 text-sm text-gray-300 bg-gray-700 hover:bg-gray-600 rounded transition-colors"
              disabled={loading}
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={loading || deleteConfirm !== categoryName}
              className="flex-1 px-3 py-2 text-sm text-white bg-red-600 hover:bg-red-500 rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Deleting...' : 'Delete'}
            </button>
          </div>
        </div>
      )}

      {/* Non-editor message */}
      {!isEditor && (
        <div className="text-sm text-gray-400 text-center py-4">
          Sign in as an editor to manage categories.
        </div>
      )}
    </div>
  )
}
