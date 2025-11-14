// src/store.ts
import { create } from 'zustand'
import axios from 'axios'  // Add this import

interface State {
  tree: any
  loading: boolean
  error: string | null
  stories: any[]
  selectedPath: string[]
  selectedStory: any | null
  loadTree: () => Promise<void>
  loadStories: (path: string[]) => Promise<void>
  selectStory: (story: any) => void
  toggleMode: (title: string, mode: 'static' | 'book', search_query?: string) => Promise<void>
  setStories: (stories: any[]) => void
}

export const useStore = create<State>((set, get) => ({
  tree: {},
  loading: false,
  error: null,
  stories: [],
  selectedPath: [],
  selectedStory: null,
  loadTree: async () => {
    set({ loading: true })
    try {
      const res = await axios.get('/api/get-tree')
      set({ tree: res.data, loading: false })
    } catch (err) {
      set({ error: err.message, loading: false })
    }
  },
  loadStories: async (path: string[]) => {
    set({ loading: true })
    try {
      const pathStr = path.join('/')
      const res = await axios.get(`/api/get-stories/${pathStr}`)
      set({ stories: res.data, selectedPath: path, loading: false })
    } catch (err) {
      set({ error: err.message, loading: false })
    }
  },
  selectStory: (story) => set({ selectedStory: story }),
  toggleMode: async (title: string, mode: 'static' | 'book', search_query?: string) => {
    set({ loading: true })
    try {
      const res = await axios.post('/api/render-story', { title, mode, search_query })
      set({ selectedStory: { ...get().selectedStory, html: res.data.html, mode }, loading: false })
    } catch (err) {
      set({ error: err.message, loading: false })
    }
  },
  setStories: (stories) => set({ stories }),
}))