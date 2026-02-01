# ==================================================================================
# BLOCK RETROFIT OPTIMIZED: ADD METADATA TO EXISTING BOOKS (FAST VERSION)
# ==================================================================================
# Optimizations:
# 1. Combined Grok call for locations + topics (2 calls → 1 call)
# 2. Parallel processing with threading (5 stories at once)
# 3. Same quality - just more efficient

import concurrent.futures
from typing import Dict, List, Tuple

def extract_metadata_combined(story_text: str, title: str) -> Tuple[Dict, Dict]:
    """
    Extract locations AND topics in a single Grok call.
    Returns: (locations_dict, topics_dict)
    """
    try:
        client = globals().get('grok_client')
        model = globals().get('GROK_MODEL', 'grok-4-1-fast-reasoning')
        if not client:
            return {}, {}
    except Exception:
        return {}, {}
    
    prompt = f"""Analyze this supernatural/historical story titled "{title}" and extract metadata.

Text (first 1200 chars):
{story_text[:1200]}

Extract and return ONLY a JSON object with this structure:
{{
  "locations": [
    {{"name": "Loudun", "type": "city", "country": "France", "confidence": 0.95}},
    {{"name": "Rhineland", "type": "region", "country": "Germany", "confidence": 0.9}}
  ],
  "topics": {{
    "phenomena": ["possession", "levitation"],
    "entities": ["demon", "nun"],
    "context": ["exorcism", "monastery"],
    "functional_purpose": ["protection", "spiritual_warfare"],
    "people": ["Father Surin", "Sister Jeanne"],
    "historical_groups": ["Ursuline nuns"],
    "implements": ["holy_water", "crucifix"]
  }}
}}

LOCATION RULES:
- Include cities, regions, countries, religious sites
- Confidence: 0-1 (0.7+ for clear mentions, 0.5-0.7 for inferred)
- Return [] if no locations found

TOPIC RULES:
- phenomena: supernatural events (possession, apparition, bilocation, etc.)
- entities: beings involved (demon, angel, saint, ghost, etc.)
- context: circumstances (exorcism, prayer, vision, etc.)
- functional_purpose: what the story teaches (protection, discernment, spiritual_warfare, etc.)
- people: Named individuals (saints, witnesses, subjects)
- historical_groups: Orders, movements, groups
- implements: Objects used (relics, holy_water, crucifix, etc.)

Return ONLY the JSON, no other text."""

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Extract JSON
        if "```json" in result_text:
            import re
            result_text = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
            if result_text:
                result_text = result_text.group(1)
        elif "```" in result_text:
            import re
            result_text = re.search(r'```\s*(.*?)\s*```', result_text, re.DOTALL)
            if result_text:
                result_text = result_text.group(1)
        
        import json
        data = json.loads(result_text)
        
        # Process locations
        locations_list = data.get("locations", [])
        cities = []
        regions = []
        countries = set()
        
        for loc in locations_list:
            if loc.get("confidence", 0) >= 0.5:
                loc_type = loc.get("type", "").lower()
                name = loc.get("name")
                
                if loc_type == "city":
                    cities.append(name)
                    if loc.get("country"):
                        countries.add(loc["country"])
                elif loc_type == "region":
                    regions.append(name)
                    if loc.get("country"):
                        countries.add(loc["country"])
                elif loc_type == "country":
                    countries.add(name)
        
        locations = {
            "cities": list(set(cities)),
            "regions": list(set(regions)),
            "countries": sorted(list(countries)),
            "raw_mentions": [loc.get("name") for loc in locations_list],
            "normalized": locations_list
        }
        
        # Process topics
        topics_data = data.get("topics", {})
        primary = (topics_data.get("phenomena", []) + 
                  topics_data.get("context", []) + 
                  topics_data.get("functional_purpose", []))
        secondary = (topics_data.get("entities", []) + 
                    topics_data.get("implements", []) + 
                    topics_data.get("people", []) + 
                    topics_data.get("historical_groups", []))
        
        topics = {
            "primary": [x.lower() for x in primary if x],
            "secondary": [x.lower() for x in secondary if x],
            "raw_analysis": topics_data
        }
        
        return locations, topics
        
    except Exception as e:
        print(f"  ✗ Combined extraction failed: {e}")
        return {}, {}


