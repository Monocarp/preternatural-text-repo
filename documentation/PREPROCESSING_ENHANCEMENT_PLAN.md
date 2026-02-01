# Preprocessing Enhancement Plan

**Goal**: Improve preprocessing accuracy, consistency, and precision to enable research queries like "demonic possessions in France 1500s-1700s"

**Date**: January 30, 2026

---

## Problem Statement

### Metadata Issues
Current preprocessing extracts loose keywords but lacks structured metadata needed for precise historical/geographic research queries. This limits:
- Temporal filtering (centuries, date ranges)
- Geographic filtering (hierarchical location search)
- Topic-based filtering (phenomenon types, entities)
- Quality validation (bad metadata reaches production)

### Document Processing Issues
Current book conversion pipeline has critical accuracy problems:
- **Inaccurate page numbers**: Uses word-count approximation (650 words/page) instead of actual PDF pages
- **Lossy conversion**: DOCX → MD loses formatting and page boundaries
- **Manual inefficiency**: Strip footnotes manually, insert page numbers manually, chunk manually
- **Inconsistent results**: Different books processed differently depending on manual intervention
- **No verification**: No way to validate that page numbers match source document

---

## Architecture Overview

### Redesigned Preprocessing Pipeline
```
PDF Input (SOURCE OF TRUTH)
  ↓
Page-by-Page Extraction (NEW - accurate page numbers)
  ├─ Extract text per page with PyMuPDF
  ├─ Preserve page boundaries exactly
  ├─ Clean footnotes automatically
  └─ Generate Full_Text.md with [Page N] markers
  ↓
Story Boundary Detection (SEMI-AUTOMATED)
  ├─ Option 1: Manual chunking with clear page references
  ├─ Option 2: ML-based boundary detection + manual review
  └─ Output: story_boundaries.json
  ↓
Story Extraction & Validation
  ├─ Extract stories using exact character positions
  ├─ Validate no overlaps/gaps
  └─ Link stories to exact page ranges
  ↓
Metadata Extraction (ENHANCED)
  ├─ Entities (NER + normalization)
  ├─ Temporal (regex + parsing)
  ├─ Topics (domain patterns)
  └─ Keywords (synthesized from above)
  ↓
Validation Phase (NEW)
  ├─ Required field checks
  ├─ Sanity checks (year ranges, etc)
  └─ Quality warnings
  ↓
Manual Review Queue (NEW)
  ↓
story_positions.json (enhanced format)
  ↓
Search Index (FAISS + FTS5 with metadata filters)
```

---

## Enhanced Metadata Schema

### Current Format
```json
{
  "title": "Story Title",
  "start_char": 1234,
  "end_char": 5678,
  "pages": "45-52",
  "keywords": ["keyword1", "keyword2"],
  "verbatim": "excerpt..."
}
```

### Enhanced Format
```json
{
  "title": "The Possessed Nuns of Loudun",
  "start_char": 1234,
  "end_char": 5678,
  "pages": "45-52",
  
  "entities": {
    "locations": {
      "cities": ["Loudun"],
      "regions": ["Poitou"],
      "countries": ["France"]
    },
    "persons": ["Urbain Grandier", "Sister Jeanne des Anges"],
    "organizations": ["Ursuline Convent"]
  },
  
  "temporal": {
    "years": [1632, 1633, 1634],
    "centuries": [17],
    "decades": ["1630s"],
    "periods": ["Early Modern Period"]
  },
  
  "topics": {
    "primary": ["possession", "exorcism"],
    "secondary": ["witch trial", "religious persecution"],
    "phenomena": ["demonic", "clerical abuse"]
  },
  
  "keywords": ["possession", "France", "17th century", "nuns", "exorcism", "Loudun"],
  "verbatim": "excerpt...",
  
  "validation": {
    "preprocessed_date": "2026-01-30",
    "warnings": [],
    "manual_review": false
  }
}
```

---

## Implementation Phases

### Phase 0: Document Processing Overhaul (6-8 hours)
**Priority**: CRITICAL - Foundation for all other phases

**Problem**: Current DOCX→MD with word-count pagination produces inaccurate page numbers, making citations unreliable.

**Solution**: PDF-first extraction with exact page boundaries.

#### Implementation

**File**: `preprocessing/pdf_to_markdown.py`

