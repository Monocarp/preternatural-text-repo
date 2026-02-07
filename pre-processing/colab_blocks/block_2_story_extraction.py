# ==================================================================================
# BLOCK 2: STORY EXTRACTION (GPT)
# ==================================================================================
# Run this cell to define story extraction functions
# Then call run_story_extraction() at the bottom

def make_slug(text: str) -> str:
    return re.sub(r'[^\w\s-]', '', text).strip().lower().replace(' ', '-')

SYSTEM_PROMPT = """
You are the world's most exhaustive and precise verbatim extractor of supernatural, paranormal, miraculous, magical, or otherwise odd occurrences from historical, medieval, and scholarly texts.

FUNDAMENTAL RULE (APPLY ALWAYS)
• COMPLETENESS IS PARAMOUNT. Extract EVERY single incident that fits the definition, no matter how short, passing, or minor. When in doubt, extract it. Missing stories is worse than including borderline cases.

WHAT COUNTS AS AN EXTRACTABLE STORY
✓ EXTRACT these types of content (including one-sentence mentions and testimonies):
- "X was possessed by a demon"
- "Miracles occurred at [location]"
- "According to testimony, Y saw the devil"
- "Legend says Z could fly"
- "The trial records show A confessed to witchcraft"
- "The author mentions that B was bewitched"
- "As an example of possession, consider C who..."
- Any named individuals + supernatural events in ANY combination
• Critical: Historical analysis, theological discussion, legal commentary, philosophical argument — if they mention or give examples of specific incidents, extract the incidents verbatim.

✗ DO NOT EXTRACT:
- Pure theory or abstract doctrine (e.g., "Demons are fallen angels")
- Purely general statements without specifics (e.g., "Witches meet at sabbaths", "Many were possessed")

VERBATIM RULES — NO ALTERATION
• VERBATIM ONLY — NEVER TRUNCATE OR SUMMARIZE. Copy the exact original text word-for-word, preserving all original wording, casing, punctuation, and formatting within the excerpt.
• NEVER change capitalization, punctuation, spelling, or wording.
• If the same story appears multiple times with slight differences, include the longest version and append any unique verbatim sentences from the shorter versions at the end, separated by " --- ".

STORY BOUNDARIES & SENTENCE RULES
• Every individual story extraction MUST begin at the start of a sentence and MUST end at the end of a sentence. NEVER start or end mid-sentence.
• If the sentence boundary requirement would create ambiguous pronouns, expand the excerpt (backward and/or forward) to include antecedent context so the excerpt is self-contained.
• If extending to the sentence boundary would include unrelated material, prefer including that extra material rather than cutting mid-sentence.

NO AMBIGUOUS PRONOUNS
• ALWAYS include antecedent context. If a pronoun appears whose antecedent is not inside the extraction, expand the extraction using original sentences until the antecedent is explicit. Do not guess or insert names — include only original text.

UNIQUENESS, MERGING, AND THE " --- " RULE
• A story is unique if it has a distinct event, actors, location, or outcome.
• Combine only identical or near-identical retellings. When combining, append unique sentences from shorter or variant retellings separated by " --- ".
• For scattered mentions of the same event across the text, you may assemble them into a single extraction using " --- " between verbatim segments, but only when doing so preserves chronological/coherent sense and does not conflate distinct events.
• Do NOT merge stories that differ in any significant detail.

FORMAT (EXACT)
• Each extraction must use this exact header format (replace placeholders as specified):
  <div align="center"><b>[Concise Descriptive Title Based Solely on Content]</b></div>
  <div align="center">"{book_title}" Pages X-Y</div>

• Use the exact book title provided in the {book_title} placeholder — do NOT infer or use any title from the source text.
• Page ranges may be non-consecutive (e.g., Pages 45-47, 192, 305-307).
• After the two header lines, place the full verbatim story text here, including all original formatting and quotes.
• Separate multiple story extractions with exactly ONE blank line.
• If no stories are found, output only the single line:
  No supernatural stories extracted.

ADDITIONAL PRACTICAL RULES
• Start/end extracts at sentence boundaries even if this requires including full paragraphs or additional sentences for context.
• Include context for unclear pronouns or references so each extraction is self-contained.
• Extract liberally — better to include borderline/extra items than to miss a true incident.
• You have unlimited output length — be exhaustive.

MINDSET
• You are mining for supernatural events hidden in any type of text: scholarly articles, legal records, theological works, chronicles, trial transcripts, etc. Treat passing mentions, testimonies, legends, trial references, and examples as extractable stories.
"""

def extract_supernatural_stories(text: str, book_title: str) -> str:
    """Extract supernatural stories from text using GPT."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT.format(book_title=book_title)},
        {"role": "user", "content": text}
    ]
    response = openai_client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        temperature=0.0,
    )
    usage = response.usage
    print(f"Tokens → Prompt: {usage.prompt_tokens:,} | Completion: {usage.completion_tokens:,} | Total: {usage.total_tokens:,}")
    return response.choices[0].message.content.strip()

def run_story_extraction():
    """Main workflow for story extraction."""
    print("SUPERNATURAL STORY EXTRACTOR\n")

    # 1. Human enters the correct metadata
    book_title = input("Exact book title: ").strip()
    book_author = input("Author (optional): ").strip() or "Unknown"
    book_year_str = input("Publication year (optional): ").strip()
    book_year = book_year_str if book_year_str.isdigit() else None

    book_slug = make_slug(book_title)

    print(f"\nBook slug generated: {book_slug}")
    print(f"Title: {book_title}")
    print(f"Author: {book_author}")
    print(f"Year: {book_year or 'N/A'}\n")

    input("Looks good? Press Enter to continue, or Ctrl+C to cancel...")

    # 2. Upload Markdown parts
    print("\nUpload your cleaned Markdown files (part1.md, part2.md, etc.)")
    uploaded = files.upload()
    sorted_files = sorted(uploaded.keys(), key=lambda f: (
        999 if not re.search(r'part[ _-]?(\d+)', f, re.I) else
        int(re.search(r'part[ _-]?(\d+)', f, re.I).group(1))
    ))

    all_stories = []
    for filename in sorted_files:
        if not filename.lower().endswith('.md'):
            print(f"Skipping non-md: {filename}")
            continue

        print(f"\nProcessing → {filename}")
        text = open(filename, 'rb').read().decode('utf-8', errors='ignore')
        stories = extract_supernatural_stories(text, book_title)

        if stories and "No supernatural stories extracted" not in stories:
            all_stories.append(stories)

    final_stories = "\n\n".join(all_stories) if all_stories else "No supernatural stories extracted."

    # 3. Save the extracted stories + metadata
    safe_name = re.sub(r'[^\w\s-]', '', book_title).strip()[:50]
    base_filename = f"extracted_stories_{book_slug}"

    stories_file = f"{base_filename}.md"
    with open(stories_file, "w", encoding="utf-8") as f:
        f.write(final_stories)
    print(f"\nSaved → {stories_file}")

    metadata = {
        "book_slug": book_slug,
        "book_title": book_title,
        "book_author": book_author,
        "book_year": book_year,
        "extracted_at": datetime.utcnow().isoformat() + "Z",
        "source_files": list(uploaded.keys())
    }

    metadata_file = f"{base_filename}_meta.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata saved → {metadata_file}")

    files.download(stories_file)
    files.download(metadata_file)

    return book_slug, book_title

# ==================================================================================
# UNCOMMENT TO RUN:
# ==================================================================================
run_story_extraction()
