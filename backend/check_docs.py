from haystack.document_stores.in_memory import InMemoryDocumentStore
from collections import Counter

ds = InMemoryDocumentStore.load_from_disk('../data/document_store.json')
print(f'Total documents: {ds.count_documents()}')

docs = ds.filter_documents({})
types = Counter(d.meta.get('type') for d in docs)
print(f'By type: {dict(types)}')

print('\nSample docs:')
for doc in list(docs)[:5]:
    doc_type = doc.meta.get('type')
    title = doc.meta.get('title', doc.meta.get('chunk_id', 'Unknown'))
    print(f'  {doc.id[:16]}... | {doc_type} | {title}')