```python
"""
PDF to Markdown converter with accurate page numbers
Replaces DOCX-based workflow with PDF-first approach
"""

import fitz  # PyMuPDF
import re
from pathlib import Path
from typing import List, Dict, Tuple
import json

def extract_text_from_pdf(pdf_path: str, output_dir: str = "processed") -> str:
    """
    Extract text from PDF with accurate page markers
    
    Args:
        pdf_path: Path to source PDF
        output_dir: Where to save Full_Text.md
    
    Returns:
        Path to generated Full_Text.md
    """
    Path(output_dir).mkdir(exist_ok=True)
    
    pdf_name = Path(pdf_path).stem
    output_path = Path(output_dir) / f"{pdf_name}_Full_Text.md"
    
    doc = fitz.open(pdf_path)
    full_text = []
    
    print(f"Processing {len(doc)} pages from {pdf_path}")
    
    for page_num in range(len(doc)):
        page = doc[page_num]
        
        # Extract text (PyMuPDF preserves layout better than most)
        text = page.get_text("text")
        
        # Clean extracted text
        cleaned = clean_page_text(text, page_num + 1)
        
        if cleaned.strip():  # Only add non-empty pages
            full_text.append(f"[Page {page_num + 1}]\n\n{cleaned}\n")
    
    doc.close()
    
    # Save to file
    final_text = "\n".join(full_text)
    output_path.write_text(final_text, encoding="utf-8")
    
    print(f"✅ Extracted {len(doc)} pages to {output_path}")
    print(f"📄 Total characters: {len(final_text):,}")
    
    return str(output_path)


def clean_page_text(text: str, page_num: int) -> str:
    """
    Clean extracted page text
    - Remove headers/footers
    - Remove footnote numbers
    - Fix common OCR errors
    - Preserve paragraph structure
    """
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            cleaned_lines.append('')
            continue
        
        # Remove common headers (page numbers at top/bottom)
        if re.match(r'^\d+$', line):  # Just a number
            continue
        if re.match(r'^Page \d+', line, re.I):
            continue
        
        # Remove footnote markers: superscript numbers
        # Pattern: word¹ or word[1] → word
        line = re.sub(r'[\u00B9\u00B2\u00B3\u2074-\u2079]', '', line)  # Superscripts
        line = re.sub(r'\[\d+\]', '', line)  # [1] style
        line = re.sub(r'\d+(?=\s|$)', '', line)  # Trailing numbers
        
        # Fix common OCR artifacts
        line = line.replace('ﬁ', 'fi').replace('ﬂ', 'fl')  # Ligatures
        line = line.replace(''', "'").replace(''', "'")  # Smart quotes
        line = line.replace('"', '"').replace('"', '"')
        line = line.replace('—', '--').replace('–', '-')
        
        # Remove standalone footnote sections at bottom of page
        if re.match(r'^[\d\s]+$', line):  # Line of just numbers
            continue
        
        cleaned_lines.append(line)
    
    # Reconstruct text with paragraph breaks
    cleaned = '\n'.join(cleaned_lines)
    
    # Normalize whitespace: max 2 consecutive newlines
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    return cleaned.strip()


def detect_story_boundaries_auto(full_text: str, min_story_length: int = 500) -> List[Dict]:
    """
    Attempt automatic story boundary detection
    Uses heuristics: new heading, page breaks, content patterns
    
    Returns list of detected boundaries for manual review
    """
    boundaries = []
    
    # Split by page markers
    pages = re.split(r'\[Page \d+\]', full_text)
    
    current_pos = 0
    for page_content in pages:
        # Look for story title patterns
        # Common patterns: 
        # - "Chapter N: Title"
        # - "N. Title"
        # - "Title" (all caps or title case on its own line)
        
        lines = page_content.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Pattern 1: Chapter/Case headings
            if re.match(r'^(Chapter|Case|Story|Part)\s+\d+', line, re.I):
                boundaries.append({
                    "type": "chapter_heading",
                    "position": current_pos + page_content[:page_content.find(line)].count('\n'),
                    "title_candidate": line,
                    "confidence": 0.9
                })
            
            # Pattern 2: Numbered sections
            elif re.match(r'^\d+\.\s+[A-Z]', line):
                boundaries.append({
                    "type": "numbered_section",
                    "position": current_pos + page_content[:page_content.find(line)].count('\n'),
                    "title_candidate": line,
                    "confidence": 0.7
                })
            
            # Pattern 3: All-caps titles (at least 3 words)
            elif len(line.split()) >= 3 and line.isupper():
                boundaries.append({
                    "type": "caps_title",
                    "position": current_pos + page_content[:page_content.find(line)].count('\n'),
                    "title_candidate": line,
                    "confidence": 0.6
                })
        
        current_pos += len(page_content)
    
    return boundaries


def manual_chunking_helper(full_text_path: str, output_path: str = "story_boundaries.json"):
    """
    Generate interactive helper for manual story chunking
    Shows page markers, character positions, content preview
    """
    full_text = Path(full_text_path).read_text(encoding="utf-8")
    
    # Auto-detect potential boundaries
    candidates = detect_story_boundaries_auto(full_text)
    
    # Generate helper output
    helper_data = {
        "source_file": full_text_path,
        "total_length": len(full_text),
        "detected_boundaries": candidates,
        "instructions": """
        MANUAL CHUNKING INSTRUCTIONS:
        
        1. Open Full_Text.md in editor
        2. Search for [Page N] markers to navigate
        3. Identify story start positions (character index)
        4. Fill in story_positions below
        5. Verify no overlaps using validate_boundaries()
        
        FINDING CHARACTER POSITIONS:
        - Most editors show line:column
        - Use grep -n "story title" Full_Text.md to find line
        - Count characters from start to that line
        - Or use this script's find_position() function
        """,
        "story_positions": {
            "Example Story Title": {
                "start_char": 0,
                "end_char": 5000,
                "pages": "1-5",
                "notes": "Starts after introduction, ends before next chapter"
            }
        }
    }
    
    Path(output_path).write_text(json.dumps(helper_data, indent=2), encoding="utf-8")
    print(f"✅ Generated manual chunking helper: {output_path}")
    print(f"📝 Found {len(candidates)} potential story boundaries")
    print(f"   Review candidates and fill in story_positions")


def find_position(full_text_path: str, search_text: str) -> List[Tuple[int, str]]:
    """
    Find character position(s) of search text in Full_Text.md
    Returns: [(char_position, context_preview), ...]
    """
    full_text = Path(full_text_path).read_text(encoding="utf-8")
    
    results = []
    start = 0
    while True:
        pos = full_text.find(search_text, start)
        if pos == -1:
            break
        
        # Get surrounding context (50 chars before/after)
        context_start = max(0, pos - 50)
        context_end = min(len(full_text), pos + len(search_text) + 50)
        context = full_text[context_start:context_end]
        
        # Find which page this is on
        pages_before = full_text[:pos].count('[Page ')
        
        results.append((pos, f"Page ~{pages_before + 1}: ...{context}..."))
        start = pos + 1
    
    return results


def validate_boundaries(story_positions: Dict) -> Dict:
    """
    Validate story boundaries have no overlaps or gaps
    """
    issues = {
        "overlaps": [],
        "gaps": [],
        "invalid": []
    }
    
    # Sort by start position
    sorted_stories = sorted(
        story_positions.items(),
        key=lambda x: x[1]["start_char"]
    )
    
    for i, (title, pos) in enumerate(sorted_stories):
        start = pos["start_char"]
        end = pos["end_char"]
        
        # Check valid range
        if end <= start:
            issues["invalid"].append(f"{title}: end ({end}) <= start ({start})")
        
        # Check for overlap with next story
        if i < len(sorted_stories) - 1:
            next_title, next_pos = sorted_stories[i + 1]
            next_start = next_pos["start_char"]
            
            if end > next_start:
                issues["overlaps"].append(
                    f"{title} ({start}-{end}) overlaps with {next_title} ({next_start}-...)"
                )
            elif end < next_start:
                gap_size = next_start - end
                if gap_size > 100:  # Only flag significant gaps
                    issues["gaps"].append(
                        f"Gap of {gap_size} chars between {title} and {next_title}"
                    )
    
    return issues


def extract_stories_from_boundaries(
    full_text_path: str,
    story_positions: Dict,
    output_dir: str = "stories"
) -> Dict:
    """
    Extract individual story files from Full_Text.md using boundaries
    Also extracts accurate page ranges for each story
    """
    full_text = Path(full_text_path).read_text(encoding="utf-8")
    Path(output_dir).mkdir(exist_ok=True)
    
    # First validate boundaries
    issues = validate_boundaries(story_positions)
    if issues["overlaps"] or issues["invalid"]:
        print("❌ VALIDATION ERRORS:")
        for error in issues["overlaps"] + issues["invalid"]:
            print(f"  - {error}")
        raise ValueError("Fix boundary errors before extracting stories")
    
    if issues["gaps"]:
        print("⚠️  WARNINGS:")
        for warning in issues["gaps"]:
            print(f"  - {warning}")
    
    # Extract each story
    extracted = {}
    for title, pos in story_positions.items():
        start = pos["start_char"]
        end = pos["end_char"]
        
        story_text = full_text[start:end]
        
        # Calculate accurate page range
        pages_before_start = full_text[:start].count('[Page ')
        pages_before_end = full_text[:end].count('[Page ')
        
        start_page = pages_before_start + 1
        end_page = pages_before_end + 1
        
        # Save individual story file
        safe_filename = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        story_path = Path(output_dir) / f"{safe_filename}.md"
        story_path.write_text(story_text, encoding="utf-8")
        
        extracted[title] = {
            "start_char": start,
            "end_char": end,
            "pages": f"{start_page}-{end_page}",
            "length": len(story_text),
            "file": str(story_path)
        }
        
        print(f"✅ {title}: pages {start_page}-{end_page}, {len(story_text):,} chars")
    
    return extracted


# CLI Interface for Google Colab
def main():
    """Interactive CLI for book processing"""
    import sys
    
    print("=" * 60)
    print("PDF to Markdown Converter with Accurate Page Numbers")
    print("=" * 60)
    
    # Step 1: PDF extraction
    print("\n📥 STEP 1: Upload PDF")
    from google.colab import files
    uploaded = files.upload()
    if not uploaded:
        print("❌ No file uploaded")
        return
    
    pdf_file = next(iter(uploaded))
    print(f"✅ Uploaded: {pdf_file}")
    
    # Step 2: Extract to Full_Text.md
    print("\n📝 STEP 2: Extracting text with accurate page numbers...")
    full_text_path = extract_text_from_pdf(pdf_file)
    
    # Step 3: Generate chunking helper
    print("\n🔍 STEP 3: Detecting potential story boundaries...")
    manual_chunking_helper(full_text_path)
    
    print("\n" + "=" * 60)
    print("NEXT STEPS:")
    print("1. Download Full_Text.md and story_boundaries.json")
    print("2. Review detected boundaries in Full_Text.md")
    print("3. Fill in story_positions in story_boundaries.json")
    print("4. Use find_position() to locate exact character positions")
    print("5. Run extract_stories_from_boundaries() to validate & extract")
    print("=" * 60)
    
    # Download outputs
    files.download(full_text_path)
    files.download("story_boundaries.json")


if __name__ == "__main__":
    main()
```

