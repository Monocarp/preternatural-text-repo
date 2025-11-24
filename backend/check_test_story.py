import json

# Check story_positions.json
with open('../books/christian_mysticism_vol_iv/story_positions.json', 'r', encoding='utf-8') as f:
    positions = json.load(f)
    
test_stories = [title for title in positions.keys() if 'TEST' in title.upper() or 'Occurrence of Possession' in title]
print(f'Found {len(test_stories)} test stories in story_positions.json:')
for title in test_stories:
    print(f'  - {title}')
    print(f'    start_char: {positions[title].get("start_char")}')
    print(f'    end_char: {positions[title].get("end_char")}')

# Check if it's in the document store
print('\nChecking document_store.json...')
from haystack.document_stores.in_memory import InMemoryDocumentStore
ds = InMemoryDocumentStore.load_from_disk('../data/document_store.json')
docs = ds.filter_documents({})

test_docs = [doc for doc in docs if 'TEST' in doc.meta.get('title', '').upper() or 'Occurrence of Possession' in doc.meta.get('title', '')]
print(f'Found {len(test_docs)} test documents in document_store.json:')
for doc in test_docs:
    print(f'  - {doc.meta.get("title")} (type: {doc.meta.get("type")})')
