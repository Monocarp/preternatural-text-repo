# Frontend Context

**Last Updated:** 2025-11-27

## Overview

React 18 + TypeScript frontend with Tailwind CSS styling. Uses Zustand for state management.

## Architecture

```
frontend/src/
├── main.tsx           # App entry, routing, Stack Auth provider
├── App.tsx            # Unused (routes defined in main.tsx)
├── store.ts           # Zustand global state
├── index.css          # Tailwind imports + global styles
├── pages/             # Route components
├── components/        # Reusable UI components
└── utils/             # axios config, path helpers
```

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
| Archive | `/api/get-tree`, `/api/get-stories/{path}` |
| SearchCurate | `/api/search`, `/api/render-story`, `/api/assign-category` |
| BookArchive | `/api/books` |
| BookDetail | `/api/books/{slug}`, `/api/full-text/{slug}`, `/api/update-boundaries`, `/api/update-title`, `/api/add-story`, `/api/delete-story/{title}` |
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

- `SearchCurate.tsx` is ~1200 lines - should split into sub-components
- `BookDetail.tsx` is ~1300 lines - Story Review could be extracted
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
