# app.py for HF Spaces: Gradio UI for Multi-Book Paranormal Text Repository
# (Trimmed for HF: No Colab installs/downloads/ngrok; relative paths)

import gradio as gr
from haystack import Pipeline, Document
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.retrievers.in_memory import InMemoryEmbeddingRetriever, InMemoryBM25Retriever
from haystack.components.joiners import DocumentJoiner
from haystack.document_stores.in_memory import InMemoryDocumentStore
import json
import re
import os
import subprocess
from docx import Document as DocxDocument
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import logging
from collections import Counter
import numpy as np
import sys
import base64

# Set up logging (stream to stdout for HF logs)
logging.basicConfig(level=logging.INFO, force=True, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)

# Paths (HF repo root)
books_dir = "books/"
data_dir = "data/"
document_store_path = os.path.join(data_dir, "document_store.json")

# Lazy-load full MD texts and story positions {book_slug: data}
full_mds = {}
story_positions = {}

def load_full_md(book_slug):
    if book_slug not in full_mds:
        md_path = os.path.join(books_dir, book_slug, "Full_Text.md")
        try:
            with open(md_path, "r", encoding="utf-8") as f:
                full_mds[book_slug] = f.read()
            logger.debug(f"Loaded Full_Text.md for {book_slug}, length: {len(full_mds[book_slug])}")
        except Exception as e:
            logger.error(f"Failed to load Full_Text.md for {book_slug}: {e}")
            full_mds[book_slug] = ""
    return full_mds[book_slug]

def load_story_positions(book_slug):
    if book_slug not in story_positions:
        pos_path = os.path.join(books_dir, book_slug, "story_positions.json")
        try:
            with open(pos_path, "r", encoding="utf-8") as f:
                story_positions[book_slug] = json.load(f)
            logger.debug(f"Loaded story_positions for {book_slug} with {len(story_positions[book_slug])} entries")
        except Exception as e:
            logger.error(f"Failed to load story_positions.json for {book_slug}: {e}")
            story_positions[book_slug] = {}
    return story_positions[book_slug]

# Discover books dynamically (skip hidden/invalid dirs like .ipynb_checkpoints)
books = [d for d in os.listdir(books_dir) if os.path.isdir(os.path.join(books_dir, d)) and not d.startswith('.')]
sources = ["All Sources"] + sorted(books)  # For UI dropdown
logger.info(f"Discovered books: {sources}")

# Load document store
document_store = None
if os.path.exists(document_store_path):
    logger.info("Loading document store from JSON...")
    try:
        document_store = InMemoryDocumentStore.load_from_disk(document_store_path)
        logger.info(f"Loaded {document_store.count_documents()} documents")
        loaded_docs = document_store.filter_documents({})
        doc_types = Counter(doc.meta.get("type", "unknown") for doc in loaded_docs)
        sample_ids = [doc.id for doc in loaded_docs[:3]]
        sample_metadata = [doc.meta for doc in loaded_docs[:3]]
        sample_content = [doc.content[:50] for doc in loaded_docs[:3]]
        logger.info(f"Document types: {dict(doc_types)}, Sample IDs: {sample_ids}, Sample Metadata: {sample_metadata}, Sample Content: {sample_content}")
        if doc_types.get("story", 0) == 0:
            logger.error("No 'story' type documents found; searches may fail. Re-run step 4.")
        # Convert embeddings to numpy arrays if needed
        for doc in loaded_docs:
            if doc.embedding is not None and isinstance(doc.embedding, list):
                try:
                    doc.embedding = np.array(doc.embedding, dtype=np.float32)
                except Exception as e:
                    logger.warning(f"Failed to convert embedding for doc {doc.id}: {e}; setting to None")
                    doc.embedding = None
        has_embeddings = any(doc.embedding is not None and len(doc.embedding) == 384 for doc in loaded_docs)
        if not has_embeddings:
            logger.warning("No valid embeddings found; re-embedding...")
            from haystack.components.embedders import SentenceTransformersDocumentEmbedder
            embedder = SentenceTransformersDocumentEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
            embedder.warm_up()
            try:
                valid_docs = [doc for doc in loaded_docs if doc.content and len(doc.content.strip()) >= 10]
                if not valid_docs:
                    raise ValueError("No valid documents for re-embedding")
                embedded_docs = embedder.run(valid_docs)["documents"]
                document_store.delete_documents([doc.id for doc in loaded_docs])
                document_store.write_documents(embedded_docs)
            except Exception as e:
                logger.error(f"Re-embedding failed: {e}")
                raise
        # Force re-index if needed
        logger.info("Re-writing documents to new store for index rebuild...")
        new_store = InMemoryDocumentStore(embedding_similarity_function="dot_product")
        new_store.write_documents(loaded_docs)
        document_store = new_store
        logger.info(f"Index rebuilt, store has {document_store.count_documents()} documents")
    except Exception as e:
        logger.error(f"Failed to load/re-embed document store: {e}")
        raise
