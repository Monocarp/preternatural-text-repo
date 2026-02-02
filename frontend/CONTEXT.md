# Frontend Context

**Last Updated:** 2026-02-02

## Overview

React 18 + TypeScript frontend with Tailwind CSS styling. Uses Zustand for state management and custom hooks for shared component logic.

## Recent UI Improvements (Feb 2026)

### Search/Curate Page Enhancements
- **Story Titles:** Displayed prominently above story content in search results
- **Find Similar:** Button for each story to discover related content
- **Keywords Display:** All stories now show proper keywords (no longer "title as keywords")
- **TypeScript Cleanup:** Removed unused variables to fix build warnings

## Architecture

```
frontend/src/
├── main.tsx           # App entry, routing, Stack Auth provider
├── App.tsx            # Unused (routes defined in main.tsx)
├── store.ts           # Zustand global state
├── index.css          # Tailwind imports + global styles
├── pages/             # Route components
├── components/        # Reusable UI components
├── hooks/             # Custom React hooks for shared logic
│   ├── index.ts               # Hook exports
│   ├── useTextPositionClick.ts # Text click position calculation
│   ├── useBoundaryEditor.ts    # Story boundary editing
│   ├── useCategoryAssignment.ts # Category tree management
│   ├── useKeywordsEditor.ts    # Keywords inline editing
│   └── useNewStoryCreator.ts   # New story creation flow
└── utils/             # axios config, path helpers
```

---

## Custom Hooks (`hooks/`)

Shared state logic extracted from large page components to reduce duplication and improve maintainability.

### `useTextPositionClick.ts`

Utility for calculating character position from click events on text containers.

| Export | Signature | Purpose |
|--------|-----------|---------|
| `calculateCharPositionFromClick(e, ref, length, options)` | `(MouseEvent, RefObject, number, Options) => number \| null` | Calculate char position from click using caretRangeFromPoint + TreeWalker |
| `useTextPositionClick(ref, fullText, onSelect, options)` | Hook | Returns click handler for text position selection |

**Options:**
- `stopPropagation`: Call e.stopPropagation() (needed in BookDetail nested elements)
- `useIndexOfFallback`: Enable indexOf fallback for complex DOM structures

---

### `useKeywordsEditor.ts`

Hook for inline keywords editing with save/cancel.

| Function | Signature | Purpose |
|----------|-----------|---------|
| `useKeywordsEditor(options)` | `(Options) => Return` | Returns editing state and handlers |

**Return:**
- `isEditing`, `editedKeywords`, `saving` - State
- `startEditing(story)`, `setEditedKeywords(kw)`, `saveKeywords(story)`, `cancelEditing()` - Actions

**Options:**
- `onSaveSuccess(story, newKeywords)` - Called after successful save
- `onError(error)` - Called on error

---

### `useCategoryAssignment.ts`

Hook for managing category assignment state and operations.

| Function | Signature | Purpose |
|----------|-----------|---------|
| `useCategoryAssignment(selectedStory, options)` | `(Story \| null, Options) => Return` | Returns tree, path selection, and assign/remove handlers |

**Return:**
- `codexTree`, `selectedPath`, `currentAssignments`, `assigning`, `loading` - State
- `loadTree()`, `setSelectedPath(path)`, `handlePathLevelChange(level, value)` - Path management
- `assignCategory()`, `removeCategory(path)` - Assignment operations
- `getPathOptions(currentPath)` - Get child categories for dropdowns

**Options:**
- `onAssignSuccess(path)`, `onRemoveSuccess(path)`, `onError(error, op)` - Callbacks

---

### `useBoundaryEditor.ts`

Hook for story boundary editing state and click handling.

| Function | Signature | Purpose |
|----------|-----------|---------|
| `useBoundaryEditor(fullText, currentStory, options)` | `(string, Story \| null, Options) => Return` | Returns editing state, click handler, and save/cancel actions |

**Return:**
- `isEditing`, `editedStart`, `editedEnd`, `selectingStart`, `saving` - State
- `textContainerRef` - Ref for text container
- `startEditing(story)`, `cancelEditing()`, `handleTextClick(e)`, `saveBoundaries()` - Actions
- `setEditedStart(pos)`, `setEditedEnd(pos)` - Manual setters

