import { useEffect, useMemo, useRef, useState } from 'react'
import apiClient from '../utils/api'

interface Story {
  title: string
  book_slug: string
  book_title?: string
  pages?: string
  keywords?: string
  start_char: number
  end_char: number
}

interface StoryReviewTabProps {
  slug: string
  stories: Story[]
  onStoriesChange: (stories: Story[]) => void
}

// Alternating colors for story segments
const STORY_COLORS = [
  { bg: 'rgba(37,99,235,0.35)', border: '#3b82f6', label: 'text-blue-300' },
  { bg: 'rgba(22,163,74,0.35)', border: '#22c55e', label: 'text-green-300' },
  { bg: 'rgba(147,51,234,0.35)', border: '#a855f7', label: 'text-purple-300' },
  { bg: 'rgba(217,119,6,0.35)', border: '#f59e0b', label: 'text-amber-300' },
  { bg: 'rgba(6,182,212,0.35)', border: '#06b6d4', label: 'text-cyan-300' },
  { bg: 'rgba(225,29,72,0.35)', border: '#f43f5e', label: 'text-rose-300' },
]

type ReviewMode = 'view' | 'edit-boundary' | 'new-story'

export default function StoryReviewTab({ slug, stories, onStoriesChange }: StoryReviewTabProps) {
  const [fullText, setFullText] = useState<string | null>(null)
  const [loadingText, setLoadingText] = useState(false)
  const [selectedStory, setSelectedStory] = useState<Story | null>(null)
  const [showStoryList, setShowStoryList] = useState(false)
  const [mode, setMode] = useState<ReviewMode>('view')

  // Boundary editing state
  const [editedStart, setEditedStart] = useState(0)
  const [editedEnd, setEditedEnd] = useState(0)
  const [selectingStart, setSelectingStart] = useState(true)
  const [savingBoundaries, setSavingBoundaries] = useState(false)

  // New story state
  const [newStoryStart, setNewStoryStart] = useState<number | null>(null)
  const [newStoryEnd, setNewStoryEnd] = useState<number | null>(null)
  const [newStorySelectingStart, setNewStorySelectingStart] = useState(true)
  const [newStoryTitle, setNewStoryTitle] = useState('')
  const [newStoryKeywords, setNewStoryKeywords] = useState('')
  const [newStoryPages, setNewStoryPages] = useState('')
  const [addingStory, setAddingStory] = useState(false)

  // Edit title state
  const [editingTitle, setEditingTitle] = useState(false)
  const [newTitle, setNewTitle] = useState('')

  // Edit keywords state
  const [editingKeywords, setEditingKeywords] = useState(false)
  const [editedKeywords, setEditedKeywords] = useState('')
  const [savingKeywords, setSavingKeywords] = useState(false)

  const reviewContainerRef = useRef<HTMLDivElement>(null)

  // Load full text on mount
  useEffect(() => {
    if (slug && !fullText) {
      loadFullText()
    }
  }, [slug])

  // Reset selections when mode changes
  useEffect(() => {
    if (mode === 'view') {
      setEditedStart(0)
      setEditedEnd(0)
      setSelectingStart(true)
      setNewStoryStart(null)
      setNewStoryEnd(null)
      setNewStorySelectingStart(true)
      setNewStoryTitle('')
      setNewStoryKeywords('')
      setNewStoryPages('')
    }
  }, [mode])

  // Auto-scroll to selected story
  useEffect(() => {
    if (selectedStory && mode === 'view' && reviewContainerRef.current) {
      setTimeout(() => {
        const el = reviewContainerRef.current?.querySelector(
          `[data-story="${CSS.escape(selectedStory.title)}"]`
        ) as HTMLElement | null
        if (el && reviewContainerRef.current) {
          const containerRect = reviewContainerRef.current.getBoundingClientRect()
          const elRect = el.getBoundingClientRect()
          const relTop = elRect.top - containerRect.top + reviewContainerRef.current.scrollTop
          reviewContainerRef.current.scrollTop = relTop - 80
        }
      }, 100)
    }
  }, [selectedStory?.title, mode])

  // Auto-scroll when entering boundary edit mode
  useEffect(() => {
    if (mode === 'edit-boundary' && selectedStory && reviewContainerRef.current) {
      setTimeout(() => {
        const highlight = reviewContainerRef.current?.querySelector('.boundary-highlight') as HTMLElement | null
        if (highlight && reviewContainerRef.current) {
          const containerRect = reviewContainerRef.current.getBoundingClientRect()
          const hRect = highlight.getBoundingClientRect()
          const relTop = hRect.top - containerRect.top + reviewContainerRef.current.scrollTop
          reviewContainerRef.current.scrollTop = relTop - reviewContainerRef.current.clientHeight / 3
        }
      }, 150)
    }
  }, [mode, editedStart, editedEnd])

  const loadFullText = async () => {
    setLoadingText(true)
    try {
      const res = await apiClient.get(`/full-text/${slug}`)
      setFullText(res.data.text)
    } catch (err) {
      console.error('Error loading full text:', err)
      setFullText(null)
    } finally {
      setLoadingText(false)
    }
  }

  // Sort stories by start position and assign color indices
  const sortedStories = useMemo(() => {
    return [...stories]
      .sort((a, b) => a.start_char - b.start_char)
      .map((story, idx) => ({
        ...story,
        colorIndex: idx % STORY_COLORS.length,
      }))
  }, [stories])

  // Build segments for review view (colored story regions + gray gaps)
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
      if (story.start_char < 0 || story.end_char <= story.start_char) continue

      if (story.start_char > currentPos) {
        segments.push({
          type: 'gap',
          start: currentPos,
          end: story.start_char,
          text: fullText.substring(currentPos, story.start_char),
        })
      }

      const storyStart = Math.max(currentPos, story.start_char)
      const storyEnd = Math.min(fullText.length, story.end_char)

      if (storyEnd > storyStart) {
        segments.push({
          type: 'story',
          start: storyStart,
          end: storyEnd,
          text: fullText.substring(storyStart, storyEnd),
          story,
          colorIndex: story.colorIndex,
        })
        currentPos = storyEnd
      }
    }

    if (currentPos < fullText.length) {
      segments.push({
        type: 'gap',
        start: currentPos,
        end: fullText.length,
        text: fullText.substring(currentPos),
      })
    }

    return segments
  }, [fullText, sortedStories])

  // Build segments for boundary editing mode
  const editingSegments = useMemo(() => {
    if (mode !== 'edit-boundary' || !fullText) return []

    const segments: Array<{ type: 'before' | 'selected' | 'after'; text: string }> = []

    if (editedStart > 0) {
      segments.push({ type: 'before', text: fullText.substring(0, editedStart) })
    }
    if (editedEnd > editedStart) {
      segments.push({ type: 'selected', text: fullText.substring(editedStart, editedEnd) })
    }
    if (editedEnd < fullText.length) {
      segments.push({ type: 'after', text: fullText.substring(editedEnd) })
    }

    return segments
  }, [mode, fullText, editedStart, editedEnd])

  // Build segments for new story mode
  const newStorySegments = useMemo(() => {
    if (mode !== 'new-story' || !fullText) return []

    const start = newStoryStart ?? 0
    const end = newStoryEnd ?? start
    const segments: Array<{ type: 'before' | 'selected' | 'after'; text: string }> = []

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
  }, [mode, fullText, newStoryStart, newStoryEnd])

  // Handle tapping text to set boundary positions  
  const handleTextTap = (e: React.MouseEvent<HTMLDivElement> | React.TouchEvent<HTMLDivElement>) => {
    if (mode === 'view') return
    if (!fullText || !reviewContainerRef.current) return

    e.preventDefault()
    e.stopPropagation()

    let clientX: number, clientY: number
    if ('touches' in e) {
      const touch = e.changedTouches[0]
      clientX = touch.clientX
      clientY = touch.clientY
    } else {
      clientX = e.clientX
      clientY = e.clientY
    }

    const range = document.caretRangeFromPoint?.(clientX, clientY)
    if (!range) return

    const textContainer = reviewContainerRef.current
    let charPos = 0
    const walker = document.createTreeWalker(textContainer, NodeFilter.SHOW_TEXT, null)

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

    if (mode === 'edit-boundary') {
      if (selectingStart) {
        setEditedStart(charPos)
        setSelectingStart(false)
      } else {
        if (charPos > editedStart) {
          setEditedEnd(charPos)
        } else {
          setEditedStart(charPos)
        }
        setSelectingStart(true)
      }
    } else if (mode === 'new-story') {
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
  }

  // Story actions
  const handleStartBoundaryEdit = () => {
    if (!selectedStory) return
    setMode('edit-boundary')
    setEditedStart(selectedStory.start_char)
    setEditedEnd(selectedStory.end_char)
    setSelectingStart(true)
  }

  const handleSaveBoundaries = async () => {
    if (!selectedStory) return
    if (editedEnd <= editedStart) {
      alert('End position must be after start position.')
      return
    }
    setSavingBoundaries(true)
    try {
      await apiClient.post('/update-boundaries', {
        title: selectedStory.title,
        book_slug: slug,
        start_char: editedStart,
        end_char: editedEnd,
      })
      const updated = stories.map((s) =>
        s.title === selectedStory.title ? { ...s, start_char: editedStart, end_char: editedEnd } : s
      )
      onStoriesChange(updated)
      setSelectedStory({ ...selectedStory, start_char: editedStart, end_char: editedEnd })
      setMode('view')
      alert('Boundaries saved!')
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor.')
      } else {
        alert('Failed to save boundaries.')
      }
    } finally {
      setSavingBoundaries(false)
    }
  }

  const handleEnterNewStoryMode = () => {
    setSelectedStory(null)
    setMode('new-story')
    setNewStoryStart(null)
    setNewStoryEnd(null)
    setNewStorySelectingStart(true)
    setNewStoryTitle('')
    setNewStoryKeywords('')
    setNewStoryPages('')
  }

  const handleAddNewStory = async () => {
    if (newStoryStart === null || newStoryEnd === null || !newStoryTitle.trim()) return

    setAddingStory(true)
    try {
      const response = await apiClient.post('/add-story', {
        book_slug: slug,
        title: newStoryTitle.trim(),
        keywords: newStoryKeywords.trim(),
        pages: newStoryPages.trim(),
        start_char: newStoryStart,
        end_char: newStoryEnd,
      })

      if (response.data?.status === 'overlap_warning') {
        const overlaps = response.data.overlaps || []
        const msg = overlaps.map((o: any) => `  • ${o.title} (${o.overlap_percent}%)`).join('\n')
        if (!confirm(`Overlap warning:\n${msg}\n\nAdd anyway?`)) {
          setAddingStory(false)
          return
        }
        await apiClient.post('/add-story', {
          book_slug: slug,
          title: newStoryTitle.trim(),
          keywords: newStoryKeywords.trim(),
          pages: newStoryPages.trim(),
          start_char: newStoryStart,
          end_char: newStoryEnd,
          force_overlap: true,
        })
      }

      const newStory: Story = {
        title: newStoryTitle.trim(),
        book_slug: slug,
        pages: newStoryPages.trim(),
        keywords: newStoryKeywords.trim(),
        start_char: newStoryStart,
        end_char: newStoryEnd,
      }
      onStoriesChange([...stories, newStory])
      setMode('view')
      alert(`Story "${newStoryTitle.trim()}" added!`)
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor.')
      } else {
        alert('Failed to add story.')
      }
    } finally {
      setAddingStory(false)
    }
  }

  const handleSaveTitle = async () => {
    if (!selectedStory || !newTitle.trim()) return
    try {
      await apiClient.post('/update-title', {
        old_title: selectedStory.title,
        new_title: newTitle.trim(),
        book_slug: slug,
      })
      const updated = stories.map((s) =>
        s.title === selectedStory.title ? { ...s, title: newTitle.trim() } : s
      )
      onStoriesChange(updated)
      setSelectedStory({ ...selectedStory, title: newTitle.trim() })
      setEditingTitle(false)
      alert('Title updated!')
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor.')
      } else {
        alert('Failed to update title.')
      }
    }
  }

  const handleSaveKeywords = async () => {
    if (!selectedStory) return
    setSavingKeywords(true)
    try {
      await apiClient.post('/update-keywords', {
        title: selectedStory.title,
        book_slug: slug,
        keywords: editedKeywords.trim(),
      })
      const updated = stories.map((s) =>
        s.title === selectedStory.title ? { ...s, keywords: editedKeywords.trim() } : s
      )
      onStoriesChange(updated)
      setSelectedStory({ ...selectedStory, keywords: editedKeywords.trim() })
      setEditingKeywords(false)
      alert('Keywords updated!')
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor.')
      } else {
        alert('Failed to update keywords.')
      }
    } finally {
      setSavingKeywords(false)
    }
  }

  const handleDeleteStory = async () => {
    if (!selectedStory) return
    if (!confirm(`Delete "${selectedStory.title}"? This cannot be undone.`)) return
    try {
      await apiClient.delete(`/delete-story/${encodeURIComponent(selectedStory.title)}`)
      onStoriesChange(stories.filter((s) => s.title !== selectedStory.title))
      setSelectedStory(null)
      alert('Story deleted.')
    } catch (err: any) {
      const status = err?.response?.status
      if (status === 401 || status === 403) {
        alert('You must be signed in as an editor.')
      } else {
        alert('Failed to delete story.')
      }
    }
  }

  // --- RENDER ---

  if (loadingText) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
      </div>
    )
  }

  if (!fullText) {
    return (
      <div className="text-center py-8 text-gray-400">
        <p>No text available for this book.</p>
        <button onClick={loadFullText} className="mt-3 text-blue-400 underline text-sm">
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="flex flex-col" style={{ height: 'calc(100vh - 120px)' }}>
      {/* Top toolbar */}
      <div className="flex items-center justify-between px-2 py-2 bg-gray-800 border-b border-gray-700 flex-shrink-0">
        <div className="flex items-center gap-2">
          {mode !== 'view' && (
            <button
              onClick={() => setMode('view')}
              className="px-2 py-1 text-xs bg-gray-600 text-white rounded"
            >
              Cancel
            </button>
          )}
          {mode === 'view' && (
            <>
              <button
                onClick={() => setShowStoryList(!showStoryList)}
                className={`px-2 py-1 text-xs rounded transition-colors ${
                  showStoryList ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
                }`}
              >
                Stories ({sortedStories.length})
              </button>
              <button
                onClick={handleEnterNewStoryMode}
                className="px-2 py-1 text-xs bg-purple-600 text-white rounded"
              >
                + New Story
              </button>
            </>
          )}
        </div>
        <div className="text-xs text-gray-400">
          {mode === 'edit-boundary' && (
            <span className={selectingStart ? 'text-blue-400' : 'text-green-400'}>
              Tap to set {selectingStart ? 'START' : 'END'}
            </span>
          )}
          {mode === 'new-story' && (
            <span className={newStorySelectingStart ? 'text-green-400' : 'text-yellow-400'}>
              Tap to set {newStorySelectingStart ? 'START' : 'END'}
            </span>
          )}
          {mode === 'view' && (
            <span>Tap highlighted text to select</span>
          )}
        </div>
      </div>

      {/* Story list drawer (slides down) */}
      {showStoryList && mode === 'view' && (
        <div className="max-h-48 overflow-y-auto bg-gray-800 border-b border-gray-700 flex-shrink-0">
          {sortedStories.map((story) => {
            const color = STORY_COLORS[story.colorIndex]
            const isSelected = selectedStory?.title === story.title
            return (
              <button
                key={story.title}
                onClick={() => {
                  setSelectedStory(isSelected ? null : story)
                  setShowStoryList(false)
                }}
                className="w-full text-left px-3 py-2 border-b border-gray-700/50 active:bg-gray-700"
                style={isSelected ? { backgroundColor: color.bg, borderLeftWidth: 3, borderLeftColor: color.border } : {}}
              >
                <div className={`text-sm font-medium truncate ${isSelected ? color.label : 'text-gray-200'}`}>
                  {story.title}
                </div>
                <div className="text-xs text-gray-500">
                  {story.pages && `p.${story.pages} • `}
                  {(story.end_char - story.start_char).toLocaleString()} chars
                </div>
              </button>
            )
          })}
        </div>
      )}

      {/* Text viewer - takes remaining space */}
      <div
        ref={reviewContainerRef}
        className={`flex-1 overflow-y-auto px-3 py-3 ${
          mode !== 'view' ? 'border-2 border-blue-500' : ''
        }`}
        style={{
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
          overscrollBehavior: 'contain',
          WebkitUserSelect: mode !== 'view' ? 'none' : 'auto',
          userSelect: mode !== 'view' ? 'none' : 'auto',
        }}
        onClick={mode !== 'view' ? handleTextTap : undefined}
        onTouchEnd={mode !== 'view' ? handleTextTap : undefined}
      >
        <div className="font-mono text-xs leading-relaxed">
          {/* Normal view mode */}
          {mode === 'view' && reviewSegments.length > 0 &&
            reviewSegments.map((seg, idx) => {
              if (seg.type === 'gap') {
                return (
                  <span key={idx} className="text-gray-400">
                    {seg.text}
                  </span>
                )
              } else {
                const color = STORY_COLORS[seg.colorIndex!]
                const isSelected = selectedStory?.title === seg.story?.title
                return (
                  <span
                    key={idx}
                    data-story={seg.story?.title}
                    onClick={() => seg.story && setSelectedStory(
                      selectedStory?.title === seg.story.title ? null : seg.story
                    )}
                    className="cursor-pointer rounded-sm transition-all"
                    style={{
                      backgroundColor: color.bg,
                      outline: isSelected ? `2px solid ${color.border}` : 'none',
                      padding: '0 1px',
                    }}
                  >
                    {seg.text}
                  </span>
                )
              }
            })}

          {/* View mode with no stories */}
          {mode === 'view' && reviewSegments.length === 0 && (
            <span className="text-gray-400">{fullText}</span>
          )}

          {/* Boundary editing mode */}
          {mode === 'edit-boundary' &&
            editingSegments.map((seg, idx) => {
              if (seg.type === 'selected') {
                return (
                  <span key={idx} className="boundary-highlight bg-yellow-600/50 text-yellow-100 rounded-sm px-0.5">
                    {seg.text}
                  </span>
                )
              }
              return (
                <span key={idx} className="text-gray-400">
                  {seg.text}
                </span>
              )
            })}

          {/* New story mode */}
          {mode === 'new-story' &&
            newStorySegments.map((seg, idx) => {
              if (seg.type === 'selected') {
                return (
                  <span key={idx} className="bg-purple-600/50 text-purple-100 rounded-sm px-0.5">
                    {seg.text}
                  </span>
                )
              }
              return (
                <span key={idx} className="text-gray-400">
                  {seg.text}
                </span>
              )
            })}
        </div>
      </div>

      {/* Bottom panel: selected story details / boundary controls / new story form */}
      {(selectedStory || mode === 'edit-boundary' || mode === 'new-story') && (
        <div className="flex-shrink-0 bg-gray-800 border-t border-gray-700 max-h-[45vh] overflow-y-auto safe-area-bottom">
          {/* Boundary editing controls */}
          {mode === 'edit-boundary' && selectedStory && (
            <div className="p-3 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold text-blue-400">Edit Boundaries</h4>
                <span className="text-xs text-gray-400 truncate ml-2">{selectedStory.title}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className={`p-2 rounded ${selectingStart ? 'bg-blue-900/50 border border-blue-500' : 'bg-gray-700'}`}>
                  <p className="text-gray-400">Start</p>
                  <p className="text-white font-mono">{editedStart.toLocaleString()}</p>
                  {selectingStart && <p className="text-blue-400 mt-0.5">← Tap text</p>}
                </div>
                <div className={`p-2 rounded ${!selectingStart ? 'bg-green-900/50 border border-green-500' : 'bg-gray-700'}`}>
                  <p className="text-gray-400">End</p>
                  <p className="text-white font-mono">{editedEnd.toLocaleString()}</p>
                  {!selectingStart && <p className="text-green-400 mt-0.5">← Tap text</p>}
                </div>
              </div>
              <div className="text-xs text-gray-400 text-center">
                Length: {editedEnd > editedStart ? (editedEnd - editedStart).toLocaleString() + ' chars' : '—'}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleSaveBoundaries}
                  disabled={savingBoundaries || editedEnd <= editedStart}
                  className="flex-1 py-2 bg-green-600 active:bg-green-700 disabled:bg-gray-600 text-white text-sm font-medium rounded-lg"
                >
                  {savingBoundaries ? 'Saving...' : 'Save Boundaries'}
                </button>
                <button
                  onClick={() => setMode('view')}
                  disabled={savingBoundaries}
                  className="flex-1 py-2 bg-gray-600 active:bg-gray-500 text-white text-sm font-medium rounded-lg"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* New story form */}
          {mode === 'new-story' && (
            <div className="p-3 space-y-3">
              <h4 className="text-sm font-semibold text-purple-400">Add New Story</h4>
              <input
                type="text"
                value={newStoryTitle}
                onChange={(e) => setNewStoryTitle(e.target.value)}
                placeholder="Story title *"
                className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-500"
              />
              <div className="grid grid-cols-2 gap-2">
                <input
                  type="text"
                  value={newStoryKeywords}
                  onChange={(e) => setNewStoryKeywords(e.target.value)}
                  placeholder="Keywords"
                  className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-500"
                />
                <input
                  type="text"
                  value={newStoryPages}
                  onChange={(e) => setNewStoryPages(e.target.value)}
                  placeholder="Pages"
                  className="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-500"
                />
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className={`p-2 rounded ${newStorySelectingStart ? 'bg-green-900/50 border border-green-500' : 'bg-gray-700'}`}>
                  <p className="text-gray-400">Start</p>
                  <p className="text-white font-mono">{newStoryStart?.toLocaleString() ?? '—'}</p>
                  {newStorySelectingStart && <p className="text-green-400 mt-0.5">← Tap text</p>}
                </div>
                <div className={`p-2 rounded ${!newStorySelectingStart ? 'bg-yellow-900/50 border border-yellow-500' : 'bg-gray-700'}`}>
                  <p className="text-gray-400">End</p>
                  <p className="text-white font-mono">{newStoryEnd?.toLocaleString() ?? '—'}</p>
                  {!newStorySelectingStart && <p className="text-yellow-400 mt-0.5">← Tap text</p>}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={handleAddNewStory}
                  disabled={addingStory || !newStoryTitle.trim() || newStoryStart === null || newStoryEnd === null || (newStoryEnd ?? 0) <= (newStoryStart ?? 0)}
                  className="flex-1 py-2 bg-purple-600 active:bg-purple-700 disabled:bg-gray-600 text-white text-sm font-medium rounded-lg"
                >
                  {addingStory ? 'Adding...' : 'Add Story'}
                </button>
                <button
                  onClick={() => setMode('view')}
                  disabled={addingStory}
                  className="flex-1 py-2 bg-gray-600 active:bg-gray-500 text-white text-sm font-medium rounded-lg"
                >
                  Cancel
                </button>
              </div>
            </div>
          )}

          {/* Selected story details (view mode) */}
          {mode === 'view' && selectedStory && (
            <div className="p-3 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0 mr-2">
                  {editingTitle ? (
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={newTitle}
                        onChange={(e) => setNewTitle(e.target.value)}
                        className="flex-1 px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm text-white"
                        autoFocus
                      />
                      <button onClick={handleSaveTitle} className="px-2 py-1 bg-green-600 text-white text-xs rounded">Save</button>
                      <button onClick={() => setEditingTitle(false)} className="px-2 py-1 bg-gray-600 text-white text-xs rounded">✕</button>
                    </div>
                  ) : (
                    <h4 className="text-sm font-semibold text-green-400 truncate">{selectedStory.title}</h4>
                  )}
                </div>
                <button
                  onClick={() => setSelectedStory(null)}
                  className="p-1 text-gray-400"
                >
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              {/* Story metadata */}
              <div className="text-xs text-gray-300 space-y-1">
                {selectedStory.pages && <p>Pages: {selectedStory.pages}</p>}
                {editingKeywords ? (
                  <div className="space-y-1">
                    <input
                      type="text"
                      value={editedKeywords}
                      onChange={(e) => setEditedKeywords(e.target.value)}
                      placeholder="ghost, haunting, supernatural"
                      className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs"
                    />
                    <div className="flex gap-1">
                      <button
                        onClick={handleSaveKeywords}
                        disabled={savingKeywords}
                        className="flex-1 px-2 py-1 bg-green-600 text-white text-xs rounded"
                      >
                        {savingKeywords ? '...' : 'Save'}
                      </button>
                      <button
                        onClick={() => setEditingKeywords(false)}
                        className="flex-1 px-2 py-1 bg-gray-600 text-white text-xs rounded"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-1">
                    <p className="flex-1 truncate">
                      Keywords: {selectedStory.keywords || <span className="italic text-gray-500">none</span>}
                    </p>
                    <button
                      onClick={() => { setEditingKeywords(true); setEditedKeywords(selectedStory.keywords || '') }}
                      className="px-1.5 py-0.5 bg-gray-600 text-white rounded text-xs flex-shrink-0"
                    >
                      ✎
                    </button>
                  </div>
                )}
                <p>Chars: {selectedStory.start_char.toLocaleString()} – {selectedStory.end_char.toLocaleString()} ({(selectedStory.end_char - selectedStory.start_char).toLocaleString()})</p>
              </div>

              {/* Action buttons */}
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={handleStartBoundaryEdit}
                  className="flex-1 py-2 bg-blue-600 active:bg-blue-700 text-white text-sm font-medium rounded-lg"
                >
                  Edit Bounds
                </button>
                {!editingTitle && (
                  <button
                    onClick={() => { setEditingTitle(true); setNewTitle(selectedStory.title) }}
                    className="flex-1 py-2 bg-amber-600 active:bg-amber-700 text-white text-sm font-medium rounded-lg"
                  >
                    Edit Title
                  </button>
                )}
                <button
                  onClick={handleDeleteStory}
                  className="py-2 px-4 bg-red-600 active:bg-red-700 text-white text-sm font-medium rounded-lg"
                >
                  Delete
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