#### Requirements
```txt
# Add to preprocessing requirements
PyMuPDF>=1.23.0  # fitz module for PDF extraction
```

#### Advantages Over Current Approach

| Aspect | Current (DOCX + word-count) | New (PDF + exact pages) |
|--------|----------------------------|------------------------|
| **Page Accuracy** | ±2-3 pages (word-count estimate) | Exact (from source PDF) |
| **Footnote Handling** | Manual deletion | Automatic pattern-based removal |
| **Verification** | No way to validate | Boundary validation built-in |
| **Consistency** | Varies by manual intervention | Automated cleaning rules |
| **Citations** | Unreliable page references | Accurate page-to-page ranges |
| **Process** | Multi-step manual | Semi-automated with helpers |

#### Migration Path for Existing Books

```python
# scripts/reprocess_existing_books.py

def reprocess_with_accurate_pages(book_dir: str, source_pdf: str):
    """
    Reprocess an existing book with accurate page numbers
    Preserves manual categorization but updates page ranges
    """
    book_path = Path(book_dir)
    
    # Load existing story positions (has manual categories)
    existing_positions = json.loads((book_path / "story_positions.json").read_text())
    
    # Extract new Full_Text.md from PDF
    new_full_text_path = extract_text_from_pdf(source_pdf, output_dir=str(book_path))
    new_full_text = Path(new_full_text_path).read_text()
    
    # Re-calculate page ranges using story titles
    updated_positions = {}
    for title, old_data in existing_positions.items():
        # Find story in new text by title search
        positions = find_position(new_full_text_path, title[:50])  # First 50 chars
        
        if positions:
            char_pos, context = positions[0]
            # Use old boundaries as relative offsets, but recalc pages
            # This is semi-automated - still needs manual review
            
            updated_positions[title] = {
                **old_data,  # Preserve keywords, categories, etc.
                "pages_old": old_data["pages"],
                "pages_new": "NEEDS_REVIEW",  # Human must verify
                "char_position_found": char_pos
            }
    
    # Save for manual review
    review_path = book_path / "page_number_migration.json"
    review_path.write_text(json.dumps(updated_positions, indent=2))
    
    print(f"✅ Generated migration review file: {review_path}")
    print(f"📝 Manually review and update page ranges, then replace story_positions.json")
```

#### Testing

```python
# tests/test_pdf_extraction.py

def test_page_marker_accuracy():
    """Verify page markers match PDF page count"""
    pdf = fitz.open("test_book.pdf")
    extracted_text = extract_text_from_pdf("test_book.pdf")
    
    page_count_pdf = len(pdf)
    page_count_extracted = extracted_text.count('[Page ')
    
    assert page_count_pdf == page_count_extracted

def test_no_boundary_overlaps():
    """Ensure story boundaries don't overlap"""
    positions = {
        "Story 1": {"start_char": 0, "end_char": 1000},
        "Story 2": {"start_char": 1000, "end_char": 2000}
    }
    issues = validate_boundaries(positions)
    assert not issues["overlaps"]

def test_page_range_calculation():
    """Verify page ranges are calculated correctly"""
    full_text = "[Page 1]\nContent1\n[Page 2]\nContent2\n[Page 3]\nContent3"
    # Story from after "Content1" to before "Content3"
    # Should be pages 2-2 or 1-3 depending on boundaries
    pass
```

**Deliverable**: `preprocessing/pdf_to_markdown.py`, updated workflow documentation

---

### Phase 1: Temporal Extraction (3-4 hours)
**Priority**: CRITICAL for historical research

**Implementation**:
```python
def extract_temporal_metadata(text):
    """Extract all time references from text"""
    temporal = {
        "years": set(),
        "centuries": set(),
        "decades": set(),
        "periods": []
    }
    
    # 1. Explicit years: "in 1632", "year 1645"
    years = re.findall(r'\b(1[0-9]{3}|20[0-2][0-9])\b', text)
    temporal["years"].update(map(int, years))
    
    # 2. Century mentions: "17th century", "seventeenth century"
    century_num = re.findall(r'(\d{1,2})(?:st|nd|rd|th)\s+century', text, re.I)
    for c in century_num:
        temporal["centuries"].add(int(c))
    
    century_words = {
        "fifteenth": 15, "sixteenth": 16, "seventeenth": 17,
        "eighteenth": 18, "nineteenth": 19, "twentieth": 20
    }
    for word, num in century_words.items():
        if re.search(rf'\b{word}\s+century\b', text, re.I):
            temporal["centuries"].add(num)
    
    # 3. Date ranges: "1632-1634", "from 1640 to 1645"
    ranges = re.findall(r'(\d{4})\s*(?:-|to)\s*(\d{4})', text)
    for start, end in ranges:
        temporal["years"].update(range(int(start), int(end)+1))
    
    # 4. Decades: "1630s", "the thirties"
    decades = re.findall(r'(\d{3})0s', text)
    temporal["decades"].extend([f"{d}0s" for d in decades])
    
    # 5. Historical periods (hardcoded mapping)
    period_map = {
        "Renaissance": (1300, 1600),
        "Reformation": (1517, 1648),
        "Enlightenment": (1685, 1815),
        "Victorian": (1837, 1901)
    }
    for period, (start, end) in period_map.items():
        if re.search(rf'\b{period}\b', text, re.I):
            temporal["periods"].append(period)
            temporal["years"].update(range(start, end+1))
    
    # Convert sets to sorted lists
    return {
        "years": sorted(list(temporal["years"])),
        "centuries": sorted(list(temporal["centuries"])),
        "decades": temporal["decades"],
        "periods": temporal["periods"]
    }
```

