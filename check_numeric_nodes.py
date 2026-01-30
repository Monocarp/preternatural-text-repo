#!/usr/bin/env python
"""Check for numeric node names in the database"""
import re
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from models import SessionLocal, CodexNode
from sqlalchemy.orm import selectinload

db = SessionLocal()

# Load all nodes
nodes = db.query(CodexNode).options(
    selectinload(CodexNode.children), 
    selectinload(CodexNode.stories)
).all()

print(f'Total nodes in database: {len(nodes)}')

# Find nodes with numeric names
problematic = []
for node in nodes:
    if re.match(r'^\d+$', node.name):
        problematic.append((node.id, node.name, node.parent_id))

print(f'\nNodes with purely numeric names: {len(problematic)}')

if problematic:
    print('\nProblematic nodes:')
    # Create lookup
    node_lookup = {n.id: n for n in nodes}
    
    for nid, name, pid in problematic:
        if pid and pid in node_lookup:
            parent_name = node_lookup[pid].name
            # Get grandparent too for context
            gp_id = node_lookup[pid].parent_id
            if gp_id and gp_id in node_lookup:
                grandparent = node_lookup[gp_id].name
                print(f'  Node ID {nid}: name="{name}" parent="{parent_name}" grandparent="{grandparent}"')
            else:
                print(f'  Node ID {nid}: name="{name}" parent="{parent_name}" (root level)')
        else:
            print(f'  Node ID {nid}: name="{name}" (no parent - root level)')
    
    # Also show children count
    print('\nChildren assigned to numeric nodes:')
    for nid, name, pid in problematic:
        node = node_lookup[nid]
        children_count = len(node.children) if node.children else 0
        stories_count = len(node.stories) if node.stories else 0
        print(f'  "{name}": {children_count} children, {stories_count} stories')

db.close()