else:
    logger.error("document_store.json not found. Re-run step 4.")
    raise FileNotFoundError("document_store.json missing")

# Set up Haystack pipeline
logger.debug("Setting up Haystack pipeline...")
embedder = SentenceTransformersTextEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
retriever_embedding = InMemoryEmbeddingRetriever(document_store=document_store)
retriever_bm25 = InMemoryBM25Retriever(document_store=document_store)
joiner = DocumentJoiner()
search_pipeline = Pipeline()
search_pipeline.add_component("embedder", embedder)
search_pipeline.add_component("retriever_embedding", retriever_embedding)
search_pipeline.add_component("retriever_bm25", retriever_bm25)
search_pipeline.add_component("joiner", joiner)
search_pipeline.connect("embedder.embedding", "retriever_embedding.query_embedding")
search_pipeline.connect("retriever_embedding", "joiner")
search_pipeline.connect("retriever_bm25", "joiner")
logger.info(f"Pipeline components: {search_pipeline.graph.nodes.keys()}")

# Helper: Run search (updated for book filter via meta['book'], added debug logs for doc counts)
def search_stories(query, source_filter=None, type_filter=None, page_range=None, top_k=15):
    logger.info(f"Searching for query: {query}, source: {source_filter}, type: {type_filter}, pages: {page_range}")
    filters = {"operator": "AND", "conditions": []}
    if source_filter and source_filter != "All Sources":
        filters["conditions"].append({"field": "book", "operator": "==", "value": source_filter})
    if type_filter and type_filter != "Both":
        filters["conditions"].append({"field": "type", "operator": "==", "value": type_filter.lower()})
    if page_range:
        try:
            start, end = map(int, page_range.split('-')) if '-' in page_range else (int(page_range), int(page_range))
            filters["conditions"].append({"field": "pages", "operator": ">=", "value": str(start)})
            filters["conditions"].append({"field": "pages", "operator": "<=", "value": str(end)})
        except ValueError:
            logger.warning(f"Invalid page range: {page_range}")
            return []
    logger.debug(f"Applying filters: {filters}")
    try:
        results = search_pipeline.run({
            "embedder": {"text": query},
            "retriever_embedding": {"top_k": top_k, "filters": filters if filters["conditions"] else None},
            "retriever_bm25": {"query": query, "top_k": top_k, "filters": filters if filters["conditions"] else None}
        })
        logger.debug(f"Retrieved docs: {len(results['joiner']['documents'])}")
    except Exception as e:
        logger.error(f"Search pipeline failed: {e}")
        return []
    grouped = {}
    for doc in results["joiner"]["documents"]:
        stories = doc.meta.get("stories", [])
        book_slug = doc.meta.get("book", "unknown")
        positions = load_story_positions(book_slug)
        for story in stories:
            title = story["title"]
            if doc.score > 0.2 and title not in grouped and positions.get(title, {}).get("start_char", -1) != -1:
                grouped[title] = {
                    "title": title,
                    "book_slug": book_slug,
                    "pages": story["pages"],
                    "keywords": ', '.join(positions.get(title, {}).get("keywords", [])),
                    "start_char": positions.get(title, {}).get("start_char", 0),
                    "end_char": positions.get(title, {}).get("end_char", len(load_full_md(book_slug))),
                    "score": doc.score
                }
            elif title in grouped:
                grouped[title]["score"] = max(grouped[title]["score"], doc.score)
    sorted_results = sorted(grouped.values(), key=lambda x: x["score"], reverse=True)[:top_k]
    logger.info(f"Search returned {len(sorted_results)} results for query: {query}")
    return sorted_results

