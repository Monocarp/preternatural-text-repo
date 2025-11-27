from typing import List, Dict

def get_stories_for_subcats(tree: Dict, path_parts: List[str], subcat_names: List[str]) -> List[str]:
    """
    Given a tree, path parts, and list of subcategory names,
    return deduplicated list of story titles from those subcategories.
    Tree structure: nested dicts where '_stories' key contains story titles.
    Example: tree["Demonic Activity"]["Possession"]["_stories"] = ["Title1", "Title2"]
    
    Args:
        tree: The full category tree dictionary
        path_parts: List of path segments to navigate to base node (e.g., ["Demonic Activity", "Possession"])
        subcat_names: List of subcategory names to filter by (e.g., ["Exorcism", "Demonic Pacts"])
    
    Returns:
        A deduplicated list of story titles from the specified subcategories under the base path
    """
    # Navigate to base node using path parts
    node = tree
    for part in path_parts:
        if not isinstance(node, dict) or part not in node:
            return []
        node = node[part]
    
    if not isinstance(node, dict):
        return []
    
    result_stories = set()
    
    for subcat_name in subcat_names:
        if subcat_name in node and isinstance(node[subcat_name], dict):
            # Collect stories recursively from this subcategory
            _collect_stories_recursive(node[subcat_name], result_stories)
    
    return sorted(list(result_stories))

def _collect_stories_recursive(node: Dict, stories_set: set):
    """
    Helper function to recursively collect story titles from a node and its children.
    
    Args:
        node: Current node in the tree (dictionary)
        stories_set: Set to accumulate unique story titles
    """
    if "_stories" in node and node["_stories"]:
        stories_set.update(node["_stories"])
    
    for key, child_node in node.items():
        if key != "_stories" and isinstance(child_node, dict):
            _collect_stories_recursive(child_node, stories_set)