**Testing**:
- Run on christian_mysticism stories
- Verify "15th Century" extracts century=15
- Verify year ranges expand correctly

**Deliverable**: `temporal_extraction.py`

---

### Phase 2: Location Extraction + Hierarchy (3-4 hours)
**Priority**: CRITICAL for geographic filtering

**Requirements**:
- spaCy `en_core_web_sm` model
- Optional: GeoNames database or hardcoded gazetteer

**Implementation**:
```python
import spacy

nlp = spacy.load("en_core_web_sm")

def extract_locations(text):
    """Extract locations with hier (End-to-End)

```python
# preprocessing_pipeline.py

import json
from pathlib import Path
from pdf_to_markdown import (
    extract_text_from_pdf,
    manual_chunking_helper,
    extract_stories_from_boundaries,
    validate_boundaries
)
from temporal_extraction import extract_temporal_metadata
from location_extraction import extract_locations
from topic_extraction import extract_domain_topics
from keyword_synthesis import synthesize_keywords
from validation import validate_story_metadata, generate_review_queue

def process_new_book_from_pdf(
    pdf_path: str,
    book_name: str,
    story_boundaries_path: str = None,
    output_dir: str = None
):
    """
    Complete pipeline from PDF to indexed book
    
    Workflow:
    1. Extract PDF → Full_Text.md (accurate pages)
    2. Manual chunking or load boundaries
    3. Extract & validate stories
    4. Extract metadata for each story
    5. Validate & generate review queue
    6. Output ready-to-index story_positions.json
    
    Args:
        pdf_path: Source PDF file
        book_name: Name for the book directory
        story_boundaries_path: Optional pre-defined story boundaries JSON
        output_dir: Where to create book directory (default: books/)
    """
    if output_dir is None:
        output_dir = Path("books") / book_name
    else:
        output_dir = Path(output_dir) / book_name
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print(f"PROCESSING NEW BOOK: {book_name}")
    print("=" * 70)
    
    # PHASE 1: PDF Extraction
    print("\n📄 PHASE 1: Extracting PDF with accurate page numbers...")
    full_text_path = extract_text_from_pdf(
        pdf_path,
        output_dir=str(output_dir)
    )
    
    # PHASE 2: Story Boundaries
    if not story_boundaries_path:
        print("\n✂️  PHASE 2: Generating manual chunking helper...")
        manual_chunking_helper(
            full_text_path,
            output_path=str(output_dir / "story_boundaries.json")
        )
        print("\n⏸️  PAUSED: Manual chunking required")
        print(f"   1. Review {full_text_path}")
        print(f"   2. Fill in story_positions in {output_dir}/story_boundaries.json")
        print(f"   3. Re-run with story_boundaries_path parameter")
        return
    
    print("\n✂️  PHASE 2: Loading story boundaries...")
    with open(story_boundaries_path, 'r') as f:
        boundaries_data = json.load(f)
        story_positions = boundaries_data["story_positions"]
    
    # Validate boundaries
    print("\n✅ PHASE 2.5: Validating boundaries...")
    issues = validate_boundaries(story_positions)
    if issues["overlaps"] or issues["invalid"]:
        print("❌ BOUNDARY ERRORS FOUND:")
        for error in issues["overlaps"] + issues["invalid"]:
            print(f"  {error}")
        raise ValueError("Fix boundaries before continuing")
    
    # PHASE 3: Extract Stories
    print("\n📚 PHASE 3: Extracting stories from Full_Text...")
    extracted = extract_stories_from_boundaries(
        full_text_path,
        story_positions,
        output_dir=str(output_dir / "stories")
    )
    
    # PHASE 4: Metadata Extraction
    print("\n🔍 PHASE 4: Extracting metadata for each story...")
    full_text = Path(full_text_path).read_text(encoding="utf-8")
    enhanced_positions = {}
    
    for title, position_data in story_positions.items():
        print(f"  Processing: {title[:50]}...")
        
        # Extract story content
        start = position_data["start_char"]
        end = position_data["end_char"]
        content = full_text[start:end]
        
        # Extract all metadata
        try:
            entities = extract_locations(title + " " + content)
            temporal = extract_temporal_metadata(content)
            topics = extract_domain_topics(content)
            keywords = synthesize_keywords(title, entities, temporal, topics)
            
            # Build enhanced metadata
            enhanced_metadata = {
                **position_data,  # Preserve start_char, end_char, pages
                "entities": entities,
                "temporal": temporal,
                "topics": topics,
                "keywords": keywords,
                "validation": {
                    "preprocessed_date": "2026-01-30",
                    "warnings": [],
                    "manual_review": False
                }
            }
            
            # Validate
            validation = validate_story_metadata(enhanced_metadata)
            enhanced_metadata["validation"]["warnings"] = validation["warnings"]
            enhanced_metadata["validation"]["manual_review"] = bool(
                validation["warnings"] or validation["errors"]
            )
            
            if validation["errors"]:
                print(f"    ❌ ERRORS: {validation['errors']}")
            if validation["warnings"]:
                print(f"    ⚠️  {len(validation['warnings'])} warnings")
            
            enhanced_positions[title] = enhanced_metadata
            
        except Exception as e:
            print(f"    ❌ FAILED: {str(e)}")
            # Add minimal metadata to continue
            enhanced_positions[title] = {
                **position_data,
                "validation": {
                    "preprocessed_date": "2026-01-30",
                    "errors": [str(e)],
                    "manual_review": True
                }
            }
    
    # PHASE 5: Generate Review Queue
    print("\n📋 PHASE 5: Generating manual review queue...")
    review_queue = generate_review_queue(enhanced_positions)
    
    # PHASE 6: Save Outputs
    print("\n💾 PHASE 6: Saving outputs...")
    
    # Save enhanced story_positions.json
    positions_output = output_dir / "story_positions.json"
    positions_output.write_text(
        json.dumps(enhanced_positions, indent=2),
        encoding="utf-8"
    )
    
    # Save manual review queue
    review_output = output_dir / "manual_review.json"
    review_output.write_text(
        json.dumps(review_queue, indent=2),
        encoding="utf-8"
    )
    
    # Generate summary stats
    stats = {
        "book_name": book_name,
        "total_stories": len(enhanced_positions),
        "needs_review": len(review_queue),
        "total_pages": full_text.count('[Page '),
        "total_chars": len(full_text),
        "avg_story_length": sum(p["end_char"] - p["start_char"] 
                               for p in story_positions.values()) // len(story_positions),
        "extraction_errors": sum(1 for p in enhanced_positions.values() 
                                if p.get("validation", {}).get("errors")),
        "files": {
            "full_text": str(full_text_path),
            "story_positions": str(positions_output),
            "manual_review": str(review_output)
        }
    }
    
    stats_output = output_dir / "preprocessing_stats.json"
    stats_output.write_text(json.dumps(stats, indent=2), encoding="utf-8")
    
    # Print summary
    print("\n" + "=" * 70)
    print("✅ PREPROCESSING COMPLETE")
    print("=" * 70)
    print(f"📚 Book: {book_name}")
    print(f"📄 Stories: {stats['total_stories']}")
    print(f"📃 Pages: {stats['total_pages']}")
    print(f"⚠️  Needs Review: {stats['needs_review']}")
    print(f"❌ Extraction Errors: {stats['extraction_errors']}")
    print(f"\n📂 Output Directory: {output_dir}")
    print(f"   - story_positions.json (ready to index)")
    print(f"   - manual_review.json ({len(review_queue)} stories)")
    print(f"   - Full_Text.md")
    print(f"   - preprocessing_stats.json")
    print("=" * 70)
    
    if review_queue:
        print("\n⚠️  NEXT STEP: Review flagged stories in manual_review.json")
    else:
        print("\n✅ No manual review needed - ready to index!")
    
    return enhanced_positions, review_queue, stats