# Helper: Generate HTML for MD with anchors, highlight, and scroll (updated for per-book full_md)
def render_md_with_scroll_and_highlight(book_slug, start_char, end_char, page):
    full_md = load_full_md(book_slug)
    try:
        logger.debug(f"Rendering MD for {book_slug} with start_char={start_char}, end_char={end_char}, page={page}")

        # Step 1: Adjust for HTML escaping (< and >)
        escape_pattern = r'[<>]'
        escape_matches = list(re.finditer(escape_pattern, full_md))
        def get_escape_delta(pos):
            delta = 0
            for m in escape_matches:
                if m.start() < pos:
                    delta += 3  # &lt; or &gt; adds 3 characters
            return delta
        escaped_start = start_char + get_escape_delta(start_char)
        escaped_end = end_char + get_escape_delta(end_char)

        # Escape the MD
        escaped_md = full_md.replace('<', '&lt;').replace('>', '&gt;')

        # Step 2: Adjust for anchor insertions on escaped_md
        anchor_pattern = r'\\\[Page (\d+)\\\]'
        anchor_matches = list(re.finditer(anchor_pattern, escaped_md, re.IGNORECASE))
        def get_anchor_delta(pos):
            delta = 0
            for m in anchor_matches:
                if m.start() < pos:
                    page_num = m.group(1)
                    replacement = f'<div id="page-{page_num}">[Page {page_num}]</div>'
                    orig_len = m.end() - m.start()
                    rep_len = len(replacement)
                    delta += rep_len - orig_len
            return delta
        adjusted_start = escaped_start + get_anchor_delta(escaped_start)
        adjusted_end = escaped_end + get_anchor_delta(escaped_end)

        # Add anchors
        def replace_anchor(match):
            page_num = match.group(1)
            return f'<div id="page-{page_num}">[Page {page_num}]</div>'
        md_with_anchors = re.sub(anchor_pattern, replace_anchor, escaped_md, flags=re.IGNORECASE)

        # Highlight story range using adjusted positions
        highlighted = (
            md_with_anchors[:adjusted_start] +
            '<span style="background-color: yellow;">' +
            md_with_anchors[adjusted_start:adjusted_end] +
            '</span>' +
            md_with_anchors[adjusted_end:]
        )
        html = f"""
        <div style="height: 500px; overflow-y: scroll; font-family: Arial; white-space: pre-wrap;">{highlighted}</div>
        """
        return html
    except Exception as e:
        logger.error(f"Failed to render MD for {book_slug}: {e}")
        return "Error rendering story."

# Helper: Export single story or list (updated for per-book full_md and source)
def export_stories(stories, format='md', is_single=True):
    try:
        format = format.lower()
        logger.debug(f"Exporting stories, format={format}, is_single={is_single}")
        content = ""
        for story in stories:
            full_md = load_full_md(story['book_slug'])
            title = story['title']
            pages = story['pages']
            keywords = story['keywords']
            start = story.get('start_char', 0)
            end = story.get('end_char', len(full_md))
            text = full_md[start:end]
            logger.debug(f"Exporting story '{title}' from {story['book_slug']} with slice [{start}:{end}], text length: {len(text)}")
            content += f"# {title}\n\nSource: {story['book_slug'].replace('_', ' ').title()}\nPages: {pages}\nKeywords: {keywords}\n\n{text}\n\n---\n\n"
        base_filename = "export_single" if is_single else "export_list"
        temp_md = f"/tmp/{base_filename}.md"
        with open(temp_md, "w", encoding="utf-8") as f:
            f.write(content)
        if format == 'md':
            filepath = temp_md
            mime = 'text/markdown'
            ext = 'md'
        elif format == 'pdf':
            filepath = f"/tmp/{base_filename}.pdf"
            try:
                subprocess.run(['pandoc', temp_md, '-o', filepath], check=True)
            except:
                logger.warning("Pandoc failed; using reportlab fallback.")
                c = canvas.Canvas(filepath, pagesize=letter)
                y = 750
                for line in content.split('\n')[:50]: # Limit for prototype
                    c.drawString(50, y, line[:100])
                    y -= 15
                c.save()
            mime = 'application/pdf'
            ext = 'pdf'
        elif format == 'word':
            filepath = f"/tmp/{base_filename}.docx"
            try:
                subprocess.run(['pandoc', temp_md, '-o', filepath], check=True)
            except:
                logger.warning("Pandoc failed; using python-docx fallback.")
                doc = DocxDocument()
                doc.add_paragraph(content)
                doc.save(filepath)
            mime = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ext = 'docx'
        else:
            raise ValueError(f"Unsupported format: {format}")
        with open(filepath, "rb") as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        return {'mime': mime, 'data': data, 'filename': f"{base_filename}.{ext}"}
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return None

