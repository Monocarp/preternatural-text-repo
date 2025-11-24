from haystack.document_stores.in_memory import InMemoryDocumentStore

ds = InMemoryDocumentStore.load_from_disk('../data/document_store.json')
docs = list(ds.filter_documents({}))

print(f'Total documents: {len(docs)}')

# Find the recently added story
fake_docs = [d for d in docs if 'FAKE' in d.meta.get('title', '').upper()]
print(f'\nFAKE story documents: {len(fake_docs)}')
for doc in fake_docs:
    print(f"  - {doc.meta.get('title')}")
    print(f"    type: {doc.meta.get('type')}")
    print(f"    book: {doc.meta.get('book')}")

# Check if it's marked as indexed in the database
print(f"\nChecking database...")
import sys
sys.path.insert(0, '../backend')
from utils import USE_DB, SessionLocal

if USE_DB and SessionLocal:
    with SessionLocal() as db:
        from models import Story
        fake_stories = db.query(Story).filter(Story.title.ilike('%FAKE%')).all()
        print(f"Found {len(fake_stories)} FAKE stories in database:")
        for story in fake_stories:
            print(f"  - {story.title}: indexed={story.indexed}")
