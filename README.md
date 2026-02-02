---
title: Preternatural Text Repository
emoji: 👻
short_description: Search and curate paranormal stories from historical texts
---

# Preternatural Text Repository

![GitHub License](https://img.shields.io/github/license/hetzerdj/paranormal-text-repo)  
![GitHub Repo stars](https://img.shields.io/github/stars/hetzerdj/paranormal-text-repo?style=social)

## Overview

A scalable system for extracting, indexing, searching, and curating stories of preternatural phenomena from historical texts. Currently includes several example texts with plans to expand to 100+ volumes.

### Key Features
- **Hybrid semantic search** — combines keyword (BM25) and embedding-based search using FAISS + SQLite FTS5
- **Find Similar** — discover related stories using hybrid query (title + keywords + content)
- **Multi-book support** — process and search across multiple historical texts
- **Hierarchical categorization** — organize stories into a "Codex Tree" taxonomy (Demonic Activity, Ghostly Activity, Cryptids, etc.)
- **Story Review** — visual editor showing all stories highlighted in book text with inline boundary editing
- **Boundary editing** — adjust story start/end positions with click-to-select and auto-scroll
- **Story management** — add new stories, edit titles, delete stories directly from the UI
- **React production UI** — search, curate, and manage stories with real-time updates
- **AI-assisted development** — structured workflow for sustainable feature development

### Tech Stack
| Layer | Technology |
|-------|----------|
| Search Engine | Direct FAISS + SQLite FTS5, Sentence Transformers (bge-large-en-v1.5) |
| Backend API | FastAPI, SQLAlchemy, PostgreSQL |
| Frontend UI | React 19, TypeScript, Vite, Tailwind CSS, Zustand |
| Auth | Stack Auth (JWT-based) |
| Development | Continue.dev, Claude AI, git-based workflows |

---

## Development Approach

This project uses a **sustainable AI-assisted development workflow** that keeps the codebase manageable without dumping entire files into prompts. Key documents:

- **[CONTEXT.md](./CONTEXT.md)** — Development context for AI assistants (architecture, module responsibilities, conventions)
- **[TECH_DEBT_BACKLOG.md](./documentation/TECH_DEBT_BACKLOG.md)** — Prioritized refactoring tasks with acceptance criteria
- **GitHub branch naming:** `ai/task-name-YYYYMMDD` for AI-generated changes

---

## Architecture

```
┌─────────────────┐      ┌─────────────────────┐      ┌─────────────┐
│   Data Layer    │ ───► │   Search Engine     │ ───► │     UI      │
│                 │      │                     │      │             │
│ books/          │      │ backend/main.py     │      │ frontend/   │
│ data/           │      │ backend/utils/      │      │ (React)     │
│ Pre-Processing/ │      │ (FastAPI)           │      │             │
└─────────────────┘      └─────────────────────┘      └─────────────┘
        │                         │                          │
        ▼                         ▼                          ▼
  document_store.json       /api/* endpoints          React components
  story_positions.json      Haystack pipelines        Zustand state
  codex_tree.json           JWT auth                  Tailwind styling
```

See [CONTEXT.md](./CONTEXT.md) for architecture deep-dive and [REPO_SUMMARY.md](./REPO_SUMMARY.md) for API documentation.

---

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL (for production backend)

### 1. Clone & Install

```bash
git clone https://github.com/Monocarp/preternatural-text-repo.git
cd preternatural-text-repo
```

### 2. Run the Full Stack (Backend + Frontend)

**Backend:**
```bash
cd backend
pip install -r requirements.txt
# Create .env.local with DATABASE_URL, STACK_PROJECT_ID, etc.
uvicorn main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:5173
```

---

## File Structure

```
preternatural-text-repo/
├── CONTEXT.md                # Development context for AI assistants
├── documentation/
│   └── TECH_DEBT_BACKLOG.md  # Prioritized refactoring tasks
│
├── backend/                  # FastAPI production API
│   ├── main.py               # All API endpoints
│   ├── models.py             # SQLAlchemy models
│   ├── utils/                # Modular utilities (P2-1)
│   │   ├── __init__.py       # Re-exports for backwards compatibility
│   │   ├── rendering.py      # Story rendering functions
│   │   ├── cache.py          # Tree/metadata caching
│   │   ├── storage.py        # File I/O operations
│   │   └── export.py         # Export to PDF/DOCX/JSON
│   ├── utils_legacy.py       # Core infra (pipelines, search, DB ops)
│   └── requirements.txt
│
├── frontend/                 # React production UI
│   ├── src/
│   │   ├── App.tsx
│   │   ├── store.ts          # Zustand state
│   │   ├── pages/            # SearchCurate, Archive, BookDetail
│   │   └── components/       # SidebarTree, Login
│   └── package.json
│
├── books/                    # Per-book data
│   └── {book_slug}/
│       ├── Full_Text.md      # Source text with [Page X] markers
│       ├── story_positions.json
│       └── Stories.md
│
├── data/                     # Shared data stores
│   ├── document_store.json   # Haystack embeddings (Git LFS)
│   ├── codex_tree.json       # Category hierarchy
│   └── stories_dict.json     # Flat story lookup
│
└── Pre-Processing/           # Text extraction scripts (private)
```

---

## Adding New Books

1. Process DOCX source via preprocessing scripts → generates `Full_Text.md`, `story_positions.json`
2. Place output in `books/{book_slug}/`
3. Run `backend/ingest_book.py` to embed and index
4. Update `data/codex_tree.json` with initial categories
5. Commit and push

Effort: ~15-30 minutes per book depending on length.

---

## API Reference

Full endpoint documentation in [`REPO_SUMMARY.md`](./REPO_SUMMARY.md#key-public-interfaces-as-of-2025-11-25).

Key endpoints:
| Endpoint | Description |
|----------|-------------|
| `POST /api/search` | Hybrid search across all books |
| `GET /api/get-tree` | Fetch category hierarchy |
| `POST /api/assign-category` | Assign story to category path |
| `POST /api/render-story` | Get HTML rendering of a story |
| `POST /api/add-story` | Add new story with immediate indexing |
| `POST /api/update-boundaries` | Update story start/end character positions |
| `POST /api/update-title` | Rename a story |
| `DELETE /api/delete-story/{title}` | Remove a story from all stores |
| `GET /api/books/{slug}` | Get book details with stories |
| `GET /api/full-text/{slug}` | Get full book text for review |

---

## Contributing

1. Fork the repo
2. Create a feature branch: `ai/task-name-YYYYMMDD` or `fix/issue-name`
3. Pick a task from [TECH_DEBT_BACKLOG.md](./documentation/TECH_DEBT_BACKLOG.md) or open an issue
4. Reference [CONTEXT.md](./CONTEXT.md) for architecture and module responsibilities
5. Verify acceptance criteria before submitting PR
6. Submit pull request with task ID and summary

Issues and enhancement suggestions welcome via GitHub Issues.

---

## License

MIT — see [LICENSE](./LICENSE)

---

## Credits

- **Texts**: Public domain historical works
- **Search**: [Haystack AI](https://haystack.deepset.ai/)
- **Embeddings**: [BAAI/bge-large-en-v1.5](https://huggingface.co/BAAI/bge-large-en-v1.5)
- **UI**: [React](https://react.dev/), [Tailwind CSS](https://tailwindcss.com/)
- **State**: [Zustand](https://github.com/pmndrs/zustand)
