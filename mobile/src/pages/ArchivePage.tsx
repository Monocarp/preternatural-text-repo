import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStore } from '../store'
import apiClient from '../utils/api'

export default function ArchivePage() {
  const navigate = useNavigate()
  const { tree, setTree, loading, setLoading } = useStore()

  useEffect(() => {
    if (Object.keys(tree).length === 0) {
      loadTree()
    }
  }, [])

  const loadTree = async () => {
    setLoading(true)
    try {
      const res = await apiClient.get('/get-tree')
      setTree(res.data)
    } catch (err) {
      console.error('Error loading tree:', err)
    } finally {
      setLoading(false)
    }
  }

  // Get top-level categories
  const categories = Object.keys(tree).filter(key => key !== '_stories')

  const handleCategoryTap = (category: string) => {
    // Navigate to category page
    navigate(`/archive/${encodeURIComponent(category)}`)
  }

  return (
    <div className="min-h-full bg-gray-900 pb-4">
      {/* Header */}
      <header className="sticky top-0 z-10 bg-gray-800 border-b border-gray-700 px-4 py-3 safe-area-top">
        <h1 className="text-xl font-bold text-white text-center">Story Archive</h1>
      </header>

      {/* Content */}
      <div className="px-4 pt-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
          </div>
        ) : categories.length === 0 ? (
          <div className="text-center py-12 text-gray-400">
            <p>No categories found</p>
          </div>
        ) : (
          <div className="space-y-2">
            {categories.map((category) => {
              const node = tree[category]
              const isArray = Array.isArray(node)
              const subcategoryCount = isArray ? 0 : Object.keys(node || {}).filter(k => k !== '_stories').length
              const storyCount = isArray ? node.length : (node?._stories?.length || 0)
              
              return (
                <button
                  key={category}
                  onClick={() => handleCategoryTap(category)}
                  className="w-full bg-gray-800 hover:bg-gray-700 active:bg-gray-600 border border-gray-700 rounded-xl p-4 text-left transition-colors"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-medium text-white truncate">
                        {category}
                      </h3>
                      <p className="text-sm text-gray-400 mt-0.5">
                        {subcategoryCount > 0 && `${subcategoryCount} subcategories`}
                        {subcategoryCount > 0 && storyCount > 0 && ' • '}
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

            {/* Unassigned section */}
            <button
              onClick={() => navigate('/archive/unassigned')}
              className="w-full bg-gray-800 hover:bg-gray-700 active:bg-gray-600 border border-amber-700/50 rounded-xl p-4 text-left transition-colors mt-4"
            >
              <div className="flex items-center justify-between">
                <div className="flex-1 min-w-0">
                  <h3 className="text-lg font-medium text-amber-400 truncate">
                    Unassigned
                  </h3>
                  <p className="text-sm text-gray-400 mt-0.5">
                    Stories without categories
                  </p>
                </div>
                <svg className="w-5 h-5 text-gray-400 flex-shrink-0 ml-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                </svg>
              </div>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
