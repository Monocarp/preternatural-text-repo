"""
Retrofit Existing Books - Metadata Enhancement Only

This script adds rich metadata (temporal, locations, topics) to existing 
story_positions.json files WITHOUT changing boundaries, titles, or story lists.

Safety constraints:
- Does NOT modify start_char or end_char
- Does NOT add or delete stories
- Does NOT change story titles
- Does NOT touch the database
- Only ADDS new metadata fields

Usage:
    python retrofit_existing_books.py <book_slug>
    python retrofit_existing_books.py operation_trojan_horse --dry-run
"""

import os
import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path to import Block 3 functions
sys.path.insert(0, str(Path(__file__).parent))

# Import metadata extraction functions from Block 3
try:
    # These need to be available from your colab_blocks
    from colab_blocks.block_3_metadata_extraction import (
        extract_temporal,
        extract_locations_with_grok,
        extract_domain_topics,
        synthesize_keywords,
        calculate_confidence,
        generate_warnings
    )
    print("✓ Loaded metadata extraction functions from Block 3")
except ImportError as e:
    print(f"✗ Failed to import Block 3 functions: {e}")
    print("\nMake sure you have the Block 3 colab script in colab_blocks/")
    sys.exit(1)


def load_full_text(book_path: Path) -> str:
    """Load Full_Text.md for a book."""
    full_text_path = book_path / "Full_Text.md"
    if not full_text_path.exists():
        raise FileNotFoundError(f"Full_Text.md not found at {full_text_path}")
    
    with open(full_text_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_story_positions(book_path: Path) -> dict:
    """Load existing story_positions.json."""
    positions_path = book_path / "story_positions.json"
    if not positions_path.exists():
        raise FileNotFoundError(f"story_positions.json not found at {positions_path}")
    
    with open(positions_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_story_positions(book_path: Path, positions: dict, dry_run: bool = False):
    """Save updated story_positions.json."""
    positions_path = book_path / "story_positions.json"
    
    if dry_run:
        print(f"\n[DRY RUN] Would save to: {positions_path}")
        return
    
    # Create backup first
    backup_path = book_path / "story_positions.json.backup"
    if positions_path.exists():
        import shutil
        shutil.copy2(positions_path, backup_path)
        print(f"✓ Backup created: {backup_path}")
    
    with open(positions_path, 'w', encoding='utf-8') as f:
        json.dump(positions, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Saved updated positions to: {positions_path}")


def extract_story_metadata(story_text: str, title: str, existing_keywords: list) -> dict:
    """
    Extract metadata for a single story.
    
    Args:
        story_text: The full story text
        title: Story title
        existing_keywords: Current keywords (preserved)
    
    Returns:
        Dictionary with temporal, locations, topics, keywords, confidence, warnings
    """
    print(f"  → Extracting temporal data...")
    temporal = extract_temporal(story_text)
    
    print(f"  → Extracting locations...")
    locations = extract_locations_with_grok(story_text)
    
    print(f"  → Extracting topics...")
    topics = extract_domain_topics(story_text)
    
    print(f"  → Synthesizing keywords...")
    keywords = synthesize_keywords(title, temporal, locations, topics, existing_keywords)
    
    print(f"  → Calculating confidence...")
    confidence = calculate_confidence(temporal, locations, topics)
    
    warnings = generate_warnings(temporal, locations, topics)
    
    return {
        "temporal": temporal,
        "locations": locations,
        "topics": topics,
        "keywords": keywords,
        "confidence": confidence,
        "warnings": warnings,
        "status": "OK" if confidence > 0.5 else "REVIEW"
    }


def retrofit_book(book_slug: str, books_dir: str = "books", dry_run: bool = False):
    """
    Retrofit a single book with enhanced metadata.
    
    Args:
        book_slug: The book directory name
        books_dir: Root books directory
        dry_run: If True, don't save changes
    """
    book_path = Path(books_dir) / book_slug
    
    if not book_path.exists():
        print(f"✗ Book directory not found: {book_path}")
        return False
    
    print(f"\n{'='*60}")
    print(f"RETROFITTING: {book_slug}")
    print(f"{'='*60}")
    
    # Load data
    print("\n1. Loading existing data...")
    try:
        full_text = load_full_text(book_path)
        positions = load_story_positions(book_path)
        print(f"  ✓ Loaded {len(positions)} stories")
        print(f"  ✓ Full text: {len(full_text):,} characters")
    except Exception as e:
        print(f"  ✗ Failed to load data: {e}")
        return False
    
    # Process each story
    print("\n2. Extracting metadata for each story...")
    updated_count = 0
    skipped_count = 0
    
    for idx, (title, pos) in enumerate(positions.items(), 1):
        print(f"\n[{idx}/{len(positions)}] {title}")
        
        # Validate boundaries
        start = pos.get("start_char", -1)
        end = pos.get("end_char", -1)
        
        if start == -1 or end == -1:
            print(f"  ⚠️  Missing boundaries, skipping...")
            skipped_count += 1
            continue
        
        if start >= end:
            print(f"  ⚠️  Invalid boundaries (start >= end), skipping...")
            skipped_count += 1
            continue
        
        # Extract story text
        story_text = full_text[start:end].strip()
        if not story_text:
            print(f"  ⚠️  Empty story text, skipping...")
            skipped_count += 1
            continue
        
        # Check if already has metadata
        if "temporal" in pos and "locations" in pos and "topics" in pos:
            print(f"  ℹ️  Already has metadata, skipping...")
            skipped_count += 1
            continue
        
        # Extract metadata
        try:
            existing_keywords = pos.get("keywords", [])
            metadata = extract_story_metadata(story_text, title, existing_keywords)
            
            # Add metadata to position dict (preserve existing fields)
            pos["temporal"] = metadata["temporal"]
            pos["locations"] = metadata["locations"]
            pos["topics"] = metadata["topics"]
            pos["keywords"] = metadata["keywords"]
            pos["confidence"] = metadata["confidence"]
            pos["status"] = metadata["status"]
            
            if metadata["warnings"]:
                pos["warnings"] = metadata["warnings"]
            
            # Print summary
            print(f"  ✓ Confidence: {metadata['confidence']:.2f}")
            print(f"  ✓ Years: {metadata['temporal']['years'][:3]}")
            print(f"  ✓ Locations: {metadata['locations'].get('cities', [])[:3]}")
            print(f"  ✓ Topics: {metadata['topics']['primary'][:3]}")
            
            updated_count += 1
            
        except Exception as e:
            print(f"  ✗ Extraction failed: {e}")
            skipped_count += 1
            continue
    
    # Save results
    print(f"\n3. Saving results...")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped: {skipped_count}")
    
    if updated_count > 0:
        save_story_positions(book_path, positions, dry_run=dry_run)
    else:
        print("  No changes to save.")
    
    print(f"\n{'='*60}")
    print(f"✓ RETROFIT COMPLETE: {book_slug}")
    print(f"{'='*60}\n")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Retrofit existing books with enhanced metadata"
    )
    parser.add_argument(
        "book_slug",
        help="Book slug to retrofit (e.g., operation_trojan_horse)"
    )
    parser.add_argument(
        "--books-dir",
        default="../books",
        help="Root books directory (default: ../books)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't save changes, just preview"
    )
    
    args = parser.parse_args()
    
    # Check if books directory exists
    books_path = Path(args.books_dir)
    if not books_path.exists():
        print(f"✗ Books directory not found: {books_path}")
        print(f"  Current directory: {os.getcwd()}")
        print(f"  Try: cd pre-processing && python retrofit_existing_books.py {args.book_slug}")
        sys.exit(1)
    
    # Run retrofit
    success = retrofit_book(args.book_slug, args.books_dir, args.dry_run)
    
    if not success:
        sys.exit(1)
    
    if args.dry_run:
        print("\n⚠️  DRY RUN - No files were modified")
        print("Remove --dry-run to apply changes")


if __name__ == "__main__":
    main()
