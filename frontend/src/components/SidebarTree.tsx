// src/components/SidebarTree.tsx
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import Tree from 'rc-tree'
import 'rc-tree/assets/index.css'
import './SidebarTree.css'
import { useStore } from '../store'
import { encodePathSegmentsForRoute } from '../utils/path'

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
  const [expandedKeys, setExpandedKeys] = useState<string[]>(['archive'])
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  useEffect(() => {
    loadTree()
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
    
    return (
      <div className="flex items-center w-full group relative pr-6">
        <span 
          className="cursor-pointer hover:text-blue-400 flex-1 text-gray-200 pr-4"
          onClick={(e) => {
            e.stopPropagation()
            onTitleClick(e, nodeData)
          }}
        >
          {nodeData.title}
        </span>
        {hasChildren && (
          <span
            className="text-gray-500 text-xs cursor-pointer hover:text-gray-300 absolute right-0"
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
    <aside className={`h-full bg-gray-800 border-r border-gray-700 transition-all duration-300 ease-in-out flex flex-col relative ${
      sidebarCollapsed ? 'w-12' : 'w-64'
    }`}>
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
        </div>
      )}

      {/* Tree Content */}
      {!sidebarCollapsed ? (
        <div className="flex-1 overflow-y-auto pl-4 pt-4 pb-4 pr-0">
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
    </aside>
  )
}

export default SidebarTree