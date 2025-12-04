# backend/routes/ai.py
"""
AI-powered category suggestion endpoint using Grok API.
"""

import os
import json
import logging
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from .dependencies import DATA_DIR

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["ai"])

# Load config from environment
GROK_API_KEY = os.environ.get("GROK_API_KEY")
XAI_MODEL = os.environ.get("XAI_MODEL", "grok-2-latest")
XAI_API_URL = "https://api.x.ai/v1/chat/completions"


class SuggestCategoriesRequest(BaseModel):
    story_title: str
    story_text: str


class CategorySuggestion(BaseModel):
    path: List[str]
    confidence: float
    reason: Optional[str] = None


class SuggestCategoriesResponse(BaseModel):
    suggestions: List[CategorySuggestion]
    model_used: str


def build_category_tree_prompt(codex_tree: dict) -> str:
    """Build a formatted category hierarchy for the prompt."""
    
    def format_node(node: dict, path: List[str] = [], indent: int = 0) -> List[str]:
        lines = []
        prefix = "  " * indent
        
        for key, value in sorted(node.items()):
            if key == "_stories":
                continue  # Skip story lists
            
            current_path = path + [key]
            path_str = " > ".join(current_path)
            
            if isinstance(value, dict) and len([k for k in value.keys() if k != "_stories"]) > 0:
                lines.append(f"{prefix}- {key}")
                lines.extend(format_node(value, current_path, indent + 1))
            elif isinstance(value, dict):
                lines.append(f"{prefix}- {key} (leaf)")
            elif isinstance(value, list):
                lines.append(f"{prefix}- {key} (leaf)")
        
        return lines
    
    lines = format_node(codex_tree)
    return "\n".join(lines)


def build_system_prompt(codex_tree: dict) -> str:
    """Build the system prompt with category taxonomy."""
    
    category_tree = build_category_tree_prompt(codex_tree)
    
    return f"""You are a categorization assistant for a paranormal/supernatural story database. Your task is to analyze a story and suggest the most appropriate categories from the taxonomy below.

## CATEGORY TAXONOMY:
{category_tree}

## INSTRUCTIONS:
1. Read the story carefully
2. Identify ALL relevant categories (stories often fit multiple categories)
3. Be as specific as possible - choose the deepest subcategory that applies
4. Assign a confidence score (0.0 to 1.0) for each suggestion
5. Provide a brief reason for each suggestion

## RESPONSE FORMAT:
Respond with a JSON array of suggestions. Each suggestion must have:
- "path": array of strings representing the category path (e.g., ["Demonic Activity", "Possession", "Levitation"])
- "confidence": number between 0.0 and 1.0
- "reason": brief explanation (1 sentence)

Example response:
```json
[
  {{"path": ["Demonic Activity", "Possession", "Levitation"], "confidence": 0.95, "reason": "Story explicitly describes the subject floating off the ground during an exorcism."}},
  {{"path": ["Witchcraft", "Ritual", "Contract", "With a Demon"], "confidence": 0.8, "reason": "The narrative mentions a pact made with a demonic entity."}}
]
```

Only respond with the JSON array, no other text."""


@router.post("/suggest-categories", response_model=SuggestCategoriesResponse)
async def suggest_categories(request: SuggestCategoriesRequest):
    """
    Use Grok AI to suggest categories for a story.
    """
    if not GROK_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="GROK_API_KEY environment variable is not set"
        )
    
    # Load the codex tree
    tree_path = os.path.join(DATA_DIR, "codex_tree.json")
    try:
        with open(tree_path, "r", encoding="utf-8") as f:
            codex_tree = json.load(f)
    except Exception as e:
        log.error(f"Failed to load codex tree: {e}")
        raise HTTPException(status_code=500, detail="Failed to load category tree")
    
    # Build the prompt
    system_prompt = build_system_prompt(codex_tree)
    user_message = f"## STORY TITLE:\n{request.story_title}\n\n## STORY TEXT:\n{request.story_text}"
    
    # Call Grok API
    headers = {
        "Authorization": f"Bearer {GROK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": XAI_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.3,  # Lower temperature for more consistent categorization
        "max_tokens": 2000
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(XAI_API_URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
    except httpx.TimeoutException:
        log.error("Grok API request timed out")
        raise HTTPException(status_code=504, detail="AI request timed out")
    except httpx.HTTPStatusError as e:
        log.error(f"Grok API error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=502, detail=f"AI service error: {e.response.status_code}")
    except Exception as e:
        log.error(f"Grok API request failed: {e}")
        raise HTTPException(status_code=502, detail="Failed to connect to AI service")
    
    # Parse the response
    try:
        content = result["choices"][0]["message"]["content"]
        
        # Extract JSON from the response (handle markdown code blocks)
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        suggestions_raw = json.loads(content)
        
        # Validate and convert to response model
        suggestions = []
        for s in suggestions_raw:
            if isinstance(s.get("path"), list) and len(s["path"]) > 0:
                suggestions.append(CategorySuggestion(
                    path=s["path"],
                    confidence=float(s.get("confidence", 0.5)),
                    reason=s.get("reason")
                ))
        
        # Sort by confidence descending
        suggestions.sort(key=lambda x: x.confidence, reverse=True)
        
        log.info(f"AI suggested {len(suggestions)} categories for '{request.story_title}'")
        
        return SuggestCategoriesResponse(
            suggestions=suggestions,
            model_used=XAI_MODEL
        )
        
    except json.JSONDecodeError as e:
        log.error(f"Failed to parse AI response as JSON: {e}\nContent: {content[:500]}")
        raise HTTPException(status_code=500, detail="Failed to parse AI response")
    except Exception as e:
        log.error(f"Error processing AI response: {e}")
        raise HTTPException(status_code=500, detail="Error processing AI response")


@router.get("/status")
async def ai_status():
    """Check if AI features are configured."""
    return {
        "configured": bool(GROK_API_KEY),
        "model": XAI_MODEL if GROK_API_KEY else None
    }
