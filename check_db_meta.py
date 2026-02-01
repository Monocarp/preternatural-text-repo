import sqlite3
import json

db_path = "data/stories_fts.db"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Get rows where metadata_json is NOT NULL and not empty string
    cursor.execute("SELECT doc_id, metadata_json FROM stories_meta WHERE metadata_json IS NOT NULL AND length(metadata_json) > 0 LIMIT 5")
    rows = cursor.fetchall()
    
    print(f"Found {len(rows)} rows with metadata.")
    for i, row in enumerate(rows):
        doc_id = row[0]
        raw_json = row[1]
        print(f"\n--- Row {i+1} (ID: {doc_id}) ---")
        try:
            meta = json.loads(raw_json)
            # print("Keys:", list(meta.keys()))
            if "people" in meta:
                print("People:", meta["people"])
            elif "entities" in meta:
                 print("Entities:", meta["entities"])
            else:
                print("No people/entities field.")

            if "locations" in meta:
                print("Locations raw:", str(meta["locations"])[:200] + "...")
            
            if "temporal" in meta:
                 print("Temporal:", meta["temporal"])
            
            # Check for year/date specific fields if temporal object is complex
            if "year" in meta:
                print("Year:", meta["year"])

        except json.JSONDecodeError:
            print("Invalid JSON:", raw_json)
            
    conn.close()
except Exception as e:
    print(f"Error: {e}")
