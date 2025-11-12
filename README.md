---
title: Preternatural Text Repository UI
emoji: 👻
colorFrom: indigo
colorTo: purple
sdk: gradio
sdk_version: 5.49.1
app_file: app.py
pinned: false
tags:
- paranormal
- historical-texts
- semantic-search
- haystack
- gradio
short_description: Dashboard
---
# Paranormal Text Repository

[![Hugging Face Spaces](https://img.shields.io/badge/%F0%9F%A4%97%20Hugging%20Face-Spaces-blue)](https://huggingface.co/spaces/hetzerdj/paranormal-text-ui)  
![GitHub License](https://img.shields.io/github/license/hetzerdj/paranormal-text-repo)  
![GitHub Repo stars](https://img.shields.io/github/stars/hetzerdj/paranormal-text-repo?style=social)

## Overview

This repository hosts the backend data and frontend code for a scalable system designed to extract, index, search, and curate stories of preternatural phenomena from a wide range of texts. Currently limited to a few examples texts, the project aims to expand to 100+ texts.

The system processes DOCX files into Markdown, extracts stories with pagination, embeds them for semantic search (using Haystack and FAISS), and provides an interactive Gradio-based UI for querying, viewing, editing boundaries, curating lists, and exporting to MD/PDF/Word. It's built for research, such as analyzing motifs in paranormal events.

- **Key Features**:
  - Semantic hybrid search (e.g., "demonic activity" matches "possession").
  - Multi-book support with incremental processing.
  - Three-panel UI: Search results, full-text viewer with auto-scroll/highlight, curated list.
  - Exports for motif analysis.
  - Open-source stack: Python, Haystack, Sentence Transformers, Gradio, FAISS.

This is a **beta version**—core functionality is implemented, but we're iterating on scalability, UI polish, and additional books.

## Demo

Try the interactive dashboard on Hugging Face Spaces: [Paranormal Text UI](https://huggingface.co/spaces/hetzerdj/paranormal-text-ui).

- Search example: "witch trials" → Lists matching stories with pages/keywords.
- View/Edit: Auto-scrolls to page, highlight story, adjust boundaries via sliders/phrases.
- Curate/Export: Build lists and download as MD/PDF/Word.

## File Structure

```
paranormal-text-repo/
├── app.py                  # Gradio UI script (deployed to HF Spaces)
├── requirements.txt        # Dependencies for HF build
├── books/                  # Book data (subdirs per book, e.g., christian_mysticism_volume_iv/)
│   ├── book_slug/          # Example: christian_mysticism_volume_iv
│   │   ├── Full_Text.md    # Full Markdown text with [Page X] markers
│   │   ├── Stories.md      # Extracted stories
│   │   ├── grouped_index.md# Indexed terms with pages
│   │   └── story_positions.json # Char positions, pages, keywords for stories
├── data/                   # Shared backend data
│   ├── document_store.json # Haystack in-memory store with embeddings
│   ├── faiss_index.bin     # FAISS vector index (via Git LFS)
│   └── documents.json      # Metadata for documents
├── README.md               # This file
└── .gitattributes          # Git LFS tracking patterns
```

Large files (e.g., .md, .json, .bin) are managed via Git LFS for efficiency.

## Setup and Usage

### Local Development
1. Clone the repo: `git clone https://github.com/hetzerdj/paranormal-text-repo.git`
2. Install dependencies: `pip install -r requirements.txt` (also needs `apt install pandoc` on Linux).
3. Run the UI: `python app.py` → Opens at http://localhost:7860.
4. To add new books:
   - Run preprocessing scripts (Steps 1-4 from project docs) in Colab/local to generate/update `books/` and `data/`.
   - Commit and push: `git add . && git commit -m "Add new book" && git push`.

### Deployment on Hugging Face Spaces
- The UI is deployed at [hetzerdj/paranormal-text-ui](https://huggingface.co/spaces/hetzerdj/paranormal-text-ui).
- Syncs automatically with this GitHub repo (push changes here → HF rebuilds).
- Free tier sufficient; scales to 100+ books with <0.5s queries.

### Adding Books (Scaling)
- Process new DOCX texts via the batch script (Step 4) for incremental embedding. (Pre-processing is not publicly available code)
- Effort: ~5-20 min per book addition.
- Target: 100 texts; test multi-book searches for any issues.

## Technologies
- **Backend**: Haystack (search/embedding), FAISS (vector store), Sentence Transformers (all-MiniLM-L6-v2).
- **UI**: Gradio (dashboard).
- **Processing**: python-docx, pandoc, difflib for extraction/matching.
- **Deployment**: Hugging Face Spaces, GitHub for persistence.

## Contributing
- Fork the repo and submit pull requests for new books, UI features, or bug fixes.
- Issues: Report bugs or suggest enhancements via GitHub Issues.
- License: MIT (feel free to use/modify).

## Credits
- Texts: Public domain historical works (e.g., Joseph Von Gorres).
- Tools: Open-source libraries as listed.

For questions, contact via GitHub or HF discussions. Beta feedback appreciated! 🚀