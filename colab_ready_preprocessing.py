# Colab-ready version of preprocessing pipeline
# To use in Colab before step4.py

# Install dependencies (run once in Colab)
# !pip install -q spacy
# !python -m spacy download en_core_web_trf

import spacy
import re
from typing import List

# Load model (will download on first use in Colab)
try:
    nlp = spacy.load("en_core_web_trf")
except:
    print("Downloading spaCy model...")
    import os
    os.system("python -m spacy download en_core_web_trf")
    nlp = spacy.load("en_core_web_trf")

def prepare_chunk_for_extraction(markdown_chunk: str, book_title: str, start_page: int = 1) -> str:
    """
    Prepare a manually-created chunk for LLM extraction
    
    Args:
        markdown_chunk: Your 10-15 page chunk with [Page XXX] markers
        book_title: Title of the book
        start_page: Starting page number (default 1)
    
    Returns:
        Formatted prompt ready for Claude/LLM
    """
    
    # Protect common abbreviations from sentence splitting
    protected_text = markdown_chunk
    
    abbrevs = ["Fr", "Dr", "Mr", "Mrs", "St", "Rev", "pp", "p", "ch", "vol", 
               "etc", "viz", "i.e", "e.g", "cf", "Mt", "Mk", "Lk", "Jn", 
               "Ven", "Bl", "SS", "ff", "sq", "Ibid", "Op", "cit", "al"]
    
    for abbrev in abbrevs:
        protected_text = re.sub(f'\\b{abbrev}\\.', f'{abbrev}<!DOT!>', protected_text, flags=re.I)
    
    # Process with spaCy
    doc = nlp(protected_text)
    
    sentences = []
    current_page = start_page
    
    for sent_idx, sent in enumerate(doc.sents):
        sent_text = sent.text.strip()
        if not sent_text:
            continue
            
        # Restore dots
        sent_text = sent_text.replace("<!DOT!>", ".")
        
        # Extract page from standardized markers
        page_match = re.search(r'\[Page (\d+)\]', sent_text)
        if page_match:
            current_page = int(page_match.group(1))
        
        # Add markers
        marked = f"[S{sent_idx}][P{current_page}] {sent_text}"
        sentences.append(marked)
    
    marked_text = "\n".join(sentences)
    
    # Return formatted prompt
    prompt = f"""BOOK: {book_title}

EXTRACT ALL supernatural/paranormal/miraculous/magical incidents from the text below.

CRITICAL RULES:
1. Extract EVERYTHING - even single sentences like "she was possessed" 
2. Start and end at [S#] markers (sentence boundaries)
3. If starting with he/she/it/they, expand backwards until the person is identified

FORMAT each story as:
<div align="center"><b>[Descriptive Title]</b></div>
<div align="center">"{book_title}" Pages X-Y</div>

[Verbatim text]

Use [P#] markers for page ranges. Missing a story is worse than including a borderline case.

TEXT:
{marked_text}"""

    return prompt


def clean_extracted_output(extracted_text: str) -> str:
    """
    Remove markers from LLM output
    
    Args:
        extracted_text: Raw output from Claude/LLM with markers
        
    Returns:
        Clean text without markers
    """
    # Remove sentence/page markers
    cleaned = re.sub(r'\[S\d+\]\[P\d+\]\s*', '', extracted_text)
    return cleaned


def process_multiple_chunks(chunks: List[str], book_title: str) -> List[str]:
    """
    Process multiple chunks and return prompts for each
    
    Args:
        chunks: List of markdown chunks
        book_title: Title of the book
        
    Returns:
        List of formatted prompts
    """
    prompts = []
    
    for i, chunk in enumerate(chunks):
        # Try to detect starting page from first [Page X] marker
        page_match = re.search(r'\[Page (\d+)\]', chunk)
        start_page = int(page_match.group(1)) if page_match else 1
        
        prompt = prepare_chunk_for_extraction(chunk, book_title, start_page)
        prompts.append(prompt)
        
        print(f"Prepared chunk {i+1}/{len(chunks)} (starting at page {start_page})")
    
    return prompts


# For Colab usage
def colab_example():
    """Example of how to use in Colab"""
    
    # Example chunk
    test_chunk = """[Page 45]
Fr. Bernard witnessed a possession most terrible. The woman spoke in tongues. 
She levitated above her bed.

[Page 46]  
This same woman vomited nails. The Bishop performed exorcism. Seven demons 
revealed themselves."""
    
    # Process
    prompt = prepare_chunk_for_extraction(test_chunk, "Test Book", 45)
    
    print("="*60)
    print("PREPARED PROMPT FOR LLM:")
    print("="*60)
    print(prompt)
    print("="*60)
    
    # Simulate LLM response
    fake_llm_response = """<div align="center"><b>Possession of Unknown Woman</b></div>
<div align="center">"Test Book" Pages 45-46</div>

[S0][P45] Fr. Bernard witnessed a possession most terrible. [S1][P45] The woman spoke in tongues. [S2][P45] She levitated above her bed. [S4][P46] This same woman vomited nails. [S5][P46] The Bishop performed exorcism. [S6][P46] Seven demons revealed themselves."""
    
    # Clean output
    cleaned = clean_extracted_output(fake_llm_response)
    
    print("\nCLEANED OUTPUT:")
    print("="*60)
    print(cleaned)
    
    
if __name__ == "__main__":
    colab_example()
