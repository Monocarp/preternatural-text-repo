# Search Improvements Implementation Summary

## Features Implemented

### 1. **Sort Options** ✅
**Backend:** `backend/search/stories_direct.py`
- Added `sort_by` parameter to `search_stories()`
- Options: `relevance` (default), `chronological`, `alphabetical`, `by_book`, `by_pages`
- Chronological sorts by earliest year extracted from keywords
- By book groups results by source
- By pages sorts within book by page number

**Frontend:** Add UI in SearchCurate.tsx filters panel
```tsx
<select value={sortBy} onChange={(e) => setSortBy(e.target.value)}>
  <option value="relevance">Relevance</option>
  <option value="chronological">Chronological (Earliest)</option>
  <option value="alphabetical">Alphabetical</option>
  <option value="by_book">By Book</option>
  <option value="by_pages">By Pages</option>
</select>
```

### 2. **Topic Tag Filter** ✅
**Backend:**
- `GET /api/topics` - Returns all unique topics from keywords
- Added `topic_filter` parameter to search
- Filters stories where keywords contain any of the comma-separated topics

**Frontend:** Add topic selector (multi-select or comma-separated input)

### 3. **Find Similar** ✅
**Backend:** `POST /api/find-similar`
- Takes `{title, book_slug, top_k}`
- Extracts story's embedding from FAISS
- Runs semantic search with that embedding
- Returns similar stories (excluding the query story)

**Frontend:** Add button in story viewer header:
```tsx
<button onClick={handleFindSimilar}>
  🔍 Find Similar Stories
</button>
```

### 4. **Bulk Operations** (Frontend Only)
**State:**
- `selectedResults: Set<string>` - Track selected result keys
- `bulkMode: boolean` - Toggle bulk selection mode

**UI Components:**
- Checkboxes on result cards
- Bulk action bar: "Assign All to Category", "Export Selected"
- Uses existing `/api/assign` endpoint with multiple stories

### 5. **Match Highlighting** (TODO - Complex)
**Backend:** Would need to return match context/snippets
**Frontend:** Render bold keywords in result cards

## Files Modified

### Backend
1. `backend/routes/dependencies.py` - Added `topic_filter` and `sort_by` to SearchQuery model
2. `backend/routes/search.py` - Added `/topics` and `/find-similar` endpoints
3. `backend/search/stories_direct.py` - Implemented topic filtering and sorting logic

### Frontend
1. `frontend/src/pages/SearchCurate.tsx` - Added state vars for new features

## Frontend Implementation Needed

Add to SearchCurate.tsx filters panel (around line 550-620):

```tsx
{/* Sort Options */}
<div>
  <label className="block text-xs font-medium mb-1 text-gray-400">Sort By</label>
  <select
    value={sortBy}
    onChange={(e) => setSortBy(e.target.value)}
    className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm"
  >
    <option value="relevance">Relevance</option>
    <option value="chronological">Chronological</option>
    <option value="alphabetical">Alphabetical</option>
    <option value="by_book">By Book</option>
    <option value="by_pages">By Pages</option>
  </select>
</div>

{/* Topic Filter */}
<div>
  <label className="block text-xs font-medium mb-1 text-gray-300">🏷️ Topic Filter</label>
  <input
    type="text"
    placeholder="e.g., possession, ufo, witch"
    value={topicFilter}
    onChange={(e) => setTopicFilter(e.target.value)}
    className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-sm"
  />
  <div className="text-xs text-gray-500 mt-1">
    Comma-separated topics from keywords
  </div>
</div>

{/* Bulk Mode Toggle */}
<div className="pt-2 border-t border-gray-700">
  <button
    onClick={() => setBulkMode(!bulkMode)}
    className="w-full px-2 py-1 bg-purple-600 hover:bg-purple-700 rounded text-sm"
  >
    {bulkMode ? '✓ Bulk Mode Active' : 'Enable Bulk Selection'}
  </button>
</div>
```

Add Find Similar handler:
```tsx
const handleFindSimilar = async () => {
  if (!selectedStory) return
  
  setSearching(true)
  try {
    const res = await apiClient.post('/find-similar', {
      title: selectedStory.title,
      book_slug: selectedStory.book_slug,
      top_k: 20
    })
    setResults(res.data.results)
    setQuery(`Similar to: ${selectedStory.title}`)
  } catch (err) {
    console.error('Find similar failed:', err)
  } finally {
    setSearching(false)
  }
}
```

Add Find Similar button in story viewer header (around line 710):
```tsx
<button
  onClick={handleFindSimilar}
  className="px-4 py-2 rounded text-sm bg-indigo-600 text-white hover:bg-indigo-700"
>
  🔍 Find Similar
</button>
```

Add bulk selection to results list (around line 640):
```tsx
{results.map((result, idx) => {
  const resultKey = `${result.book_slug}-${result.title}`
  return (
    <div key={resultKey} className="flex items-start gap-2">
      {bulkMode && (
        <input
          type="checkbox"
          checked={selectedResults.has(resultKey)}
          onChange={(e) => {
            const newSet = new Set(selectedResults)
            if (e.target.checked) {
              newSet.add(resultKey)
            } else {
              newSet.delete(resultKey)
            }
            setSelectedResults(newSet)
          }}
          className="mt-2"
        />
      )}
      <button
        onClick={() => handleSelectStory(result)}
        className={`flex-1 text-left p-2 rounded border ${...}`}
      >
        {/* Existing result card content */}
      </button>
    </div>
  )
})}

{/* Bulk Action Bar */}
{bulkMode && selectedResults.size > 0 && (
  <div className="fixed bottom-4 left-1/2 transform -translate-x-1/2 bg-gray-800 border border-gray-600 rounded-lg shadow-lg px-4 py-3 flex items-center gap-3">
    <span className="text-sm text-gray-300">
      {selectedResults.size} selected
    </span>
    <button className="px-3 py-1 bg-blue-600 hover:bg-blue-700 rounded text-sm">
      Assign All to Category
    </button>
    <button className="px-3 py-1 bg-green-600 hover:bg-green-700 rounded text-sm">
      Export Selected
    </button>
    <button 
      onClick={() => setSelectedResults(new Set())}
      className="px-3 py-1 bg-gray-600 hover:bg-gray-700 rounded text-sm"
    >
      Clear
    </button>
  </div>
)}
```

## Testing Checklist

- [ ] Sort by chronological returns oldest stories first
- [ ] Sort by alphabetical returns A-Z
- [ ] Topic filter with "possession" returns only possession stories
- [ ] Find Similar returns thematically related stories
- [ ] Bulk mode allows multi-select
- [ ] Bulk assign works with multiple stories
- [ ] Backend doesn't crash with missing parameters

## Known Limitations

1. **Match highlighting** requires content snippets - not yet implemented
2. **Topic autocomplete** would need fuzzy search - using simple input for now
3. **Bulk export** uses existing export endpoint - may need pagination for large sets
