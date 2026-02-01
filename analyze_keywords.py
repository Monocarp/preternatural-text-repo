#!/usr/bin/env python
"""Analyze keyword utility and redundancy"""
import json
import os

# Check a sample book's keywords
book_path = "books/operation_trojan_horse/story_positions.json"

with open(book_path, encoding='utf-8') as f:
    positions = json.load(f)

print("=== Keyword Analysis ===\n")
print(f"Total stories: {len(positions)}\n")

# Analyze keyword patterns
title_matches = 0
title_subset = 0
adds_value = 0
multiple_keywords = 0

examples = {
    "title_match": [],
    "adds_value": [],
    "multiple": []
}

for title, data in list(positions.items())[:20]:  # Sample first 20
    keywords = data.get("keywords", [])
    
    if not keywords:
        continue
    
    # Normalize for comparison
    title_norm = title.lower().replace(",", "").replace(".", "")
    
    if len(keywords) > 1:
        multiple_keywords += 1
        if len(examples["multiple"]) < 3:
            examples["multiple"].append((title, keywords))
    
    # Check if keywords are just the title
    if len(keywords) == 1:
        kw_norm = keywords[0].replace(",", "").replace(".", "")
        if kw_norm == title_norm:
            title_matches += 1
            if len(examples["title_match"]) < 3:
                examples["title_match"].append((title, keywords))
        elif kw_norm in title_norm or title_norm in kw_norm:
            title_subset += 1
        else:
            adds_value += 1
            if len(examples["adds_value"]) < 3:
                examples["adds_value"].append((title, keywords))
    else:
        # Multiple keywords might add value
        adds_value += 1
        if len(examples["adds_value"]) < 3:
            examples["adds_value"].append((title, keywords))

print(f"Stories where keywords = title (lowercase): {title_matches}")
print(f"Stories where keywords are subset of title: {title_subset}")
print(f"Stories where keywords might add value: {adds_value}")
print(f"Stories with multiple keywords: {multiple_keywords}")

print("\n=== Examples ===\n")

print("1. Keywords that are just title (lowercased):")
for title, kws in examples["title_match"]:
    print(f"   Title: {title}")
    print(f"   Keywords: {kws}\n")

if examples["adds_value"]:
    print("2. Keywords that might add value:")
    for title, kws in examples["adds_value"]:
        print(f"   Title: {title}")
        print(f"   Keywords: {kws}\n")

if examples["multiple"]:
    print("3. Stories with multiple keywords:")
    for title, kws in examples["multiple"]:
        print(f"   Title: {title}")
        print(f"   Keywords: {kws}\n")

# Check all books
print("\n=== Checking All Books ===\n")
books_dir = "books"
for book_slug in os.listdir(books_dir):
    book_path = os.path.join(books_dir, book_slug, "story_positions.json")
    if not os.path.exists(book_path):
        continue
    
    with open(book_path, encoding='utf-8') as f:
        positions = json.load(f)
    
    total = len(positions)
    title_only = sum(1 for v in positions.values() 
                     if len(v.get("keywords", [])) == 1 and 
                     v["keywords"][0].replace(",", "").replace(".", "") == 
                     v.get("title", "").lower().replace(",", "").replace(".", ""))
    
    multi = sum(1 for v in positions.values() if len(v.get("keywords", [])) > 1)
    
    print(f"{book_slug}:")
    print(f"  Total: {total}")
    print(f"  Keywords = title: {title_only} ({100*title_only//total if total else 0}%)")
    print(f"  Multiple keywords: {multi} ({100*multi//total if total else 0}%)")
