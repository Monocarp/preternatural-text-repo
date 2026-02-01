"""
Regenerate stories_dict.json from story_positions.json files
"""
import json
from pathlib import Path

BOOKS_DIR = Path("books")
OUTPUT_FILE = Path("data/stories_dict.json")

def load_story_positions():
    """Load all story_positions.json files from book folders"""
    stories_dict = {}
    
    for book_dir in BOOKS_DIR.iterdir():
        if not book_dir.is_dir():
            continue
            
        positions_file = book_dir / "story_positions.json"
        if not positions_file.exists():
            print(f"⚠️  Skipping {book_dir.name} - no story_positions.json")
            continue
        
        print(f"Processing {book_dir.name}...")
        
        with open(positions_file, 'r', encoding='utf-8') as f:
            positions = json.load(f)
        
        for title, data in positions.items():
            # Extract only the fields needed for stories_dict.json
            stories_dict[title] = {
                "title": title,
                "book_slug": book_dir.name,
                "pages": data.get("pages", "Unknown"),
                "keywords": ", ".join(data.get("keywords", [])),  # Join list to string
                "start_char": data.get("start_char", -1),
                "end_char": data.get("end_char", -1)
            }
        
        print(f"  ✓ Added {len(positions)} stories")
    
    return stories_dict

def main():
    print("Regenerating stories_dict.json from story_positions.json files...\n")
    
    stories_dict = load_story_positions()
    
    print(f"\nTotal stories: {len(stories_dict)}")
    
    # Save to file
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(stories_dict, f, indent=4, ensure_ascii=False, sort_keys=True)
    
    print(f"✓ Saved to {OUTPUT_FILE}")
    
    # Verify a sample
    sample_title = "Teenaged Boy Sees His Deceased Father Emerge from a UFO"
    if sample_title in stories_dict:
        print(f"\n✓ Verification - {sample_title}:")
        print(f"  Keywords: {stories_dict[sample_title]['keywords'][:100]}...")

if __name__ == "__main__":
    main()
