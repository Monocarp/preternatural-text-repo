# Example: How to integrate preprocessing with your existing pipeline

import os
from preprocessing_pipeline import process_book_chunks

def preprocess_book_for_extraction(book_slug: str, markdown_files: List[str]) -> str:
    """
    Preprocess a book's markdown files using the chunk-based approach
    before feeding to your existing story extraction
    """
    # Configuration
    CHUNK_SIZE_PAGES = 12  # Sweet spot for accuracy vs efficiency
    
    all_chunks = []
    
    # Read and chunk the markdown files
    for md_file in sorted(markdown_files):
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Split into ~12 page chunks (assuming ~3000 chars per page)
        chunk_size = CHUNK_SIZE_PAGES * 3000
        
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            
            # Extend to next sentence boundary to avoid cuts
            if i + chunk_size < len(content):
                # Find next sentence end
                next_period = content.find('. ', i + chunk_size)
                next_exclaim = content.find('! ', i + chunk_size)
                next_question = content.find('? ', i + chunk_size)
                
                ends = [e for e in [next_period, next_exclaim, next_question] if e > 0]
                if ends:
                    chunk_end = min(ends) + 1
                    chunk = content[i:chunk_end]
            
            all_chunks.append(chunk)
    
    # Process chunks through the pipeline
    book_title = book_slug.replace('_', ' ').title()
    extracted_stories = process_book_chunks(
        chunks=all_chunks,
        book_title=book_title,
        model="claude-3-5-haiku-20241022"  # Use cheaper model
    )
    
    return extracted_stories

# How this connects to your existing flow:
# 1. Original flow: Raw MD → Direct extraction → Stories.md
# 2. New flow: Raw MD → Chunk → Preprocess → Extract → Merge → Stories.md

# The output from preprocessing can then feed into your existing
# story_positions.json generation and document store creation