# Simplified function for existing books (metadata only)
def enhance_existing_book(
    book_dir: str,
    full_text_path: str = None,
    story_positions_path: str = None
):
    """
    Enhance existing book with new metadata extraction
    Preserves manual categorization, updates metadata only
    """
    book_dir = Path(book_dir)
    
    if full_text_path is None:
        full_text_path = book_dir / "Full_Text.md"
    if story_positions_path is None:
        story_positions_path = book_dir / "story_positions.json"
    
    # Load existing
    full_text = Path(full_text_path).read_text(encoding="utf-8")
    story_positions = json.loads(Path(story_positions_path).read_text())
    
    # Run metadata extraction only (preserves existing boundaries/categories)
    enhanced_positions = {}
    
    for title, position_data in story_positions.items():
        start = position_data["start_char"]
        end = position_data["end_char"]
        content = full_text[start:end]
        
        # Extract metadata
        entities = extract_locations(title + " " + content)
        temporal = extract_temporal_metadata(content)
        topics = extract_domain_topics(content)
        keywords = synthesize_keywords(title, entities, temporal, topics)
        
        enhanced_positions[title] = {
            **position_data,  # Preserve everything
            "entities": entities,
            "temporal": temporal,
            "topics": topics,
            "keywords": keywords  # May overwrite existing - be careful!
        }
    
    # Save backup
    backup_path = story_positions_path.with_suffix('.json.backup')
    backup_path.write_text(
        json.dumps(story_positions, indent=2),
        encoding="utf-8"
    )
    
    # Save enhanced
    story_positions_path.write_text(
        json.dumps(enhanced_positions, indent=2),
        encoding="utf-8"
    )
    
    print(f"✅ Enhanced {len(enhanced_positions)} stories")
    print(f"💾 Backup saved: {backup_path}")
    
    return enhanced_positions


# Example usage
if __name__ == "__main__":
    # NEW BOOK FROM PDF
    process_new_book_from_pdf(
        pdf_path="Investigations_into_Magic_Vol_2.pdf",
        book_name="investigations_magic_vol_2",
        story_boundaries_path=None  # Will pause for manual chunking
    )
    
    # After manual chunking, resume:
    # process_new_book_from_pdf(
    #     pdf_path="Investigations_into_Magic_Vol_2.pdf",
    #     book_name="investigations_magic_vol_2",
    #     story_boundaries_path="books/investigations_magic_vol_2/story_boundaries.json"
    # )
    
    # ENHANCE EXISTING BOOK
    # enhance_existing_book("books/ecology_of_souls_volume_i"for entity_type, patterns in DOMAIN_PATTERNS["entity_types"].items():
        if any(pattern in text_lower for pattern in patterns):
            topics["entities"].append(entity_type)
    
    # Determine primary topics (most frequently mentioned)
    # This requires more sophisticated counting and ranking
    all_matches = topics["phenomena"] + topics["entities"]
    if all_matches:
        topics["primary"] = all_matches[:3]  # Top 3
        topics["secondary"] = all_matches[3:6]  # Next 3
    
    return topics
```

**Pattern Dictionary Expansion**:
- Review existing books for common terms
- Build comprehensive pattern dictionary
- Store in `domain_patterns.json`

**Testing**:
- Test on stories with "possession", "UFO", "haunting"
- Verify topic extraction accuracy

**Deliverable**: `topic_extraction.py`, `domain_patterns.json`

---

### Phase 4: Validation System (2-3 hours)
**Priority**: HIGH for data quality

**Implementation**:
```python
def validate_story_metadata(story_metadata):
    """Comprehensive validation checks"""
    errors = []
    warnings = []
    
    # 1. Required fields
    required = ["title", "start_char", "end_char", "keywords"]
    for field in required:
        if not story_metadata.get(field):
            errors.append(f"Missing required field: {field}")
    
    # 2. Temporal sanity checks
    if "temporal" in story_metadata:
        years = story_metadata["temporal"].get("years", [])
        if years:
            if any(y < 1000 or y > 2026 for y in years):
                warnings.append(f"Suspicious years: {years}")
            if max(years) - min(years) > 100:
                warnings.append(f"Large year span: {min(years)}-{max(years)}")
    
    # 3. Entity extraction quality
    entities = story_metadata.get("entities", {})
    if not entities.get("locations") and not entities.get("persons"):
        warnings.append("No entities extracted - may need manual review")
    
    # 4. Topic extraction quality
    topics = story_metadata.get("topics", {})
    if not topics.get("primary"):
        warnings.append("No primary topics extracted")
    
    # 5. Keyword quality (from earlier analysis)
    keywords = story_metadata.get("keywords", [])
    title = story_metadata.get("title", "")
    if len(keywords) == 1 and keywords[0].lower() == title.lower():
        warnings.append("Keywords auto-generated from title only - needs enrichment")
    
    # 6. Boundary sanity
    start = story_metadata.get("start_char", 0)
    end = story_metadata.get("end_char", 0)
    if end <= start:
        errors.append(f"Invalid boundaries: {start}-{end}")
    if end - start < 100:
        warnings.append(f"Very short story: {end - start} chars")
    if end - start > 50000:
        warnings.append(f"Very long story: {end - start} chars")
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }
```

**Deliverable**: `validation.py`

---

### Phase 5: Manual Review Workflow (2-3 hours)
**Priority**: MEDIUM for consistency

**Implementation**:
```python
def generate_review_queue(book_data):
    """Create manual review file for stories with warnings"""
    review_queue = []
    
    for story_title, metadata in book_data.items():
        validation = validate_story_metadata(metadata)
        
        if not validation["valid"]:
            review_queue.append({
                "story": story_title,
                "status": "ERROR",
                "issues": validation["errors"],
                "metadata": metadata
            })
        elif validation["warnings"]:
            review_queue.append({
                "story": story_title,
                "status": "WARNING",
                "issues": validation["warnings"],
                "metadata": metadata,
                "suggestions": generate_fix_suggestions(metadata, validation["warnings"])
            })
    
    return review_queue

