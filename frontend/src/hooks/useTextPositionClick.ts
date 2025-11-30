// src/hooks/useTextPositionClick.ts
/**
 * Hook for calculating character position from click events on text containers.
 * 
 * This is used by boundary editing and new story selection features.
 * Different components may have slightly different needs:
 * - BookDetail uses stopPropagation (nested clickable elements in review view)
 * - Some components need the indexOf fallback for complex DOM structures
 */

import { useCallback } from 'react'
import type { RefObject } from 'react'

interface UseTextPositionClickOptions {
  /** Whether to call stopPropagation (needed when nested in clickable containers) */
  stopPropagation?: boolean
  /** Enable fallback using indexOf for complex DOM structures */
  useIndexOfFallback?: boolean
}

/**
 * Calculate character position from a click event within a text container.
 * 
 * Uses document.caretRangeFromPoint and TreeWalker to accurately determine
 * the character index where the user clicked.
 */
export function calculateCharPositionFromClick(
  e: React.MouseEvent<HTMLDivElement>,
  textContainerRef: RefObject<HTMLDivElement | null>,
  fullTextLength: number,
  options: UseTextPositionClickOptions = {}
): number | null {
  const { stopPropagation = false, useIndexOfFallback = true } = options
  
  if (!textContainerRef.current) return null
  
  e.preventDefault()
  if (stopPropagation) {
    e.stopPropagation()
  }
  
  const textContainer = textContainerRef.current
  const clickX = e.clientX
  const clickY = e.clientY
  
  // Create a range at the click point
  const range = document.caretRangeFromPoint?.(clickX, clickY)
  if (!range) return null
  
  // Calculate character position by walking through text nodes
  let charPos = 0
  const walker = document.createTreeWalker(
    textContainer,
    NodeFilter.SHOW_TEXT,
    null
  )
  
  let node: Node | null
  while ((node = walker.nextNode())) {
    const textNode = node as Text
    if (range.startContainer === textNode) {
      charPos += range.startOffset
      break
    } else if (range.startContainer.contains?.(textNode) || textNode.contains?.(range.startContainer)) {
      // If the range is within this text node's parent, calculate offset
      if (range.startContainer.nodeType === Node.TEXT_NODE) {
        if (useIndexOfFallback) {
          const rangeText = (range.startContainer as Text).textContent || ''
          const beforeRange = textContainer.textContent?.indexOf(rangeText, charPos) || charPos
          charPos = beforeRange + range.startOffset
        } else {
          charPos += range.startOffset
        }
      } else {
        charPos += textNode.textContent?.length || 0
      }
      break
    } else {
      charPos += textNode.textContent?.length || 0
    }
  }
  
  // Fallback: use textContent if walker didn't find it
  if (useIndexOfFallback && charPos === 0 && range.startContainer.nodeType === Node.TEXT_NODE) {
    const allText = textContainer.textContent || ''
    const clickedText = (range.startContainer as Text).textContent || ''
    const index = allText.indexOf(clickedText)
    if (index !== -1) {
      charPos = index + range.startOffset
    }
  }
  
  // Ensure valid range
  return Math.min(Math.max(0, charPos), fullTextLength)
}

/**
 * Hook that creates a click handler for text position selection.
 * 
 * @param textContainerRef - Ref to the text container element
 * @param fullText - The full text content (for length validation)
 * @param onPositionSelect - Callback when position is selected
 * @param options - Additional options
 */
export function useTextPositionClick(
  textContainerRef: RefObject<HTMLDivElement | null>,
  fullText: string,
  onPositionSelect: (charPos: number) => void,
  options: UseTextPositionClickOptions = {}
) {
  const handleClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const charPos = calculateCharPositionFromClick(
      e,
      textContainerRef,
      fullText.length,
      options
    )
    
    if (charPos !== null) {
      onPositionSelect(charPos)
    }
  }, [textContainerRef, fullText.length, onPositionSelect, options])
  
  return handleClick
}
