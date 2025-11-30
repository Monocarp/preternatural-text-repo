// src/hooks/index.ts
/**
 * Shared hooks for story management operations.
 * 
 * These hooks centralize logic that was previously duplicated across
 * SearchCurate, BookDetail, and Archive pages.
 * 
 * Usage:
 * 
 * ```tsx
 * import { 
 *   useBoundaryEditor, 
 *   useCategoryAssignment,
 *   useKeywordsEditor,
 *   useNewStoryCreator 
 * } from '../hooks'
 * ```
 */

// Text position calculation (low-level utility)
export { 
  useTextPositionClick, 
  calculateCharPositionFromClick 
} from './useTextPositionClick'

// Boundary editing for existing stories
export { useBoundaryEditor } from './useBoundaryEditor'
export type { Story as BoundaryEditorStory } from './useBoundaryEditor'

// Category assignment
export { useCategoryAssignment } from './useCategoryAssignment'
export type { Story as CategoryAssignmentStory } from './useCategoryAssignment'

// Keywords editing
export { useKeywordsEditor } from './useKeywordsEditor'
export type { Story as KeywordsEditorStory } from './useKeywordsEditor'

// New story creation
export { useNewStoryCreator } from './useNewStoryCreator'