def generate_fix_suggestions(metadata, warnings):
    """Suggest fixes for common issues"""
    suggestions = []
    
    for warning in warnings:
        if "auto-generated from title" in warning:
            suggestions.append({
                "issue": "Poor keywords",
                "action": "Add entities, locations, temporal terms from content",
                "example": "Add: [location names], [person names], [century]"
            })
        
        if "No entities extracted" in warning:
            suggestions.append({
                "issue": "Missing entities",
                "action": "Manually review content for person/location names",
                "example": "Look for proper nouns"
            })
    
    return suggestions
```

**Workflow**:
1. Preprocessing generates `manual_review.json`
2. Human curator reviews flagged stories
3. Curator edits `story_positions.json` directly
4. Re-run validation to clear warnings
5. Only validated stories move to production

**Deliverable**: `review_workflow.py`, `manual_review.json` template

---

### Phase 6: Enhanced Keyword Synthesis (3-4 hours)
**Priority**: MEDIUM (builds on Phases 1-3)

**Implementation**:
```python
def synthesize_keywords(title, entities, temporal, topics, max_keywords=15):
    """Generate rich keywords from structured metadata"""
    keywords = set()
    
    # 1. Add title words (existing approach)
    title_words = [w for w in title.lower().split() if len(w) > 3]
    keywords.update(title_words[:5])
    
    # 2. Add locations (hierarchical)
    if entities.get("locations"):
        locs = entities["locations"]
        keywords.update(locs.get("cities", [])[:3])
        keywords.update(locs.get("countries", [])[:2])
    
    # 3. Add persons (top 3)
    if entities.get("persons"):
        keywords.update(entities["persons"][:3])
    
    # 4. Add temporal keywords
    if temporal.get("centuries"):
        for century in temporal["centuries"][:2]:
            keywords.add(f"{century}th century")
    if temporal.get("decades"):
        keywords.update(temporal["decades"][:2])
    
    # 5. Add primary topics
    if topics.get("primary"):
        keywords.update(topics["primary"][:3])
    
    # 6. Add phenomena types
    if topics.get("phenomena"):
        keywords.update(topics["phenomena"][:2])
    
    # Limit to max_keywords
    return sorted(list(keywords))[:max_keywords]
```

**Testing**:
- Compare against manually curated christian_mysticism keywords
- Ensure new synthesis adds same value

**Deliverable**: `keyword_synthesis.py`

---

### Phase 7: Search Backend Integration (4-5 hours)
**Priority**: HIGH (makes metadata actionable)

**Backend Changes**:

**File**: `backend/search/engine.py`
```python
def add_documents(self, stories):
    """Add documents with enhanced metadata"""
    for story in stories:
        # FTS5: Index for keyword search
        self.fts_index.add(
            title=story["title"],
            content=story["content"],
            keywords=" ".join(story.get("keywords", []))
        )
        
        # FAISS: Embed content + store metadata
        embedding = self.embed_text(story["content"])
        
        # Enhanced metadata for filtering
        metadata = {
            "title": story["title"],
            "book": story.get("book"),
            "locations": story.get("entities", {}).get("locations", {}),
            "persons": story.get("entities", {}).get("persons", []),
            "years": story.get("temporal", {}).get("years", []),
            "centuries": story.get("temporal", {}).get("centuries", []),
            "topics": story.get("topics", {}).get("primary", []),
            "phenomena": story.get("topics", {}).get("phenomena", [])
        }
        
        self.faiss_index.add(embedding, metadata=metadata)

def search_with_filters(self, query, filters=None, mode="hybrid", limit=50):
    """Search with post-filtering on metadata"""
    # Get search results
    results = self.search(query, mode=mode, limit=limit*2)  # Get extra for filtering
    
    # Apply filters
    if filters:
        filtered = []
        for result in results:
            if self._matches_filters(result.metadata, filters):
                filtered.append(result)
                if len(filtered) >= limit:
                    break
        return filtered
    
    return results[:limit]

def _matches_filters(self, metadata, filters):
    """Check if metadata matches filter criteria"""
    # Country filter
    if filters.get("countries"):
        story_countries = metadata.get("locations", {}).get("countries", [])
        if not any(c in story_countries for c in filters["countries"]):
            return False
    
    # Century filter
    if filters.get("centuries"):
        story_centuries = metadata.get("centuries", [])
        if not any(c in story_centuries for c in filters["centuries"]):
            return False
    
    # Year range filter
    if filters.get("year_range"):
        min_year, max_year = filters["year_range"]
        story_years = metadata.get("years", [])
        if not any(min_year <= y <= max_year for y in story_years):
            return False
    
    # Topic filter
    if filters.get("topics"):
        story_topics = metadata.get("topics", []) + metadata.get("phenomena", [])
        if not any(t in story_topics for t in filters["topics"]):
            return False
    
    return True
```

**New Endpoint**: `backend/routes/search.py`
```python
@router.get("/search/filtered")
async def search_with_filters(
    q: str,
    countries: List[str] = Query(None),
    centuries: List[int] = Query(None),
    year_min: int = Query(None),
    year_max: int = Query(None),
    topics: List[str] = Query(None),
    mode: str = "hybrid",
    limit: int = 50
):
    """Search with metadata filters"""
    filters = {}
    
    if countries:
        filters["countries"] = countries
    if centuries:
        filters["centuries"] = centuries
    if year_min and year_max:
        filters["year_range"] = (year_min, year_max)
    if topics:
        filters["topics"] = topics
    
    results = engine.search_with_filters(
        query=q,
        filters=filters,
        mode=mode,
        limit=limit
    )
    
    return {"results": results}