def process_single_story(title: str, pos: Dict, full_text: str, idx: int, total: int) -> Tuple[str, Dict, bool]:
    """
    Process a single story. Returns (title, updated_pos, success).
    """
    import json
    
    # Validate boundaries
    start = pos.get("start_char", -1)
    end = pos.get("end_char", -1)
    
    if start == -1 or end == -1 or start >= end:
        return (title, pos, False)
    
    # Check if already has metadata
    if "temporal" in pos and "locations" in pos and "topics" in pos:
        return (title, pos, False)
    
    # Extract story text
    story_text = full_text[start:end].strip()
    if not story_text:
        return (title, pos, False)
    
    try:
        # Extract temporal (fast, mostly regex)
        temporal = extract_temporal(story_text)
        
        # Extract locations + topics in ONE call
        locations, topics = extract_metadata_combined(story_text, title)
        
        if not locations or not topics:
            return (title, pos, False)
        
        # Synthesize keywords
        existing_keywords = pos.get("keywords", [])
        keywords = synthesize_keywords(title, temporal, locations, topics, existing_keywords)
        
        # Calculate confidence
        confidence = calculate_confidence(temporal, locations, topics)
        warnings = generate_warnings(temporal, locations, topics)
        
        # Update position dict (preserve existing fields)
        pos["temporal"] = temporal
        pos["locations"] = locations
        pos["topics"] = topics
        pos["keywords"] = keywords
        pos["confidence"] = confidence
        pos["status"] = "OK" if confidence > 0.5 else "REVIEW"
        
        if warnings:
            pos["warnings"] = warnings
        
        return (title, pos, True)
        
    except Exception as e:
        print(f"  [{idx}/{total}] {title}: ✗ {str(e)[:50]}")
        return (title, pos, False)


def retrofit_existing_book_fast(book_slug: str, dry_run: bool = False, max_workers: int = 5):
    """
    Optimized retrofit with parallel processing and combined API calls.
    
    Args:
        book_slug: Book directory name
        dry_run: If True, don't save changes
        max_workers: Number of parallel workers (default 5, adjust based on API rate limits)
    """
    import json
    import shutil
    from pathlib import Path
    
    book_path = Path(books_dir) / book_slug
    
    if not book_path.exists():
        print(f"✗ Book directory not found: {book_path}")
        return False
    
    print(f"\n{'='*60}")
    print(f"RETROFITTING (OPTIMIZED): {book_slug}")
    print(f"{'='*60}")
    
    # Load data
    print("\n1. Loading existing data...")
    full_text_path = book_path / "Full_Text.md"
    positions_path = book_path / "story_positions.json"
    
    if not full_text_path.exists() or not positions_path.exists():
        print(f"✗ Missing required files")
        return False
    
    with open(full_text_path, 'r', encoding='utf-8') as f:
        full_text = f.read()
    
    with open(positions_path, 'r', encoding='utf-8') as f:
        positions = json.load(f)
    
    print(f"  ✓ Loaded {len(positions)} stories")
    print(f"  ✓ Full text: {len(full_text):,} characters")
    
    # Process stories in parallel
    print(f"\n2. Extracting metadata (parallel processing with {max_workers} workers)...")
    
    updated_count = 0
    skipped_count = 0
    
    stories_to_process = list(positions.items())
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all stories
        futures = {
            executor.submit(process_single_story, title, pos, full_text, idx, len(stories_to_process)): title
            for idx, (title, pos) in enumerate(stories_to_process, 1)
        }
        
        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            title, updated_pos, success = future.result()
            
            if success:
                positions[title] = updated_pos
                updated_count += 1
                
                # Print summary
                conf = updated_pos.get("confidence", 0)
                years = updated_pos.get("temporal", {}).get("years", [])
                cities = updated_pos.get("locations", {}).get("cities", [])
                topics = updated_pos.get("topics", {}).get("primary", [])
                
                print(f"  ✓ {title[:50]}... | Conf: {conf:.2f} | Years: {years[:2]} | Cities: {cities[:2]}")
            else:
                skipped_count += 1
    
    # Save results
    print(f"\n3. Saving results...")
    print(f"  Updated: {updated_count}")
    print(f"  Skipped: {skipped_count}")
    
    if updated_count == 0:
        print("  No changes to save.")
        return True
    
    if dry_run:
        print(f"\n[DRY RUN] Would save to: {positions_path}")
        return True
    
    # Create backup
    backup_path = book_path / "story_positions.json.backup"
    shutil.copy2(positions_path, backup_path)
    print(f"✓ Backup created: {backup_path.name}")
    
    # Save
    with open(positions_path, 'w', encoding='utf-8') as f:
        json.dump(positions, f, indent=2, ensure_ascii=False)
    print(f"✓ Saved updated positions")
    
    # Download
    try:
        files.download(str(positions_path))
        print(f"✓ Downloaded: {positions_path.name}")
    except:
        print(f"⚠️  Could not auto-download")
    
    print(f"\n{'='*60}")
    print(f"✓ RETROFIT COMPLETE: {book_slug}")
    print(f"{'='*60}\n")
    
    return True


# ==================================================================================
# USAGE - UNCOMMENT TO RUN:
# ==================================================================================

# Test (no changes, no parallel):
# retrofit_existing_book_fast("operation_trojan_horse", dry_run=True, max_workers=1)

# Full run with 5 parallel workers:
# retrofit_existing_book_fast("operation_trojan_horse", max_workers=5)

# Conservative (3 workers if you hit rate limits):
# retrofit_existing_book_fast("operation_trojan_horse", max_workers=3)
