# ==================================================================================
# BLOCK RETROFIT: ADD METADATA TO EXISTING BOOKS
# ==================================================================================
# This block retrofits existing story_positions.json files with rich metadata
# WITHOUT changing boundaries, titles, or story lists.
#
# SAFETY: Creates .backup files before modifying anything

def retrofit_existing_book(book_slug: str, dry_run: bool = False):
    """
    Retrofit a single book with enhanced metadata.
    
    Args:
        book_slug: The book directory name (e.g., "operation_trojan_horse")
        dry_run: If True, show what would be done without saving
    """
    import json
    import shutil
    from pathlib import Path
    
    book_path = Path(books_dir) / book_slug
    
    if not book_path.exists():
        print(f"✗ Book directory not found: {book_path}")
        return False
    
    print(f"\n{'='*60}")
    print(f"RETROFITTING: {book_slug}")
    print(f"{'='*60}")
    
    # 1. Load existing data
    print("\n1. Loading existing data...")
    full_text_path = book_path / "Full_Text.md"
    positions_path = book_path / "story_positions.json"
    
    if not full_text_path.exists():
        print(f"✗ Full_Text.md not found")
        return False
    
    if not positions_path.exists():
        print(f"✗ story_positions.json not found")
        return False
    
    with open(full_text_path, 'r', encoding='utf-8') as f:
        full_text = f.read()
    
    with open(positions_path, 'r', encoding='utf-8') as f:
        positions = json.load(f)
    
    print(f"  ✓ Loaded {len(positions)} stories")
    print(f"  ✓ Full text: {len(full_text):,} characters")
    
    # 2. Process each story
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
        
        # Check if already has metadata
        if "temporal" in pos and "locations" in pos and "topics" in pos:
            print(f"  ℹ️  Already has metadata, skipping...")
            skipped_count += 1
            continue
        
        # Extract story text
        story_text = full_text[start:end].strip()
        if not story_text:
            print(f"  ⚠️  Empty story text, skipping...")
            skipped_count += 1
            continue
        
        # Extract metadata using Block 3 functions
        try:
            print(f"  → Extracting temporal data...")
            temporal = extract_temporal(story_text)
            
            print(f"  → Extracting locations...")
            # Use location cache if available
            location_cache = globals().get('location_cache', {})
            locations = extract_and_normalize_locations(story_text, title, location_cache)
            # Update global cache
            globals()['location_cache'] = location_cache
            
            print(f"  → Extracting topics...")
            topics = extract_domain_topics(story_text)
            
            print(f"  → Synthesizing keywords...")
            existing_keywords = pos.get("keywords", [])
            keywords = synthesize_keywords(title, temporal, locations, topics, existing_keywords)
            
            print(f"  → Calculating confidence...")
            confidence = calculate_confidence(temporal, locations, topics)
            warnings = generate_warnings(temporal, locations, topics)
            
            # Add metadata to position dict (PRESERVE all existing fields)
            pos["temporal"] = temporal
            pos["locations"] = locations
            pos["topics"] = topics
            pos["keywords"] = keywords
            pos["confidence"] = confidence
            pos["status"] = "OK" if confidence > 0.5 else "REVIEW"
            
            if warnings:
                pos["warnings"] = warnings
            
            # Print summary
            print(f"  ✓ Confidence: {confidence:.2f}")
            print(f"  ✓ Years: {temporal['years'][:3]}")
            print(f"  ✓ Locations: {locations.get('cities', [])[:3]}")
            print(f"  ✓ Topics: {topics['primary'][:3]}")
            
            updated_count += 1
            
        except Exception as e:
            print(f"  ✗ Extraction failed: {e}")
            import traceback
            traceback.print_exc()
            skipped_count += 1
            continue
    
    # 3. Save results
    print(f"\n3. Saving results...")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped: {skipped_count}")
    
    if updated_count == 0:
        print("  No changes to save.")
        return True
    
    if dry_run:
        print(f"\n[DRY RUN] Would save to: {positions_path}")
        print("Remove dry_run=True to apply changes")
        return True
    
    # Create backup
    backup_path = book_path / "story_positions.json.backup"
    shutil.copy2(positions_path, backup_path)
    print(f"✓ Backup created: {backup_path.name}")
    
    # Save updated positions
    with open(positions_path, 'w', encoding='utf-8') as f:
        json.dump(positions, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved updated positions")
    
    # Download the file
    try:
        files.download(str(positions_path))
        print(f"✓ Downloaded: {positions_path.name}")
    except:
        print(f"⚠️  Could not auto-download, manually download: {positions_path}")
    
    print(f"\n{'='*60}")
    print(f"✓ RETROFIT COMPLETE: {book_slug}")
    print(f"{'='*60}\n")
    
    return True


# ==================================================================================
# USAGE EXAMPLES - UNCOMMENT TO RUN:
# ==================================================================================

# Test run (no changes):
# retrofit_existing_book("operation_trojan_horse", dry_run=True)

# Apply changes to one book:
# retrofit_existing_book("operation_trojan_horse")

# Process all three existing books:
# retrofit_existing_book("christian_mysticism_vol_iv")
# retrofit_existing_book("ecology_of_souls_volume_i")
# retrofit_existing_book("operation_trojan_horse")