**Options:**
- `onSave(story, start, end)` - Called to persist (should call API)
- `onSaveSuccess(story, start, end)` - Called after successful save
- `onCancel()` - Called on cancel
- `smartStartSelection` - BookDetail behavior: click before start sets new start
- `stopPropagation` - Call stopPropagation on clicks
- `useIndexOfFallback` - Enable indexOf fallback

---

### `useNewStoryCreator.ts`

Hook for creating new stories with text boundary selection.

| Function | Signature | Purpose |
|----------|-----------|---------|
| `useNewStoryCreator(options)` | `(Options) => Return` | Returns full new story creation state and flow |

**Return:**
- `isActive`, `bookSlug`, `start`, `end`, `selectingStart` - Position state
- `title`, `keywords`, `pages` - Form state
- `adding`, `fullText`, `loadingFullText` - Loading state
- `textContainerRef` - Ref for text container
- `canAdd`, `previewText` - Computed values
- `startCreating(bookSlug)`, `handleTextClick(e)`, `addStory(force?)`, `cancel()` - Actions
- `setTitle(t)`, `setKeywords(kw)`, `setPages(p)`, `setStart(pos)`, `setEnd(pos)` - Setters

**Options:**
- `onSuccess(response)`, `onError(error)` - Callbacks
- `stopPropagation`, `useIndexOfFallback` - Click options

---

## Function Reference

### Entry Point: `main.tsx`

| Element | Type | Purpose |
|---------|------|---------|
| `stackApp` | StackClientApp | Stack Auth client with cookie-based token storage |
| `queryClient` | QueryClient | React Query client for data caching |
| `<StackProvider>` | Provider | Wraps app with Stack Auth context |
| `<StackTheme>` | Provider | Applies dark theme to Stack Auth components |
| `<QueryClientProvider>` | Provider | Wraps app with React Query context |
| `<TooltipProvider>` | Provider | Radix UI tooltip context |
| **Routes** | | |
| `/` | Route | → `<Archive />` (category browser) |
| `/archive/:path*` | Route | → `<Archive />` (nested category) |
| `/search-curate` | Route | → `<SearchCurate />` (search & edit) |
| `/book-archive` | Route | → `<BookArchive />` (book list) |
| `/book-archive/:slug` | Route | → `<BookDetail />` (single book) |
| `/login` | Route | → `<Login />` (auth page) |
| `/callback` | Route | → `<Callback />` (OAuth callback) |

---

### State Management: `store.ts`

| Function/Property | Signature | Purpose |
|-------------------|-----------|---------|
| `useStore` | `create<State>()` | Zustand store hook |
| **State Properties** | | |
| `tree` | `any` | Codex tree hierarchy from `/api/get-tree` |
| `loading` | `boolean` | Global loading state |
| `error` | `string \| null` | Error message |
| `stories` | `any[]` | Currently displayed stories |
| `selectedPath` | `string[]` | Current category path segments |
| `selectedStory` | `any \| null` | Currently selected story for detail view |
| **Actions** | | |
| `loadTree()` | `() => Promise<void>` | Fetches codex tree from API, sets `tree` state |
| `loadStories(path)` | `(path: string[]) => Promise<void>` | Fetches stories for category path, sets `stories` & `selectedPath` |
| `selectStory(story)` | `(story: any) => void` | Sets `selectedStory` state |
| `toggleMode(title, mode, query?)` | `(title, mode, query?) => Promise<void>` | Renders story in static/book mode, updates `selectedStory.html` |
| `setStories(stories)` | `(stories: any[]) => void` | Direct setter for stories array |

---

### Utils: `axios.ts`

