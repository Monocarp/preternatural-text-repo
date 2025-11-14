# backend/utils.py
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
import base64
import zipfile
import io
from huggingface_hub import HfApi
from haystack import Pipeline, Document
from haystack.components.embedders import SentenceTransformersTextEmbedder
from haystack.components.retrievers.in_memory import InMemoryEmbeddingRetriever, InMemoryBM25Retriever
from haystack.components.joiners import DocumentJoiner
from haystack.document_stores.in_memory import InMemoryDocumentStore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Story, CodexNode, NodeStory
from dotenv import load_dotenv
# Load .env.local from project root (since we're in backend subdir)
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env.local'))
logger = logging.getLogger(__name__)
# Paths (relative to root from backend)
books_dir = "../books/"
data_dir = "../data/"
document_store_path = os.path.join(data_dir, "document_store.json")
codex_tree_path = os.path.join(data_dir, "codex_tree.json")
stories_dict_path = os.path.join(data_dir, "stories_dict.json")
# DB Connection
DB_URL = os.getenv("POSTGRES_PRISMA_URL") # Pooled for serverless
if DB_URL and "postgres" in DB_URL:
    DB_URL = DB_URL.replace("postgres://", "postgresql://")
engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
# Create tables if not exist
Base.metadata.create_all(bind=engine)
# Global flat story storage (in-memory cache; load from DB)
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
# Discover books dynamically
books = [d for d in os.listdir(books_dir) if os.path.isdir(os.path.join(books_dir, d)) and not d.startswith('.')]
sources = ["All Sources"] + sorted(books)
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
            logger.error("No 'story' type documents found; searches may fail.")
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
            import os
            MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "bge-large-en-v1.5")
            MODEL_PATH = MODEL_DIR if os.path.exists(MODEL_DIR) else "BAAI/bge-large-en-v1.5"
            embedder = SentenceTransformersDocumentEmbedder(model=MODEL_PATH, normalize_embeddings=True)
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
    logger.error("document_store.json not found.")
    raise FileNotFoundError("document_store.json missing")
# Set up Haystack pipelines
logger.debug("Setting up Haystack pipelines...")
import os
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models", "bge-large-en-v1.5")
MODEL_PATH = MODEL_DIR if os.path.exists(MODEL_DIR) else "BAAI/bge-large-en-v1.5"
embedder_both = SentenceTransformersTextEmbedder(model=MODEL_PATH, normalize_embeddings=True)
retriever_embedding_both = InMemoryEmbeddingRetriever(document_store=document_store)
retriever_bm25_both = InMemoryBM25Retriever(document_store=document_store)
joiner = DocumentJoiner(
    join_mode="reciprocal_rank_fusion",
    weights=[0.5, 0.5]
)
both_pipeline = Pipeline()
both_pipeline.add_component("embedder", embedder_both)
both_pipeline.add_component("retriever_embedding", retriever_embedding_both)
both_pipeline.add_component("retriever_bm25", retriever_bm25_both)
both_pipeline.add_component("joiner", joiner)
both_pipeline.connect("embedder.embedding", "retriever_embedding.query_embedding")
both_pipeline.connect("retriever_embedding", "joiner")
both_pipeline.connect("retriever_bm25", "joiner")
logger.info(f"Both pipeline components: {list(both_pipeline.graph.nodes.keys())}")
retriever_bm25_key = InMemoryBM25Retriever(document_store=document_store)
keyword_pipeline = Pipeline()
keyword_pipeline.add_component("retriever_bm25", retriever_bm25_key)
logger.info(f"Keyword pipeline components: {list(keyword_pipeline.graph.nodes.keys())}")
embedder_sem = SentenceTransformersTextEmbedder(model=MODEL_PATH, normalize_embeddings=True)
retriever_embedding_sem = InMemoryEmbeddingRetriever(document_store=document_store)
semantic_pipeline = Pipeline()
semantic_pipeline.add_component("embedder", embedder_sem)
semantic_pipeline.add_component("retriever_embedding", retriever_embedding_sem)
semantic_pipeline.connect("embedder.embedding", "retriever_embedding.query_embedding")
logger.info(f"Semantic pipeline components: {list(semantic_pipeline.graph.nodes.keys())}")
# Ported helpers (all below from app.py)
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
                    "score": doc.score
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
def find_book_slug(title):
    for book_slug in books:
        positions = load_story_positions(book_slug)
        if title in positions:
            return book_slug
    raise ValueError(f"Book not found for title: {title}")
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
def export_updated_jsons(pending_updates):
    try:
        if not pending_updates:
            return ""
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for book_slug, updates in pending_updates.items():
                original_positions = load_story_positions(book_slug).copy()
                for title, bounds in updates.items():
                    if title in original_positions:
                        for key, val in bounds.items():
                            original_positions[title][key] = val
                    else:
                        logger.warning(f"Title {title} not found in {book_slug}; skipping update.")
                json_data = json.dumps(original_positions, indent=4, ensure_ascii=False).encode('utf-8')
                zip_file.writestr(f"updated_story_positions_{book_slug}.json", json_data)
        zip_buffer.seek(0)
        data = base64.b64encode(zip_buffer.read()).decode('utf-8')
        data_uri = f"data:application/zip;base64,{data}"
        return f'<a href="{data_uri}" download="updated_story_positions.zip">Download Updated JSONs ZIP</a>'
    except Exception as e:
        logger.error(f"JSON export failed: {e}")
        return "Export failed."
# CATEGORIES dict (ported from HF app.py)
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
def load_codex_tree_from_json():
    if os.path.exists(codex_tree_path):
        with open(codex_tree_path, "r") as f:
            tree = json.load(f)
    else:
        tree = CATEGORIES.copy()
        def ensure_lists(d):
            for k, v in d.items():
                if isinstance(v, dict):
                    ensure_lists(v)
                else:
                    d[k] = []
        ensure_lists(tree)
        save_codex_tree_to_json(tree)
    return tree

def save_codex_tree_to_json(tree):
    with open(codex_tree_path, "w") as f:
        json.dump(tree, f, indent=4)
# Load codex_tree (from DB, fallback to JSON if empty)
def load_codex_tree():
    global stories_dict
    with SessionLocal() as db:
        stories = db.query(Story).all()
        stories_dict = {s.title: {
            "title": s.title, "book_slug": s.book_slug, "pages": s.pages,
            "keywords": s.keywords, "start_char": s.start_char, "end_char": s.end_char
        } for s in stories}
        if not stories:
            print("No stories in DB - loading from story_positions.json")
            stories_dict = load_all_stories()
            # Insert if not exist
            for title, s in stories_dict.items():
                if not db.query(Story).filter_by(title=title).first():
                    db.add(Story(**s))
            db.commit()
        
        root_nodes = db.query(CodexNode).filter_by(parent_id=None).all()
        if not root_nodes:
            print("No codex nodes in DB - initializing from CATEGORIES")
            tree_json = load_codex_tree_from_json()
            # Insert from JSON
            insert_recursive(tree_json)
            db.commit()
            root_nodes = db.query(CodexNode).filter_by(parent_id=None).all()
        
        def build_tree(node):
            tree = {node.name: {}}
            for child in node.children:
                tree[node.name].update(build_tree(child))
            return tree
        
        tree = {}
        for root in root_nodes:
            tree.update(build_tree(root))
        return tree

# Other functions remain the same


def save_codex_tree_to_json(tree):
    with open(codex_tree_path, "w") as f:
        json.dump(tree, f, indent=4)