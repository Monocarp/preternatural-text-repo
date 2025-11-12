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
import zipfile
import io
from huggingface_hub import HfApi # For optional auto-commit
# Set up logging (stream to stdout for HF logs)
logging.basicConfig(level=logging.INFO, force=True, handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
# Paths (HF repo root)
books_dir = "books/"
data_dir = "data/"
document_store_path = os.path.join(data_dir, "document_store.json")
codex_tree_path = os.path.join(data_dir, "codex_tree.json")
stories_dict_path = os.path.join(data_dir, "stories_dict.json")
# Global flat story storage
stories_dict = {}
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
sources = ["All Sources"] + sorted(books) # For UI dropdown
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
        has_embeddings = any(doc.embedding is not None and len(doc.embedding) == 1024 for doc in loaded_docs)
        if not has_embeddings:
            logger.warning("No valid embeddings found; re-embedding...")
            from haystack.components.embedders import SentenceTransformersDocumentEmbedder
            embedder = SentenceTransformersDocumentEmbedder(model="BAAI/bge-large-en-v1.5", normalize_embeddings=True)
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
        new_store = InMemoryDocumentStore(embedding_similarity_function="cosine")
        new_store.write_documents(loaded_docs)
        document_store = new_store
        logger.info(f"Index rebuilt, store has {document_store.count_documents()} documents")
    except Exception as e:
        logger.error(f"Failed to load/re-embed document store: {e}")
        raise
else:
    logger.error("document_store.json not found. Re-run step 4.")
    raise FileNotFoundError("document_store.json missing")
# Set up Haystack pipelines
logger.debug("Setting up Haystack pipelines...")
# Components for both_pipeline
embedder_both = SentenceTransformersTextEmbedder(model="BAAI/bge-large-en-v1.5", normalize_embeddings=True)
retriever_embedding_both = InMemoryEmbeddingRetriever(document_store=document_store)
retriever_bm25_both = InMemoryBM25Retriever(document_store=document_store)
joiner = DocumentJoiner(
    join_mode="reciprocal_rank_fusion",
    weights=[0.5, 0.5]
)
# Both (Hybrid) pipeline
both_pipeline = Pipeline()
both_pipeline.add_component("embedder", embedder_both)
both_pipeline.add_component("retriever_embedding", retriever_embedding_both)
both_pipeline.add_component("retriever_bm25", retriever_bm25_both)
both_pipeline.add_component("joiner", joiner)
both_pipeline.connect("embedder.embedding", "retriever_embedding.query_embedding")
both_pipeline.connect("retriever_embedding", "joiner")
both_pipeline.connect("retriever_bm25", "joiner")
logger.info(f"Both pipeline components: {both_pipeline.graph.nodes.keys()}")
# Components for keyword_pipeline
retriever_bm25_key = InMemoryBM25Retriever(document_store=document_store)
# Keywords pipeline
keyword_pipeline = Pipeline()
keyword_pipeline.add_component("retriever_bm25", retriever_bm25_key)
logger.info(f"Keyword pipeline components: {keyword_pipeline.graph.nodes.keys()}")
# Components for semantic_pipeline
embedder_sem = SentenceTransformersTextEmbedder(model="BAAI/bge-large-en-v1.5", normalize_embeddings=True)
retriever_embedding_sem = InMemoryEmbeddingRetriever(document_store=document_store)
# Semantic pipeline
semantic_pipeline = Pipeline()
semantic_pipeline.add_component("embedder", embedder_sem)
semantic_pipeline.add_component("retriever_embedding", retriever_embedding_sem)
semantic_pipeline.connect("embedder.embedding", "retriever_embedding.query_embedding")
logger.info(f"Semantic pipeline components: {semantic_pipeline.graph.nodes.keys()}")
# Helper: Run search (updated for book filter via meta['book'], added debug logs for doc counts)
def search_stories(query, source_filter=None, type_filter=None, search_mode="Both", top_k=1000, min_score=0.2):
    logger.info(f"Searching for query: {query}, source: {source_filter}, type: {type_filter}, mode: {search_mode}, min_score: {min_score}")
    filters = {"operator": "AND", "conditions": []}
    if source_filter and source_filter != "All Sources":
        filters["conditions"].append({"field": "book", "operator": "==", "value": source_filter})
    if type_filter and type_filter != "Both":
        filters["conditions"].append({"field": "type", "operator": "==", "value": type_filter.lower()})
    logger.debug(f"Applying filters: {filters}")
    filters_param = filters if filters["conditions"] else None
    try:
        if search_mode == "Both":
            results = both_pipeline.run({
                "embedder": {"text": query},
                "retriever_embedding": {"top_k": top_k, "filters": filters_param},
                "retriever_bm25": {"query": query, "top_k": top_k, "filters": filters_param}
            })
            documents = results["joiner"]["documents"]
        elif search_mode == "Keywords":
            results = keyword_pipeline.run({
                "retriever_bm25": {"query": query, "top_k": top_k, "filters": filters_param}
            })
            documents = results["retriever_bm25"]["documents"]
        elif search_mode == "Semantic":
            results = semantic_pipeline.run({
                "embedder": {"text": query},
                "retriever_embedding": {"top_k": top_k, "filters": filters_param}
            })
            documents = results["retriever_embedding"]["documents"]
        elif search_mode == "Exact":
            all_docs = document_store.filter_documents(filters=filters_param)
            documents = []
            query = query.strip()
            if ' ' in query:
                pattern = re.escape(query)
            else:
                pattern = r'\b' + re.escape(query) + r'\b'
            for doc in all_docs:
                content = doc.content
                count = len(re.findall(pattern, content, re.IGNORECASE))
                if count > 0:
                    doc.score = count # Use count as score for sorting by frequency
                    documents.append(doc)
        else:
            raise ValueError(f"Invalid search mode: {search_mode}")
        logger.debug(f"Retrieved docs: {len(documents)}")
    except Exception as e:
        logger.error(f"Search pipeline failed: {e}")
        return []
    grouped = {}
    for doc in documents:
        stories = doc.meta.get("stories", [])
        book_slug = doc.meta.get("book", "unknown")
        positions = load_story_positions(book_slug)
        for story in stories:
            title = story["title"]
            if doc.score > min_score and title not in grouped and positions.get(title, {}).get("start_char", -1) != -1:
                grouped[title] = {
                    "title": title,
                    "book_slug": book_slug,
                    "pages": story["pages"],
                    "keywords": ', '.join(positions.get(title, {}).get("keywords", [])),
                    "start_char": positions.get(title, {}).get("start_char", 0),
                    "end_char": positions.get(title, {}).get("end_char", len(load_full_md(book_slug))),
                    "score": doc.score # UPDATED: This will now be the fused RRF score for hybrid mode
                }
            elif title in grouped:
                grouped[title]["score"] = max(grouped[title]["score"], doc.score)
    sorted_results = sorted(grouped.values(), key=lambda x: x["score"], reverse=True)
    if search_mode == "Exact":
        sorted_results = [{**r, "search_query": query} for r in sorted_results]
    logger.info(f"Search returned {len(sorted_results)} results for query: {query}")
    if sorted_results:
        logger.info(f"Top result: {sorted_results[0]['title']} | Score: {sorted_results[0]['score']:.3f}")
    return sorted_results
# Helper: Generate HTML for MD with anchors, highlight, and scroll (updated for per-book full_md)
def render_md_with_scroll_and_highlight(book_slug, start_char, end_char, page, search_query=None):
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
                    delta += 3 # < or > adds 3 characters
            return delta
        escaped_start = start_char + get_escape_delta(start_char)
        escaped_end = end_char + get_escape_delta(end_char)
        # Escape the MD
        escaped_md = full_md.replace('<', '&lt;').replace('>', '&gt;')
        # Step 2: Adjust for anchor insertions on escaped_md
        anchor_pattern = r'\\?\[\s*Page\s*(\d+)\s*\\?\]'
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
        # Step 3: If search_query (from Exact mode), add red highlights and adjust deltas
        md_with_red = md_with_anchors
        if search_query:
            search_query = search_query.strip()
            if ' ' in search_query:
                pattern = re.escape(search_query)
            else:
                pattern = r'\b' + re.escape(search_query) + r'\b'
            red_matches = list(re.finditer(pattern, md_with_anchors, re.IGNORECASE))
            def get_red_delta(pos):
                delta = 0
                for m in red_matches:
                    if m.start() < pos:
                        delta += 33 # len('<span style="color: red;"></span>')
                return delta
            adjusted_start += get_red_delta(adjusted_start)
            adjusted_end += get_red_delta(adjusted_end)
            # Apply red highlights
            def replace_red(match):
                return '<span style="color: red;">' + match.group(0) + '</span>'
            md_with_red = re.sub(pattern, replace_red, md_with_anchors, flags=re.IGNORECASE)
        # Highlight story range using adjusted positions
        highlighted = (
            md_with_red[:adjusted_start] +
            '<span style="background-color: yellow;">' +
            md_with_red[adjusted_start:adjusted_end] +
            '</span>' +
            md_with_red[adjusted_end:]
        )
        html = f"""
        <div style="height: 500px; overflow-y: scroll; font-family: Arial; white-space: pre-wrap;">{highlighted}</div>
        """
        return html
    except Exception as e:
        logger.error(f"Failed to render MD for {book_slug}: {e}")
        return "Error rendering story."
# Helper: Find book_slug for a given title by searching story_positions
def find_book_slug(title):
    for book_slug in books:
        positions = load_story_positions(book_slug)
        if title in positions:
            return book_slug
    raise ValueError(f"Book not found for title: {title}")
# Helper: Export single story or list (updated for per-book full_md and source)
def export_stories(stories, format='md', is_single=True):
    try:
        format = format.lower()
        logger.debug(f"Exporting stories, format={format}, is_single={is_single}")
        content = ""
        for story in stories:
            book_slug = story.get('book_slug')
            if book_slug is None:
                book_slug = find_book_slug(story['title'])
            full_md = load_full_md(book_slug)
            title = story['title']
            pages = story['pages']
            keywords = story['keywords']
            start = story.get('start_char', 0)
            end = story.get('end_char', len(full_md))
            text = full_md[start:end]
            logger.debug(f"Exporting story '{title}' from {book_slug} with slice [{start}:{end}], text length: {len(text)}")
            content += f"# {title}\n\nSource: {book_slug.replace('_', ' ').title()}\nPages: {pages}\nKeywords: {keywords}\n\n{text}\n\n---\n\n"
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
# Helper: Export updated story_positions JSONs as ZIP
def export_updated_jsons(pending_updates):
    try:
        if not pending_updates:
            return ""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for book_slug, updates in pending_updates.items():
                # Load original positions
                original_positions = load_story_positions(book_slug).copy()
                # Apply updates
                for title, bounds in updates.items():
                    if title in original_positions:
                        for key, val in bounds.items():
                            original_positions[title][key] = val
                    else:
                        logger.warning(f"Title {title} not found in {book_slug}; skipping update.")
                # Serialize updated dict
                json_data = json.dumps(original_positions, indent=4, ensure_ascii=False).encode('utf-8')
                zip_file.writestr(f"updated_story_positions_{book_slug}.json", json_data)
        zip_buffer.seek(0)
        data = base64.b64encode(zip_buffer.read()).decode('utf-8')
        data_uri = f"data:application/zip;base64,{data}"
        return f'<a href="{data_uri}" download="updated_story_positions.zip">Download Updated JSONs ZIP</a>'
    except Exception as e:
        logger.error(f"JSON export failed: {e}")
        return "Export failed."
# Codex Tree: Pre-defined hierarchy (from your updated list)
CATEGORIES = {
    "Demonic Activity": {
        "Obsession": {
            "Fear/Anxiety": [],
            "Emotional Guilt": [],
            "Anger": [],
            "Reduction of Voluntariness": []
        },
        "Oppression": {
            "Haunting Vexations": {
                "Poltergeist": [],
                "Shadow People": [],
                "Sleep Paralysis": [],
                "Static People": [],
                "Glimmer Man": [],
                "Flannel Man": []
            },
            "Physical Health Vexations": {
                "Death": [],
                "Bruise": [],
                "Bite Marks": [],
                "Scratches": [],
                "Unexplained Physical Pain": [],
                "Headaches": [],
                "Insomnia": [],
                "Bumps, Cysts, other Protrusions": [],
                "Bone Dislocation": [],
                "Distention of the Stomach": [],
                "Nausea": [],
                "Foul Breath": [],
                "Miscarriages": [],
                "Blocked Conception": [],
                "Sexual Assault": [],
                "Pronounced Sleep Behaviors/Manifestations": [],
                "Minor Morphing": [],
                "Suffocation": [],
                "Choking": [],
                "Serious Physical Injury": []
            },
            "Mental Health Vexations": {
                "Weariness": [],
                "Dreams": [],
                "Depression": [],
                "Anger": [],
                "Emotional/Relational Block": [],
                "Visual Hallucinations": [],
                "Auditory Hallucinations": [],
                "Severe Mental Disorder": []
            },
            "Peripheral Vexations": {
                "Pets": [],
                "Bugs/Pests": [],
                "Financial": [],
                "Occupational": [],
                "Reputational": []
            }
        },
        "Possession": {
            "Speaking a Foreign Language": [],
            "Occult Knowledge": [],
            "Morphing": [],
            "Strength": [],
            "Appearance of Fortunae": {
                "Nails": [],
                "Glass": [],
                "Cloth": [],
                "Other": []
            },
            "Levitation": [],
            "Superhuman Speed": [],
            "Superhuman Agility": [],
            "Gravitas": [],
            "Sustained Unnatural Posture": [],
            "Fasting": [],
            "Secondary Signs": {
                "Repugnance towards Holiness": [],
                "Obscene Thoughts Around Holiness": [],
                "Blocked Prayer": [],
                "Aversion to Scripture": [],
                "Illness around Holiness": [],
                "Aversion to Sacred Names": [],
                "Pain From Holy Items": [],
                "Difficulty in Receiving Sacraments": [],
                "Liturgical Calendar Suffering": [],
                "Chronic Insomnia": [],
                "Affected Dreams": [],
                "Falsified Emotions": [],
                "Speaking in Tongues": [],
                "Possession-Specific Physical Vexation": {
                    "Foul Odor": [],
                    "Drastic Eating Changes": [],
                    "Fluctuation in Body Temperature": [],
                    "Diabolical Incandescence": []
                },
                "Suffering Spirituality": {
                    "Fruitless Self-Satisfaction": [],
                    "Anguish over sins": [],
                    "Spiritual Security": [],
                    "Self-Aggrandizing Behavior": [],
                    "Contempt for little things (spiritual)": [],
                    "Closed towards Spiritual Director": [],
                    "Nonconformity with scripture and tradition": [],
                    "animus delendi (destruction)": []
                }
            }
        }
    },
    "Ghostly Activity": {
        "Family Member/Loved One": {
            "Appearance": [],
            "Voice": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Stranger": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Individual Connected To Place/Person": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Family Pet": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Other Animal": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        }
    },
    "Cryptid": {
        "Canine": {
            "Dogman": [],
            "Werewolf": [],
            "Chupacabra": [],
            "Other": []
        },
        "Avian": {
            "Thunderbird": [],
            "Mothman": [],
            "Other": []
        },
        "Bipedal": {
            "Sasquatch": [],
            "Humanoid": [],
            "Other": []
        },
        "Aquatic": [],
        "Feline": [],
        "Cervidae": {
            "Deer": [],
            "Moose": []
        }
    },
    "Fae": {
        "Fairy": [],
        "Nymph": [],
        "Gnome": [],
        "Other": []
    },
    "Witchcraft": {
        "Flying": [],
        "Levitation": [],
        "Transportation": [],
        "Cursing": [],
        "Hagriding": [],
        "Evil Eye": [],
        "Abduction": {
            "Child": [],
            "Adult": [],
            "Pet": [],
            "Non-Pet Animal": []
        },
        "Physical Harm": [],
        "Physical Harm To Children": [],
        "Herbal/Natural": [],
        "Divination": [],
        "Harm to Crops": [],
        "Harm to Livestock": [],
        "Harm To Pets": [],
        "Sacrificing Children": [],
        "Indoctrinating Children": [],
        "Black Sabbath": [],
        "Ritual": {
            "Black Sabbath": [],
            "Contract with Demon": [],
            "Contract with Another": [],
            "Sacrilegious Baptism": [],
            "Sacrifice": {
                "Sacrificing a Person": {
                    "Sacrificing a Family Member": {
                        "Sacrificing a Parent": [],
                        "Sacrificing a Child": [],
                        "Sacrificing a Sibling": [],
                        "Sacrificing a Grandparent": [],
                        "Sacrificing an Aunt/Uncle": [],
                        "Sacrificing a cousin": [],
                        "Sacrificing a niece/nephew": []
                    },
                    "Sacrificing a Friend": [],
                    "Sacrificing a known associate": [],
                    "Sacrificing a stranger": []
                },
                "Sacrificing an Animal": [],
                "Sacrificing a Family Member": []
            },
            "Rejection of Sacraments": {
                "Rejection of Baptism": [],
                "Rejection of Confirmation": [],
                "Rejection of Confession": [],
                "Rejection of Eucharist": [],
                "Rejection of Marriage": [],
                "Rejection of Holy Orders": []
            }
        }
    },
    "Supernatural Phenomena": {
        "Time Slip": [],
        "Time Loss": []
    }
}
# Helper: Load/save codex_tree.json (pre-populate if empty)
def load_codex_tree():
    global stories_dict
    if os.path.exists(codex_tree_path):
        with open(codex_tree_path, "r") as f:
            tree = json.load(f)
    else:
        tree = dict(CATEGORIES) # Pre-populate empty lists as dicts for nesting
        # Convert leaves to lists if not
        def ensure_lists(d):
            for k, v in d.items():
                if isinstance(v, dict):
                    ensure_lists(v)
                else:
                    d[k] = []
        ensure_lists(tree)
        save_codex_tree(tree)
    if os.path.exists(stories_dict_path):
        with open(stories_dict_path, "r") as f:
            stories_dict = json.load(f)
    else:
        stories_dict = {}
    return tree
def save_codex_tree(tree):
    global stories_dict
    os.makedirs(data_dir, exist_ok=True)
    with open(codex_tree_path, "w") as f:
        json.dump(tree, f, indent=4)
    with open(stories_dict_path, "w") as f:
        json.dump(stories_dict, f, indent=4)
    # Optional auto-commit
    token = os.getenv("HF_TOKEN")
    if token:
        try:
            api = HfApi(token=token)
            api.upload_file(
                path_or_fileobj=codex_tree_path,
                path_in_repo=codex_tree_path,
                repo_id="hetzerdj/preternatural-text-ui",
                repo_type="space" # Fixed for Spaces
            )
            api.upload_file(
                path_or_fileobj=stories_dict_path,
                path_in_repo=stories_dict_path,
                repo_id="hetzerdj/preternatural-text-ui",
                repo_type="space"
            )
            logger.info("Auto-committed codex_tree.json and stories_dict.json to HF repo")
        except Exception as e:
            logger.error(f"Auto-commit failed: {e}")
    else:
        logger.info("HF_TOKEN not set; changes saved locally only")
# Helper: Assign story to path in tree (updated for references)
def assign_to_path(tree, path, story):
    global stories_dict
    title = story['title']
    # Store full details once
    if title not in stories_dict:
        stories_dict[title] = story
    current = tree
    for level in path[:-1]:
        if level not in current:
            current[level] = {}
        if not isinstance(current[level], dict):
            current[level] = {'_stories': current[level]}
        current = current[level]
    leaf = path[-1]
    if leaf not in current:
        current[leaf] = []
    leaf_val = current[leaf]
    if isinstance(leaf_val, list):
        if title not in leaf_val: # Store title only
            leaf_val.append(title)
    elif isinstance(leaf_val, dict):
        if '_stories' not in leaf_val:
            leaf_val['_stories'] = []
        if title not in leaf_val['_stories']:
            leaf_val['_stories'].append(title)
    else:
        raise ValueError("Invalid tree structure")
    return tree
# Helper: Remove story from path in tree
def remove_from_path(tree, path, title):
    current = tree
    for level in path[:-1]:
        if level not in current:
            return tree
        current = current[level]
    leaf = path[-1]
    if leaf in current:
        leaf_val = current[leaf]
        if isinstance(leaf_val, list) and title in leaf_val:
            leaf_val.remove(title)
        elif isinstance(leaf_val, dict) and '_stories' in leaf_val and title in leaf_val['_stories']:
            leaf_val['_stories'].remove(title)
    return tree
# Helper: Find all paths for a title
def find_paths_for_title(tree, title, current_path=None, paths=None):
    if current_path is None:
        current_path = []
    if paths is None:
        paths = []
    if isinstance(tree, dict):
        if '_stories' in tree and title in tree['_stories']:
            paths.append(current_path[:])
        for key, value in tree.items():
            if key != '_stories':
                find_paths_for_title(value, title, current_path + [key], paths)
    elif isinstance(tree, list):
        if title in tree:
            paths.append(current_path[:])
    return paths
# Helper: Get all stories at/existing a path (aggregate descendants, updated for references)
def get_stories_at_path(tree, path):
    global stories_dict
    current = tree
    for level in path:
        if level not in current:
            return []
        current = current[level]
    titles = []
    def recurse(d):
        if isinstance(d, list):
            titles.extend(d)
        elif isinstance(d, dict):
            if '_stories' in d:
                titles.extend(d['_stories'])
            for v in d.values():
                recurse(v)
    recurse(current)
    # Dedupe titles and resolve to full stories
    unique_titles = set(titles)
    unique_stories = [stories_dict[title] for title in sorted(unique_titles) if title in stories_dict]
    return unique_stories
# Helper: Get full path string for display
def path_to_string(path):
    return " > ".join(path) if path else "Root"
# Helper: Static story Markdown
def render_static_story(story):
    book_slug = story['book_slug']
    full_md = load_full_md(book_slug)
    text = full_md[story['start_char']:story['end_char']]
    return f"# {story['title']}\n\n**Source**: {book_slug.replace('_', ' ').title()}\n**Pages**: {story['pages']}\n**Keywords**: {story['keywords']}\n\n{text}"
# Helper: Reset hidden page
def reset_hidden_page():
    return "0" # Invalid page to trigger change
# Helper: Set hidden page
def set_hidden_page(selected):
    if not selected:
        return "1"
    return selected['pages'].split('-')[0]
# Helper: Update pending after changes
def update_pending_after_changes(pending, selected, new_start, new_end, new_keywords):
    if not selected:
        return pending
    book_slug = selected['book_slug']
    title = selected['title']
    orig_start = selected['start_char']
    orig_end = selected['end_char']
    orig_keywords = selected['keywords']
    update_dict = {}
    changed = False
    if new_start != orig_start:
        changed = True
        update_dict['start_char'] = new_start
    if new_end != orig_end:
        changed = True
        update_dict['end_char'] = new_end
    if new_keywords != orig_keywords:
        changed = True
        kw_list = list(set([k.strip() for k in new_keywords.split(',') if k.strip()]))
        update_dict['keywords'] = kw_list
    if changed:
        if book_slug not in pending:
            pending[book_slug] = {}
        pending[book_slug][title] = update_dict
    elif book_slug in pending and title in pending[book_slug]:
        del pending[book_slug][title]
        if not pending[book_slug]:
            del pending[book_slug]
    return pending
# Helper: Update level2
def update_level2(l1, current):
    new_choices = sorted(CATEGORIES.get(l1, {}).keys()) if l1 else []
    value = current if current and current in new_choices else None
    return gr.update(choices=new_choices, value=value)
# Helper: Update level3
def update_level3(l1, l2, current):
    current_dict = CATEGORIES.get(l1, {}).get(l2, {})
    new_choices = sorted(current_dict.keys()) if l2 and isinstance(current_dict, dict) else []
    value = current if current and current in new_choices else None
    return gr.update(choices=new_choices, value=value)
# Helper: Update level4
def update_level4(l1, l2, l3, current):
    current_dict = CATEGORIES.get(l1, {}).get(l2, {}).get(l3, {})
    new_choices = sorted(current_dict.keys()) if l3 and isinstance(current_dict, dict) else []
    value = current if current and current in new_choices else None
    return gr.update(choices=new_choices, value=value)
# Helper: Update level5
def update_level5(l1, l2, l3, l4, current):
    current_dict = CATEGORIES.get(l1, {}).get(l2, {}).get(l3, {}).get(l4, {})
    new_choices = sorted(current_dict.keys()) if l4 and isinstance(current_dict, dict) else []
    value = current if current and current in new_choices else None
    return gr.update(choices=new_choices, value=value)
# Helper: Update level6
def update_level6(l1, l2, l3, l4, l5, current):
    current_dict = CATEGORIES.get(l1, {}).get(l2, {}).get(l3, {}).get(l4, {}).get(l5, {})
    new_choices = sorted(current_dict.keys()) if l5 and isinstance(current_dict, dict) else []
    value = current if current and current in new_choices else None
    return gr.update(choices=new_choices, value=value)
# Helper: Assign category
def assign_category(l1, l2, l3, l4, l5, l6, tree, sel, start, end, kw):
    if not sel:
        return tree
    path = [p for p in [l1, l2, l3, l4, l5, l6] if p]
    if not path:
        return tree
    story = {
        "title": sel['title'],
        "book_slug": sel['book_slug'],
        "pages": sel['pages'],
        "keywords": kw,
        "start_char": int(start),
        "end_char": int(end)
    }
    tree = assign_to_path(tree, path, story)
    # Removed save_codex_tree here; now tied to button
    return tree
# Helper: Remove category
def remove_category(l1, l2, l3, l4, l5, l6, tree, sel):
    if not sel:
        return tree
    path = [p for p in [l1, l2, l3, l4, l5, l6] if p]
    if not path:
        return tree
    return remove_from_path(tree, path, sel['title'])
# Helper: Update current categories display
def update_current_categories(selected, tree):
    if not selected:
        return "No story selected."
    title = selected['title']
    paths = find_paths_for_title(tree, title)
    if not paths:
        return "No categories assigned."
    return "\n".join(" > ".join(p) for p in sorted(paths, key=lambda p: ''.join(p)))
# Helper: Update tree stories
def update_tree_stories(l1, l2, l3, l4, l5, l6, tree):
    path = [p for p in [l1, l2, l3, l4, l5, l6] if p]
    stories = get_stories_at_path(tree, path)
    choices = [s['title'] for s in stories]
    return gr.update(choices=choices, value=None)
# Helper: Select tree story
def select_tree_story(selected_title, l1, l2, l3, l4, l5, l6, tree):
    if not selected_title:
        return "No story selected.", "Static"
    path = [p for p in [l1, l2, l3, l4, l5, l6] if p]
    stories = get_stories_at_path(tree, path)
    story = next((s for s in stories if s['title'] == selected_title), None)
    if story:
        return render_static_story(story), "Static"
    return "Story not found.", "Static"
# Helper: Toggle view mode
def toggle_view_mode(selected_title, mode, l1, l2, l3, l4, l5, l6, tree):
    path = [p for p in [l1, l2, l3, l4, l5, l6] if p]
    stories = get_stories_at_path(tree, path)
    story = next((s for s in stories if s['title'] == selected_title), None)
    if not story:
        return "Story not found.", "Static"
    if mode == "Static":
        page = story['pages'].split('-')[0]
        html = render_md_with_scroll_and_highlight(story['book_slug'], story['start_char'], story['end_char'], page)
        return html, "Book"
    else:
        return render_static_story(story), "Static"
# Helper: Save and get status
def save_and_status(tree):
    save_codex_tree(tree)
    return "Changes saved. Space may restart shortly."
# Helper: Update results
def update_results(query, source, type_filter, search_mode, min_score):
    try:
        mode_map = {
            "Keywords (Exact/Phrase Matches)": "Keywords",
            "Semantic (Conceptual Similarity)": "Semantic",
            "Both (Hybrid)": "Both",
            "Exact (Word/Phrase)": "Exact"
        }
        mode = mode_map.get(search_mode, "Both")
        results = search_stories(query, source, type_filter, mode, min_score=min_score)
        choices = [
            f"{r['title']} (Score: {r['score']:.2f}) (Book: {r['book_slug'].replace('_', ' ').title()}) (Pages: {r['pages']}, Keywords: {r['keywords']})"
            for r in results
        ] if results else ["No results found"]
        count = str(len(results)) if results else "0"
        return results, gr.update(choices=choices, value=None), count
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return [], gr.update(choices=["No results found"], value=None), "0"
# Helper: Select story
def select_story(results, selected):
    try:
        if not selected or selected == "No results found":
            return None, 0, 0, ""
        for r in results:
            if selected.startswith(r['title']):
                return r, r['start_char'], r['end_char'], r['keywords']
        return None, 0, 0, ""
    except Exception as e:
        logger.error(f"Select story failed: {e}")
        return None, 0, 0, ""
# Helper: Update viewer
def update_viewer(selected, start, end):
    try:
        if not selected:
            return "No story selected."
        page = selected['pages'].split('-')[0]
        book_slug = selected['book_slug']
        search_query = selected.get('search_query')
        return render_md_with_scroll_and_highlight(book_slug, int(start), int(end), page, search_query=search_query)
    except Exception as e:
        logger.error(f"Update viewer failed: {e}")
        return "Error rendering viewer."
# Helper: Apply phrase boundaries
def apply_phrase_boundaries(start_phrase, end_phrase, current_start, current_end, selected):
    status = "Boundaries updated."
    new_start = current_start
    new_end = current_end
    book_slug = selected.get('book_slug', 'unknown') if selected else 'unknown'
    full_md = load_full_md(book_slug)
    window_size = 5000 # Search window around current range
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
# Helper: Reset boundaries
def reset_boundaries(selected):
    if not selected:
        return 0, 0, "", "Reset to defaults."
    return selected['start_char'], selected['end_char'], selected['keywords'], "Reset to originals."
# Helper: Add to list
def add_to_list(cl, sel, start, end, keywords):
    try:
        if not sel:
            return cl
        # Check for duplicates by title
        if any(c['title'] == sel['title'] for c in cl):
            return cl # Already in list
        return cl + [{"title": sel['title'], "pages": sel['pages'], "keywords": keywords, "start_char": start, "end_char": end, "book_slug": sel['book_slug']}]
    except Exception as e:
        logger.error(f"Add to list failed: {e}")
        return cl
# Helper: Update curated radio
def update_curated_radio(cl):
    return gr.update(choices=[f"{c['title']} (Pages: {c['pages']})" for c in cl], value=None)
# Helper: Remove from list
def remove_from_list(cl, selected):
    try:
        if not selected:
            return cl
        for i, c in enumerate(cl):
            if selected.startswith(c['title']):
                del cl[i]
                return cl[:]
        return cl
    except Exception as e:
        logger.error(f"Remove from list failed: {e}")
        return cl
# Helper: Export single
def export_single(selected, start, end, keywords, fmt):
    try:
        if not selected:
            return ""
        stories = [{"title": selected['title'], "pages": selected['pages'], "keywords": keywords, "start_char": start, "end_char": end, "book_slug": selected['book_slug']}]
        export_data = export_stories(stories, fmt, is_single=True)
        if not export_data:
            return "Export failed."
        data_uri = f"data:{export_data['mime']};base64,{export_data['data']}"
        return f'<a href="{data_uri}" download="{export_data["filename"]}">Download Single {fmt}</a>'
    except Exception as e:
        logger.error(f"Single export failed: {e}")
        return "Export failed."
# Helper: Export list
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
# Helper: Conditional export
def conditional_export(cl, fmt, output):
    if fmt: # Only export if a format is selected
        return export_list(cl, fmt)
    return output # Otherwise, keep the current output
# Gradio UI Definition (updated for multi-book: book dropdown, per-book loads)
def gradio_ui():
    try:
        logger.info("Building Gradio UI...")
        css = """
        .scrollable { max-height: 400px; overflow-y: auto; }
        """
        with gr.Blocks(title="Paranormal Text Repository", css=css) as demo:
            # States (add codex_tree_state)
            selected_story = gr.State(None)
            curated_list = gr.State([])
            edited_start = gr.State(0)
            edited_end = gr.State(0)
            edited_keywords = gr.State("")
            results_state = gr.State([])
            pending_updates = gr.State({}) # {book_slug: {title: {'start_char': int, 'end_char': int}}}
            codex_tree_state = gr.State(load_codex_tree())
            # For chained dropdowns (shared for assignment and tree nav)
            cat_path = gr.State([])
            tree_selected_story = gr.State(None)
            view_mode = gr.State("Static")
            with gr.Tabs():
                with gr.TabItem("Search & Curate"):
                    # Top Bar
                    with gr.Row():
                        query = gr.Textbox(label="Search (e.g., demonic possession)", placeholder="Enter query...")
                        source_filter = gr.Dropdown(label="Source", choices=sources, value="All Sources")
                        type_filter = gr.Dropdown(label="Type", choices=["Story", "Non-Story", "Both"], value="Both")
                        search_mode = gr.Dropdown(label="Search Mode", choices=["Keywords (Exact/Phrase Matches)", "Semantic (Conceptual Similarity)", "Both (Hybrid)", "Exact (Word/Phrase)"], value="Both (Hybrid)")
                        min_score_input = gr.Number(label="Min Score Threshold", value=0.1, minimum=0.0, step=0.05)
                        search_btn = gr.Button("Search")
                    # Main Row: Three Columns
                    with gr.Row(variant="panel"):
                        # Left: Search results
                        with gr.Column(scale=1):
                            gr.Markdown("### Search Results")
                            stories_count = gr.Textbox(label="Stories Found", value="0", interactive=False)
                            results_radio = gr.Radio(label="Select Story", choices=[], interactive=True, elem_id="results_radio", elem_classes="scrollable")
                        # Middle: Story Viewer
                        with gr.Column(scale=3):
                            gr.Markdown("### Story Viewer")
                            viewer = gr.HTML(value="Select a story to view...", show_label=False)
                            hidden_page = gr.Textbox(visible=False, show_label=False)
                            start_slider = gr.Slider(label="Start Char", minimum=0, maximum=1000000, step=1, interactive=True, visible=False) # Larger max for multi-book
                            end_slider = gr.Slider(label="End Char", minimum=0, maximum=1000000, step=1, interactive=True, visible=False)
                            start_phrase = gr.Textbox(label="Start After Phrase (e.g., introduction)", placeholder="Phrase to set start after...")
                            end_phrase = gr.Textbox(label="End Before Phrase (e.g., conclusion)", placeholder="Phrase to set end before...")
                            apply_boundaries_btn = gr.Button("Apply Phrase Boundaries")
                            keywords_textbox = gr.Textbox(label="Keywords (comma-separated, editable)", interactive=True)
                            # Category Assignment Dropdowns
                            gr.Markdown("### Assign Category")
                            level1 = gr.Dropdown(label="Level 1", choices=sorted(CATEGORIES.keys()), value=None, allow_custom_value=True)
                            level2 = gr.Dropdown(label="Level 2", choices=[], value=None, allow_custom_value=True)
                            level3 = gr.Dropdown(label="Level 3", choices=[], value=None, allow_custom_value=True)
                            level4 = gr.Dropdown(label="Level 4", choices=[], value=None, allow_custom_value=True)
                            level5 = gr.Dropdown(label="Level 5", choices=[], value=None, allow_custom_value=True)
                            level6 = gr.Dropdown(label="Level 6", choices=[], value=None, allow_custom_value=True)
                            assign_btn = gr.Button("Assign to Category")
                            remove_category_btn = gr.Button("Remove from Category")
                            current_categories = gr.Textbox(label="Current Categories", interactive=False, lines=5)
                            reset_btn = gr.Button("Reset Boundaries")
                            edit_status = gr.Textbox(label="Status", value="", interactive=False)
                            add_btn = gr.Button("Add to List")
                            export_single_btn = gr.Dropdown(label="Export Single", choices=["MD", "PDF", "Word"], interactive=True)
                            export_single_output = gr.HTML(value="", show_label=False)
                            export_json_btn = gr.Button("Export All Updated JSONs")
                            export_json_output = gr.HTML(value="", show_label=False)
                        # Right: Curated List
                        with gr.Column(scale=1):
                            gr.Markdown("### Curated List")
                            curated_radio = gr.Radio(label="Select to Remove", choices=[], interactive=True)
                            remove_btn = gr.Button("Remove from List")
                            export_list_btn = gr.Dropdown(label="Export List", choices=["MD", "PDF", "Word"], interactive=True)
                            export_list_output = gr.HTML(value="", show_label=False)
                    # Event Handlers (updated for book_slug)
                    search_btn.click(update_results, [query, source_filter, type_filter, search_mode, min_score_input], [results_state, results_radio, stories_count])
                    results_radio.change(
                        select_story, [results_state, results_radio], [selected_story, edited_start, edited_end, edited_keywords]
                    ).then(
                        update_viewer, [selected_story, edited_start, edited_end], viewer
                    ).then(
                        lambda selected: selected['pages'].split('-')[0] if selected else '1', [selected_story], hidden_page
                    ).then(
                        lambda kw: gr.update(value=kw), [edited_keywords], [keywords_textbox]
                    ).then(
                        update_current_categories, [selected_story, codex_tree_state], current_categories
                    )
                    start_slider.change(update_viewer, [selected_story, start_slider, end_slider], viewer)
                    end_slider.change(update_viewer, [selected_story, start_slider, end_slider], viewer)
                    hidden_page.change(
                        None, [hidden_page], None,
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
                    apply_boundaries_btn.click(
                        apply_phrase_boundaries, [start_phrase, end_phrase, edited_start, edited_end, selected_story], [edited_start, edited_end, edit_status]
                    ).then(
                        update_viewer, [selected_story, edited_start, edited_end], viewer
                    ).then(
                        lambda start, end: (gr.update(value=start), gr.update(value=end)), [edited_start, edited_end], [start_slider, end_slider]
                    ).then(
                        reset_hidden_page, None, hidden_page
                    ).then(
                        set_hidden_page, [selected_story], hidden_page
                    ).then(
                        update_pending_after_changes, [pending_updates, selected_story, edited_start, edited_end, edited_keywords], pending_updates
                    )
                    reset_btn.click(
                        reset_boundaries, [selected_story], [edited_start, edited_end, edited_keywords, edit_status]
                    ).then(
                        update_viewer, [selected_story, edited_start, edited_end], viewer
                    ).then(
                        lambda start, end: (gr.update(value=start), gr.update(value=end)), [edited_start, edited_end], [start_slider, end_slider]
                    ).then(
                        reset_hidden_page, None, hidden_page
                    ).then(
                        set_hidden_page, [selected_story], hidden_page
                    ).then(
                        update_pending_after_changes, [pending_updates, selected_story, edited_start, edited_end, edited_keywords], pending_updates
                    ).then(
                        lambda kw: gr.update(value=kw), [edited_keywords], [keywords_textbox]
                    )
                    # Add similar .then(update_pending_after_edit) to slider changes if needed
                    start_slider.change(
                        update_viewer, [selected_story, start_slider, end_slider], viewer
                    ).then(
                        update_pending_after_changes, [pending_updates, selected_story, start_slider, end_slider, edited_keywords], pending_updates
                    )
                    end_slider.change(
                        update_viewer, [selected_story, start_slider, end_slider], viewer
                    ).then(
                        update_pending_after_changes, [pending_updates, selected_story, start_slider, end_slider, edited_keywords], pending_updates
                    )
                    keywords_textbox.change(
                        lambda val: val, [keywords_textbox], [edited_keywords]
                    ).then(
                        update_pending_after_changes, [pending_updates, selected_story, edited_start, edited_end, edited_keywords], pending_updates
                    )
                    add_btn.click(add_to_list, [curated_list, selected_story, edited_start, edited_end, edited_keywords], curated_list)
                    curated_list.change(update_curated_radio, curated_list, curated_radio)
                    remove_btn.click(remove_from_list, [curated_list, curated_radio], curated_list)
                    export_single_btn.change(export_single, [selected_story, edited_start, edited_end, edited_keywords, export_single_btn], export_single_output)
                    export_list_btn.change(export_list, [curated_list, export_list_btn], export_list_output)
                    curated_list.change(conditional_export, [curated_list, export_list_btn, export_list_output], export_list_output)
                    export_json_btn.click(export_updated_jsons, pending_updates, export_json_output)
                    # Chained dropdown updates and assign, with resets for lower levels
                    level1.change(update_level2, [level1, level2], level2).then(lambda: gr.update(value=None), None, level3).then(lambda: gr.update(value=None), None, level4).then(lambda: gr.update(value=None), None, level5).then(lambda: gr.update(value=None), None, level6)
                    level2.change(update_level3, [level1, level2, level3], level3).then(lambda: gr.update(value=None), None, level4).then(lambda: gr.update(value=None), None, level5).then(lambda: gr.update(value=None), None, level6)
                    level3.change(update_level4, [level1, level2, level3, level4], level4).then(lambda: gr.update(value=None), None, level5).then(lambda: gr.update(value=None), None, level6)
                    level4.change(update_level5, [level1, level2, level3, level4, level5], level5).then(lambda: gr.update(value=None), None, level6)
                    level5.change(update_level6, [level1, level2, level3, level4, level5, level6], level6)
                    # Remove assignment from level6.change; now on button
                    # level6.change(assign_category, [level1, level2, level3, level4, level5, level6, codex_tree_state, selected_story, edited_start, edited_end, edited_keywords], codex_tree_state)
                    assign_btn.click(assign_category, [level1, level2, level3, level4, level5, level6, codex_tree_state, selected_story, edited_start, edited_end, edited_keywords], codex_tree_state).then(update_current_categories, [selected_story, codex_tree_state], current_categories)
                    remove_category_btn.click(remove_category, [level1, level2, level3, level4, level5, level6, codex_tree_state, selected_story], codex_tree_state).then(update_current_categories, [selected_story, codex_tree_state], current_categories)
                with gr.TabItem("Codex Tree"):
                    with gr.Row():
                        with gr.Column(scale=1):
                            gr.Markdown("### Browse Hierarchy")
                            # Reuse chained dropdowns for tree nav
                            tree_level1 = gr.Dropdown(label="Level 1", choices=sorted(CATEGORIES.keys()), value=None, allow_custom_value=True)
                            tree_level2 = gr.Dropdown(label="Level 2", choices=[], value=None, allow_custom_value=True)
                            tree_level3 = gr.Dropdown(label="Level 3", choices=[], value=None, allow_custom_value=True)
                            tree_level4 = gr.Dropdown(label="Level 4", choices=[], value=None, allow_custom_value=True)
                            tree_level5 = gr.Dropdown(label="Level 5", choices=[], value=None, allow_custom_value=True)
                            tree_level6 = gr.Dropdown(label="Level 6", choices=[], value=None, allow_custom_value=True)
                            tree_stories_radio = gr.Radio(label="Stories", choices=[], interactive=True)
                            # Chained updates same as above
                            tree_level1.change(update_level2, [tree_level1, tree_level2], tree_level2).then(lambda: gr.update(value=None), None, tree_level3).then(lambda: gr.update(value=None), None, tree_level4).then(lambda: gr.update(value=None), None, tree_level5).then(lambda: gr.update(value=None), None, tree_level6).then(update_tree_stories, [tree_level1, tree_level2, tree_level3, tree_level4, tree_level5, tree_level6, codex_tree_state], tree_stories_radio)
                            tree_level2.change(update_level3, [tree_level1, tree_level2, tree_level3], tree_level3).then(lambda: gr.update(value=None), None, tree_level4).then(lambda: gr.update(value=None), None, tree_level5).then(lambda: gr.update(value=None), None, tree_level6).then(update_tree_stories, [tree_level1, tree_level2, tree_level3, tree_level4, tree_level5, tree_level6, codex_tree_state], tree_stories_radio)
                            tree_level3.change(update_level4, [tree_level1, tree_level2, tree_level3, tree_level4], tree_level4).then(lambda: gr.update(value=None), None, tree_level5).then(lambda: gr.update(value=None), None, tree_level6).then(update_tree_stories, [tree_level1, tree_level2, tree_level3, tree_level4, tree_level5, tree_level6, codex_tree_state], tree_stories_radio)
                            tree_level4.change(update_level5, [tree_level1, tree_level2, tree_level3, tree_level4, tree_level5], tree_level5).then(lambda: gr.update(value=None), None, tree_level6).then(update_tree_stories, [tree_level1, tree_level2, tree_level3, tree_level4, tree_level5, tree_level6, codex_tree_state], tree_stories_radio)
                            tree_level5.change(update_level6, [tree_level1, tree_level2, tree_level3, tree_level4, tree_level5, tree_level6], tree_level6).then(update_tree_stories, [tree_level1, tree_level2, tree_level3, tree_level4, tree_level5, tree_level6, codex_tree_state], tree_stories_radio)
                            tree_level6.change(update_tree_stories, [tree_level1, tree_level2, tree_level3, tree_level4, tree_level5, tree_level6, codex_tree_state], tree_stories_radio)
                            save_tree_btn = gr.Button("Save Codex Tree")
                            save_status = gr.Textbox(label="Save Status", value="", interactive=False)
                            save_tree_btn.click(save_and_status, codex_tree_state, save_status)
                        with gr.Column(scale=3):
                            gr.Markdown("### Story Viewer")
                            tree_viewer = gr.Markdown(value="Select a path and story...")
                            view_in_text_btn = gr.Button("View in Text")
                    # Tree events
                    tree_stories_radio.change(select_tree_story, [tree_stories_radio, tree_level1, tree_level2, tree_level3, tree_level4, tree_level5, tree_level6, codex_tree_state], [tree_viewer, view_mode])
                    view_in_text_btn.click(toggle_view_mode, [tree_stories_radio, view_mode, tree_level1, tree_level2, tree_level3, tree_level4, tree_level5, tree_level6, codex_tree_state], [tree_viewer, view_mode])
            return demo
    except Exception as e:
        logger.error(f"Failed to build Gradio UI: {e}")
        raise
# Launch (no server_name/port for HF defaults)
if __name__ == "__main__":
    demo = gradio_ui()
    demo.launch()