| Function/Variable | Signature | Purpose |
|-------------------|-----------|---------|
| `appInstance` | `StackClientApp \| null` | Module-level reference to Stack Auth app |
| `setStackApp(app)` | `(app: StackClientApp) => void` | Sets the Stack Auth app instance for token access |
| `getAccessToken()` | `() => Promise<string \| null>` | Extracts access token from cookies (stack-access-token, etc.) |
| `apiClient` | `AxiosInstance` | Pre-configured axios with `/api` baseURL, auth interceptor |
| **Request Interceptor** | | Adds `Authorization: Bearer {token}` header if available |
| **Response Interceptor** | | On 401, stores return URL in sessionStorage, redirects to `/login` |

---

### Utils: `path.ts`

| Function | Signature | Purpose |
|----------|-----------|---------|
| `encodePathSegmentsForApi(segments)` | `(segments: string[]) => string` | Single URL-encode, joins with `/` for API calls |
| `encodePathSegmentsForRoute(segments)` | `(segments: string[]) => string` | Double URL-encode for React Router (browser decodes once) |
| `decodeRoutePath(path)` | `(path?: string) => string[]` | Splits path by `/`, double-decodes each segment, handles edge cases |

---

### Page: `Archive.tsx`

Main category browser with story list and editing capabilities.

| Function | Signature | Purpose |
|----------|-----------|---------|
| **State** | | |
| `decodedPath` | `useMemo` | Extracts and decodes path from URL |
| `isUnassigned` | `boolean` | True if viewing `/archive/unassigned` |
| `subcategoryNames` | `useMemo` | Extracts child category names from tree for filter dropdown |
| `selectedSubcats` | `useMemo` | Parses `?subcats=` URL param for filtering |
| **Story Operations** | | |
| `handleEditTitle(story)` | `(story) => void` | Enters title editing mode for story |
| `handleSaveTitle(story)` | `(story) => Promise<void>` | POSTs `/update-title`, updates local state |
| `handleCancelEdit()` | `() => void` | Exits title editing mode |
| `handleDeleteStory(story)` | `(story) => Promise<void>` | DELETEs `/delete-story/{title}` with confirmation |
| `handleEditKeywords(story)` | `(story) => void` | Enters keywords editing mode |
| `handleSaveKeywords(story)` | `(story) => Promise<void>` | POSTs `/update-keywords`, updates local state |
| `handleCancelKeywordsEdit()` | `() => void` | Exits keywords editing mode |
| **View Toggle** | | |
| `handleToggleMode(story, mode)` | `(story, 'static' \| 'book') => Promise<void>` | POSTs `/render-story`, caches HTML, auto-scrolls in book mode |
| `handleStoryOpen(story)` | `(story) => Promise<void>` | Loads story content if not cached (called on Disclosure open) |
| **Boundary Editing** | | |
| `handleAdjustBoundaries(story)` | `(story) => Promise<void>` | Enters boundary edit mode, fetches `/full-text/{slug}` |
| `handleBoundaryTextClick(e)` | `(e: MouseEvent) => void` | Calculates char position from click, sets start/end |
| `handleSaveBoundaries()` | `() => Promise<void>` | POSTs `/update-boundaries`, re-renders story |
| `handleCancelBoundaryEdit()` | `() => void` | Exits boundary editing mode |
| **New Story Creation** | | |
| `handleEnterNewStoryMode(bookSlug)` | `(bookSlug) => Promise<void>` | Enters new story mode, loads full text |
| `handleNewStoryTextClick(e)` | `(e: MouseEvent) => void` | Click-to-set start/end for new story region |
| `handleAddNewStory()` | `() => Promise<void>` | POSTs `/add-story` with overlap detection |
| `handleCancelNewStory()` | `() => void` | Exits new story mode |
| **Navigation** | | |
| `getPageTitle()` | `() => string` | Returns breadcrumb title (last path segment or "Story Archive") |
| `getBreadcrumb()` | `() => string[]` | Returns full breadcrumb path array |

---

### Page: `SearchCurate.tsx`

Three-panel search, view, and category assignment interface. Uses custom hooks for shared logic.

