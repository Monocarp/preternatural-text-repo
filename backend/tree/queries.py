from typing import List, Dict, Union

def get_stories_for_subcats(tree: Dict, path_parts: List[str], subcat_names: List[str]) -> List[str]:
    """
    Given a tree, path parts, and list of subcategory names,
    return deduplicated list of story titles from those subcategories.
    
    Tree structure supports two formats:
    1. Nested dicts where '_stories' key contains story titles:
       tree["Demonic Activity"]["Possession"]["_stories"] = ["Title1", "Title2"]
    2. Leaf nodes that are directly lists of story titles:
       tree["Witchcraft"]["Flying"] = ["Title1", "Title2"]
    
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
        if subcat_name not in node:
            continue
        subcat_value = node[subcat_name]
        
        if isinstance(subcat_value, list):
            # Leaf node: subcategory value is directly a list of story titles
            result_stories.update(subcat_value)
        elif isinstance(subcat_value, dict):
            # Branch node: subcategory is a dict, recurse to collect stories
            _collect_stories_recursive(subcat_value, result_stories)
    
    return sorted(list(result_stories))

def _collect_stories_recursive(node: Union[Dict, List], stories_set: set):
    """
    Helper function to recursively collect story titles from a node and its children.
    
    Args:
        node: Current node in the tree (dictionary or list)
        stories_set: Set to accumulate unique story titles
    """
    # Handle case where node is directly a list of story titles
    if isinstance(node, list):
        stories_set.update(node)
        return
    
    # Handle dict node
    if not isinstance(node, dict):
        return
    
    if "_stories" in node and node["_stories"]:
        # _stories can be a list or empty dict
        if isinstance(node["_stories"], list):
            stories_set.update(node["_stories"])
    
    for key, child_node in node.items():
        if key != "_stories":
            if isinstance(child_node, list):
                # Child is a list of story titles (leaf node)
                stories_set.update(child_node)
            elif isinstance(child_node, dict):
                # Child is a dict, recurse
                _collect_stories_recursive(child_node, stories_set)