# Enhanced Preprocessing Pipeline for Supernatural Story Extraction
# pip install tiktoken spacy anthropic

import spacy
import re
from typing import List, Dict, Tuple
import json

# Load the most accurate spaCy model for historical text
nlp = spacy.load("en_core_web_trf")

def prepare_chunk_for_extraction(
    markdown_chunk: str, 
    book_title: str, 
    start_page: int,
    chunk_index: int = 0
) -> str:
    """
    Takes your pre-cleaned 10-15 page MD chunk and returns text ready for the LLM
    
    Enhancements:
    1. Better page detection with multiple patterns
    2. Preserves story boundaries across chunks
    3. Adds chunk context for cross-chunk story detection
    """
    # Convert MD to plain text but keep paragraph breaks
    text = re.sub(r'^#+\s+.*$', '', markdown_chunk, flags=re.MULTILINE)  # remove headings
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)   # strip bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)       # strip italic
    text = re.sub(r'`(.*?)`', r'\1', text)         # strip inline code
    
    # Process with spaCy
    doc = nlp(text)
    
    sentences = []
    current_page = start_page
    sentence_idx = 0
    
    # Enhanced page detection patterns
    page_patterns = [
        r'\[?\s*Page\s+(\d+)\s*\]?',           # [Page 123] or Page 123
        r'\[?\s*p\.\s*(\d+)\s*\]?',            # [p. 123] or p. 123
        r'^(\d+)\s*$',                          # Just page number on its own line
        r'--\s*(\d+)\s*--',                     # -- 123 --
    ]
    
    for sent in doc.sents:
        sent_text = sent.text.strip()
        if not sent_text: 
            continue
        
        # Check all page patterns
        page_found = False
        for pattern in page_patterns:
            page_match = re.search(pattern, sent_text, re.I | re.M)
            if page_match:
                new_page = int(page_match.group(1))
                # Sanity check - pages should increment
                if new_page >= current_page and new_page <= current_page + 20:
                    current_page = new_page
                    page_found = True
                    break
        
        # Skip pure page marker sentences
        if page_found and len(sent_text) < 20:
            continue
        
        # Inject markers
        marked_sent = f"[S{sentence_idx}][PAGE:{current_page}][CHUNK:{chunk_index}] {sent_text}"
        sentences.append(marked_sent)
        sentence_idx += 1
    
    marked_text = "\n".join(sentences)
    
    # Enhanced prompt with better structure
    return f"""BOOK TITLE: {book_title}
CHUNK: {chunk_index + 1}

EXTRACT EVERY supernatural, paranormal, miraculous, demonic, witchcraft, possession, apparition, poltergeist, or otherwise preternatural incident mentioned in the text below.

CRITICAL EXTRACTION RULES:

1. COMPLETENESS
   - Extract EVERY incident, including one-sentence mentions
   - Even passing references like "X was bewitched" must be extracted
   - If unsure whether something is supernatural, INCLUDE IT

2. BOUNDARY RULES
   - Each extraction MUST start and end on sentence boundaries
   - Use the [S{n}] markers to ensure clean boundaries
   - NEVER cut mid-sentence

3. PRONOUN RESOLUTION
   - If a pronoun (he, she, it, they, this) lacks its antecedent, expand backward
   - Include previous sentences until all pronouns are clear
   - Example: "He saw the demon" → expand to include who "he" is

4. OUTPUT FORMAT (EXACTLY AS SHOWN)

<div align="center"><b>[Descriptive title, max 8 words]</b></div>
<div align="center">"{book_title}" Pages X-Y</div>

[Full verbatim text, respecting sentence boundaries]

5. SPECIAL CASES
   - Stories continuing from previous chunks: Mark with "CONTINUES FROM PREVIOUS"
   - Stories continuing to next chunk: Mark with "CONTINUES TO NEXT"
   - Merge variants with " --- " between them
   - Use embedded [PAGE:X] markers for accurate page ranges

6. CONTEXT AWARENESS
   - This is chunk {chunk_index + 1} of a larger work
   - Some stories may span chunks - extract what you can see
   - Include [CHUNK:{chunk_index}] marker in your extraction for tracking

Text to extract from:
{marked_text}
"""