| Function/Hook | Signature | Purpose |
|---------------|-----------|---------|
| **Custom Hooks** | | |
| `keywordsEditor` | `useKeywordsEditor()` | Keywords editing state and handlers |
| `categoryAssignment` | `useCategoryAssignment(selectedStory)` | Category tree, assignments, assign/remove handlers |
| `newStoryCreator` | `useNewStoryCreator()` | New story form state, text selection, add handler |
| **Search** | | |
| `handleSearch()` | `() => Promise<void>` | POSTs `/search` with query, filters; populates results |
| **Story Selection** | | |
| `handleSelectStory(story)` | `(story: SearchResult) => Promise<void>` | Sets selected story, loads static view, initializes boundary state |
| **View Toggle** | | |
| `handleToggleMode(mode)` | `('static' \| 'book') => Promise<void>` | Switches story view mode, auto-scrolls in book context |
| **Boundary Editing** | | |
| `handleAdjustBoundaries()` | `() => Promise<void>` | Enters edit mode, loads full text for selected story's book |
| `handleTextClick(e)` | `(e: MouseEvent) => void` | Uses `calculateCharPositionFromClick` utility to set start/end positions |
| `handleSaveBoundaries()` | `() => Promise<void>` | Persists boundaries via `/update-boundaries`, re-renders |
| `handleCancelEdit()` | `() => void` | Reverts to original boundaries, exits edit mode |
| **New Story Creation** | | |
| `handleEnterNewStoryMode()` | `() => Promise<void>` | Calls `newStoryCreator.startCreating(selectedStory.book_slug)` |
| **Story Deletion** | | |
| `handleDeleteStory()` | `() => Promise<void>` | DELETEs story with confirmation, removes from results |

**Note:** SearchCurate was reduced from ~1300 lines to ~900 lines by extracting shared logic into hooks.

---

### Page: `BookArchive.tsx`

Simple book listing page.

| Function | Signature | Purpose |
|----------|-----------|---------|
| `loadBooks()` | `() => Promise<void>` | GETs `/books`, populates book list |
| `handleBookClick(slug)` | `(slug: string) => void` | Navigates to `/book-archive/{slug}` |

---

### Page: `BookDetail.tsx`

Comprehensive book view with text, stories, and visual story review editor.

| Function | Signature | Purpose |
|----------|-----------|---------|
| **Data Loading** | | |
| `loadBook()` | `() => Promise<void>` | GETs `/books/{slug}?include_stories=true` |
| `loadFullText()` | `() => Promise<void>` | GETs `/full-text/{slug}`, caches text |
| **View Switching** | | |
| `handleViewText()` | `() => void` | Switches to full text view, loads text if needed |
| `handleViewStories()` | `() => void` | Switches to story list view |
| `handleViewReview()` | `() => void` | Switches to Story Review view, loads text |
| **Story Review** | | |
| `sortedStories` | `useMemo` | Stories sorted by `start_char` with color indices |
| `reviewSegments` | `useMemo` | Builds gap/story segments for highlighted text display |
| `handleStoryClick(story)` | `(story) => void` | Selects/deselects story in review mode |
| `scrollToStory(story)` | `(story) => void` | Scrolls review container to story position |
| **Boundary Editing (Review)** | | |
| `handleStartBoundaryEdit()` | `() => void` | Enters boundary edit mode for selected story |
| `handleBoundaryClick(e)` | `(e: MouseEvent) => void` | Click-to-set start/end positions |
| `editingSegments` | `useMemo` | Builds before/selected/after segments for edit display |
| `handleSaveBoundaries()` | `() => Promise<void>` | POSTs `/update-boundaries`, updates local state |
| `handleCancelBoundaryEdit()` | `() => void` | Exits boundary editing |
| **Title/Keywords Editing** | | |
| `handleStartEditTitle()` | `() => void` | Enters title edit mode |
| `handleSaveTitle()` | `() => Promise<void>` | POSTs `/update-title`, updates state |
| `handleCancelEditTitle()` | `() => void` | Exits title edit mode |
| `handleStartEditKeywords()` | `() => void` | Enters keywords edit mode |
| `handleSaveKeywords()` | `() => Promise<void>` | POSTs `/update-keywords`, updates state |
| `handleCancelEditKeywords()` | `() => void` | Exits keywords edit mode |
| **Story Deletion** | | |
| `handleDeleteStory()` | `() => Promise<void>` | DELETEs selected story with confirmation |
| **New Story Creation** | | |
| `handleEnterNewStoryMode()` | `() => void` | Enters new story mode |
| `handleNewStoryTextClick(e)` | `(e: MouseEvent) => void` | Click-to-set boundaries for new story |
| `newStorySegments` | `useMemo` | Builds segments for new story preview |
| `handleAddNewStory()` | `() => Promise<void>` | POSTs `/add-story` with overlap handling |
| `handleCancelNewStory()` | `() => void` | Exits new story mode |
| **Category Assignment** | | |
| `getPathOptions(tree, currentPath)` | `(tree, path) => string[]` | Gets child categories for dropdowns |
| `handlePathLevelChange(level, value)` | `(level, value) => void` | Updates path selection |
| `handleAssignCategory()` | `() => Promise<void>` | Assigns story to selected path |
| `handleRemoveCategory(path)` | `(path) => Promise<void>` | Removes story from category |
| **Story List View** | | |
| `handleToggleMode(story, mode)` | `(story, mode) => Promise<void>` | Renders story in static/book mode |
| `handleStoryOpen(story)` | `(story) => Promise<void>` | Loads story content on expand |

