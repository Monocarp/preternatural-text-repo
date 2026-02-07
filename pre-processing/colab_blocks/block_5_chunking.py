# ==================================================================================
# BLOCK 5: CHUNKING & EMBEDDING
# ==================================================================================
# This block chunks the full text with enhanced metadata for vector search

def chunk_full_md(full_md_path, positions, book_slug):
    """Chunk full text with enhanced metadata."""
    with open(full_md_path, encoding="utf-8") as f:
        txt = f.read()

    chunks = []
    pos = 0
    cid = 0

    # Extract page markers for page tracking
    page_splits = re.split(r"\s*\[?\s*Page\s*[:\s]*(\d+)\s*\]?\s*", txt, flags=re.IGNORECASE)
    page_map = {}
    char_offset = 0
    for i in range(1, len(page_splits), 2):
        page_num = int(page_splits[i])
        page_content = page_splits[i+1] if i+1 < len(page_splits) else ""
        page_map[char_offset] = page_num
        char_offset += len(page_content)

    def get_page_for_char(char_pos):
        pages = sorted(page_map.items())
        for i, (offset, page_num) in enumerate(pages):
            if i + 1 < len(pages):
                if offset <= char_pos < pages[i+1][0]:
                    return page_num
            else:
                if offset <= char_pos:
                    return page_num
        return 1

    while pos < len(txt):
        end = txt.find("\n\n", pos + 1800)
        if end == -1:
            end = len(txt)
        chunk = txt[pos:end]

        # Find which stories overlap with this chunk
        stories_in_chunk = []
        for t, p in positions.items():
            if p.get("start_char", -1) != -1 and p["start_char"] < end and p["end_char"] > pos:
                stories_in_chunk.append({
                    "title": t,
                    "start_char": max(pos, p["start_char"]),
                    "end_char": min(end, p["end_char"]),
                    "pages": p.get("pages", "Unknown"),
                    "keywords": p.get("keywords", []),
                    # Enhanced metadata
                    "temporal": p.get("temporal", {}),
                    "locations": p.get("locations", {}),
                    "topics": p.get("topics", {})
                })

        # Extract keywords from chunk content
        heading_matches = re.findall(r"# (.*?)\n", chunk)
        non_story_keywords = [h.lower() for h in heading_matches]

        if not non_story_keywords:
            word_counts = Counter(re.findall(r'\w+', chunk.lower()))
            non_story_keywords = [word for word, count in word_counts.most_common(5)]

        # Combine keywords from stories and chunk
        all_keywords = set(non_story_keywords)
        for story in stories_in_chunk:
            all_keywords.update(story.get("keywords", [])[:5])

        keywords_str = ", ".join(list(all_keywords)[:10]) if all_keywords else ""

        # Determine page range
        start_page = get_page_for_char(pos)
        end_page = get_page_for_char(end)
        pages_str = str(start_page) if start_page == end_page else f"{start_page}-{end_page}"

        # Aggregate temporal/location/topic data from stories in chunk
        chunk_centuries = set()
        chunk_countries = set()
        chunk_topics = set()
        for story in stories_in_chunk:
            chunk_centuries.update(story.get("temporal", {}).get("centuries", []))
            chunk_countries.update(story.get("locations", {}).get("countries", []))
            chunk_topics.update(story.get("topics", {}).get("primary", []))

        meta = {
            "book": book_slug,
            "source": book_slug.replace('_', ' '),
            "chunk_id": f"{book_slug}_{cid}",
            "type": "chunk",
            "has_story": bool(stories_in_chunk),
            "pages": pages_str,
            "keywords": keywords_str,
            # Enhanced metadata
            "centuries": list(chunk_centuries),
            "countries": list(chunk_countries),
            "topics": list(chunk_topics)
        }

        if stories_in_chunk:
            meta["stories"] = stories_in_chunk

        if keywords_str:
            chunk = chunk.strip() + "\n\nKeywords: " + keywords_str

        chunks.append(Document(content=chunk, meta=meta))
        pos = end
        cid += 1

    return chunks
