# Complete extraction step that goes BEFORE step4.py
# This creates the Stories.md file that step4 expects

import os
import re
from anthropic import Anthropic
from google.colab import files, userdata

# Import our preprocessing
from final_minimal_preprocessing import prepare_chunk_for_extraction, clean_extracted_output

def extract_stories_from_book(book_dir: str, book_title: str, model: str = "claude-3-5-haiku-20241022"):
    """
    Extract stories from a book's chunks and create Stories.md
    
    Args:
        book_dir: Path to book directory containing chunk files
        book_title: Title of the book for the extraction
        model: Claude model to use
    """
    
    # Set up Claude
    client = Anthropic(api_key=userdata.get('ANTHROPIC_API_KEY'))
    
    # Find all chunk files (assuming they're named like part_1.md, part_2.md, etc.)
    chunk_files = sorted([f for f in os.listdir(book_dir) if f.startswith('part_') and f.endswith('.md')])
    
    if not chunk_files:
        print(f"No chunk files found in {book_dir}")
        return
    
    all_stories = []
    
    for chunk_file in chunk_files:
        print(f"\nProcessing {chunk_file}...")
        
        # Read chunk
        with open(os.path.join(book_dir, chunk_file), 'r', encoding='utf-8') as f:
            chunk_content = f.read()
        
        # Get starting page from first [Page X] marker
        page_match = re.search(r'\[Page (\d+)\]', chunk_content)
        start_page = int(page_match.group(1)) if page_match else 1
        
        # Preprocess the chunk
        prepared_prompt = prepare_chunk_for_extraction(chunk_content, book_title, start_page)
        
        # Send to Claude
        try:
            response = client.messages.create(
                model=model,
                max_tokens=64000,
                temperature=0.0,
                system="You are an exhaustive extractor of supernatural stories. Follow the instructions exactly.",
                messages=[{"role": "user", "content": prepared_prompt}]
            )
            
            # Get extracted stories
            raw_extraction = response.content[0].text
            
            # Clean the extraction (remove markers)
            cleaned_stories = clean_extracted_output(raw_extraction)
            
            # Skip if no stories found
            if "No supernatural stories extracted" not in cleaned_stories:
                all_stories.append(cleaned_stories)
                
            # Print token usage for cost tracking
            if hasattr(response, 'usage'):
                print(f"Tokens used: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
                
        except Exception as e:
            print(f"Error processing {chunk_file}: {e}")
            continue
    
    # Combine all stories
    if all_stories:
        final_stories = "\n\n".join(all_stories)
        
        # Save as Stories.md in the book directory
        stories_path = os.path.join(book_dir, "Stories.md")
        with open(stories_path, 'w', encoding='utf-8') as f:
            f.write(final_stories)
        
        print(f"\nSaved {stories_path}")
        
        # Also create a simple grouped_index.md if it doesn't exist
        # (This would normally come from your earlier processing)
        index_path = os.path.join(book_dir, "grouped_index.md")
        if not os.path.exists(index_path):
            create_simple_index(final_stories, index_path)
            print(f"Created simple index at {index_path}")
    else:
        print("No stories extracted from any chunks")

def create_simple_index(stories_content: str, index_path: str):
    """Create a simple grouped_index.md from extracted stories"""
    
    # Parse story titles and pages
    pattern = r'<div align="center"><b>(.*?)</b></div>\n<div align="center">"[^"]+" Pages? (\d+(?:-\d+)?)</div>'
    matches = re.findall(pattern, stories_content, re.IGNORECASE)
    
    index_content = []
    for title, pages in matches:
        # Simple format: Title - Pages
        index_content.append(f"{title} - {pages}")
    
    with open(index_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(index_content))

# Example usage in Colab
def process_book_complete_pipeline(book_slug: str, book_title: str):
    """
    Complete pipeline: chunks → extraction → Stories.md → step4 processing
    
    1. Upload your manually created chunks as part_1.md, part_2.md, etc.
    2. Run this to create Stories.md
    3. Then run step4.py to create the searchable database
    """
    
    book_dir = f"/content/books/{book_slug}/"
    
    # Ensure directory exists
    os.makedirs(book_dir, exist_ok=True)
    
    print(f"Processing book: {book_title}")
    print(f"Book directory: {book_dir}")
    print("\nPlease upload your chunk files (part_1.md, part_2.md, etc.) to the book directory")
    print("Make sure Full_Text.md is also in the directory")
    
    # Wait for user to confirm files are uploaded
    input("\nPress Enter when all files are uploaded...")
    
    # Run extraction
    extract_stories_from_book(book_dir, book_title)
    
    print("\n" + "="*60)
    print("Extraction complete! You can now run step4.py to process the book.")
    print("="*60)

if __name__ == "__main__":
    # Example: process Christian Mysticism Volume IV
    process_book_complete_pipeline(
        book_slug="christian_mysticism_vol_iv",
        book_title="Christian Mysticism Volume IV"
    )
