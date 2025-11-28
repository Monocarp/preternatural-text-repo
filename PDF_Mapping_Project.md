# PDF Mapping Project

## Goal
Enable citation verification and access to original source material (footnotes, pagination) while maintaining clean Markdown for story extraction.

## Current State
- Books converted to Markdown after stripping footnotes
- Page numbers inserted as markers for reference
- "Book context" feature shows full MD version
- Works well for story extraction but lacks original footnotes and true pagination

## Proposed Solution: Hybrid Reference System

### Architecture
```
books/
  [book-name]/
    [book-name].md          # Clean version (current)
    [book-name].pdf         # Original with footnotes
    page-map.json           # Page number mapping
    footnotes.json          # Extracted footnotes (optional)
```

### Key Components

1. **Bidirectional Page Mapping**
   - Map MD page markers to PDF page numbers
   - Format: `{"md_page": X, "pdf_page": Y}`
   - Created during MD conversion process

2. **Footnote Layer**
   - Extract footnotes during processing
   - Store as separate metadata
   - Optionally display as tooltips/overlays on MD text

3. **Book Context Enhancement**
   - Current: Shows MD text
   - Enhanced: Add "View original (PDF page X)" link
   - Optional: Render footnotes inline without complicating extraction

## Benefits
- Researchers get clean reading experience
- Citation verification via PDF reference
- No complex PDF rendering required
- Footnotes accessible without interfering with story extraction
- PDF remains source-of-truth

## Implementation Considerations

### Storage
- PDFs larger than MD files
- Consider external hosting (archive.org) vs. local storage
- Copyright implications differ for full PDFs vs. processed MD

### Mapping Accuracy
- MD page numbers may not match PDF 1:1 due to footnote removal
- Use original book page numbers (already in MD) as canonical reference
- Map to PDF coordinates as needed

## Alternative: Lightweight Approach
- Maintain footnotes.json only
- Link to external PDF sources rather than hosting
- Display footnotes in MD view when needed

## Status
Planning phase - not for immediate implementation