---

### Page: `Callback.tsx`

OAuth callback handler.

| Function | Signature | Purpose |
|----------|-----------|---------|
| `checkAuth()` | `() => Promise<void>` | Waits 500ms, checks auth state, redirects to returnTo or `/login` |

---

### Component: `Login.tsx`

Authentication page with Stack Auth SignIn component.

| Function | Signature | Purpose |
|----------|-----------|---------|
| `useEffect` | | Checks URL for `?error=` param, displays error message |
| "Continue without signing in" button | | Reads `returnTo` from storage, navigates there |

---

### Component: `SidebarTree.tsx`

Collapsible navigation sidebar with category tree.

| Function | Signature | Purpose |
|----------|-----------|---------|
| **Tree Building** | | |
| `buildTreeData(current, pathSegments)` | `(node, path) => TreeNode[]` | Recursively builds rc-tree compatible node structure |
| **Auth State** | | |
| `extractUserLabel(user)` | `(user) => string \| null` | Extracts display name/email from Stack Auth user object |
| **Event Handlers** | | |
| `onTitleClick(e, node)` | `(e, node) => void` | Navigates to category path when clicking node title |
| `onExpand(expandedKeys)` | `(keys) => void` | Updates expanded keys state |
| `titleRender(nodeData)` | `(nodeData) => JSX` | Custom renderer: title (clickable) + expand arrow |
| `onSelect()` | `() => void` | No-op (navigation handled by title click) |
| **Sidebar Toggle** | | |
| Auto-collapse | `useEffect` | Collapses sidebar on window resize < 1024px |
| Toggle button | | Expands/collapses sidebar manually |
| **Auth Controls** | | |
| Sign out button | | Calls `app.signOut()`, clears user state |
| Sign in button | | Navigates to `/login` |

---

### Component: `SubcategoryFilter.tsx`

Dropdown checkbox filter for subcategories.

| Function | Signature | Purpose |
|----------|-----------|---------|
| `handleCheckboxChange(subcat, checked)` | `(subcat, checked) => void` | Adds/removes subcat from selection, calls `onFilterChange` |
| `handleClearFilters()` | `() => void` | Clears all selections |
| Click outside handler | `useEffect` | Closes dropdown when clicking outside |

---

### Component: `CategoryManager.tsx`

Popup component for creating and deleting categories (editor only).

| Function | Signature | Purpose |
|----------|-----------|---------|
| `loadCategoryInfo()` | `() => Promise<void>` | Fetches category metadata (story count, children) |
| `handleCreate()` | `() => Promise<void>` | Creates new subcategory via `/api/create-category` |
| `handleDelete()` | `() => Promise<void>` | Deletes category via `/api/delete-category` with confirmation |

**Props:**
- `currentPath: string[]` - Path to selected category (empty for root)
- `categoryName: string | null` - Name of selected category
- `isEditor: boolean` - Whether user has editor privileges
- `onTreeChange: () => void` - Callback to refresh tree after changes
- `position: { x, y }` - Screen position for popup
- `onClose: () => void` - Close callback

