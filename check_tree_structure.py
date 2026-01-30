#!/usr/bin/env python
"""Check for leaf nodes that are arrays instead of dicts with _stories"""
import json

with open('data/codex_tree.json') as f:
    tree = json.load(f)

def check_structure(node, path=[]):
    """Find nodes that are arrays or have unexpected structure"""
    results = {
        'arrays': [],  # Leaf nodes that are arrays
        'mixed': [],   # Nodes with both _stories and other keys
        'numeric_keys': []  # Nodes with numeric keys
    }
    
    if isinstance(node, dict):
        has_stories = '_stories' in node
        other_keys = [k for k in node.keys() if k != '_stories']
        
        # Check for numeric keys
        for k in other_keys:
            if k.isdigit():
                results['numeric_keys'].append(('/'.join(path), k, type(node[k]).__name__))
        
        if has_stories and other_keys:
            results['mixed'].append('/'.join(path))
        
        # Recurse into children
        for k, v in node.items():
            if k != '_stories':
                child_results = check_structure(v, path + [k])
                results['arrays'].extend(child_results['arrays'])
                results['mixed'].extend(child_results['mixed'])
                results['numeric_keys'].extend(child_results['numeric_keys'])
                
    elif isinstance(node, list):
        # This is a leaf node with direct story array
        results['arrays'].append(('/'.join(path), len(node)))
    
    return results

results = check_structure(tree)

print(f"=== Tree Structure Analysis ===\n")
print(f"Leaf nodes with direct story arrays: {len(results['arrays'])}")
if results['arrays']:
    print("\nFirst 10 array leaf nodes:")
    for path, count in results['arrays'][:10]:
        print(f"  {path}: {count} stories")

print(f"\nNodes with numeric keys: {len(results['numeric_keys'])}")
if results['numeric_keys']:
    print("\nNodes with numeric keys:")
    for parent_path, key, value_type in results['numeric_keys']:
        print(f"  At '{parent_path}', found key '{key}' (value type: {value_type})")

print(f"\nNodes with both _stories and children: {len(results['mixed'])}")
if results['mixed']:
    print("\nFirst 5 mixed nodes:")
    for path in results['mixed'][:5]:
        print(f"  {path}")
