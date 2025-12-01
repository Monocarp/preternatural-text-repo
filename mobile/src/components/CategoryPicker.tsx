import { useEffect, useState, useMemo } from 'react'
import apiClient from '../utils/api'

interface TreeNode {
  [key: string]: TreeNode | string[]
}

interface CategoryPickerProps {
  keywords?: string
  onSelect: (path: string[]) => void
  onCancel: () => void
  assigning: boolean
}

export default function CategoryPicker({ keywords, onSelect, onCancel, assigning }: CategoryPickerProps) {
  const [tree, setTree] = useState<TreeNode>({})
  const [loading, setLoading] = useState(true)
  const [currentPath, setCurrentPath] = useState<string[]>([])
  const [newCategoryName, setNewCategoryName] = useState('')
  const [showNewInput, setShowNewInput] = useState(false)

  useEffect(() => {
    loadTree()
  }, [])

  const loadTree = async () => {
    try {
      const res = await apiClient.get('/get-tree')
      setTree(res.data || {})
    } catch (err) {
      console.error('Error loading tree:', err)
    } finally {
      setLoading(false)
    }
  }

  // Generate suggestions based on keywords matching category names
  const suggestions = useMemo(() => {
    if (!keywords || !tree || Object.keys(tree).length === 0) return []

    const keywordList = keywords.toLowerCase().split(',').map(k => k.trim()).filter(Boolean)
    const matches: Array<{ path: string[]; score: number }> = []

    // Recursive function to find all paths and score them
    const findPaths = (node: TreeNode, path: string[]) => {
      for (const key of Object.keys(node)) {
        if (key === '_stories') continue
        
        const currentPath = [...path, key]
        const keyLower = key.toLowerCase()
        
        // Score based on keyword matches
        let score = 0
        for (const kw of keywordList) {
          if (keyLower.includes(kw) || kw.includes(keyLower)) {
            score += 2
          }
          // Partial match
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
          findPaths(child as TreeNode, currentPath)
        }
      }
    }

    findPaths(tree, [])

    // Sort by score and take top 5
    return matches
      .sort((a, b) => b.score - a.score)
      .slice(0, 5)
      .map(m => m.path)
  }, [keywords, tree])

  // Get current level of tree based on path
  const getCurrentNode = (): TreeNode => {
    let node = tree
    for (const segment of currentPath) {
      const child = node[segment]
      if (child && typeof child === 'object' && !Array.isArray(child)) {
        node = child as TreeNode
      } else {
        break
      }
    }
    return node
  }

  const currentNode = getCurrentNode()
  const categories = Object.keys(currentNode).filter(k => k !== '_stories')

  const navigateInto = (name: string) => {
    setCurrentPath(prev => [...prev, name])
    setShowNewInput(false)
    setNewCategoryName('')
  }

  const navigateUp = () => {
    setCurrentPath(prev => prev.slice(0, -1))
    setShowNewInput(false)
    setNewCategoryName('')
  }

  const handleSelect = (additionalPath: string[] = []) => {
    onSelect([...currentPath, ...additionalPath])
  }

  const handleCreateAndSelect = () => {
    if (newCategoryName.trim()) {
      onSelect([...currentPath, newCategoryName.trim()])
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-400"></div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Suggestions section */}
      {suggestions.length > 0 && currentPath.length === 0 && (
        <div>
          <h4 className="text-sm font-medium text-gray-400 mb-2 flex items-center gap-2">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 text-yellow-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            Suggested Categories
          </h4>
          <div className="space-y-2">
            {suggestions.map((path, idx) => (
              <button
                key={idx}
                onClick={() => onSelect(path)}
                disabled={assigning}
                className="w-full bg-gradient-to-r from-yellow-500/10 to-orange-500/10 border border-yellow-500/30 rounded-lg px-4 py-3 text-left hover:from-yellow-500/20 hover:to-orange-500/20 active:from-yellow-500/30 active:to-orange-500/30 transition-colors disabled:opacity-50"
              >
                <div className="text-white text-sm">{path.join(' → ')}</div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Divider */}
      {suggestions.length > 0 && currentPath.length === 0 && (
        <div className="flex items-center gap-3 text-gray-500 text-sm">
          <div className="flex-1 h-px bg-gray-700"></div>
          <span>or browse</span>
          <div className="flex-1 h-px bg-gray-700"></div>
        </div>
      )}

      {/* Breadcrumb navigation */}
      {currentPath.length > 0 && (
        <div className="flex items-center gap-2 text-sm">
          <button
            onClick={() => setCurrentPath([])}
            className="text-blue-400 hover:text-blue-300"
          >
            Root
          </button>
          {currentPath.map((segment, idx) => (
            <span key={idx} className="flex items-center gap-2">
              <span className="text-gray-500">→</span>
              <button
                onClick={() => setCurrentPath(currentPath.slice(0, idx + 1))}
                className={idx === currentPath.length - 1 ? 'text-white' : 'text-blue-400 hover:text-blue-300'}
              >
                {segment}
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Tree browser */}
      <div>
        <h4 className="text-sm font-medium text-gray-400 mb-2">
          {currentPath.length === 0 ? 'Browse Categories' : 'Subcategories'}
        </h4>
        
        {categories.length > 0 ? (
          <div className="space-y-2">
            {categories.map((name) => {
              const child = currentNode[name]
              const hasChildren = child && typeof child === 'object' && !Array.isArray(child) && 
                Object.keys(child).some(k => k !== '_stories')
              
              return (
                <div key={name} className="bg-gray-800 border border-gray-700 rounded-lg overflow-hidden">
                  <div className="flex items-center">
                    {/* Navigate into button */}
                    {hasChildren && (
                      <button
                        onClick={() => navigateInto(name)}
                        className="px-3 py-3 text-gray-400 hover:text-white hover:bg-gray-700"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </button>
                    )}
                    
                    {/* Category name */}
                    <div className={`flex-1 py-3 ${hasChildren ? '' : 'pl-4'}`}>
                      <span className="text-white">{name}</span>
                    </div>
                    
                    {/* Select button */}
                    <button
                      onClick={() => handleSelect([name])}
                      disabled={assigning}
                      className="px-4 py-3 text-blue-400 hover:text-blue-300 hover:bg-gray-700 font-medium text-sm disabled:opacity-50"
                    >
                      {assigning ? '...' : 'Select'}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        ) : (
          <p className="text-gray-500 text-sm py-2">No subcategories here</p>
        )}

        {/* Assign to current path (if not root) */}
        {currentPath.length > 0 && (
          <button
            onClick={() => handleSelect()}
            disabled={assigning}
            className="w-full mt-3 py-3 bg-blue-600 hover:bg-blue-500 active:bg-blue-700 text-white rounded-lg font-medium disabled:opacity-50"
          >
            {assigning ? 'Assigning...' : `Assign to "${currentPath[currentPath.length - 1]}"`}
          </button>
        )}

        {/* Create new category */}
        <div className="mt-4 pt-4 border-t border-gray-700">
          {showNewInput ? (
            <div className="space-y-2">
              <input
                type="text"
                value={newCategoryName}
                onChange={(e) => setNewCategoryName(e.target.value)}
                placeholder="New category name"
                className="w-full bg-gray-800 border border-gray-600 rounded-lg px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
                autoFocus
              />
              <div className="flex gap-2">
                <button
                  onClick={handleCreateAndSelect}
                  disabled={!newCategoryName.trim() || assigning}
                  className="flex-1 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium disabled:opacity-50 disabled:bg-gray-700"
                >
                  Create & Assign
                </button>
                <button
                  onClick={() => { setShowNewInput(false); setNewCategoryName('') }}
                  className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg"
                >
                  Cancel
                </button>
              </div>
              {currentPath.length > 0 && (
                <p className="text-xs text-gray-500">
                  Will create under: {currentPath.join(' → ')}
                </p>
              )}
            </div>
          ) : (
            <button
              onClick={() => setShowNewInput(true)}
              className="w-full py-3 border border-dashed border-gray-600 rounded-lg text-gray-400 hover:text-white hover:border-gray-500 transition-colors flex items-center justify-center gap-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Create New Category
            </button>
          )}
        </div>
      </div>

      {/* Back / Cancel button */}
      <div className="flex gap-2 pt-2">
        {currentPath.length > 0 && (
          <button
            onClick={navigateUp}
            className="flex-1 py-3 bg-gray-700 text-gray-300 rounded-lg font-medium"
          >
            ← Back
          </button>
        )}
        <button
          onClick={onCancel}
          className="flex-1 py-3 bg-gray-700 text-gray-300 rounded-lg font-medium"
        >
          Cancel
        </button>
      </div>
    </div>
  )
}