def post_process_extractions(
    all_chunk_outputs: List[str], 
    book_title: str
) -> str:
    """
    Merge extractions from all chunks, handling cross-chunk stories
    
    Features:
    1. Detects and merges stories that span chunks
    2. Removes duplicate extractions
    3. Cleans up markers from final output
    """
    # Collect all stories with their metadata
    stories = []
    
    for chunk_idx, chunk_output in enumerate(all_chunk_outputs):
        # Parse stories from chunk output
        story_blocks = chunk_output.split('\n\n')
        
        current_story = None
        for block in story_blocks:
            # Check if this is a story header
            if '<div align="center"><b>' in block:
                if current_story:
                    stories.append(current_story)
                current_story = {
                    'title': '',
                    'pages': '',
                    'text': '',
                    'chunk': chunk_idx,
                    'continues_from': False,
                    'continues_to': False
                }
                # Extract title
                title_match = re.search(r'<b>(.*?)</b>', block)
                if title_match:
                    current_story['title'] = title_match.group(1)
                # Extract pages
                pages_match = re.search(r'Pages?\s*([\d\-,\s]+)', block)
                if pages_match:
                    current_story['pages'] = pages_match.group(1)
            elif current_story:
                # This is story content
                if 'CONTINUES FROM PREVIOUS' in block:
                    current_story['continues_from'] = True
                    block = block.replace('CONTINUES FROM PREVIOUS', '').strip()
                if 'CONTINUES TO NEXT' in block:
                    current_story['continues_to'] = True
                    block = block.replace('CONTINUES TO NEXT', '').strip()
                current_story['text'] += block + '\n'
        
        if current_story:
            stories.append(current_story)
    
    # Merge stories that span chunks
    merged_stories = []
    i = 0
    while i < len(stories):
        story = stories[i]
        
        # Look for continuation in next chunk
        if story['continues_to'] and i + 1 < len(stories):
            next_story = stories[i + 1]
            if next_story['continues_from']:
                # Merge them
                merged_story = {
                    'title': story['title'],  # Use first title
                    'pages': merge_page_ranges(story['pages'], next_story['pages']),
                    'text': story['text'].strip() + ' --- ' + next_story['text'].strip(),
                    'chunk': story['chunk'],
                    'continues_from': story['continues_from'],
                    'continues_to': next_story['continues_to']
                }
                merged_stories.append(merged_story)
                i += 2  # Skip next story since we merged it
                continue
        
        merged_stories.append(story)
        i += 1
    
    # Remove duplicate stories (same title + similar content)
    unique_stories = []
    seen_titles = {}
    
    for story in merged_stories:
        title_key = story['title'].lower().strip()
        
        if title_key in seen_titles:
            # Check if it's a true duplicate or a variant
            existing = seen_titles[title_key]
            similarity = calculate_similarity(existing['text'], story['text'])
            
            if similarity > 0.9:  # Very similar, skip
                continue
            elif similarity > 0.7:  # Similar but different, merge
                existing['text'] += ' --- ' + story['text']
                existing['pages'] = merge_page_ranges(existing['pages'], story['pages'])
            else:  # Different story with same title
                unique_stories.append(story)
        else:
            seen_titles[title_key] = story
            unique_stories.append(story)
    
    # Format final output
    final_output = []
    for story in unique_stories:
        # Clean markers from text
        clean_text = re.sub(r'\[S\d+\]\[PAGE:\d+\]\[CHUNK:\d+\]\s*', '', story['text'])
        
        story_output = f"""<div align="center"><b>{story['title']}</b></div>
<div align="center">"{book_title}" Pages {story['pages']}</div>

{clean_text.strip()}"""
        final_output.append(story_output)
    
    return '\n\n'.join(final_output)

def merge_page_ranges(pages1: str, pages2: str) -> str:
    """Merge two page range strings intelligently"""
    # Extract all page numbers
    all_pages = []
    for pages in [pages1, pages2]:
        # Find all numbers
        nums = re.findall(r'\d+', pages)
        all_pages.extend([int(n) for n in nums])
    
    if not all_pages:
        return pages1 or pages2
    
    # Get min and max
    min_page = min(all_pages)
    max_page = max(all_pages)
    
    if min_page == max_page:
        return str(min_page)
    else:
        return f"{min_page}-{max_page}"

def calculate_similarity(text1: str, text2: str) -> float:
    """Simple text similarity calculation"""
    # Normalize texts
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 or not words2:
        return 0.0
    
    # Jaccard similarity
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    
    return len(intersection) / len(union) if union else 0.0

# Enhanced validation function
def validate_extraction_output(extraction: str, original_text: str) -> Dict[str, any]:
    """
    Validate that extraction follows all rules
    
    Returns dict with:
    - is_valid: bool
    - errors: List of error messages
    - warnings: List of warning messages
    """
    errors = []
    warnings = []
    
    # Check for mid-sentence cuts
    sentences = [s.strip() for s in re.split(r'[.!?]\s+', extraction) if s.strip()]
    for sent in sentences:
        if sent and not re.search(r'[.!?]$', sent):
            warnings.append(f"Possible mid-sentence cut: '{sent[:50]}...'")
    
    # Check for unresolved pronouns at story start
    first_sentence = sentences[0] if sentences else ""
    pronoun_pattern = r'^(He|She|It|They|This|That|These|Those)\s'
    if re.match(pronoun_pattern, first_sentence):
        errors.append(f"Story starts with unresolved pronoun: '{first_sentence[:50]}...'")
    
    # Check format compliance
    if '<div align="center"><b>' not in extraction:
        errors.append("Missing required title format")
    
    if 'Pages' not in extraction:
        warnings.append("Missing page reference")
    
    # Check if we have actual content
    content_lines = [l for l in extraction.split('\n') if l.strip() and '<div' not in l]
    if len(content_lines) < 1:
        errors.append("No actual story content found")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors,
        'warnings': warnings
    }

# Main processing function
def process_book_chunks(
    chunks: List[str], 
    book_title: str, 
    start_page: int = 1,
    model: str = "claude-3-5-sonnet-20241022"
) -> str:
    """
    Process all chunks and return final extracted stories
    """
    from anthropic import Anthropic
    client = Anthropic()  # Assumes ANTHROPIC_API_KEY env var
    
    all_extractions = []
    
    for idx, chunk in enumerate(chunks):
        print(f"\nProcessing chunk {idx + 1}/{len(chunks)}...")
        
        # Prepare chunk
        prepared = prepare_chunk_for_extraction(
            chunk, 
            book_title, 
            start_page + (idx * 15),  # Estimate 15 pages per chunk
            idx
        )
        
        # Call LLM
        response = client.messages.create(
            model=model,
            messages=[
                {"role": "user", "content": prepared}
            ],
            temperature=0.0,
            max_tokens=8000
        )
        
        extraction = response.content[0].text
        all_extractions.append(extraction)
        
        # Validate
        validation = validate_extraction_output(extraction, chunk)
        if not validation['is_valid']:
            print(f"⚠️  Chunk {idx + 1} validation errors: {validation['errors']}")
        if validation['warnings']:
            print(f"⚠️  Chunk {idx + 1} warnings: {validation['warnings']}")
    
    # Post-process and merge
    final_output = post_process_extractions(all_extractions, book_title)
    
    return final_output
