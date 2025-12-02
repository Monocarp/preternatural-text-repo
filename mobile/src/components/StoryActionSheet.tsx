import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store'
import CategoryPicker from './CategoryPicker'
import apiClient from '../utils/api'

interface Story {
  title: string
  book_slug: string
  book_title?: string
  book_author?: string
  pages?: string
  keywords?: string
  start_char: number
  end_char: number
  score?: number
}

interface StoryActionSheetProps {
  story: Story
  isOpen: boolean
  onClose: () => void
  onAssigned?: () => void  // Callback when story is assigned (for refreshing lists)
  currentPath?: string[]   // Current category path if viewing from a category
}

export default function StoryActionSheet({ story, isOpen, onClose, onAssigned }: StoryActionSheetProps) {
  const navigate = useNavigate()
  const { setSelectedStory } = useStore()
  const [showAssign, setShowAssign] = useState(false)
  const [assigning, setAssigning] = useState(false)
  const [removing, setRemoving] = useState<number | null>(null)
  const [currentAssignments, setCurrentAssignments] = useState<string[][]>([])
  const [loadingAssignments, setLoadingAssignments] = useState(false)

  // Fetch current assignments when sheet opens
  useEffect(() => {
    if (isOpen) {
      loadCurrentAssignments()
    } else {
      // Reset state when closed
      setShowAssign(false)
      setCurrentAssignments([])
      setRemoving(null)
    }
  }, [isOpen, story.title])

  const loadCurrentAssignments = async () => {
    setLoadingAssignments(true)
    try {
      const res = await apiClient.get(`/story-assignments/${encodeURIComponent(story.title)}`)
      setCurrentAssignments(res.data.paths || [])
    } catch (err) {
      console.error('Error loading assignments:', err)
      setCurrentAssignments([])
    } finally {
      setLoadingAssignments(false)
    }
  }

  const handleRemove = async (path: string[], idx: number) => {
    setRemoving(idx)
    try {
      await apiClient.delete('/remove-category', {
        data: {
          title: story.title,
          path: path
        }
      })
      // Refresh assignments
      await loadCurrentAssignments()
      onAssigned?.()
    } catch (err) {
      console.error('Error removing assignment:', err)
      alert('Failed to remove. Make sure you are logged in as an editor.')
    } finally {
      setRemoving(null)
    }
  }

  if (!isOpen) return null

  const handleRead = () => {
    setSelectedStory(story)
    onClose()
    navigate(`/story/${encodeURIComponent(story.title)}`)
  }

  const handleAssign = async (path: string[]) => {
    setAssigning(true)
    try {
      await apiClient.post('/assign-category', {
        story: {
          title: story.title,
          book_slug: story.book_slug,
          start_char: story.start_char,
          end_char: story.end_char,
          pages: story.pages,
          keywords: story.keywords,
        },
        path: path
      })
      
      setShowAssign(false)
      onClose()
      onAssigned?.()
    } catch (err) {
      console.error('Error assigning story:', err)
      alert('Failed to assign story. Make sure you are logged in as an editor.')
    } finally {
      setAssigning(false)
    }
  }

  const bookDisplay = story.book_title || story.book_slug?.replace(/_/g, ' ') || 'Unknown Book'

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      {/* Backdrop */}
      <div 
        className="absolute inset-0 bg-black/60"
        onClick={() => {
          if (showAssign) {
            setShowAssign(false)
          } else {
            onClose()
          }
        }}
      />
      
      {/* Sheet */}
      <div className="relative w-full max-w-lg bg-gray-800 rounded-t-2xl safe-area-bottom overflow-hidden max-h-[85vh] flex flex-col">
        {showAssign ? (
          // Assignment view
          <>
            <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
              <button
                onClick={() => setShowAssign(false)}
                className="text-blue-400"
              >
                ← Back
              </button>
              <h3 className="text-white font-medium">Assign to Category</h3>
              <div className="w-12"></div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4">
              {/* Story summary */}
              <div className="bg-gray-700/50 rounded-lg p-3 mb-4">
                <p className="text-white text-sm font-medium truncate">{story.title}</p>
                <p className="text-gray-400 text-xs mt-1">{bookDisplay}</p>
              </div>
              
              <CategoryPicker
                keywords={story.keywords}
                assigning={assigning}
                onSelect={handleAssign}
                onCancel={() => setShowAssign(false)}
              />
            </div>
          </>
        ) : (
          // Action menu view
          <>
            {/* Scrollable content */}
            <div className="flex-1 overflow-y-auto">
              {/* Story info header */}
              <div className="px-4 pt-4 pb-3">
                <h3 className="text-white font-medium leading-snug">{story.title}</h3>
                <div className="mt-1 flex items-center gap-2 text-sm text-gray-400">
                  <span>{bookDisplay}</span>
                  {story.pages && (
                    <>
                      <span className="text-gray-600">•</span>
                      <span>p.{story.pages}</span>
                    </>
                  )}
                </div>
                {story.keywords && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {story.keywords.split(',').slice(0, 4).map((kw, i) => (
                      <span key={i} className="px-2 py-0.5 bg-gray-700 text-gray-300 text-xs rounded-full">
                        {kw.trim()}
                      </span>
                    ))}
                  </div>
                )}
                
                {/* Current assignments */}
                {loadingAssignments ? (
                  <div className="mt-3 text-xs text-gray-500">Loading assignments...</div>
                ) : currentAssignments.length > 0 ? (
                  <div className="mt-3">
                    <p className="text-xs text-gray-500 mb-1">
                      Currently assigned to ({currentAssignments.length}):
                    </p>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {currentAssignments.map((path, idx) => (
                        <div key={idx} className="flex items-center justify-between text-xs bg-green-400/10 px-2 py-1 rounded">
                          <span className="text-green-400 truncate flex-1">{path.join(' → ')}</span>
                          <button
                            onClick={() => handleRemove(path, idx)}
                            disabled={removing === idx}
                            className="ml-2 text-red-400 hover:text-red-300 disabled:opacity-50 flex-shrink-0"
                          >
                            {removing === idx ? '...' : '✕'}
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="mt-3 text-xs text-orange-400">
                    ⚠ Not assigned to any category
                  </div>
                )}
              </div>
            </div>

            {/* Fixed Actions at bottom */}
            <div className="flex-shrink-0 p-4 space-y-2 border-t border-gray-700">
              <button
                onClick={handleRead}
                className="w-full py-3 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white rounded-xl font-medium flex items-center justify-center gap-2"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
                Read Story
              </button>
              
              <button
                onClick={() => setShowAssign(true)}
                className="w-full py-3 bg-gray-700 hover:bg-gray-600 active:bg-gray-600 text-white rounded-xl font-medium flex items-center justify-center gap-2"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z" />
                </svg>
                {currentAssignments.length > 0 ? 'Add/Move Category' : 'Assign to Category'}
              </button>
              
              <button
                onClick={onClose}
                className="w-full py-3 text-gray-400 font-medium"
              >
                Cancel
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
