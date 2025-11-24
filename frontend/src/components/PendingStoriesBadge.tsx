import { useState, useEffect, forwardRef, useImperativeHandle } from 'react'
import apiClient from '../utils/axios'

interface PendingStoriesBadgeProps {
  onReindexClick?: () => void
}

export interface PendingStoriesBadgeRef {
  refresh: () => void
}

const PendingStoriesBadge = forwardRef<PendingStoriesBadgeRef, PendingStoriesBadgeProps>(({ onReindexClick }, ref) => {
  const [pendingCount, setPendingCount] = useState(0)
  const [reindexing, setReindexing] = useState(false)

  const fetchPendingCount = async () => {
    try {
      const response = await apiClient.get('/pending-stories-count')
      setPendingCount(response.data.count)
    } catch (error) {
      console.error('Failed to fetch pending count:', error)
    }
  }

  useEffect(() => {
    fetchPendingCount()
    
    // Poll every 30 seconds
    const interval = setInterval(fetchPendingCount, 30000)
    
    // Listen for custom event when stories are added
    const handlePendingStoriesChanged = () => {
      fetchPendingCount()
    }
    window.addEventListener('pendingStoriesChanged', handlePendingStoriesChanged)
    
    return () => {
      clearInterval(interval)
      window.removeEventListener('pendingStoriesChanged', handlePendingStoriesChanged)
    }
  }, [])

  // Expose refresh function to parent components
  useImperativeHandle(ref, () => ({
    refresh: fetchPendingCount
  }))

  const handleReindex = async () => {
    if (!confirm(`Reindex ${pendingCount} pending stories? This may take 10-30 seconds.`)) {
      return
    }

    setReindexing(true)
    try {
      const response = await apiClient.post('/reindex-pending')
      alert(`Success! Indexed ${response.data.indexed_count} stories in ${response.data.duration_seconds}s`)
      setPendingCount(0)
      if (onReindexClick) {
        onReindexClick()
      }
    } catch (error: any) {
      const message = error?.response?.data?.detail || 'Reindex failed'
      alert(`Error: ${message}`)
    } finally {
      setReindexing(false)
    }
  }

  if (pendingCount === 0) {
    return null
  }

  return (
    <div className="flex items-center gap-2 px-3 py-1 bg-yellow-500 text-black rounded text-sm">
      <span className="font-medium">{pendingCount} Pending Stories</span>
      <button
        onClick={handleReindex}
        disabled={reindexing}
        className="px-2 py-1 bg-yellow-600 hover:bg-yellow-700 rounded text-xs disabled:opacity-50"
      >
        {reindexing ? 'Reindexing...' : 'Reindex Now'}
      </button>
    </div>
  )
})

PendingStoriesBadge.displayName = 'PendingStoriesBadge'

export default PendingStoriesBadge