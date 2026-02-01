# ==================================================================================
# BLOCK 4: STORY POSITION LOCATION & METADATA ENHANCEMENT
# ==================================================================================
# This block locates stories in the full text and extracts enhanced metadata

def normalize(text):
    """Normalize text for comparison."""
    text = re.sub(r"<.*?>", "", text)
    text = re.sub(r"\"[^\"]+\" Pages? \d+(-\d+)?", "", text)
    text = re.sub(r"[,:;.!?–—]", "", text)
    return re.sub(r"\s+", " ", text.strip().lower())


def parse_index_md(path, titles, slug):
    """Parse index markdown for additional metadata."""
    if not os.path.exists(path):
        return {t: {"pages": "Unknown", "keywords": []} for t in titles}
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    data = {}
    for line in txt.splitlines():
        m = re.match(r"^(.*?) - (\d+)(?:-(\d+))?$", line.strip())
        if m:
            desc = m.group(1).strip()
            pages = m.group(2) if not m.group(3) else f"{m.group(2)}-{m.group(3)}"
            keywords = [desc.lower()]
            if "demon" in desc.lower():
                keywords.extend(["possession", "demonic possession"])
            elif "witch" in desc.lower():
                keywords.append("witch trials")
            data[desc] = {"pages": pages, "keywords": keywords}
    result = {}
    for t in titles:
        best, ratio = None, 0
        nt = re.sub(r"[^\w\s]", "", t.lower())
        for k in data:
            nk = re.sub(r"[^\w\s]", "", k.lower())
            r = difflib.SequenceMatcher(None, nt, nk).ratio()
            if r > ratio and r > 0.5:
                ratio, best = r, k
        result[t] = data.get(best, {"pages": "Unknown", "keywords": [re.sub(r"[^\w\s]", "", t.lower())]}) if best else {"pages": "Unknown", "keywords": [re.sub(r"[^\w\s]", "", t.lower())]}
    return result


def locate_story_positions(full_md_path, stories_md_path, index_md_path, book_slug, book_path):
    """Locate story positions in full text and extract basic metadata."""
    with open(full_md_path, encoding="utf-8") as f:
        full_md = f.read()
    with open(stories_md_path, encoding="utf-8") as f:
        stories_md = f.read()

    # Extract individual stories from Stories.md
    blocks = re.finditer(
        r'<div align="center"><b>(.*?)</b></div>\s*'
        r'(?:<div align="center">"[^"]+" Pages? ([^<]+?)</div>\s*)?'
        r'(.*?)(?=<div align="center"><b>|$)',
        stories_md, flags=re.IGNORECASE | re.DOTALL
    )
    stories = []
    for m in blocks:
        title = m.group(1).strip()
        pages = m.group(2).strip() if m.group(2) else "Unknown"
        content = m.group(3).strip()
        stories.append({"title": title, "pages": pages, "content": content})
        print(f"Parsed: {title} ({len(content)} chars)")

    index_data = parse_index_md(index_md_path, [s["title"] for s in stories], book_slug)
    positions = {}

    for s in stories:
        title = s["title"]
        content = s["content"].strip()

        # 1. Try exact match first
        start = full_md.find(content)
        if start != -1:
            end = start + len(content)
            verbatim = content
        else:
            # 2. Fallback: fuzzy alignment with sliding window
            start_guess = full_md.find(content[:200])
            if start_guess == -1:
                start = end = -1
                verbatim = ""
            else:
                best_s = best_e = start_guess
                best_r = 0
                norm_c = normalize(content)
                for ds in range(-500, 501, 50):
                    for de in range(-500, 1001, 100):
                        ts = start_guess + ds
                        te = start_guess + len(content) + de
                        if ts < 0 or te > len(full_md) or te <= ts:
                            continue
                        r = difflib.SequenceMatcher(None, normalize(full_md[ts:te]), norm_c).ratio()
                        if r > best_r:
                            best_r, best_s, best_e = r, ts, te
                start, end, verbatim = best_s, best_e, full_md[best_s:best_e]

        story_meta = index_data.get(title, {"pages": "Unknown", "keywords": []})
        final_pages = s["pages"] if s["pages"] != "Unknown" else story_meta.get("pages", "Unknown")
        final_keywords = story_meta.get("keywords", [])
        if not final_keywords:
            final_keywords = [re.sub(r"[^\w\s]", "", title.lower())]

        positions[title] = {
            "start_char": int(start) if start != -1 else -1,
            "end_char": int(end) if end != -1 else -1,
            "pages": final_pages,
            "keywords": final_keywords,
            "verbatim": verbatim
        }

    return positions, full_md


