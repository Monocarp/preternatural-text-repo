#!/usr/bin/env python
"""Analyze codex tree for duplicate/redundant categories"""
import json
from collections import defaultdict

with open('data/codex_tree.json') as f:
    tree = json.load(f)

def get_all_paths(node, path=[]):
    """Get all category paths in the tree"""
    paths = []
    if isinstance(node, dict):
        for k, v in node.items():
            if k != '_stories':
                current = path + [k]
                paths.append(current)
                if isinstance(v, dict):
                    paths.extend(get_all_paths(v, current))
    return paths

def get_category_names(node, names=None):
    """Get all unique category names (leaf names)"""
    if names is None:
        names = set()
    
    if isinstance(node, dict):
        for k, v in node.items():
            if k != '_stories':
                names.add(k)
                if isinstance(v, dict):
                    get_category_names(v, names)
    return names

all_paths = get_all_paths(tree)
all_names = get_category_names(tree)

print(f"=== Tree Statistics ===")
print(f"Total category paths: {len(all_paths)}")
print(f"Unique category names: {len(all_names)}")

# Look for duplicate names (same category name in different paths)
name_occurrences = defaultdict(list)
for path in all_paths:
    leaf_name = path[-1]
    name_occurrences[leaf_name].append(' → '.join(path))

print(f"\n=== Categories That Appear Multiple Times ===")
duplicates = {name: paths for name, paths in name_occurrences.items() if len(paths) > 1}
if duplicates:
    for name, paths in sorted(duplicates.items()):
        print(f"\n'{name}' appears {len(paths)} times:")
        for p in paths:
            print(f"  - {p}")
else:
    print("No duplicate category names found")

# Look for similar names (potential typos or near-duplicates)
print(f"\n=== Potential Similar/Redundant Categories ===")
sorted_names = sorted(all_names, key=lambda x: x.lower())

similar_groups = []
for i, name1 in enumerate(sorted_names):
    name1_lower = name1.lower()
    name1_words = set(name1_lower.split())
    
    for name2 in sorted_names[i+1:]:
        name2_lower = name2.lower()
        name2_words = set(name2_lower.split())
        
        # Check for substring matches or significant word overlap
        if (name1_lower in name2_lower or name2_lower in name1_lower or
            len(name1_words & name2_words) >= min(len(name1_words), len(name2_words)) * 0.5):
            similar_groups.append((name1, name2))

if similar_groups:
    for name1, name2 in similar_groups[:30]:  # Limit output
        print(f"  - '{name1}' <-> '{name2}'")
    if len(similar_groups) > 30:
        print(f"  ... and {len(similar_groups) - 30} more")
else:
    print("No obviously similar categories found")

# Look for redundant parent-child relationships
print(f"\n=== Single-Child Categories (Potential Merges) ===")
single_children = []
for path in all_paths:
    path_str = ' → '.join(path)
    # Get node at this path
    node = tree
    for level in path:
        if isinstance(node, dict):
            node = node.get(level, {})
    
    if isinstance(node, dict):
        children = [k for k in node.keys() if k != '_stories']
        if len(children) == 1:
            single_children.append(f"{path_str} → {children[0]}")

if single_children:
    print(f"Found {len(single_children)} categories with only one child:")
    for sc in single_children[:20]:
        print(f"  - {sc}")
    if len(single_children) > 20:
        print(f"  ... and {len(single_children) - 20} more")
else:
    print("No single-child categories found")
