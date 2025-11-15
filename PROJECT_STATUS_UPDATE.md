# Project Status Update: "Lexicon of the Unexplained" Migration
**Updated: Current Session (Authentication Implementation)**

## Executive Summary - Current Status

The migration from Hugging Face Spaces prototype to standalone web app is **~75% complete**. Core functionality (search, archive browsing, story viewing, boundary editing) is implemented and working. Authentication is partially implemented but requires endpoint configuration fixes.

**Completed:**
- ✅ Backend FastAPI with core endpoints (search, tree, rendering, boundary updates)
- ✅ Frontend React/Vite with routing, sidebar tree navigation, archive pages
- ✅ Interactive boundary editing with visual text selection
- ✅ Story rendering (static and book context modes with auto-scroll)
- ✅ Dark theme UI/UX
- ✅ JSON file persistence (with Vercel Postgres as optional fallback)
- ✅ Authentication middleware structure (Neon Auth integration in progress)

**In Progress:**
- 🔄 Authentication endpoint configuration (Stack Auth/Neon Auth URL format)
- 🔄 Local development setup for OAuth redirect URIs

**Remaining:**
- ⏳ Export functionality (MD/PDF/Word)
- ⏳ Model bundling optimization (currently using local model)
- ⏳ Production deployment configuration
- ⏳ Multi-tag support
- ⏳ AI suggestions integration

---

## Changes from Original Plan

### 1. Authentication Provider: Clerk → Neon Auth

**Original Plan:** Use Clerk for authentication with role-based access control.

**Current Implementation:** Using **Neon Auth** (built on Stack Auth) integrated with GitHub OAuth.

**Rationale:** Neon Auth is already configured in your Neon database setup, providing seamless integration with your existing infrastructure.

**Status:** 
- Backend middleware implemented (`require_editor` dependency)
- Frontend login component created
- OAuth callback handler implemented
- **Blocked:** Correct Stack Auth authorization endpoint URL format needs verification

**Next Steps:**
- Verify Stack Auth authorization endpoint (currently trying `https://[project-id].stackauth.com/authorize`)
- Configure redirect URI in Stack Auth dashboard (`http://app.local:5173/callback` for local dev)
- Test full authentication flow

### 2. Persistence Strategy: Primary DB → JSON-First with DB Fallback

**Original Plan:** Vercel Postgres as primary storage for stories, tree, and auth.

**Current Implementation:** **JSON file storage as primary**, with Vercel Postgres as optional fallback.

**Rationale:** 
- Faster local development (no DB setup required)
- Works immediately in serverless environments
- DB connection is optional and gracefully degrades

**Status:**
- ✅ JSON persistence for `story_positions.json` and `codex_tree.json`
- ✅ Database models defined (`models.py` with Story, CodexNode, NodeStory)
- ✅ Automatic fallback when DB unavailable
- ✅ `update_story_boundaries()` updates both JSON and DB when available

**Files:**
- `backend/utils.py`: Handles JSON loading/saving with DB fallback
- `backend/models.py`: SQLAlchemy models for Vercel Postgres
- `books/{book_slug}/story_positions.json`: Story boundary data
- `data/codex_tree.json`: Category tree structure

### 3. Model Bundling: Status Unclear

**Original Plan:** Bundle embedding model (BAAI/bge-large-en-v1.5) via Git LFS to eliminate per-visit downloads.

**Current Status:** Model appears to be loaded locally (found in `backend/models/bge-large-en-v1.5/`), but bundling strategy for production deployment needs verification.

**Next Steps:**
- Verify model loading path in production
- Ensure model is included in Vercel deployment
- Test cold start performance

### 4. Frontend Architecture: Implemented with Enhancements

**Completed Components:**
- ✅ `SidebarTree.tsx`: Collapsible tree navigation with right-aligned arrows
- ✅ `Archive.tsx`: Category pages with story cards, expand/collapse
- ✅ `SearchCurate.tsx`: Search interface with interactive boundary editor
- ✅ `Login.tsx`: Authentication UI
- ✅ `Callback.tsx`: OAuth callback handler

**UI/UX Enhancements (Beyond Original Plan):**
- Dark theme (dark gray background, white text)
- Center-aligned story titles
- Auto-scroll to story positions in book context
- Interactive text selection for boundary editing (replaces slider/phrase approach)
- Improved sidebar spacing and alignment

