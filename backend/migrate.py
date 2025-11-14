# backend/migrate.py
import json
import os
from utils import SessionLocal, Story, CodexNode, NodeStory, books_dir, CATEGORIES, load_story_positions
from models import Base


data_dir = "../data/"
codex_tree_path = os.path.join(data_dir, "codex_tree.json")

# Load stories from story_positions.json in each book folder (since no stories_dict.json)
def load_all_stories():
    stories_dict = {}
    for book_slug in os.listdir(books_dir):
        if os.path.isdir(os.path.join(books_dir, book_slug)) and not book_slug.startswith('.'):
            positions = load_story_positions(book_slug)
            for title, details in positions.items():
                stories_dict[title] = {
                    "title": title,
                    "book_slug": book_slug,
                    "pages": details.get("pages", ""),
                    "keywords": ', '.join(details.get("keywords", [])),
                    "start_char": details.get("start_char", 0),
                    "end_char": details.get("end_char", 0)
                }
    print(f"Loaded {len(stories_dict)} stories from story_positions.json across books")
    return stories_dict

# Load tree from codex_tree.json if exists, else initialize from CATEGORIES
def old_load_codex_tree():
    tree = {}
    if os.path.exists(codex_tree_path):
        with open(codex_tree_path, "r") as f:
            tree = json.load(f)
        print(f"Loaded tree with {len(tree)} top-level categories from codex_tree.json")
    else:
        tree = CATEGORIES.copy()
        def ensure_lists(d):
            for k, v in d.items():
                if isinstance(v, dict):
                    ensure_lists(v)
                else:
                    d[k] = []
        ensure_lists(tree)
        print("codex_tree.json not found — initialized from CATEGORIES")
    return tree

stories_dict = load_all_stories()
tree = old_load_codex_tree()

with SessionLocal() as db:
    # Insert stories
    inserted = 0
    for title, s in stories_dict.items():
        if not db.query(Story).filter_by(title=title).first():
            db.add(Story(**s))
            inserted += 1
    db.commit()
    print(f"Inserted {inserted} stories")
    
    # Insert nodes and assignments (recurse tree)
    def insert_recursive(current, parent_id=None):
        for name, value in current.items():
            node = CodexNode(name=name, parent_id=parent_id)
            db.add(node)
            db.flush()  # Get ID
            print(f"Inserted node: {name} (parent: {parent_id})")
            if isinstance(value, list):
                for title in value:
                    story = db.query(Story).filter_by(title=title).first()
                    if story:
                        db.add(NodeStory(node_id=node.id, story_id=story.id))
                        print(f"Associated story {title} to node {name}")
            elif isinstance(value, dict):
                insert_recursive(value, node.id)
    
    insert_recursive(tree)
    db.commit()

print("Migration complete!")