**Features:**
- Create subcategories under any existing category
- Delete categories (with confirmation by typing name)
- Shows warnings for categories with stories or children
- Right-click context menu or gear icon to access

---

## Critical Architectural Decisions

### 1. Routes in main.tsx, Not App.tsx
Routes are defined in `main.tsx` wrapped with providers. `App.tsx` exists but is NOT used.
```typescript
// main.tsx - This is the actual router
<Routes>
  <Route path="/" element={<Archive />} />
  <Route path="/search-curate" element={<SearchCurate />} />
  ...
</Routes>
```
**Why:** Stack Auth provider needs to wrap routes. Don't add routes to App.tsx.

### 2. Sidebar in Each Page
Each page component includes `<SidebarTree />` individually:
```tsx
// Every page does this:
return (
  <div className="flex h-screen">
    <SidebarTree />
    <main className="flex-1 overflow-y-auto">...</main>
  </div>
)
```
**Why:** Different pages need different layouts. Sidebar state (collapsed) is local to component.

### 3. API Through Axios Wrapper
All API calls go through `utils/axios.ts`:
```typescript
import axios from '../utils/axios'
const res = await axios.get('/books')  // Automatically adds /api prefix
```
**Invariant:** Never use raw `fetch()` or create new axios instances. The wrapper handles auth tokens.

### 4. Responsive Breakpoints
```
< 1024px: Sidebar auto-collapses
< 768px: SearchCurate right panel hidden
```
Sidebar width: `w-64 lg:w-80 xl:w-96`

## Key Pages

| Page | Route | Panels | Purpose |
|------|-------|--------|---------|
| `Archive.tsx` | `/archive/*` | Sidebar + Main | Browse stories by category |
| `SearchCurate.tsx` | `/search-curate` | Sidebar + Left + Center + Right | Search, view, categorize |
| `BookArchive.tsx` | `/book-archive` | Sidebar + Main | List all books |
| `BookDetail.tsx` | `/book-archive/:slug` | Sidebar + Main | Book info, stories, full text, **story review** |

## BookDetail.tsx Views

The BookDetail page has four view tabs:

| Tab | Purpose | Features |
|-----|---------|----------|
| **Book Info** | Display book metadata | Title, author, year, description |
| **View Text** | Read full book text | Libre Baskerville font, page markers |
| **View Stories** | Expandable story list | Static/Book Context toggle per story |
| **Story Review** | Visual story boundary editor | See below |

### Story Review Tab Features

The Story Review tab provides a visual editor for reviewing and editing story boundaries:

1. **Highlighted Text Display**
   - Full book text with all stories highlighted in distinct colors
   - 6-color palette cycles through stories by position
   - Click on highlighted region to select story
   - Non-story text (gaps) shown in readable gray

2. **Story Sidebar**
   - Stories listed by character position (sorted)
   - Click to select and scroll to story in text
   - Color coordination between list and text highlights

3. **Selected Story Actions**
   - **Edit Boundaries**: Click-to-set start/end positions with auto-scroll
   - **Edit Title**: Inline title editing with save/cancel
   - **Delete Story**: Confirmation dialog with full cleanup
   - **+ New Story**: Create new story by selecting text region

4. **New Story Mode**
   - Purple border indicates new story mode
   - Click to set start/end positions
   - Form for title, keywords, pages
   - Overlap detection with force-add option

## Component Dependencies

```
main.tsx
  └── All pages (routing)
      └── SidebarTree (navigation)
          └── store.ts (tree data)
      └── utils/axios (API calls)

SearchCurate.tsx (~1200 lines - needs refactoring)
  ├── Search panel (left)
  ├── Story viewer (center)
  └── Category assignment (right)

BookDetail.tsx (~1300 lines)
  ├── Book info panel
  ├── Full text viewer
  ├── Stories list (with expand/collapse)
  └── Story Review (with boundary editing)
```

## State Management

