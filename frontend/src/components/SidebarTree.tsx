// src/components/SidebarTree.tsx
import { useEffect, useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { useStackApp } from '@stackframe/react'
import Tree from 'rc-tree'
import 'rc-tree/assets/index.css'
import './SidebarTree.css'
import { useStore } from '../store'
import { encodePathSegmentsForRoute } from '../utils/path'
import CategoryManager from './CategoryManager'

type TreeNode = {
  key: string
  title: string
  children?: TreeNode[]
  pathSegments?: string[]
}

const buildTreeData = (current: any, pathSegments: string[] = []): TreeNode[] => {
  if (!current || typeof current !== 'object') return []

  return Object.entries(current)
    .filter(([key]) => key !== '_stories')
    .map(([key, value]) => {
      const nodePath = [...pathSegments, key]
      const hasChildCategories =
        value &&
        typeof value === 'object' &&
        !Array.isArray(value) &&
        Object.keys(value as Record<string, any>).some((childKey) => childKey !== '_stories')

      return {
        key: nodePath.join('||'),
        title: key,
        pathSegments: nodePath,
        children: hasChildCategories ? buildTreeData(value, nodePath) : undefined,
      }
    })
}

const SidebarTree = () => {
  const { tree, loadTree } = useStore()
  const navigate = useNavigate()
  const app = useStackApp()
  const [currentUserEmail, setCurrentUserEmail] = useState<string | null>(null)
  const [isEditor, setIsEditor] = useState(false)
  const [expandedKeys, setExpandedKeys] = useState<string[]>(['archive'])
  // Category manager state
  const [categoryManagerOpen, setCategoryManagerOpen] = useState(false)
  const [categoryManagerPosition, setCategoryManagerPosition] = useState<{ x: number; y: number } | undefined>()
  const [selectedCategoryPath, setSelectedCategoryPath] = useState<string[]>([])
  const [selectedCategoryName, setSelectedCategoryName] = useState<string | null>(null)
  // Auto-collapse sidebar on smaller screens (< 1024px)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      return window.innerWidth < 1024
    }
    return false
  })

  // Calculate the maximum depth of currently visible nodes
  // When a node is expanded, its children are visible at depth + 1
  const maxVisibleDepth = useMemo(() => {
    let maxDepth = 0
    for (const key of expandedKeys) {
      // Each key uses || as separator, so count separators + 1 = depth
      // 'archive' is depth 0, 'Demonic Activity' is depth 1, etc.
      if (key === 'archive' || key === 'unassigned') continue
      const depth = key.split('||').length
      // Add 1 because expanding a node makes its children visible at the next level
      const visibleChildDepth = depth + 1
      if (visibleChildDepth > maxDepth) maxDepth = visibleChildDepth
    }
    return maxDepth
  }, [expandedKeys])

  // Calculate dynamic sidebar width based on depth
  // Base: 200px min, add 52px per level beyond 2
  const dynamicSidebarStyle = useMemo(() => {
    if (sidebarCollapsed) return { width: '3rem' } // 48px when collapsed
    const baseMinWidth = 200
    const baseMaxWidth = 280
    const extraPerLevel = 52 // pixels per additional level
    const thresholdDepth = 2 // start expanding after this depth
    
    if (maxVisibleDepth <= thresholdDepth) {
      return { 
        width: '15vw',
        minWidth: `${baseMinWidth}px`,
        maxWidth: `${baseMaxWidth}px`
      }
    }
    
    const extraLevels = maxVisibleDepth - thresholdDepth
    const newMinWidth = baseMinWidth + (extraLevels * extraPerLevel)
    const newMaxWidth = baseMaxWidth + (extraLevels * extraPerLevel)
    
    return {
      width: `max(15vw, ${newMinWidth}px)`,
      minWidth: `${newMinWidth}px`,
      maxWidth: `${newMaxWidth}px`
    }
  }, [sidebarCollapsed, maxVisibleDepth])

  // Listen for window resize to auto-collapse/expand
  useEffect(() => {
    const handleResize = () => {
      if (window.innerWidth < 1024) {
        setSidebarCollapsed(true)
      }
    }
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const extractUserLabel = (user: any | null | undefined) => {
    if (!user) return null
    return (
      user.email ??
      user.primary_email ??
      user.primaryEmail ??
      user.display_name ??
      user.displayName ??
      user.name ??
      null
    )
  }

  // List of editor emails (should match backend EDITOR_EMAILS)
  // If VITE_EDITOR_EMAILS is not set, allow any signed-in user to see the UI
  // (backend will still enforce actual permissions)
  const EDITOR_EMAILS = import.meta.env.VITE_EDITOR_EMAILS?.split(',').map((e: string) => e.trim().toLowerCase()) || []

  const checkIsEditor = (email: string | null) => {
    if (!email) return false
    // If no editor emails configured, allow any signed-in user to see editor UI
    // Backend will still enforce actual permissions
    if (EDITOR_EMAILS.length === 0) return true
    return EDITOR_EMAILS.includes(email.toLowerCase())
  }

  // Handle right-click to open category manager
  const handleCategoryContextMenu = (e: React.MouseEvent, pathSegments: string[], categoryName: string | null) => {
    e.preventDefault()
    e.stopPropagation()
    setSelectedCategoryPath(pathSegments)
    setSelectedCategoryName(categoryName)
    setCategoryManagerPosition({ x: e.clientX, y: e.clientY })
    setCategoryManagerOpen(true)
  }

  // Handle tree change (refresh after category create/delete)
  const handleTreeChange = () => {
    loadTree()
  }

  useEffect(() => {
    loadTree()
    // Load current user (if any)
    ;(async () => {
      try {
        const u = await app.getUser()
        const label = extractUserLabel(u as any)
        console.log('[SidebarTree] User loaded:', label, 'isEditor:', checkIsEditor(label))
        setCurrentUserEmail(label)
        setIsEditor(checkIsEditor(label))
      } catch (_e) {
        console.log('[SidebarTree] No user logged in')
        setCurrentUserEmail(null)
        setIsEditor(false)
      }
    })()

    // Keep auth state in sync when returning from OAuth, tab focus, etc.
    const refreshUser = async () => {
      try {
        const u = await app.getUser()
        const label = extractUserLabel(u as any)
        if (label) {
          setCurrentUserEmail(label)
          setIsEditor(checkIsEditor(label))
        } else {
          setCurrentUserEmail(null)
          setIsEditor(false)
        }
      } catch (_e) {
        setCurrentUserEmail(null)
        setIsEditor(false)
      }
    }
    const onFocus = () => { refreshUser() }
    const onVisibility = () => { if (document.visibilityState === 'visible') refreshUser() }
    window.addEventListener('focus', onFocus)
    document.addEventListener('visibilitychange', onVisibility)
    const interval = setInterval(refreshUser, 5000)

    return () => {
      window.removeEventListener('focus', onFocus)
      document.removeEventListener('visibilitychange', onVisibility)
      clearInterval(interval)
    }
  }, [])

  // Handle node title click (navigate to category page)
  const onTitleClick = (e: React.MouseEvent, node: TreeNode | any) => {
    e.stopPropagation()
    const key = node.key as string
    if (key === 'archive') {
      // Clicking "Story Archive" expands to show level 1
      if (!expandedKeys.includes('archive')) {
        setExpandedKeys([...expandedKeys, 'archive'])
      }
      navigate('/archive')
    } else if (key === 'unassigned') {
      navigate('/archive/unassigned')
    } else {
      // Try to get pathSegments from node first
      let pathSegments = (node as TreeNode).pathSegments
      
      // Fallback: reconstruct from key if pathSegments not set
      if (!pathSegments || pathSegments.length === 0) {
        pathSegments = key.split('||').filter(Boolean)
        console.warn('SidebarTree: pathSegments not found on node, reconstructed from key:', key, '->', pathSegments)
      }
      
      if (pathSegments.length > 0) {
        const encoded = encodePathSegmentsForRoute(pathSegments)
        console.log('SidebarTree navigation: node.key =', key)
        console.log('SidebarTree navigation: node.pathSegments =', (node as TreeNode).pathSegments)
        console.log('SidebarTree navigation: using pathSegments =', pathSegments)
        console.log('SidebarTree navigation: encoded =', encoded)
        console.log('SidebarTree navigation: navigating to =', `/archive/${encoded}`)
        navigate(`/archive/${encoded}`)
      } else {
        console.error('SidebarTree: No pathSegments found for node:', node)
      }
    }
  }

  // Handle expand/collapse (arrow click)
  const onExpand = (expandedKeys: React.Key[]) => {
    setExpandedKeys(expandedKeys as string[])
  }

  // Custom node renderer: title click navigates, arrow on right expands
  const titleRender = (nodeData: any) => {
    const hasChildren = nodeData.children && nodeData.children.length > 0
    const isExpanded = expandedKeys.includes(nodeData.key)
    const shouldTruncate = nodeData.title.length > 20
    const pathSegments = (nodeData as TreeNode).pathSegments || []
    
    return (
      <div 
        className="flex items-center w-full group relative overflow-hidden"
        onContextMenu={(e) => {
          // Don't show context menu for special nodes
          if (nodeData.key === 'archive' || nodeData.key === 'unassigned') return
          handleCategoryContextMenu(e, pathSegments, nodeData.title)
        }}
      >
        <span 
          className={`cursor-pointer hover:text-blue-400 text-gray-200 pr-2 ${shouldTruncate ? 'truncate' : ''}`}
          style={shouldTruncate && hasChildren ? { maxWidth: 'calc(100% - 1.5rem)' } : undefined}
          title={shouldTruncate ? nodeData.title : undefined}
          onClick={(e) => {
            e.stopPropagation()
            onTitleClick(e, nodeData)
          }}
        >
          {nodeData.title}
        </span>
        {hasChildren && (
          <span
            className="text-gray-500 text-xs cursor-pointer hover:text-gray-300 flex-shrink-0 ml-auto"
            onClick={(e) => {
              e.stopPropagation()
              // Toggle expansion
              if (isExpanded) {
                setExpandedKeys(expandedKeys.filter(k => k !== nodeData.key))
              } else {
                setExpandedKeys([...expandedKeys, nodeData.key])
              }
            }}
          >
            {isExpanded ? '▼' : '▶'}
          </span>
        )}
        {/* Show gear icon for editors on hover */}
        {isEditor && nodeData.key !== 'archive' && nodeData.key !== 'unassigned' && (
          <span
            className="text-gray-500 text-xs cursor-pointer hover:text-blue-400 flex-shrink-0 ml-1 opacity-0 group-hover:opacity-100 transition-opacity"
            onClick={(e) => {
              e.stopPropagation()
              handleCategoryContextMenu(e as any, pathSegments, nodeData.title)
            }}
            title="Manage category"
          >
            ⚙
          </span>
        )}
      </div>
    )
  }

  // Prevent default selection behavior - we handle navigation in onTitleClick
  const onSelect = () => {
    // Do nothing - navigation is handled by title click
  }

  // Build tree with "Story Archive" as root
  const treeData: TreeNode[] = [
    {
      key: 'archive',
      title: 'Story Archive',
      children: buildTreeData(tree)
    },
    {
      key: 'unassigned',
      title: 'Unassigned',
      children: undefined
    }
  ]

  return (
    <>
      {/* Category Manager Popup */}
      {categoryManagerOpen && (
        <CategoryManager
          currentPath={selectedCategoryPath}
          categoryName={selectedCategoryName}
          isEditor={isEditor}
          onTreeChange={handleTreeChange}
          position={categoryManagerPosition}
          onClose={() => setCategoryManagerOpen(false)}
        />
      )}
      
      <aside 
        className="h-full bg-gray-800 border-r border-gray-700 transition-all duration-300 ease-in-out flex flex-col relative flex-shrink-0"
        style={dynamicSidebarStyle}
      >
      {/* Header with Toggle Button */}
      <div className={`p-3 border-b border-gray-700 flex items-center ${sidebarCollapsed ? 'justify-center' : 'justify-between'} bg-gray-800`}>
        {!sidebarCollapsed && (
          <h2 className="text-lg font-semibold text-white">Navigation</h2>
        )}
        <button
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            console.log('Toggling sidebar, current state:', sidebarCollapsed)
            setSidebarCollapsed(!sidebarCollapsed)
          }}
          className="p-2.5 hover:bg-blue-600 hover:text-white active:bg-blue-700 rounded-md transition-all flex-shrink-0 border border-gray-600 bg-gray-700 shadow-sm hover:shadow-md z-10 min-w-[36px] min-h-[36px] flex items-center justify-center"
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          title={sidebarCollapsed ? 'Click to expand menu' : 'Click to collapse menu'}
        >
          {sidebarCollapsed ? (
            <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M9 5l7 7-7 7" />
            </svg>
          ) : (
            <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M15 19l-7-7 7-7" />
            </svg>
          )}
        </button>
      </div>

      {/* Navigation Links */}
      {!sidebarCollapsed && (
        <div className="p-2 border-b border-gray-700 space-y-1">
          <button
            onClick={() => navigate('/search-curate')}
            className="w-full text-left px-3 py-2 rounded text-gray-200 hover:bg-gray-700 hover:text-blue-400 transition-colors flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <span>Search & Curate</span>
          </button>
          <button
            onClick={() => navigate('/book-archive')}
            className="w-full text-left px-3 py-2 rounded text-gray-200 hover:bg-gray-700 hover:text-blue-400 transition-colors flex items-center gap-2"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
            <span>Book Archive</span>
          </button>
        </div>
      )}

      {/* Tree Content */}
      {!sidebarCollapsed ? (
        <div className="flex-1 overflow-y-auto pl-4 pt-4 pb-4 pr-0">
          {/* Add Root Category Button for Editors */}
          {isEditor && (
            <button
              onClick={(e) => {
                e.stopPropagation()
                setSelectedCategoryPath([])
                setSelectedCategoryName(null)
                setCategoryManagerPosition({ x: e.clientX + 10, y: e.clientY })
                setCategoryManagerOpen(true)
              }}
              className="mb-2 flex items-center gap-1 text-xs text-gray-400 hover:text-green-400 transition-colors"
              title="Add a new top-level category"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add Category
            </button>
          )}
          <Tree
            treeData={treeData}
            expandedKeys={expandedKeys}
            onExpand={onExpand}
            onSelect={onSelect}
            titleRender={titleRender}
            defaultExpandAll={false}
            className="text-gray-200"
            showIcon={false}
            switcherIcon={() => null}
            icon={null}
            indent={12}
          />
        </div>
      ) : (
        /* Collapsed State - Minimal icons for quick access */
        <div className="flex flex-col items-center py-2 space-y-1">
          <button
            onClick={() => {
              setSidebarCollapsed(false)
              navigate('/search-curate')
            }}
            className="p-2 hover:bg-gray-700 rounded transition-colors w-full flex items-center justify-center"
            title="Search & Curate"
          >
            <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
          </button>
          <button
            onClick={() => {
              setSidebarCollapsed(false)
              navigate('/book-archive')
            }}
            className="p-2 hover:bg-gray-700 rounded transition-colors w-full flex items-center justify-center"
            title="Book Archive"
          >
            <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
            </svg>
          </button>
          <button
            onClick={() => {
              setSidebarCollapsed(false)
              navigate('/archive')
            }}
            className="p-2 hover:bg-gray-700 rounded transition-colors w-full flex items-center justify-center"
            title="Story Archive"
          >
            <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <button
            onClick={() => {
              setSidebarCollapsed(false)
              navigate('/archive/unassigned')
            }}
            className="p-2 hover:bg-gray-700 rounded transition-colors w-full flex items-center justify-center"
            title="Unassigned"
          >
            <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
          </button>
        </div>
      )}

      {/* Footer: Auth controls */}
      <div className="border-t border-gray-700 p-3 bg-gray-800">
        {!sidebarCollapsed ? (
          <div className="flex items-center justify-between gap-2">
            <span className="text-gray-300 text-xs truncate" title={currentUserEmail || ''}>
              {currentUserEmail ? currentUserEmail : 'Not signed in'}
            </span>
            {currentUserEmail ? (
              <button
                onClick={async (e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  try { await (app as any).signOut?.() } catch {}
                  setCurrentUserEmail(null)
                  navigate('/')
                }}
                className="px-2 py-1 text-sm rounded border border-gray-600 bg-gray-700 text-gray-200 hover:bg-gray-600"
                title="Sign out"
              >
                Sign out
              </button>
            ) : (
              <button
                onClick={(e) => {
                  e.preventDefault()
                  e.stopPropagation()
                  navigate('/login')
                }}
                className="px-2 py-1 text-sm rounded border border-gray-600 bg-gray-700 text-gray-200 hover:bg-gray-600"
                title="Sign in"
              >
                Sign in
              </button>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center">
            <button
              onClick={(e) => {
                e.preventDefault()
                e.stopPropagation()
                if (currentUserEmail) {
                  (async () => { try { await (app as any).signOut?.() } catch {} })()
                  setCurrentUserEmail(null)
                  navigate('/')
                } else {
                  navigate('/login')
                }
              }}
              className="p-2 hover:bg-gray-700 rounded transition-colors"
              title={currentUserEmail ? 'Sign out' : 'Sign in'}
            >
              {currentUserEmail ? (
                <svg className="w-5 h-5 text-gray-300" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a2 2 0 01-2 2H7a2 2 0 01-2-2V7a2 2 0 012-2h4a2 2 0 012 2v1" />
                </svg>
              ) : (
                <svg className="w-5 h-5 text-gray-300" viewBox="0 0 24 24" fill="none" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h9m0 0l-3-3m3 3l-3 3M9 5v.01M9 19v.01M4 9v.01M4 15v.01" />
                </svg>
              )}
            </button>
          </div>
        )}
      </div>
    </aside>
    </>
  )
}

export default SidebarTree