```

**Deliverable**: Updated `engine.py`, new filtered search endpoint

---

### Phase 8: Frontend Filter UI (4-5 hours)
**Priority**: MEDIUM (exposes filters to users)

**Component**: `frontend/src/components/SearchFilters.tsx`
```typescript
interface SearchFiltersProps {
  onFilterChange: (filters: SearchFilters) => void;
  availableCountries: string[];
  availableTopics: string[];
}

export function SearchFilters({ onFilterChange, availableCountries, availableTopics }: SearchFiltersProps) {
  const [countries, setCountries] = useState<string[]>([]);
  const [centuries, setCenturies] = useState<number[]>([]);
  const [yearRange, setYearRange] = useState<[number, number]>([1000, 2026]);
  const [topics, setTopics] = useState<string[]>([]);
  
  useEffect(() => {
    onFilterChange({ countries, centuries, yearRange, topics });
  }, [countries, centuries, yearRange, topics]);
  
  return (
    <div className="search-filters">
      {/* Country multi-select */}
      <MultiSelect
        label="Countries"
        options={availableCountries}
        value={countries}
        onChange={setCountries}
      />
      
      {/* Century multi-select */}
      <MultiSelect
        label="Centuries"
        options={[15, 16, 17, 18, 19, 20, 21].map(c => `${c}th century`)}
        value={centuries}
        onChange={setCenturies}
      />
      
      {/* Year range slider */}
      <RangeSlider
        label="Year Range"
        min={1000}
        max={2026}
        value={yearRange}
        onChange={setYearRange}
      />
      
      {/* Topic multi-select */}
      <MultiSelect
        label="Topics"
        options={availableTopics}
        value={topics}
        onChDocument Processing Foundation (Phase 0)
- **Day 1-2**: Implement PDF extraction with PyMuPDF
  - `extract_text_from_pdf()` with page markers
  - `clean_page_text()` with footnote removal
- **Day 3**: Build boundary detection helpers
  - `detect_story_boundaries_auto()` 
  - `manual_chunking_helper()`
- **Day 4**: Build validation & extraction
  - `validate_boundaries()`
  - `extract_stories_from_boundaries()`
- **Day 5**: Test on one existing book PDF
  - Compare page numbers old vs new
  - Verify accuracy improvement

### Week 2: Core Metadata Extraction (Phases 1-3)
- **Day 1-2**: Implement temporal extraction + tests
- **Day 3-4**: Implement location extraction + build gazetteer
- **Day 5**: Implement topic extraction + domain patterns

### Week 3: Validation & Integration (Phases 4-7)
- **Day 1-2**: Build validation system + manual review workflow
- **Day 3**: Integrate keyword synthesis
- **Day 4-5**: Update search backend with filters

### Week 4: Testing & Frontend (Phase 8 + Testing)
- **Day 1-2**: Comprehensive testing (unit + integration)
- **Day 3-4**: Build frontend filter UI
- **Day 5**: Test end-to-end workflow

### Week 5: Migration & Validation
- **Day 1-2**: Reprocess existing 3 books with PDF-first pipeline
- **Day 3-4**: Manual review queue processing
- **Day 5**: Verify page number accuracy, update citations
import json
from pathlib import Path
from temporal_extraction import extract_temporal_metadata
from location_extraction import extract_locations
from topic_extraction import extract_domain_topics
from keyword_synthesis import synthesize_keywords
from validation import validate_story_metadata, generate_review_queue

def process_book(
    full_text_path: str,
    story_positions: dict,
    output_path: str,
    review_output_path: str
):
    """
    Complete preprocessing pipeline for a book
    
    Args:
        full_text_path: Path to Full_Text.md
        story_positions: Existing story_positions dict (with boundaries)
        output_path: Where to save enhanced story_positions.json
        review_output_path: Where to save manual_review.json
    """
    
    # Load full text
    with open(full_text_path, 'r', encoding='utf-8') as f:
        full_text = f.read()
    
    enhanced_positions = {}
    
    for title, position_data in story_positions.items():
        print(f"Processing: {title}")
        
        # Extract story content
        start = position_data["start_char"]
        end = position_data["end_char"]
        content = full_text[start:end]
        
        # Extract all metadata
        entities = extract_locations(title + " " + content)
        temporal = extract_temporal_metadata(content)
        topics = extract_domain_topics(content)
        keywords = synthesize_keywords(title, entities, temporal, topics)
        
        # Build enhanced metadata
        enhanced_metadata = {
            **position_data,  # Preserve existing (start_char, end_char, pages, verbatim)
            "entities": entities,
            "temporal": temporal,
            "topics": topics,
            "keywords": keywords,
            "validation": {
                "preprocessed_date": "2026-01-30",
                "warnings": [],
                "manual_review": False
            }
        }
        
        # Validate
        validation = validate_story_metadata(enhanced_metadata)
        enhanced_metadata["validation"]["warnings"] = validation["warnings"]
        enhanced_metadata["validation"]["manual_review"] = bool(validation["warnings"] or validation["errors"])
        
        if validation["errors"]:
            print(f"  ❌ ERRORS: {validation['errors']}")
        if validation["warnings"]:
            print(f"  ⚠️  WARNINGS: {validation['warnings']}")
        
        enhanced_positions[title] = enhanced_metadata
    
    # Generate review queue
    review_queue = generate_review_queue(enhanced_positions)
    
    # Save outputs
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(enhanced_positions, f, indent=2)
    
    with open(review_output_path, 'w', encoding='utf-8') as f:
        json.dump(review_queue, f, indent=2)
    
    print(f"\n✅ Processed {len(enhanced_positions)} stories")
    print(f"⚠️  {len(review_queue)} stories need review")
    print(f"📄 Output: {output_path}")
    print(f"📋 Review: {review_output_path}")
### Document Processing
1. **Do you have source PDFs for existing 3 books?** (Need these to reprocess with accurate pages)
2. **Manual vs automated chunking preference?** 
   - Option A: Manual chunking with helper tools (accurate but time-consuming)
   - Option B: ML-based auto-detection + manual review (faster but may miss edge cases)
3. **Migration strategy for existing books?** 
   - Reprocess from PDF and re-do all manual categorization?
   - Or just enhance metadata and keep existing (inaccurate) page numbers?

### Metadata Extraction
4. **Preserve existing manually-curated keywords in christian_mysticism?** 
   - Merge with new extracted metadata, or keep as-is?
5. **Target number of keywords per story?** (Current thinking: 8-12)
6. **Historical periods for period_map dictionary?** 
   - Which periods are most important for your research use cases?
7. **Location gazetteer approach?**
   - Build manually from extracted locations (high accuracy, time-consuming)
   - Use GeoNames API (comprehensive, may have historical gaps)
   - Hybrid: Manual for top 100 locations, API for rest

### Implementation
8. **Priority order?** 
   - Phase 0 (PDF processing) first, then metadata extraction
   - Or implement all extraction modules first, add PDF processing later
9. **Testing approach?**
   - Process one new book end-to-end as pilot
   - Or build all modules, then test integrated pipeline
if __name__ == "__main__":
    book_dir = Path("books/ecology_of_souls_volume_i")
    
    # Load existing positions
    with open(book_dir / "story_positions.json", 'r') as f:
        positions = json.load(f)
    
    # Process
    process_book(
        full_text_path=str(book_dir / "Full_Text.md"),
        story_positions=positions,
        output_path=str(book_dir / "story_positions_enhanced.json"),
        review_output_path=str(book_dir / "manual_review.json")
    )
```

---

## Testing Strategy

### Unit Tests
```python
# tests/test_temporal_extraction.py
def test_century_extraction():
    text = "In the 17th century, demonic possessions were common."
    result = extract_temporal_metadata(text)
    assert 17 in result["centuries"]

def test_year_range_extraction():
    text = "From 1632 to 1634, the nuns were possessed."
    result = extract_temporal_metadata(text)
    assert set([1632, 1633, 1634]).issubset(set(result["years"]))

# tests/test_location_extraction.py
def test_hierarchical_location():
    text = "The events occurred in Loudun, France."
    result = extract_locations(text)
    assert "Loudun" in result["locations"]["cities"]
    assert "France" in result["locations"]["countries"]

# tests/test_topic_extraction.py
def test_possession_detection():
    text = "The demon possessed the young woman."
    result = extract_domain_topics(text)
    assert "possession" in result["phenomena"]
    assert "demonic" in result["entities"]

# tests/test_validation.py
def test_validation_catches_bad_years():
    metadata = {"temporal": {"years": [999, 3000]}}
    result = validate_story_metadata(metadata)
    assert len(result["warnings"]) > 0
```

### Integration Tests
```python
# tests/test_pipeline.py
def test_full_pipeline_on_sample_story():
    sample_story = {
        "title": "The Loudun Possessions",
        "start_char": 0,
        "end_char": 5000,
        "pages": "1-10"
    }
    
    content = "In 1632, the Ursuline nuns of Loudun, France were possessed..."
    
    # Run full pipeline
    enhanced = process_story(sample_story, content)
    
    # Verify all fields present
    assert "entities" in enhanced
    assert "temporal" in enhanced
    assert "topics" in enhanced
    assert "keywords" in enhanced
    
    # Verify specific extractions
    assert 17 in enhanced["temporal"]["centuries"]
    assert "France" in enhanced["entities"]["locations"]["countries"]
    assert "possession" in enhanced["topics"]["phenomena"]
```

---

## Rollout Plan

### Week 1: Core Extraction (Phases 1-3)
- Day 1-2: Implement temporal extraction + tests
- Day 3-4: Implement location extraction + build gazetteer
- Day 5: Implement topic extraction + domain patterns

### Week 2: Validation & Integration (Phases 4-7)
- Day 1-2: Build validation system + manual review workflow
- Day 3: Integrate keyword synthesis
- Day 4-5: Update search backend with filters

### Week 3: Testing & Frontend (Phase 8 + Testing)
- Day 1-2: Comprehensive testing (unit + integration)
- Day 3-4: Build frontend filter UI
- Day 5: Test end-to-end workflow

### Week 4: Backfill & Validation
- Day 1-3: Reprocess existing 3 books with new pipeline
- Day 4-5: Manual review queue processing

---

## Success Metrics

### Extraction Quality
- **Temporal**: 90%+ of stories with explicit dates have extracted years
- **Location**: 80%+ of stories with place names have extracted locations
- **Topics**: 85%+ of stories have relevant primary topics
- **Keywords**: Average 8-12 keywords per story (vs current 1-2)

### Search Accuracy
- Query: "France 17th century possession" → Returns Loudun stories in top 10
- Query: "Italy Renaissance apparitions" → Returns relevant Italian stories
- Query: "UFO 1960s United States" → Returns US UFO cases from 1960s

### Validation Coverage
- 100% of stories pass validation (no errors)
- <10% of stories flagged for manual review (warnings only)
- Manual review queue completable in <2 hours per book

---

## Dependencies & Requirements

### Python Packages
```txt
spacy>=3.7.0
python-dateutil>=2.8.0
```

### spaCy Model
```bash
python -m spacy download en_core_web_sm
```

### Data Files
- `location_hierarchy.json` - Gazetteer for location normalization
- `domain_patterns.json` - Domain-specific pattern dictionary

### Infrastructure
- No new infrastructure required
- Preprocessing runs in Google Colab or locally
- Search backend requires FAISS/FTS5 metadata updates only

---

## Risk Mitigation

### Risk 1: NER Extraction Quality
**Problem**: spaCy may miss historical/paranormal-specific entities

**Mitigation**:
- Build custom NER training data from existing books
- Fine-tune spaCy model on paranormal domain
- Fallback to pattern matching for common entities

### Risk 2: Gazetteer Completeness
**Problem**: Historical locations may not be in modern gazetteers

**Mitigation**:
- Start with manual gazetteer for top 100 locations
- Expand incrementally as new locations encountered
- Flag unknown locations in manual review queue

### Risk 3: Validation False Positives
**Problem**: Too many warnings → manual review bottleneck

**Mitigation**:
- Tune validation thresholds based on real data
- Prioritize warnings by severity
- Auto-fix common issues where possible

### Risk 4: Search Performance
**Problem**: Post-filtering on large result sets may be slow

**Mitigation**:
- Over-fetch results (limit*2) for filtering headroom
- Optimize metadata structure for fast filtering
- Future: Move filters to FAISS query itself (harder but faster)

---

## Next Steps

1. **Review this plan** - Confirm approach aligns with vision
2. **Prioritize phases** - Which phases to implement first?
3. **Start Phase 1** - Implement temporal extraction on sample stories
4. **Build test dataset** - Select 10-20 representative stories for testing
5. **Iterate** - Test, refine, expand to full books

**Estimated Total Implementation Time**: 30-40 hours
**Estimated Testing Time**: 10-15 hours
**Estimated Manual Review per Book**: 1-2 hours

---

## Questions for Discussion

1. Should we preserve existing manually-curated keywords in christian_mysticism?
2. What's the target number of keywords per story? (Current thinking: 8-12)
3. Which historical periods should be in the period_map dictionary?
4. Should we build location gazetteer manually or use external API (e.g., GeoNames)?
5. Priority order: Implement all extraction first, or implement + test phase by phase?
