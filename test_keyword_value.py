#!/usr/bin/env python
"""Test whether keywords actually help search beyond what's already in title/content"""
import json

# Load a sample from each book type
books = {
    "christian_mysticism": "books/christian_mysticism_vol_iv/story_positions.json",
    "ecology": "books/ecology_of_souls_volume_i/story_positions.json",
    "trojan": "books/operation_trojan_horse/story_positions.json"
}

print("=== Do Keywords Add Information Beyond Title/Content? ===\n")

for book_name, path in books.items():
    with open(path, encoding='utf-8') as f:
        positions = json.load(f)
    
    # Get first story as example
    first_story = list(positions.items())[0]
    title, data = first_story
    keywords = data.get("keywords", [])
    
    # Check what's in the story content (verbatim text)
    content = data.get("verbatim", "")[:500]  # First 500 chars
    
    print(f"\n{'='*80}")
    print(f"Book: {book_name}")
    print(f"{'='*80}")
    print(f"\nTitle:\n  {title}")
    print(f"\nKeywords:\n  {keywords}")
    print(f"\nFirst 500 chars of content:\n  {content}...")
    
    # Analysis: Do keywords add NEW searchable terms?
    title_lower = title.lower()
    content_lower = content.lower()
    
    new_terms = []
    redundant_terms = []
    
    for kw in keywords:
        kw_lower = kw.lower()
        # Check if keyword adds something not in title or content
        if kw_lower not in title_lower and kw_lower not in content_lower:
            new_terms.append(kw)
        else:
            redundant_terms.append(kw)
    
    print(f"\n📊 Analysis:")
    print(f"  ✅ Keywords adding NEW searchable terms: {len(new_terms)}")
    if new_terms:
        print(f"     Examples: {new_terms[:5]}")
    print(f"  ❌ Keywords already in title/content: {len(redundant_terms)}")
    if redundant_terms:
        print(f"     Examples: {redundant_terms[:3]}")

print("\n" + "="*80)
print("\n🔍 KEY INSIGHT:")
print("Keywords are valuable ONLY IF they add searchable terms not in title/content.")
print("This happens when:")
print("  1. Manual curation extracts key concepts (entities, topics)")
print("  2. Keywords normalize/standardize terms (e.g., 'St.' → 'Saint')")
print("  3. Keywords add metadata (dates, locations) not in the excerpt")
print("\nKeywords are REDUNDANT when:")
print("  1. They're just the title lowercased")
print("  2. They duplicate terms already in the story text")
print("="*80)
