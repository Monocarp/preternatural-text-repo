import json

# Just check if embeddings exist
with open('11.24.25/document_store.json', 'r') as f:
    store = json.load(f)

docs = store.get('documents', [])
print(f"Backup has {len(docs)} documents")

# Check first doc
if docs:
    has_emb = 'embedding' in docs[0] and docs[0]['embedding'] is not None
    print(f"First doc has embedding: {has_emb}")
    if has_emb:
        print(f"Embedding length: {len(docs[0]['embedding'])}")
    print(f"First doc book: {docs[0].get('meta', {}).get('book')}")
    print(f"First doc type: {docs[0].get('meta', {}).get('type')}")
