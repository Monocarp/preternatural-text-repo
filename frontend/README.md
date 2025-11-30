# Preternatural Text Frontend

React + TypeScript + Vite frontend for the Preternatural Text curation platform.

## Tech Stack

- **React 18** with TypeScript
- **Vite** for build tooling
- **Tailwind CSS** for styling
- **React Router** for navigation

## Getting Started

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

## Project Structure

```
src/
├── components/     # Reusable UI components (SearchBar, TreeView, etc.)
├── hooks/          # Custom React hooks for shared logic
├── pages/          # Page components (Archive, BookDetail, SearchCurate)
├── types/          # TypeScript type definitions
├── App.tsx         # Main app with routing
└── index.css       # Tailwind imports
```

## Custom Hooks

The codebase uses custom hooks to share logic across components:

| Hook | Purpose |
|------|---------|
| `useKeywordsEditor` | Keywords editing state and persistence |
| `useCategoryAssignment` | Category tree management and assignments |
| `useNewStoryCreator` | New story form state and creation |
| `useBoundaryEditor` | Story boundary editing (start/end positions) |
| `useTextPositionClick` | Character position calculation from clicks |

See `CONTEXT.md` for detailed function signatures and usage patterns.

## Pages

- **SearchCurate** (`/`) - Main interface for searching, viewing, and categorizing stories
- **BookDetail** (`/books/:slug`) - Full book view with story navigation
- **Archive** (`/archive`) - Browse codex tree and category assignments

## Development

The frontend connects to a FastAPI backend (default: `http://localhost:8000`).

For detailed architecture and function documentation, see `CONTEXT.md`.
