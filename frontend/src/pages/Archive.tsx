// src/pages/Archive.tsx
import { useEffect, useMemo, useState } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import { Disclosure, DisclosureButton, DisclosurePanel } from '@headlessui/react'
import axios from 'axios'
import { useStore } from '../store'
import SidebarTree from '../components/SidebarTree'
import { decodeRoutePath, encodePathSegmentsForRoute } from '../utils/path'

const Archive = () => {
  const location = useLocation()
  const { path = '' } = useParams<{ path?: string }>()
  const navigate = useNavigate()
  
  // Extract path from location.pathname to ensure we detect URL changes
  // React Router's :path* might not trigger useParams updates properly
  const pathFromLocation = useMemo(() => {
    const match = location.pathname.match(/^\/archive\/(.+)$/)
    return match ? match[1] : ''
  }, [location.pathname])
  const { stories, loadStories, loading, error } = useStore()
  const [storyContents, setStoryContents] = useState<Record<string, string>>({})
  const [storyModes, setStoryModes] = useState<Record<string, 'static' | 'book'>>({})

  const decodedPath = useMemo(() => {
    // Use pathFromLocation instead of useParams path - React Router's :path* doesn't update reliably
    const pathToUse = pathFromLocation || path
    console.log('Archive: location.pathname =', location.pathname)
    console.log('Archive: pathFromLocation =', pathFromLocation)
    console.log('Archive: path param from useParams =', path)
    console.log('Archive: using path =', pathToUse)
    const decoded = decodeRoutePath(pathToUse)
    console.log('Archive: decoded path segments =', decoded)
    console.log('Archive: decoded length =', decoded.length)
    return decoded
  }, [pathFromLocation, path, location.pathname])
  const isUnassigned =
    decodedPath.length === 1 && decodedPath[0].toLowerCase() === 'unassigned'

  // Load stories based on URL path
  useEffect(() => {
    if (isUnassigned) {
      // Load unassigned stories
      axios.get('/api/get-unassigned')
        .then(res => {
          useStore.getState().setStories(res.data)
          useStore.getState().selectedPath = ['unassigned']
        })
        .catch(err => console.error('Error loading unassigned:', err))
    } else if (decodedPath.length > 0) {
      // Load stories for the category path (only if we have a path)
      loadStories(decodedPath)
    } else {
      // Root archive - don't load stories, just show empty state
      useStore.getState().setStories([])
      useStore.getState().selectedPath = []
    }
  }, [decodedPath, isUnassigned, loadStories, location.pathname])

  // Load story content when toggling modes
  const handleToggleMode = async (story: any, mode: 'static' | 'book') => {
    try {
      const res = await axios.post('/api/render-story', {
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
      useStore.getState().selectStory({ ...story, html: res.data.html, mode })
      
      // Auto-scroll to story position in book context mode
      if (mode === 'book') {
        // Wait for DOM to update, then scroll within the scrollable container
        setTimeout(() => {
          const wrapper = document.getElementById(`book-context-${story.title}`)
          const container = wrapper?.querySelector('#book-context-container') as HTMLElement
          const highlight = container?.querySelector('#story-highlight') as HTMLElement
          
          if (container && highlight) {
            // Calculate the position of the highlight relative to the container
            const highlightTop = highlight.offsetTop
            const containerHeight = container.clientHeight
            // Scroll to center the highlight in the container
            container.scrollTop = highlightTop - (containerHeight / 2) + (highlight.offsetHeight / 2)
          }
        }, 150)
      }
    } catch (err) {
      console.error('Error loading story:', err)
    }
  }

  // Load static view when story panel is opened
  const handleStoryOpen = async (story: any) => {
    // Only load if we don't already have content for this story
    if (!storyContents[story.title]) {
      await handleToggleMode(story, 'static')
    }
  }

  // Get page title from path
  const getPageTitle = () => {
    if (decodedPath.length === 0) return 'Story Archive'
    if (isUnassigned) return 'Unassigned Stories'
    return decodedPath[decodedPath.length - 1]
  }

  // Get breadcrumb path
  const getBreadcrumb = () => {
    if (decodedPath.length === 0) return ['Story Archive']
    if (isUnassigned) return ['Story Archive', 'Unassigned']
    return ['Story Archive', ...decodedPath]
  }

  return (
    <div className="flex h-screen">
      <SidebarTree />
      <main className="flex-1 overflow-y-auto bg-gray-900">
        <div className="max-w-4xl mx-auto px-6 py-6">
          <div className="mb-6">
            <nav className="text-sm text-gray-400 mb-2 text-center">
              {getBreadcrumb().map((part, idx) => (
                <span key={idx}>
                  {idx > 0 && ' > '}
                  <button
                    onClick={() => {
                      if (idx === 0) {
                        navigate('/archive')
                      } else {
                        // idx 1 = first category (decodedPath[0]), idx 2 = second category (decodedPath[0:2]), etc.
                        const targetSegments = decodedPath.slice(0, idx)
                        if (targetSegments.length > 0) {
                          const encoded = encodePathSegmentsForRoute(targetSegments)
                          navigate(`/archive/${encoded}`)
                        } else {
                          navigate('/archive')
                        }
                      }
                    }}
                    className="hover:text-blue-400"
                  >
                    {part}
                  </button>
                </span>
              ))}
            </nav>
            <h1 className="text-3xl font-bold text-white text-center">{getPageTitle()}</h1>
            {stories.length > 0 && (
              <p className="text-gray-300 mt-2 text-center">{stories.length} {stories.length === 1 ? 'story' : 'stories'}</p>
            )}
          </div>

        {loading && (
          <div className="text-center py-8">
            <p className="text-gray-400">Loading stories...</p>
          </div>
        )}

        {error && (
          <div className="bg-red-900 border border-red-700 rounded p-4 mb-4 text-center">
            <p className="text-red-200">Error: {error}</p>
          </div>
        )}

        {!loading && !error && stories.length === 0 && (
          <div className="text-center py-8">
            <p className="text-gray-400">No stories found in this category.</p>
          </div>
        )}

          {!loading && stories.length > 0 && (
            <div className="space-y-3">
            {stories.map((story: any) => {
              const currentMode = storyModes[story.title] || 'static'
              const storyContent = storyContents[story.title]
              
              return (
                <Disclosure 
                  key={story.title} 
                  as="div" 
                  className="border border-gray-700 rounded-lg shadow-sm hover:shadow-md transition-shadow bg-gray-800"
                >
                  <DisclosureButton 
                    className="w-full p-4 hover:bg-gray-700 relative"
                    onClick={() => handleStoryOpen(story)}
                  >
                    <div className="flex items-center justify-center">
                      <div className="text-center">
                        <h3 className="text-lg font-semibold text-white">{story.title}</h3>
                        <div className="mt-1 text-sm text-gray-300">
                          <span className="font-medium">{story.book_slug}</span>
                          {story.pages && <span className="ml-2">• Pages: {story.pages}</span>}
                          {story.keywords && <span className="ml-2">• Keywords: {story.keywords}</span>}
                        </div>
                      </div>
                    </div>
                    <span className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400">▼</span>
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
                        <div className="text-gray-400 text-center py-4">Loading story...</div>
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
        </div>
      </main>
    </div>
  )
}

export default Archive