**Routing:**
- ✅ `/` or `/archive`: Archive homepage
- ✅ `/archive/:path*`: Category pages (dynamic routing)
- ✅ `/search-curate`: Search and curation tools
- ✅ `/login`: Authentication page
- ✅ `/callback`: OAuth callback handler

### 5. Backend Endpoints: Core Functionality Complete

**Implemented Endpoints:**

**Search & Curate:**
- ✅ `POST /api/search`: Hybrid search (BM25 + semantic) with filters
- ✅ `POST /api/update-boundaries`: Update story start/end positions (requires editor auth)
- ✅ `POST /api/render-story`: Render story in static or book context mode
- ✅ `GET /api/sources`: List available book sources

**Codex Tree:**
- ✅ `GET /api/get-tree`: Full hierarchy from JSON/DB
- ✅ `GET /api/get-stories/{path:path}`: Stories at specific path
- ✅ `GET /api/get-unassigned`: Stories not yet categorized
- ✅ `POST /api/assign-category`: Assign story to category path (requires editor auth)
- ✅ `DELETE /api/remove-category`: Remove story from category (requires editor auth)

**Other:**
- ✅ `GET /api/health`: Health check endpoint

**Missing (From Original Plan):**
- ⏳ `POST /api/export`: Generate MD/PDF/Word exports
- ⏳ `PATCH /api/update-story/{title}`: Update keywords/metadata

### 6. Boundary Editing: Enhanced UX

**Original Plan:** Slider/phrase-based boundary adjustment.

**Current Implementation:** **Interactive text selection** - users click directly in the full text to set start and end positions.

**Features:**
- Visual highlighting of selected boundaries
- Click-to-select start, then click-to-select end
- Auto-scroll to original boundaries when entering edit mode
- Real-time preview of selected range
- Save with authentication check

**Status:** ✅ Fully functional, requires authentication to save

---

## Current File Structure

```
preternatural-text-repo/
├── backend/
│   ├── main.py              # FastAPI app, routes, auth middleware
│   ├── utils.py             # Core logic (search, tree, rendering, persistence)
│   ├── models.py             # SQLAlchemy models (Story, CodexNode, NodeStory)
│   ├── requirements.txt     # Python dependencies
│   └── models/               # Bundled embedding model (bge-large-en-v1.5)
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SidebarTree.tsx    # Tree navigation
│   │   │   └── Login.tsx          # Auth UI
│   │   ├── pages/
│   │   │   ├── Archive.tsx        # Category pages
│   │   │   ├── SearchCurate.tsx   # Search & boundary editing
│   │   │   └── Callback.tsx       # OAuth callback
│   │   ├── main.tsx               # React Router setup
│   │   └── store.ts               # Zustand state management
│   ├── vite.config.ts        # Vite config (proxy, allowed hosts)
│   └── package.json
├── books/
│   └── {book_slug}/
│       ├── Full_Text.md
│       └── story_positions.json
├── data/
│   ├── codex_tree.json
│   ├── document_store.json
│   └── stories_dict.json
├── .env.local                # Environment variables (root)
├── frontend/.env.local       # Frontend env vars (VITE_*)
├── vercel.json               # Vercel deployment config
└── README.md
```

---



---

## Technical Decisions Made

1. **JSON-First Persistence**: Chosen for simplicity and immediate functionality. DB remains optional for production scaling.

2. **Interactive Boundary Editing**: Replaced slider/phrase approach with direct text selection for better UX.

3. **Dark Theme**: Applied globally for improved readability and modern aesthetic.

4. **Local Development Domain**: Using `app.local` instead of `localhost` to satisfy Stack Auth redirect URI requirements (needs two domain labels).



#

## Testing Status

- ✅ Local development: Backend and frontend running
- ✅ Search functionality: Working
- ✅ Story rendering: Working (static and book context)
- ✅ Boundary editing: Working (UI complete, save requires auth)
- ✅ Tree navigation: Working
- 🔄 Authentication flow: Blocked on endpoint configuration
- ⏳ Export functionality: Not yet implemented
- ⏳ End-to-end tests: Not yet written

---



## Notes

- The project has made significant progress on core functionality
- Authentication is the primary blocker, but the infrastructure is in place
- JSON persistence provides a solid foundation that can scale to DB when needed
- UI/UX improvements beyond original plan enhance user experience
- Code quality is good with proper error handling and fallbacks

