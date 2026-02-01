# Keywords Analysis - Current State and Recommendations

## Current Implementation

### How Keywords Are Generated (Pre-processing)
1. **Primary Source**: Manual `grouped_index.md` file (index entries with page numbers)
   - Uses fuzzy matching to link index entries to story titles
   - Example: "Saint Walbert - 3-4" → keywords extracted from description
   
2. **Fallback**: Story title (lowercased)
   - Used when no index match found
   - Results in keywords like: `["teenaged boy sees his deceased father emerge from a ufo"]`
   
3. **Domain Enhancement** (minimal):
   - "demon" → adds "possession", "demonic possession"
   - "witch" → adds "witch trials"

### Keyword Quality by Book
- **christian_mysticism_vol_iv**: 90% have multiple meaningful keywords
  - Example: `["Saint Walbert", "15th Century", "Volombrosa", "Naples", "Italy", "Monastery", "Healings", "Exorcism", "Possession", "Blessed Virgin Mary", "Demonic Manifestation", "Relics"]`
  - **These are high-quality, manually curated keywords from the index file**

- **ecology_of_souls_volume_i**: 0% have multiple keywords
  - Keywords are just lowercased titles: `["teenaged boy sees his deceased father emerge from a ufo"]`
  - **No value over the title itself**

- **operation_trojan_horse**: 0% have multiple keywords
  - Same as ecology - just lowercased titles

### How Keywords Are Used

**In Search:**
1. **Keyword Search (FTS5 BM25)**: Keywords ARE indexed and searchable
   - Stored in separate column alongside content
   - BM25 ranks matches in keywords + content
   
2. **Semantic Search (FAISS)**: Keywords NOT used
   - Only embedded story content matters
   
3. **Hybrid Search**: FTS5 portion uses keywords, FAISS portion ignores them

**In UI:**
- Displayed in story cards and detail views
- User-editable in BookDetail and Archive pages
- Shows next to story title in lists

### Storage Locations
1. `books/{slug}/story_positions.json` - Array of strings
2. PostgreSQL `stories.keywords` - Comma-separated string
3. FAISS metadata - String (display only)
4. FTS5 database - Indexed column (searchable)

## Analysis Results

### Keywords That Add Value
✅ **christian_mysticism_vol_iv** - Rich, manually curated keywords
   - Multiple domain-specific terms per story
   - Geographic locations, time periods, saint names
   - Type of activity (exorcism, healing, possession)
   - **These DO add search value beyond the title**

### Keywords That Don't Add Value
❌ **ecology_of_souls** & **operation_trojan_horse** - Just lowercased titles
   - No additional information beyond what's in the title
   - Already searchable via title field
   - **These are redundant and wasteful**

## Recommendations

### Option 1: Remove Keywords Entirely ❌ NOT RECOMMENDED
**Pros:**
- Simplifies codebase
- Removes redundant data for 2/3 of books

**Cons:**
- Loses valuable manual curation for christian_mysticism
- Removes ability to add curated keywords in future
- Search would rely only on title + content

### Option 2: Keep Keywords, Improve Generation ✅ RECOMMENDED
**Improve preprocessing to generate meaningful keywords from story content:**

1. **Extract Named Entities** (using spaCy NER):
   - People: "Saint Walbert", "Cajetanus", "Jimmy Hoffa"
   - Places: "Naples", "Minnesota", "Tower of London"
   - Organizations: "Monastery", "Air Force"
   - Dates: "March 8, 1967", "15th Century"

2. **Extract Domain-Specific Terms** (pattern matching):
   - Paranormal: demon, ghost, spirit, apparition, possession, exorcism, UFO, alien
   - Actions: levitation, manifestation, haunting, abduction
   - Religious: saint, monastery, Virgin Mary, relics

3. **Keep Manual Index Keywords** where they exist
   - christian_mysticism has great manual keywords
   - Preserve these for books that have them

4. **Auto-enhance with Categories** (from codex_tree assignments)
   - If story is in "Demonic Activity/Possession" → add "possession", "demonic"
   - Leverages user categorization work

### Option 3: Hybrid Approach ✅ ALSO GOOD
**Keep keywords but make them optional:**
- For books WITH good index files → use rich keywords
- For books WITHOUT → leave keywords empty or minimal
- Update UI to show keywords only when meaningful
- Search would work fine without keywords (title + content still indexed)

## Impact on Search Quality

### Current State:
- **Hybrid/Keyword search**: Keywords provide minimal boost for ecology/trojan (redundant with title)
- **Semantic search**: Keywords have zero impact (only embeddings matter)
- **For christian_mysticism**: Keywords DO help keyword search find "exorcism", "relics", "Naples" etc.

### If Keywords Removed:
- **Minimal impact** for ecology/trojan books (already searchable via title)
- **Some loss** for christian_mysticism (manual keywords are valuable)
- Content embeddings would still capture semantic meaning

### If Keywords Improved:
- **Significant boost** for keyword/hybrid search
- Named entities become searchable: "What stories mention Jimmy Hoffa?"
- Location searches: "Stories in Naples"
- Time period searches: "15th century possession"
- Better category/topic clustering

## Recommended Action Plan

**Phase 1: Keep & Document (Immediate)**
1. Keep keywords as-is
2. Document their purpose and limitations
3. Make it clear some books have rich keywords, others don't

**Phase 2: Improve Generation (Future)**
1. Add NER extraction to preprocessing
2. Add domain-specific term extraction
3. Re-process books without good keywords
4. Keep manual keywords for books that have them

**Phase 3: Leverage for Features (Future)**
1. Add "keyword cloud" visualization
2. Enable "find similar by keywords" feature
3. Auto-suggest categories based on keywords
4. Generate summaries using keywords

## Bottom Line

**Don't remove keywords** - they're valuable for christian_mysticism and have potential for improvement. The current redundancy in 2/3 of books is not harmful (just not helpful). The real opportunity is to **improve keyword generation** for books that lack good manual indexes.

The preprocessing pipeline is already set up for keyword extraction - you just need to enhance it with NER and domain pattern matching instead of relying solely on title fallback.