```typescript
// store.ts - Zustand store
interface AppState {
  tree: Record<string, any>     // Codex tree hierarchy
  loadTree: () => Promise<void> // Fetches from /api/get-tree
  selectedStory: Story | null
  setSelectedStory: (s: Story | null) => void
}
```

**When to use Zustand:** Cross-component state (tree, selected story)  
**When to use useState:** Component-local state (form inputs, loading)

## Styling Patterns

### Tailwind Classes
```tsx
// Standard page layout
<div className="flex h-screen">
  <SidebarTree />
  <main className="flex-1 overflow-y-auto bg-gray-900 min-w-0">
    <div className="max-w-4xl mx-auto px-4 sm:px-6 py-4 sm:py-6">
```

### Dark Theme Colors
- Background: `bg-gray-900`, `bg-gray-800`
- Text: `text-white`, `text-gray-200`, `text-gray-400`
- Borders: `border-gray-700`
- Accent: `bg-blue-600`, `text-blue-400`

### Story Review Color Palette
```tsx
const STORY_COLORS = [
  { bg: 'bg-blue-600/40', border: 'border-blue-500', text: 'text-blue-200' },
  { bg: 'bg-green-600/40', border: 'border-green-500', text: 'text-green-200' },
  { bg: 'bg-purple-600/40', border: 'border-purple-500', text: 'text-purple-200' },
  { bg: 'bg-amber-600/40', border: 'border-amber-500', text: 'text-amber-200' },
  { bg: 'bg-cyan-600/40', border: 'border-cyan-500', text: 'text-cyan-200' },
  { bg: 'bg-rose-600/40', border: 'border-rose-500', text: 'text-rose-200' },
]
```

### Typography (Full Text View)
```tsx
// BookDetail.tsx - Libre Baskerville for book reading
style={{ 
  fontFamily: "'Libre Baskerville', Georgia, serif",
  maxWidth: '65ch',
  lineHeight: '1.9'
}}
```

## API Endpoints Used

| Component | Endpoints |
|-----------|-----------|
| Archive | `/api/get-tree`, `/api/get-stories/{path}`, `/api/update-keywords`, `/api/update-title`, `/api/delete-story/{title}` |
| SearchCurate | `/api/search`, `/api/render-story`, `/api/assign-category`, `/api/update-keywords` |
| BookArchive | `/api/books` |
| BookDetail | `/api/books/{slug}`, `/api/full-text/{slug}`, `/api/update-boundaries`, `/api/update-title`, `/api/update-keywords`, `/api/add-story`, `/api/delete-story/{title}` |
| SidebarTree | `/api/get-tree` |

## Adding a New Page

1. Create `src/pages/NewPage.tsx`
2. Add route in `main.tsx`:
   ```tsx
   <Route path="/new-page" element={<NewPage />} />
   ```
3. Include `<SidebarTree />` for consistent navigation
4. Add navigation link in `SidebarTree.tsx` if needed

## Adding a New API Call

1. Use the axios wrapper:
   ```typescript
   import axios from '../utils/axios'
   const res = await axios.post('/endpoint', data)
   ```
2. Handle loading/error states:
   ```typescript
   const [loading, setLoading] = useState(false)
   const [error, setError] = useState<string | null>(null)
   ```

## Known Tech Debt

- ~~`SearchCurate.tsx` is ~1200 lines - should split into sub-components~~ **Reduced to ~900 lines via hooks**
- `BookDetail.tsx` is ~1600 lines - Story Review could be extracted, could use shared hooks
- `Archive.tsx` is ~1100 lines - could benefit from shared hooks
- No TypeScript interfaces for API responses
- Tree is re-fetched on every page mount (should cache in store)

## Environment Variables

```
VITE_STACK_PROJECT_ID=xxx
VITE_STACK_PUBLISHABLE_CLIENT_KEY=xxx
```

## Build & Dev

```bash
npm run dev     # Development server (Vite) - port 5173
npm run build   # Production build
npm run preview # Preview production build
```

## Vercel Deployment

`vercel.json` rewrites:
- `/api/*` → Render backend (`preternatural-text-repo.onrender.com`)
- `/*` → `index.html` (SPA fallback)
