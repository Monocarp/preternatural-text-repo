# Minimal preprocessing focused on your three goals
# No duplicate detection, no complex chunking (you do that manually)

import spacy
import re

# Load the best model for sentence detection
nlp = spacy.load("en_core_web_trf")

def prepare_chunk_for_extraction(markdown_chunk: str, book_title: str, start_page: int) -> str:
    """
    Minimal preprocessing focused on:
    1. Correct sentence boundaries (for no splits)
    2. Pronoun context (via sentence markers)
    3. Aggressive extraction (via prompt)
    """
    
    # Pre-process to protect common abbreviations in historical texts
    protected_text = markdown_chunk
    abbreviations = {
        "Fr.": "Fr<!DOT!>",
        "Dr.": "Dr<!DOT!>", 
        "Mr.": "Mr<!DOT!>",
        "Mrs.": "Mrs<!DOT!>",
        "St.": "St<!DOT!>",
        "Rev.": "Rev<!DOT!>",
        "pp.": "pp<!DOT!>",
        "p.": "p<!DOT!>",
        "ch.": "ch<!DOT!>",
        "vol.": "vol<!DOT!>",
        "etc.": "etc<!DOT!>",
        "viz.": "viz<!DOT!>",
        "i.e.": "i<!DOT!>e<!DOT!>",
        "e.g.": "e<!DOT!>g<!DOT!>",
    }
    
    for abbrev, replacement in abbreviations.items():
        protected_text = protected_text.replace(abbrev, replacement)
    
    # Process with spaCy
    doc = nlp(protected_text)
    
    sentences = []
    current_page = start_page
    
    for sent_idx, sent in enumerate(doc.sents):
        sent_text = sent.text.strip()
        if not sent_text:
            continue
            
        # Restore protected dots
        sent_text = sent_text.replace("<!DOT!>", ".")
        
        # Simple page detection - only your manual markers
        page_match = re.search(r'\[Page\s+(\d+)\]', sent_text, re.I)
        if page_match:
            new_page = int(page_match.group(1))
            # Sanity check - should be within your chunk range
            if start_page <= new_page <= start_page + 15:
                current_page = new_page
        
        # Use safe markers that can't appear in text
        marked = f"◊S{sent_idx}◊P{current_page}◊ {sent_text}"
        sentences.append(marked)
    
    marked_text = "\n".join(sentences)
    
    # Aggressive prompt focused on your goals
    prompt = f"""BOOK: {book_title}

EXTRACT every supernatural, paranormal, miraculous, magical, or odd occurrence.

THREE CRITICAL RULES:

1. EXTRACT EVERYTHING - Even one-sentence mentions like "he was possessed"
2. USE SENTENCE BOUNDARIES - Each story MUST start/end at ◊S markers
3. RESOLVE PRONOUNS - If a story starts with he/she/it/they, include previous sentences until clear

FORMAT:
<div align="center"><b>[Short Title]</b></div>
<div align="center">"{book_title}" Pages X-Y</div>

[Exact text using ◊S markers for clean boundaries]

The ◊P markers show page numbers. Extract aggressively - when in doubt, include it.

Text:
{marked_text}"""

    return prompt


def clean_extracted_output(extracted_text: str) -> str:
    """Remove markers from final output"""
    # Remove all markers
    cleaned = re.sub(r'◊S\d+◊P\d+◊\s*', '', extracted_text)
    return cleaned


# Example usage with your manual chunks
def process_your_manual_chunk(chunk_text: str, book_title: str, chunk_start_page: int):
    """Process one of your manually created chunks"""
    
    # 1. Prepare with markers
    marked_prompt = prepare_chunk_for_extraction(chunk_text, book_title, chunk_start_page)
    
    # 2. Send to Claude
    # response = claude_api_call(marked_prompt)
    
    # 3. Clean the output
    # final_stories = clean_extracted_output(response)
    
    # return final_stories
    
    # For now, just return the prompt to show what it looks like
    return marked_prompt


# Test with historical text
if __name__ == "__main__":
    test_chunk = """
[Page 45]
In the year of our Lord 1623, Fr. Bernard witnessed a most terrible possession. 
The afflicted woman spoke in tongues unknown. She levitated three feet above 
her bed whilst her family cowered in fear.

[Page 46]  
This same woman later vomited forth iron nails and pieces of glass, though 
she had eaten nothing for days. The Bishop was summoned. He performed the 
rites of exorcism, during which the demons revealed themselves to be seven 
in number.
"""
    
    result = prepare_chunk_for_extraction(test_chunk, "Possessions of France", 45)
    print(result)
