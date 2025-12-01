import { create } from 'zustand'

interface Story {
  title: string
  book_slug: string
  book_title?: string
  book_author?: string
  pages?: string
  keywords?: string
  start_char: number
  end_char: number
}

interface MobileStore {
  // Tree data
  tree: Record<string, any>
  setTree: (tree: Record<string, any>) => void
  
  // Current navigation path (breadcrumb)
  currentPath: string[]
  setCurrentPath: (path: string[]) => void
  pushPath: (segment: string) => void
  popPath: () => void
  
  // Stories in current category
  stories: Story[]
  setStories: (stories: Story[]) => void
  
  // Selected story for reader
  selectedStory: Story | null
  setSelectedStory: (story: Story | null) => void
  
  // Search
  searchQuery: string
  setSearchQuery: (query: string) => void
  searchResults: Story[]
  setSearchResults: (results: Story[]) => void
  
  // Loading states
  loading: boolean
  setLoading: (loading: boolean) => void
  
  // Auth
  userEmail: string | null
  setUserEmail: (email: string | null) => void
}

export const useStore = create<MobileStore>((set) => ({
  // Tree
  tree: {},
  setTree: (tree) => set({ tree }),
  
  // Navigation path
  currentPath: [],
  setCurrentPath: (path) => set({ currentPath: path }),
  pushPath: (segment) => set((state) => ({ 
    currentPath: [...state.currentPath, segment] 
  })),
  popPath: () => set((state) => ({ 
    currentPath: state.currentPath.slice(0, -1) 
  })),
  
  // Stories
  stories: [],
  setStories: (stories) => set({ stories }),
  
  // Selected story
  selectedStory: null,
  setSelectedStory: (story) => set({ selectedStory: story }),
  
  // Search
  searchQuery: '',
  setSearchQuery: (query) => set({ searchQuery: query }),
  searchResults: [],
  setSearchResults: (results) => set({ searchResults: results }),
  
  // Loading
  loading: false,
  setLoading: (loading) => set({ loading }),
  
  // Auth
  userEmail: null,
  setUserEmail: (email) => set({ userEmail: email }),
}))
