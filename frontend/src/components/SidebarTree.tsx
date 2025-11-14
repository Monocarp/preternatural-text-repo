// src/components/SidebarTree.tsx
import { useEffect } from 'react'
import Tree from 'rc-tree'
import 'rc-tree/assets/index.css'  // Basic styling; customize with Tailwind
import { useStore } from '../store'

const SidebarTree = () => {
  const { tree, loadTree, loadStories } = useStore()

  useEffect(() => {
    loadTree()
  }, [])

  const onSelect = (selectedKeys, info) => {
    if (selectedKeys.length === 0) return;  // Skip if no selection
    const key = selectedKeys[0]
    if (key === 'unassigned') {
      // Special handling for unassigned
      axios.get('/api/get-unassigned')
        .then(res => {
          useStore.getState().setStories(res.data)  // Assume setStories in store
        })
        .catch(err => console.error(err))
    } else {
      const path = key.split('/')
      loadStories(path)
    }
  }

  const buildTreeData = (current, path = '') => {
    return Object.keys(current).map((key) => {
      const fullPath = path ? `${path}/${key}` : key
      return {
        key: fullPath,
        title: key,
        children: typeof current[key] === 'object' ? buildTreeData(current[key], fullPath) : undefined
      }
    })
  }

  const treeData = buildTreeData(tree)
  treeData.push({ key: 'unassigned', title: 'Unassigned' })  // Add unassigned as root-level

  return (
    <aside className="w-64 h-full overflow-y-auto bg-gray-100 p-4">
      <Tree
        treeData={treeData}
        onSelect={onSelect}
        defaultExpandAll
        className="text-gray-800"
      />
    </aside>
  )
}

export default SidebarTree