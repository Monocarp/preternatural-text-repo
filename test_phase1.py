#!/usr/bin/env python3
"""
Phase 1 Testing Script
Tests story-level search improvements after backend changes
"""

import requests
import json
from typing import List, Dict

# Configuration
API_URL = "http://localhost:8000"  # Change to your deployment URL
TEST_QUERIES = [
    # Format: (query, expected_story_title_fragment, description)
    ("possession speaking in tongues", "Loudun", "Multi-chunk story test"),
    ("exorcism", None, "General query - check unified results"),
    ("levitation", None, "Physical manifestation"),
    ("demonic obsession fear", None, "Conceptual multi-word query"),
    ("Father Surin", "Surin", "Named entity"),
]

def test_search(query: str, expected_fragment: str = None, description: str = "") -> Dict:
    """
    Test a single search query
    """
    print(f"\n{'='*60}")
    print(f"Query: '{query}'")
    print(f"Description: {description}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            f"{API_URL}/api/search",
            json={
                "query": query,
                "top_k": 10,
                "min_score": 0.1,
                "search_mode": "Both"
            },
            timeout=10
        )
        response.raise_for_status()
        results = response.json()["results"]
        
        print(f"\n✅ Found {len(results)} results")
        
        if len(results) == 0:
            print("❌ WARNING: No results returned!")
            return {"query": query, "success": False, "reason": "no_results"}
        
        # Display top 5
        print(f"\nTop 5 Results:")
        for i, result in enumerate(results[:5], 1):
            title = result['title']
            score = result['score']
            book = result.get('book_slug', 'unknown')
            
            # Check for expected fragment
            match_marker = ""
            if expected_fragment and expected_fragment.lower() in title.lower():
                match_marker = " ✓ MATCH"
            
            print(f"  #{i}: {title} (Score: {score:.3f}, Book: {book}){match_marker}")
        
        # Check for story title uniqueness (should be no duplicates)
        titles = [r['title'] for r in results]
        duplicates = [t for t in titles if titles.count(t) > 1]
        
        if duplicates:
            print(f"\n❌ WARNING: Found duplicate titles: {set(duplicates)}")
            print("   This suggests chunks weren't properly filtered to story-level docs")
            return {"query": query, "success": False, "reason": "duplicates"}
        else:
            print(f"\n✅ All results are unique (no chunk fragmentation)")
        
        # Check if expected fragment found in top 5
        if expected_fragment:
            top_5_titles = [r['title'].lower() for r in results[:5]]
            found = any(expected_fragment.lower() in t for t in top_5_titles)
            
            if found:
                print(f"✅ Expected fragment '{expected_fragment}' found in top 5")
                return {"query": query, "success": True}
            else:
                print(f"⚠️  Expected fragment '{expected_fragment}' NOT in top 5")
                return {"query": query, "success": False, "reason": "expected_not_found"}
        
        return {"query": query, "success": True}
        
    except requests.exceptions.RequestException as e:
        print(f"❌ ERROR: Request failed - {e}")
        return {"query": query, "success": False, "reason": "request_failed"}
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return {"query": query, "success": False, "reason": str(e)}

def test_document_types():
    """
    Test that document store has story-level documents
    """
    print(f"\n{'='*60}")
    print("Testing Document Store Structure")
    print(f"{'='*60}")
    
    try:
        # Search with type filter to verify story docs exist
        response = requests.post(
            f"{API_URL}/api/search",
            json={
                "query": "demon",
                "top_k": 100,
                "min_score": 0.01,
                "search_mode": "Both"
            },
            timeout=10
        )
        response.raise_for_status()
        results = response.json()["results"]
        
        if len(results) == 0:
            print("❌ CRITICAL: No results returned for basic query!")
            print("   Backend may not have loaded document store properly")
            return False
        
        print(f"✅ Document store is accessible ({len(results)} results found)")
        
        # Check if results have story-level metadata
        sample = results[0]
        required_fields = ["title", "book_slug", "start_char", "end_char", "pages", "score"]
        missing_fields = [f for f in required_fields if f not in sample]
        
        if missing_fields:
            print(f"❌ Missing required fields in results: {missing_fields}")
            return False
        
        print(f"✅ Results have correct story-level metadata")
        print(f"   Sample: {sample['title'][:50]}... (Score: {sample['score']:.3f})")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def main():
    """
    Run all tests
    """
    print("""
╔══════════════════════════════════════════════════════════════╗
║          PHASE 1: STORY-LEVEL SEARCH TEST SUITE              ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    # Test 1: Document store structure
    if not test_document_types():
        print("\n❌ CRITICAL: Document store tests failed!")
        print("   Make sure you've replaced document_store.json with the new version")
        return
    
    # Test 2: Search queries
    results = []
    for query, expected_fragment, description in TEST_QUERIES:
        result = test_search(query, expected_fragment, description)
        results.append(result)
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for r in results if r["success"])
    total = len(results)
    
    print(f"Passed: {passed}/{total} tests")
    
    if passed == total:
        print("\n✅ ALL TESTS PASSED!")
        print("   Story-level search is working correctly")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("\nFailed tests:")
        for r in results:
            if not r["success"]:
                print(f"  - {r['query']}: {r.get('reason', 'unknown')}")
    
    print(f"\n{'='*60}\n")

if __name__ == "__main__":
    main()