# Gradio UI Definition (updated for multi-book: book dropdown, per-book loads)
def gradio_ui():
    try:
        logger.info("Building Gradio UI...")
        with gr.Blocks(title="Paranormal Text Repository") as demo:
            # States
            selected_story = gr.State(None)
            curated_list = gr.State([])
            edited_start = gr.State(0)
            edited_end = gr.State(0)
            results_state = gr.State([])
            # Top Bar
            with gr.Row():
                query = gr.Textbox(label="Search (e.g., demonic possession)", placeholder="Enter query...")
                source_filter = gr.Dropdown(label="Source", choices=sources, value="All Sources")
                type_filter = gr.Dropdown(label="Type", choices=["Story", "Non-Story", "Both"], value="Both")
                page_range = gr.Textbox(label="Page Range (e.g., 4-10)", placeholder="Optional")
                search_btn = gr.Button("Search")
            # Main Row: Three Columns
            with gr.Row(variant="panel"):
                # Left: Search results
                with gr.Column(scale=1):
                    gr.Markdown("### Search Results")
                    results_radio = gr.Radio(label="Select Story", choices=[], interactive=True, elem_id="results_radio")
                # Middle: Story Viewer
                with gr.Column(scale=3):
                    gr.Markdown("### Story Viewer")
                    viewer = gr.HTML(value="Select a story to view...", show_label=False)
                    hidden_page = gr.Textbox(visible=False, show_label=False)
                    start_slider = gr.Slider(label="Start Char", minimum=0, maximum=1000000, step=1, interactive=True, visible=False)  # Larger max for multi-book
                    end_slider = gr.Slider(label="End Char", minimum=0, maximum=1000000, step=1, interactive=True, visible=False)
                    start_phrase = gr.Textbox(label="Start After Phrase (e.g., introduction)", placeholder="Phrase to set start after...")
                    end_phrase = gr.Textbox(label="End Before Phrase (e.g., conclusion)", placeholder="Phrase to set end before...")
                    apply_boundaries_btn = gr.Button("Apply Phrase Boundaries")
                    reset_btn = gr.Button("Reset Boundaries")
                    edit_status = gr.Textbox(label="Status", value="", interactive=False)
                    add_btn = gr.Button("Add to List")
                    export_single_btn = gr.Dropdown(label="Export Single", choices=["MD", "PDF", "Word"], interactive=True)
                    export_single_output = gr.HTML(value="", show_label=False)
                # Right: Curated List
                with gr.Column(scale=1):
                    gr.Markdown("### Curated List")
                    curated_display = gr.Dataframe(headers=["Title", "Pages"], interactive=False)
                    export_list_btn = gr.Dropdown(label="Export List", choices=["MD", "PDF", "Word"], interactive=True)
                    export_list_output = gr.HTML(value="", show_label=False)
            # Event Handlers (updated for book_slug)
            def update_results(query, source, type_filter, pages):
                try:
                    results = search_stories(query, source, type_filter, pages)
                    choices = [f"{r['title']} (Pages: {r['pages']}, Keywords: {r['keywords']})" for r in results] if results else ["No results found"]
                    return results, gr.update(choices=choices, value=None)
                except Exception as e:
                    logger.error(f"Search failed: {e}")
                    return [], gr.update(choices=["No results found"], value=None)
            search_btn.click(update_results, [query, source_filter, type_filter, page_range], [results_state, results_radio])
            def select_story(results, selected):
                try:
                    if not selected or selected == "No results found":
                        return None, 0, 0
                    for r in results:
                        if selected.startswith(r['title']):
                            return r, r['start_char'], r['end_char']
                    return None, 0, 0
                except Exception as e:
                    logger.error(f"Select story failed: {e}")
                    return None, 0, 0
            def update_viewer(selected, start, end):
                try:
                    if not selected:
                        return "No story selected."
                    page = selected['pages'].split('-')[0]
                    book_slug = selected['book_slug']
                    return render_md_with_scroll_and_highlight(book_slug, int(start), int(end), page)
                except Exception as e:
                    logger.error(f"Update viewer failed: {e}")
                    return "Error rendering viewer."
            results_radio.change(
                select_story,
                [results_state, results_radio],
                [selected_story, edited_start, edited_end]
            ).then(
                update_viewer,
                [selected_story, edited_start, edited_end],
                viewer
            ).then(
                lambda selected: selected['pages'].split('-')[0] if selected else '1',
                [selected_story],
                hidden_page
            )
            start_slider.change(update_viewer, [selected_story, start_slider, end_slider], viewer)
            end_slider.change(update_viewer, [selected_story, start_slider, end_slider], viewer)
            hidden_page.change(
                None,
                [hidden_page],
                None,
                js="""
                (page) => {
                    setTimeout(() => {
                        const target = document.getElementById(`page-${page}`);
                        if (target) {
                            target.scrollIntoView({behavior: 'smooth', block: 'start'});
                        } else {
                            console.warn(`Page anchor not found: page-${page}`);
                        }
                    }, 100);
                }
                """
            )
            def apply_phrase_boundaries(start_phrase, end_phrase, current_start, current_end, selected):
                status = "Boundaries updated."
                new_start = current_start
                new_end = current_end
                book_slug = selected.get('book_slug', 'unknown') if selected else 'unknown'
                full_md = load_full_md(book_slug)
                window_size = 5000  # Search window around current range
                search_start = max(0, current_start - window_size)
                search_end = min(len(full_md), current_end + window_size)
                search_text = full_md[search_start:search_end]
                if start_phrase:
                    match = re.search(re.escape(start_phrase), search_text, re.IGNORECASE)
                    if match:
                        new_start = search_start + match.end()
                    else:
                        status = "Start phrase not found near current range."
                if end_phrase:
                    match = re.search(re.escape(end_phrase), search_text, re.IGNORECASE)
                    if match:
                        new_end = search_start + match.start()
                    else:
                        status = "End phrase not found near current range."
                if new_start >= new_end:
                    status = "Invalid range after apply (start >= end) - no change."
                    return current_start, current_end, status
                logger.debug(f"Applied boundaries: {new_start}-{new_end}")
                return new_start, new_end, status
            def reset_hidden_page():
                return "0"  # Invalid page to trigger change
            def set_hidden_page(selected):
                if not selected:
                    return "1"
                return selected['pages'].split('-')[0]
            apply_boundaries_btn.click(
                apply_phrase_boundaries,
                [start_phrase, end_phrase, edited_start, edited_end, selected_story],
                [edited_start, edited_end, edit_status]
            ).then(
                update_viewer,
                [selected_story, edited_start, edited_end],
                viewer
            ).then(
                lambda start, end: (gr.update(value=start), gr.update(value=end)),
                [edited_start, edited_end],
                [start_slider, end_slider]
            ).then(
                reset_hidden_page,
                None,
                hidden_page
            ).then(
                set_hidden_page,
                [selected_story],
                hidden_page
            )
            def reset_boundaries(selected):
                if not selected:
                    return 0, 0, "Reset to defaults."
                return selected['start_char'], selected['end_char'], "Reset to originals."
            reset_btn.click(
                reset_boundaries,
                [selected_story],
                [edited_start, edited_end, edit_status]
            ).then(
                update_viewer,
                [selected_story, edited_start, edited_end],
                viewer
            ).then(
                lambda start, end: (gr.update(value=start), gr.update(value=end)),
                [edited_start, edited_end],
                [start_slider, end_slider]
            ).then(
                reset_hidden_page,
                None,
                hidden_page
            ).then(
                set_hidden_page,
                [selected_story],
                hidden_page
            )
            def add_to_list(cl, sel, start, end):
                try:
                    if not sel:
                        return cl
                    return cl + [{"title": sel['title'], "pages": sel['pages'], "keywords": sel['keywords'], "start_char": start, "end_char": end}]
                except Exception as e:
                    logger.error(f"Add to list failed: {e}")
                    return cl
            add_btn.click(add_to_list, [curated_list, selected_story, edited_start, edited_end], curated_list)
            curated_list.change(lambda cl: [[c['title'], c['pages']] for c in cl], curated_list, curated_display)
            def export_single(selected, start, end, fmt):
                try:
                    if not selected:
                        return ""
                    stories = [{"title": selected['title'], "pages": selected['pages'], "keywords": selected['keywords'], "start_char": start, "end_char": end, "book_slug": selected['book_slug']}]
                    export_data = export_stories(stories, fmt, is_single=True)
                    if not export_data:
                        return "Export failed."
                    data_uri = f"data:{export_data['mime']};base64,{export_data['data']}"
                    return f'<a href="{data_uri}" download="{export_data["filename"]}">Download Single {fmt}</a>'
                except Exception as e:
                    logger.error(f"Single export failed: {e}")
                    return "Export failed."
            export_single_btn.change(export_single, [selected_story, edited_start, edited_end, export_single_btn], export_single_output)
            def export_list(cl, fmt):
                try:
                    if not cl:
                        return ""
                    export_data = export_stories(cl, fmt, is_single=False)
                    if not export_data:
                        return "Export failed."
                    data_uri = f"data:{export_data['mime']};base64,{export_data['data']}"
                    return f'<a href="{data_uri}" download="{export_data["filename"]}">Download List {fmt}</a>'
                except Exception as e:
                    logger.error(f"List export failed: {e}")
                    return "Export failed."
            export_list_btn.change(export_list, [curated_list, export_list_btn], export_list_output)
        return demo
    except Exception as e:
        logger.error(f"Failed to build Gradio UI: {e}")
        raise

# Launch (no server_name/port for HF defaults)
if __name__ == "__main__":
    demo = gradio_ui()
    demo.launch()