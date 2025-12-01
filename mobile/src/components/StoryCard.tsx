import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store'
import StoryActionSheet from './StoryActionSheet'

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

interface StoryCardProps {
  story: Story
  showScore?: boolean
  currentPath?: string[]  // If viewing from a category
  onAssigned?: () => void // Callback when assigned
}

export default function StoryCard({ story, showScore = false, currentPath, onAssigned }: StoryCardProps) {
  const navigate = useNavigate()
  const { setSelectedStory } = useStore()
  const [showActions, setShowActions] = useState(false)
  const longPressTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const touchMoved = useRef(false)
  const isLongPress = useRef(false)
  const touchStartPos = useRef({ x: 0, y: 0 })

  const handleTouchStart = (e: React.TouchEvent) => {
    touchMoved.current = false
    isLongPress.current = false
    touchStartPos.current = {
      x: e.touches[0].clientX,
      y: e.touches[0].clientY
    }
    
    longPressTimer.current = setTimeout(() => {
      isLongPress.current = true
      setShowActions(true)
    }, 500)
  }

  const handleTouchMove = (e: React.TouchEvent) => {
    // Check if moved more than 10px - that's a scroll
    const dx = Math.abs(e.touches[0].clientX - touchStartPos.current.x)
    const dy = Math.abs(e.touches[0].clientY - touchStartPos.current.y)
    
    if (dx > 10 || dy > 10) {
      touchMoved.current = true
      // Cancel long press if scrolling
      if (longPressTimer.current) {
        clearTimeout(longPressTimer.current)
        longPressTimer.current = null
      }
    }
  }

  const handleTouchEnd = () => {
    if (longPressTimer.current) {
      clearTimeout(longPressTimer.current)
      longPressTimer.current = null
    }
    
    // Only trigger tap if we didn't scroll and it wasn't a long press
    if (!touchMoved.current && !isLongPress.current) {
      handleTap()
    }
  }

  const handleTap = () => {
    setSelectedStory(story)
    navigate(`/story/${encodeURIComponent(story.title)}`)
  }

  const handleMenuClick = (e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    setShowActions(true)
  }

  const bookDisplay = story.book_title || story.book_slug?.replace(/_/g, ' ') || 'Unknown Book'

  return (
    <>
      <div
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
        onTouchMove={handleTouchMove}
        className="w-full bg-gray-800 hover:bg-gray-700 active:bg-gray-600 border border-gray-700 rounded-xl p-4 text-left transition-colors relative cursor-pointer"
      >
        {/* Menu button */}
        <button
          onClick={handleMenuClick}
          onTouchEnd={(e) => {
            e.stopPropagation()
            setShowActions(true)
          }}
          className="absolute top-3 right-3 p-1 text-gray-500 hover:text-gray-300"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z" />
          </svg>
        </button>

        <h3 className="text-base font-medium text-white leading-snug pr-8">
          {story.title}
        </h3>
        
        <div className="mt-2 flex items-center gap-2 text-sm text-gray-400">
          <span className="truncate">{bookDisplay}</span>
          {story.pages && (
            <>
              <span className="text-gray-600">•</span>
              <span className="flex-shrink-0">p.{story.pages}</span>
            </>
          )}
          {showScore && story.score !== undefined && (
            <>
              <span className="text-gray-600">•</span>
              <span className="flex-shrink-0 text-blue-400">{story.score.toFixed(2)}</span>
            </>
          )}
        </div>

        {story.keywords && (
          <div className="mt-2 flex flex-wrap gap-1">
            {story.keywords.split(',').slice(0, 3).map((keyword, idx) => (
              <span
                key={idx}
                className="px-2 py-0.5 bg-gray-700 text-gray-300 text-xs rounded-full"
              >
                {keyword.trim()}
              </span>
            ))}
            {story.keywords.split(',').length > 3 && (
              <span className="px-2 py-0.5 text-gray-500 text-xs">
                +{story.keywords.split(',').length - 3} more
              </span>
            )}
          </div>
        )}

        {/* Hold hint */}
        <p className="mt-2 text-xs text-gray-600 italic">Hold to assign</p>
      </div>

      {/* Action Sheet */}
      <StoryActionSheet
        story={story}
        isOpen={showActions}
        onClose={() => setShowActions(false)}
        onAssigned={onAssigned}
        currentPath={currentPath}
      />
    </>
  )
}
