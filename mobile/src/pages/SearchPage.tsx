import { useState, useEffect } from 'react'
import { useStore } from '../store'
import apiClient from '../utils/api'
import StoryCard from '../components/StoryCard'

export default function SearchPage() {
  const { searchQuery, setSearchQuery, searchResults, setSearchResults, loading, setLoading } = useStore()
  
  // Filters
  const [searchMode, setSearchMode] = useState<'Both' | 'Semantic' | 'Keywords' | 'Exact'>('Both')
  const [sourceFilter, setSourceFilter] = useState('All Sources')
  const [typeFilter, setTypeFilter] = useState<'Both' | 'Story' | 'Non-Story'>('Both')
  const [assignmentFilter, setAssignmentFilter] = useState<'all' | 'assigned' | 'unassigned'>('all')
  const [categoryFilter, setCategoryFilter] = useState('')
  const [subcategoryFilter, setSubcategoryFilter] = useState('')
  const [minScore, setMinScore] = useState(0.1)
  
  // Available sources and categories
  const [sources, setSources] = useState<string[]>(['All Sources'])
  const [categories, setCategories] = useState<string[]>([])
  const [subcategories, setSubcategories] = useState<Record<string, string[]>>({})
  
  // UI state
  const [hasSearched, setHasSearched] = useState(false)
  const [filtersExpanded, setFiltersExpanded] = useState(false)

  // Load sources on mount
  useEffect(() => {
    apiClient.get('/sources')
      .then(res => setSources(res.data.sources || ['All Sources']))
      .catch(() => setSources(['All Sources']))
  }, [])

  // Load categories on mount
  useEffect(() => {
    apiClient.get('/categories')
      .then(res => {
        setCategories(res.data.categories || [])
        setSubcategories(res.data.subcategories || {})
      })
      .catch(() => {
        setCategories([])
        setSubcategories({})
      })
  }, [])

  const handleSearch = async () => {
    if (!searchQuery.trim()) return

    setLoading(true)
    setHasSearched(true)
    try {
      const res = await apiClient.post('/search', {
        query: searchQuery.trim(),
        source_filter: sourceFilter,
        type_filter: typeFilter,
        search_mode: searchMode,
        top_k: 100,
        min_score: minScore,
        assignment_filter: assignmentFilter,
        category_filter: categoryFilter || null,
        subcategory_filter: subcategoryFilter || null
      })
      setSearchResults(res.data.results || [])
      // Collapse filters after search on mobile
      setFiltersExpanded(false)
    } catch (err) {
      console.error('Search error:', err)
      setSearchResults([])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch()
    }
  }

  const activeFilterCount = [
    sourceFilter !== 'All Sources',
    typeFilter !== 'Both',
    assignmentFilter !== 'all',
    categoryFilter !== '',
    subcategoryFilter !== '',
    minScore !== 0.1,
    searchMode !== 'Both'
  ].filter(Boolean).length

  return (
    <div className="min-h-full bg-gray-900 pb-4">
      {/* Header with search */}
      <header className="sticky top-0 z-10 bg-gray-800 border-b border-gray-700 safe-area-top">
        <div className="px-4 py-3">
          {/* Search input row */}
          <div className="flex items-center gap-2">
            <div className="flex-1 relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Search stories..."
                className="w-full pl-10 pr-4 py-2.5 bg-gray-700 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
              </svg>
            </div>
            <button
              onClick={handleSearch}
              disabled={!searchQuery.trim() || loading}
              className="px-4 py-2.5 bg-blue-600 hover:bg-blue-700 active:bg-blue-800 disabled:bg-gray-600 disabled:cursor-not-allowed text-white font-medium rounded-xl transition-colors"
            >
              {loading ? (
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              ) : (
                'Go'
              )}
            </button>
          </div>

          {/* Filter toggle button */}
          <button
            onClick={() => setFiltersExpanded(!filtersExpanded)}
            className="mt-2 flex items-center gap-2 text-sm text-gray-400 hover:text-white transition-colors"
          >
            <svg className={`w-4 h-4 transition-transform ${filtersExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
            <span>Filters</span>
            {activeFilterCount > 0 && (
              <span className="px-1.5 py-0.5 bg-blue-600 text-white text-xs rounded-full">
                {activeFilterCount}
              </span>
            )}
          </button>

          {/* Expandable filters */}
          {filtersExpanded && (
            <div className="mt-3 space-y-3 pb-2">
              {/* Search Mode */}
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Search Mode</label>
                <div className="flex gap-1.5">
                  {(['Both', 'Semantic', 'Keywords', 'Exact'] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setSearchMode(mode)}
                      className={`flex-1 py-2 text-xs font-medium rounded-lg transition-colors ${
                        searchMode === mode
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-700 text-gray-300'
                      }`}
                    >
                      {mode === 'Both' ? 'Hybrid' : mode}
                    </button>
                  ))}
                </div>
              </div>

              {/* Source Filter */}
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Source</label>
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {sources.map((source) => (
                    <option key={source} value={source}>{source}</option>
                  ))}
                </select>
              </div>

              {/* Type and Assignment row */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">Type</label>
                  <select
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value as typeof typeFilter)}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="Both">Both</option>
                    <option value="Story">Story</option>
                    <option value="Non-Story">Non-Story</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">Assignment</label>
                  <select
                    value={assignmentFilter}
                    onChange={(e) => setAssignmentFilter(e.target.value as typeof assignmentFilter)}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="all">All</option>
                    <option value="assigned">Assigned</option>
                    <option value="unassigned">Unassigned</option>
                  </select>
                </div>
              </div>

              {/* Category and Subcategory row */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">Category</label>
                  <select
                    value={categoryFilter}
                    onChange={(e) => {
                      setCategoryFilter(e.target.value)
                      setSubcategoryFilter('') // Reset subcategory when category changes
                    }}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="">All Categories</option>
                    {categories.map((cat) => (
                      <option key={cat} value={cat}>{cat}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">Subcategory</label>
                  <select
                    value={subcategoryFilter}
                    onChange={(e) => setSubcategoryFilter(e.target.value)}
                    disabled={!categoryFilter}
                    className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
                  >
                    <option value="">All Subcategories</option>
                    {categoryFilter && subcategories[categoryFilter]?.map((subcat) => (
                      <option key={subcat} value={subcat}>{subcat}</option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Min Score */}
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">
                  Min Score: {minScore.toFixed(2)}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={minScore}
                  onChange={(e) => setMinScore(parseFloat(e.target.value))}
                  className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
                />
              </div>

              {/* Reset filters */}
              {activeFilterCount > 0 && (
                <button
                  onClick={() => {
                    setSearchMode('Both')
                    setSourceFilter('All Sources')
                    setTypeFilter('Both')
                    setAssignmentFilter('all')
                    setCategoryFilter('')
                    setSubcategoryFilter('')
                    setMinScore(0.1)
                  }}
                  className="w-full py-2 text-sm text-gray-400 hover:text-white transition-colors"
                >
                  Reset filters
                </button>
              )}
            </div>
          )}
        </div>
      </header>

      {/* Results */}
      <div className="px-4 pt-4">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
          </div>
        ) : hasSearched ? (
          searchResults.length > 0 ? (
            <div className="space-y-3">
              <p className="text-sm text-gray-400">{searchResults.length} results</p>
              {searchResults.map((story, idx) => (
                <StoryCard
                  key={`${story.book_slug}-${story.title}-${idx}`}
                  story={story}
                  showScore={true}
                  onAssigned={() => {
                    // Optionally re-run search to refresh results
                  }}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-400">
              <p>No results found</p>
              <p className="text-sm mt-1">Try different keywords or adjust filters</p>
            </div>
          )
        ) : (
          <div className="text-center py-12 text-gray-400">
            <svg className="w-12 h-12 mx-auto mb-4 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <p>Search for stories</p>
            <p className="text-sm mt-1">Use keywords, themes, or phrases</p>
          </div>
        )}
      </div>
    </div>
  )
}
