# backend/tree/operations.py
"""
Pure tree manipulation functions.

These functions work on tree dictionaries without any global state or I/O.
They are used by the persistence module and can be tested independently.
"""

import logging

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Default Category Structure (used when codex_tree.json doesn't exist)
# ------------------------------------------------------------------ #
CATEGORIES = {
    "Demonic Activity": {
        "Obsession": {
            "Fear/Anxiety": [],
            "Emotional Guilt": [],
            "Anger": [],
            "Reduction of Voluntariness": []
        },
        "Oppression": {
            "Haunting Vexations": {
                "Poltergeist": [],
                "Shadow People": [],
                "Sleep Paralysis": [],
                "Static People": [],
                "Glimmer Man": [],
                "Flannel Man": []
            },
            "Physical Health Vexations": {
                "Death": [],
                "Bruise": [],
                "Bite Marks": [],
                "Scratches": [],
                "Unexplained Physical Pain": [],
                "Headaches": [],
                "Insomnia": [],
                "Bumps, Cysts, other Protrusions": [],
                "Bone Dislocation": [],
                "Distention of the Stomach": [],
                "Nausea": [],
                "Foul Breath": [],
                "Miscarriages": [],
                "Blocked Conception": [],
                "Sexual Assault": [],
                "Pronounced Sleep Behaviors/Manifestations": [],
                "Minor Morphing": [],
                "Suffocation": [],
                "Choking": [],
                "Serious Physical Injury": []
            },
            "Mental Health Vexations": {
                "Weariness": [],
                "Dreams": [],
                "Depression": [],
                "Anger": [],
                "Emotional/Relational Block": [],
                "Visual Hallucinations": [],
                "Auditory Hallucinations": [],
                "Severe Mental Disorder": []
            },
            "Peripheral Vexations": {
                "Pets": [],
                "Bugs/Pests": [],
                "Financial": [],
                "Occupational": [],
                "Reputational": []
            }
        },
        "Possession": {
            "Speaking a Foreign Language": [],
            "Occult Knowledge": [],
            "Morphing": [],
            "Strength": [],
            "Appearance of Fortunae": {
                "Nails": [],
                "Glass": [],
                "Cloth": [],
                "Other": []
            },
            "Levitation": [],
            "Superhuman Speed": [],
            "Superhuman Agility": [],
            "Gravitas": [],
            "Sustained Unnatural Posture": [],
            "Fasting": [],
            "Secondary Signs": {
                "Repugnance towards Holiness": [],
                "Obscene Thoughts Around Holiness": [],
                "Blocked Prayer": [],
                "Aversion to Scripture": [],
                "Illness around Holiness": [],
                "Aversion to Sacred Names": [],
                "Pain From Holy Items": [],
                "Difficulty in Receiving Sacraments": [],
                "Liturgical Calendar Suffering": [],
                "Chronic Insomnia": [],
                "Affected Dreams": [],
                "Falsified Emotions": [],
                "Speaking in Tongues": [],
                "Possession-Specific Physical Vexation": {
                    "Foul Odor": [],
                    "Drastic Eating Changes": [],
                    "Fluctuation in Body Temperature": [],
                    "Diabolical Incandescence": []
                },
                "Suffering Spirituality": {
                    "Fruitless Self-Satisfaction": [],
                    "Anguish over sins": [],
                    "Spiritual Security": [],
                    "Self-Aggrandizing Behavior": [],
                    "Contempt for little things (spiritual)": [],
                    "Closed towards Spiritual Director": [],
                    "Nonconformity with scripture and tradition": [],
                    "animus delendi (destruction)": []
                }
            }
        }
    },
    "Ghostly Activity": {
        "Family Member/Loved One": {
            "Appearance": [],
            "Voice": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Stranger": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Individual Connected To Place/Person": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Family Pet": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        },
        "Other Animal": {
            "Visual": [],
            "Auditory": [],
            "Behavior": [],
            "Habitual Behavior": []
        }
    },
    "Cryptid": {
        "Canine": {
            "Dogman": [],
            "Werewolf": [],
            "Chupacabra": [],
            "Other": []
        },
        "Avian": {
            "Thunderbird": [],
            "Mothman": [],
            "Other": []
        },
        "Bipedal": {
            "Sasquatch": [],
            "Humanoid": [],
            "Other": []
        },
        "Aquatic": [],
        "Feline": [],
        "Cervidae": {
            "Deer": [],
            "Moose": []
        }
    },
    "Fae": {
        "Fairy": [],
        "Nymph": [],
        "Gnome": [],
        "Other": []
    },
    "Witchcraft": {
        "Flying": [],
        "Levitation": [],
        "Transportation": [],
        "Cursing": [],
        "Hagriding": [],
        "Evil Eye": [],
        "Abduction": {
            "Child": [],
            "Adult": [],
            "Pet": [],
            "Non-Pet Animal": []
        },
        "Physical Harm": [],
        "Physical Harm To Children": [],
        "Herbal/Natural": [],
        "Divination": [],
        "Harm to Crops": [],
        "Harm to Livestock": [],
        "Harm To Pets": [],
        "Sacrificing Children": [],
        "Indoctrinating Children": [],
        "Black Sabbath": [],
        "Ritual": {
            "Black Sabbath": [],
            "Contract with Demon": [],
            "Contract with Another": [],
            "Sacrilegious Baptism": [],
            "Sacrifice": {
                "Sacrificing a Person": {
                    "Sacrificing a Family Member": {
                        "Sacrificing a Parent": [],
                        "Sacrificing a Child": [],
                        "Sacrificing a Sibling": [],
                        "Sacrificing a Grandparent": [],
                        "Sacrificing an Aunt/Uncle": [],
                        "Sacrificing a cousin": [],
                        "Sacrificing a niece/nephew": []
                    },
                    "Sacrificing a Friend": [],
                    "Sacrificing a known associate": [],
                    "Sacrificing a stranger": []
                },
                "Sacrificing an Animal": [],
                "Sacrificing a Family Member": []
            },
            "Rejection of Sacraments": {
                "Rejection of Baptism": [],
                "Rejection of Confirmation": [],
                "Rejection of Confession": [],
                "Rejection of Eucharist": [],
                "Rejection of Marriage": [],
                "Rejection of Holy Orders": []
            }
        }
    },
    "Supernatural Phenomena": {
        "Time Slip": [],
        "Time Loss": []
    }
}


# ------------------------------------------------------------------ #
# Pure Tree Manipulation Functions
# ------------------------------------------------------------------ #

def merge_trees(existing_tree, new_tree):
    """
    Recursively merge two tree structures, preserving stories.
    
    Args:
        existing_tree: The base tree structure
        new_tree: The tree to merge in
    
    Returns:
        Merged tree structure
    """
    if isinstance(existing_tree, dict) and isinstance(new_tree, dict):
        merged = {}
        all_keys = set(existing_tree.keys()) | set(new_tree.keys())
        for key in all_keys:
            existing_val = existing_tree.get(key)
            new_val = new_tree.get(key)
            if existing_val is not None and new_val is not None:
                merged[key] = merge_trees(existing_val, new_val)
            elif existing_val is not None:
                merged[key] = existing_val
            else:
                merged[key] = new_val
        return merged
    elif isinstance(existing_tree, list) and isinstance(new_tree, list):
        # Merge lists (stories) - combine and deduplicate
        combined = list(set(existing_tree + new_tree))
        logger.debug(f"Merged story lists: {existing_tree} + {new_tree} = {combined}")
        return combined
    else:
        # Type mismatch - prefer content over empty
        existing_is_story_list = isinstance(existing_tree, list) and len(existing_tree) > 0
        new_is_story_list = isinstance(new_tree, list) and len(new_tree) > 0
        if existing_is_story_list and not new_is_story_list:
            return existing_tree
        elif new_is_story_list and not existing_is_story_list:
            return new_tree
        elif isinstance(existing_tree, dict) and isinstance(new_tree, list):
            return existing_tree
        elif isinstance(new_tree, dict) and isinstance(existing_tree, list):
            return new_tree
        else:
            return existing_tree


def assign_to_path(tree: dict, path: list, story: dict, stories_dict: dict) -> dict:
    """
    Assign story to path in tree.
    
    Args:
        tree: The codex tree dict
        path: List of path segments (e.g., ["Demonic Activity", "Obsession"])
        story: Story dict with at least 'title' key
        stories_dict: The stories_dict to update with full story data
    
    Returns:
        The modified tree
    """
    title = story['title']
    
    # Store full details once
    if title not in stories_dict:
        stories_dict[title] = story
    
    current = tree
    for level in path[:-1]:
        if level not in current:
            current[level] = {}
        if not isinstance(current[level], dict):
            current[level] = {'_stories': current[level]}
        current = current[level]
    
    leaf = path[-1]
    if leaf not in current:
        current[leaf] = []
    
    leaf_val = current[leaf]
    if isinstance(leaf_val, list):
        if title not in leaf_val:
            leaf_val.append(title)
    elif isinstance(leaf_val, dict):
        if '_stories' not in leaf_val:
            leaf_val['_stories'] = []
        # Handle case where _stories might be a dict (malformed tree)
        if isinstance(leaf_val['_stories'], dict):
            leaf_val['_stories'] = []
        if title not in leaf_val['_stories']:
            leaf_val['_stories'].append(title)
    else:
        raise ValueError("Invalid tree structure")
    
    return tree


def remove_from_path(tree: dict, path: list, title: str) -> dict:
    """
    Remove story from path in tree.
    
    Args:
        tree: The codex tree dict
        path: List of path segments
        title: Story title to remove
    
    Returns:
        The modified tree
    """
    current = tree
    for level in path[:-1]:
        if level not in current:
            return tree
        current = current[level]
    
    leaf = path[-1]
    if leaf in current:
        leaf_val = current[leaf]
        if isinstance(leaf_val, list) and title in leaf_val:
            leaf_val.remove(title)
        elif isinstance(leaf_val, dict) and '_stories' in leaf_val and title in leaf_val['_stories']:
            leaf_val['_stories'].remove(title)
    
    return tree


def find_paths_for_title(
    tree: dict,
    title: str,
    current_path: list = None,
    paths: list = None
) -> list:
    """
    Find all paths for a title in the tree.
    
    Args:
        tree: The codex tree dict
        title: Story title to find
        current_path: Internal - current path being traversed
        paths: Internal - accumulated paths found
    
    Returns:
        List of paths where title is assigned
    """
    if current_path is None:
        current_path = []
    if paths is None:
        paths = []
    
    if isinstance(tree, dict):
        if '_stories' in tree and title in tree['_stories']:
            paths.append(current_path[:])
        for key, value in tree.items():
            if key != '_stories':
                find_paths_for_title(value, title, current_path + [key], paths)
    elif isinstance(tree, list):
        if title in tree:
            paths.append(current_path[:])
    
    return paths


def create_category(tree: dict, parent_path: list, name: str) -> dict:
    """
    Create a new category (node) in the tree.
    
    Args:
        tree: The codex tree dict
        parent_path: List of path segments to parent (empty list for root-level)
        name: Name of the new category to create
    
    Returns:
        The modified tree
    
    Raises:
        ValueError: If parent path doesn't exist or category already exists
    """
    # Navigate to parent
    if not parent_path:
        # Creating at root level
        if name in tree:
            raise ValueError(f"Category '{name}' already exists at root level")
        tree[name] = []  # Empty list = leaf node with no stories
        logger.info(f"Created root-level category: {name}")
        return tree
    
    current = tree
    for i, level in enumerate(parent_path):
        if level not in current:
            raise ValueError(f"Parent path not found: {'/'.join(parent_path[:i+1])}")
        
        node = current[level]
        if isinstance(node, list):
            # Convert leaf to dict to allow children
            current[level] = {'_stories': node}
            node = current[level]
        
        if not isinstance(node, dict):
            raise ValueError(f"Invalid tree structure at: {'/'.join(parent_path[:i+1])}")
        
        if i < len(parent_path) - 1:
            current = node
        else:
            # At parent node
            if name in node and name != '_stories':
                raise ValueError(f"Category '{name}' already exists under '{'/'.join(parent_path)}'")
            node[name] = []  # Empty list = leaf node with no stories
            logger.info(f"Created category '{name}' under '{'/'.join(parent_path)}'")
    
    return tree


def delete_category(tree: dict, path: list) -> tuple:
    """
    Delete a category (node) from the tree.
    
    Args:
        tree: The codex tree dict
        path: Full path to the category to delete
    
    Returns:
        Tuple of (modified tree, list of affected story titles)
    
    Raises:
        ValueError: If path doesn't exist
    """
    if not path:
        raise ValueError("Cannot delete root of tree")
    
    affected_stories = []
    
    def collect_stories(node):
        """Recursively collect all story titles from a node and its children."""
        stories = []
        if isinstance(node, list):
            stories.extend(node)
        elif isinstance(node, dict):
            if '_stories' in node:
                stories.extend(node['_stories'])
            for key, value in node.items():
                if key != '_stories':
                    stories.extend(collect_stories(value))
        return stories
    
    # Navigate to parent
    if len(path) == 1:
        # Deleting root-level category
        if path[0] not in tree:
            raise ValueError(f"Category not found: {path[0]}")
        affected_stories = collect_stories(tree[path[0]])
        del tree[path[0]]
        logger.info(f"Deleted root-level category: {path[0]}")
        return tree, affected_stories
    
    current = tree
    for i, level in enumerate(path[:-1]):
        if level not in current:
            raise ValueError(f"Path not found: {'/'.join(path[:i+1])}")
        
        node = current[level]
        if isinstance(node, list):
            raise ValueError(f"Cannot navigate through leaf node at: {'/'.join(path[:i+1])}")
        
        if not isinstance(node, dict):
            raise ValueError(f"Invalid tree structure at: {'/'.join(path[:i+1])}")
        
        current = node
    
    # Delete the target
    target = path[-1]
    if target not in current:
        raise ValueError(f"Category not found: {'/'.join(path)}")
    
    affected_stories = collect_stories(current[target])
    del current[target]
    logger.info(f"Deleted category '{target}' from path '{'/'.join(path[:-1])}'")
    
    return tree, affected_stories


def get_category_info(tree: dict, path: list) -> dict:
    """
    Get information about a category.
    
    Args:
        tree: The codex tree dict
        path: Full path to the category
    
    Returns:
        Dict with keys: exists, has_children, has_stories, story_count, child_count
    """
    if not path:
        # Root of tree
        child_count = len([k for k in tree.keys() if k != '_stories'])
        return {
            'exists': True,
            'has_children': child_count > 0,
            'has_stories': False,
            'story_count': 0,
            'child_count': child_count
        }
    
    current = tree
    for level in path:
        if level not in current:
            return {'exists': False}
        current = current[level]
    
    if isinstance(current, list):
        return {
            'exists': True,
            'has_children': False,
            'has_stories': len(current) > 0,
            'story_count': len(current),
            'child_count': 0
        }
    elif isinstance(current, dict):
        story_count = len(current.get('_stories', []))
        child_count = len([k for k in current.keys() if k != '_stories'])
        return {
            'exists': True,
            'has_children': child_count > 0,
            'has_stories': story_count > 0,
            'story_count': story_count,
            'child_count': child_count
        }
    
    return {'exists': False}
