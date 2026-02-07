import { useEffect, useState, useMemo } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useSwipeable } from 'react-swipeable'
import { useStore } from '../store'
import apiClient from '../utils/api'
import StoryCard from '../components/StoryCard'
import { encodePathSegmentsForApi, encodePathSegmentsForRoute, decodeRoutePath } from '../utils/path'

export default function CategoryPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const { tree, setTree, stories, setStories, loading, setLoading } = useStore()
  const [showStories, setShowStories] = useState(false)

  // Parse path segments from URL
  const pathSegments = useMemo(() => {
    const path = location.pathname.replace('/archive/', '')
    if (!path) return []
    return decodeRoutePath(path)
  }, [location.pathname])

  const isUnassigned = pathSegments.length === 1 && pathSegments[0].toLowerCase() === 'unassigned'
  const currentCategory = pathSegments[pathSegments.length - 1] || ''

  // Swipe right to go back
  const swipeHandlers = useSwipeable({
    onSwipedRight: () => {
      if (pathSegments.length > 1) {
        const parentPath = encodePathSegmentsForRoute(pathSegments.slice(0, -1))
        navigate(`/archive/${parentPath}`)
      } else {
        navigate('/archive')
      }
    },
    trackMouse: false,
    delta: 50,
  })

  useEffect(() => {
    // Load tree if not loaded
    if (Object.keys(tree).length === 0) {
      loadTree()
    }
  }, [])

  useEffect(() => {
    // Load stories for current path
    if (pathSegments.length > 0) {
      loadStories()
    }
  }, [pathSegments.join('/')])

  const loadTree = async () => {
    try {
      const res = await apiClient.get('/get-tree')
      setTree(res.data)
    } catch (err) {
      console.error('Error loading tree:', err)
    }
  }

  const loadStories = async () => {
    setLoading(true)
    try {
      if (isUnassigned) {
        const res = await apiClient.get('/get-unassigned')
        setStories(res.data)
      } else {
        const pathStr = encodePathSegmentsForApi(pathSegments)
        const res = await apiClient.get(`/get-stories/${pathStr}`)
        setStories(res.data)
      }
    } catch (err) {
      console.error('Error loading stories:', err)
      setStories([])
    } finally {
      setLoading(false)
    }
  }

  // Get current node in tree
  const currentNode = useMemo(() => {
    if (!tree || isUnassigned) return null
    let node = tree
    for (const segment of pathSegments) {
      if (node && node[segment]) {
        node = node[segment]
      } else {
        return null
      }
    }
    return node
  }, [tree, pathSegments, isUnassigned])

  // Get subcategories at current level
  const subcategories = useMemo(() => {
    if (!currentNode || typeof currentNode !== 'object' || Array.isArray(currentNode)) return []
    return Object.keys(currentNode).filter(key => key !== '_stories').sort()
  }, [currentNode])

  const handleSubcategoryTap = (subcategory: string) => {
    const newPath = encodePathSegmentsForRoute([...pathSegments, subcategory])
    navigate(`/archive/${newPath}`)
  }

  const handleBack = () => {
    if (pathSegments.length > 1) {
      const parentPath = encodePathSegmentsForRoute(pathSegments.slice(0, -1))
      navigate(`/archive/${parentPath}`)
    } else {
      navigate('/archive')
    }
  }

  return (
    <div {...swipeHandlers} className="min-h-full bg-gray-900 pb-4">
      {/* Header with back button */}
      <header className="sticky top-0 z-10 bg-gray-800 border-b border-gray-700 safe-area-top">
        <div className="flex items-center px-2 py-3">
          <button
            onClick={handleBack}
            className="p-2 -ml-2 text-gray-300 hover:text-white"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div className="flex-1 min-w-0 px-2">
            <h1 className="text-lg font-bold text-white truncate">
              {isUnassigned ? 'Unassigned' : currentCategory}
            </h1>
            {pathSegments.length > 1 && !isUnassigned && (
              <p className="text-xs text-gray-400 truncate">
                {pathSegments.slice(0, -1).join(' › ')}
              </p>
            )}
          </div>
        </div>

        {/* Tab toggle for categories with both subcategories and stories */}
        {subcategories.length > 0 && stories.length > 0 && (
          <div className="flex border-t border-gray-700">
            <button
              onClick={() => setShowStories(false)}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                !showStories ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-400'
              }`}
            >
              Categories ({subcategories.length})
            </button>
            <button
              onClick={() => setShowStories(true)}
              className={`flex-1 py-2 text-sm font-medium transition-colors ${
                showStories ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-400'
              }`}
            >
              Stories ({stories.length})
            </button>
          </div>
        )}
      </header>

      {/* Content */}
      <div className="px-4 pt-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
          </div>
        ) : (
          <>
            {/* Subcategories (if not showing stories tab) */}
            {subcategories.length > 0 && !showStories && (
              <div className="space-y-2 mb-4">
                {subcategories.map((subcategory) => {
                  const node = currentNode?.[subcategory]
                  const isArray = Array.isArray(node)
                  const subCount = isArray ? 0 : Object.keys(node || {}).filter(k => k !== '_stories').length
                  const storyCount = isArray ? node.length : (node?._stories?.length || 0)

                  return (
                    <button
                      key={subcategory}
                      onClick={() => handleSubcategoryTap(subcategory)}
                      className="w-full bg-gray-800 hover:bg-gray-700 active:bg-gray-600 border border-gray-700 rounded-xl p-4 text-left transition-colors"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <h3 className="text-base font-medium text-white truncate">
                            {subcategory}
                          </h3>
                          <p className="text-sm text-gray-400 mt-0.5">
                            {subCount > 0 && `${subCount} subcategories`}
                            {subCount > 0 && storyCount > 0 && ' • '}
                            {storyCount > 0 && `${storyCount} stories`}
                          </p>
                        </div>
                        <svg className="w-5 h-5 text-gray-400 flex-shrink-0 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </div>
                    </button>
                  )
                })}
              </div>
            )}

            {/* Stories list */}
            {(showStories || subcategories.length === 0) && stories.length > 0 && (
              <div className="space-y-3">
                {subcategories.length === 0 && (
                  <p className="text-sm text-gray-400 mb-2">{stories.length} stories</p>
                )}
                {stories.map((story, idx) => (
                  <StoryCard 
                    key={`${story.book_slug}-${story.title}-${idx}`} 
                    story={story}
                    currentPath={isUnassigned ? undefined : pathSegments}
                    onAssigned={() => loadStories()}
                  />
                ))}
              </div>
            )}

            {/* Empty state */}
            {!loading && subcategories.length === 0 && stories.length === 0 && (
              <div className="text-center py-12 text-gray-400">
                <p>No content in this category</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