def extract_structured_metadata(positions: Dict, full_md: str, book_slug: str, book_path: str) -> Tuple[Dict, List]:
    """
    Extract structured metadata (temporal, locations, topics) for each story.
    Returns enhanced positions dict and review queue.
    """
    print(f"\n{'='*60}")
    print("EXTRACTING STRUCTURED METADATA")
    print(f"{'='*60}")
    
    # Load location cache
    location_cache = load_location_cache()
    initial_cache_size = len(location_cache)
    
    enhanced_positions = {}
    review_queue = []
    
    total = len([p for p in positions.values() if p.get("start_char", -1) != -1])
    processed = 0
    
    for title, pos in positions.items():
        if pos.get("start_char", -1) == -1:
            enhanced_positions[title] = pos
            continue
        
        processed += 1
        print(f"\n[{processed}/{total}] {title[:50]}...")
        
        content = full_md[pos["start_char"]:pos["end_char"]]
        
        # 1. Temporal extraction
        temporal = extract_temporal(content)
        print(f"  Temporal: {len(temporal.get('years', []))} years, {len(temporal.get('centuries', []))} centuries")
        
        # 2. Location extraction + normalization
        locations = extract_and_normalize_locations(content, title, location_cache)
        print(f"  Locations: {len(locations.get('cities', []))} cities, {len(locations.get('countries', []))} countries")
        
        # 3. Topic extraction
        topics = extract_domain_topics(content)
        print(f"  Topics: {topics.get('primary', [])}")
        
        # 4. Synthesize keywords
        keywords = synthesize_keywords(title, temporal, locations, topics, pos.get("keywords", []))
        
        # 5. Calculate confidence
        confidence = calculate_confidence(temporal, locations, topics)
        status = "AUTO_APPROVED" if confidence >= 0.75 else "NEEDS_REVIEW"
        print(f"  Confidence: {confidence:.2f} → {status}")
        
        # 6. Build enhanced entry
        enhanced = {
            **pos,
            "temporal": temporal,
            "locations": {
                "cities": locations.get("cities", []),
                "regions": locations.get("regions", []),
                "countries": locations.get("countries", [])
            },
            "topics": topics,
            "keywords": keywords,
            "confidence": round(confidence, 2),
            "status": status
        }
        
        # 7. Generate warnings and add to review queue if needed
        if confidence < 0.75:
            warnings = generate_warnings(temporal, locations, topics)
            review_queue.append({
                "title": title,
                "confidence": round(confidence, 2),
                "warnings": warnings,
                "extracted": {
                    "temporal": temporal,
                    "locations": locations,
                    "topics": topics
                },
                "current_keywords": keywords
            })
        
        enhanced_positions[title] = enhanced
    
    # Save updated location cache
    if len(location_cache) > initial_cache_size:
        save_location_cache(location_cache)
        print(f"\nLocation cache updated: {initial_cache_size} → {len(location_cache)} entries")
    
    print(f"\n{'='*60}")
    print(f"METADATA EXTRACTION COMPLETE")
    print(f"  Processed: {processed} stories")
    print(f"  Auto-approved: {processed - len(review_queue)}")
    print(f"  Needs review: {len(review_queue)}")
    print(f"{'='*60}")
    
    return enhanced_positions, review_queue


def save_review_queue(review_queue: List, book_path: str, book_slug: str):
    """Save review queue to file for manual review."""
    if not review_queue:
        print("No stories need manual review!")
        return
    
    review_file = os.path.join(book_path, "manual_review.json")
    
    review_data = {
        "book_slug": book_slug,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "confidence_threshold": 0.75,
        "total_flagged": len(review_queue),
        "instructions": """
MANUAL REVIEW INSTRUCTIONS:
1. Review each flagged story below
2. Check warnings and verify extracted metadata
3. Edit story_positions.json directly to fix issues:
   - Add missing years/centuries to temporal
   - Add missing cities/countries to locations  
   - Add missing topics
4. After fixing, change status from "NEEDS_REVIEW" to "REVIEWED"
5. Re-run indexing to update search
        """,
        "stories": review_queue
    }
    
    with open(review_file, "w", encoding="utf-8") as f:
        json.dump(review_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n📋 Review file saved: {review_file}")
    files.download(review_file)
