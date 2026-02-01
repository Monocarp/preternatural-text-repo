# ==================================================================================
# BLOCK 1: DEPENDENCIES & SETUP
# ==================================================================================
# Run this cell FIRST to install all dependencies and set up API keys

!pip install -q spacy openai anthropic
!pip install -q haystack-ai==2.5.1 sentence-transformers==3.1.1 numpy==1.26.4
!pip install -q faiss-cpu==1.8.0 --no-deps
!python -m spacy download en_core_web_trf

import os
import json
import re
import difflib
import numpy as np
import faiss
import spacy
import requests
from collections import Counter
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from haystack import Document
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack.document_stores.in_memory import InMemoryDocumentStore
from google.colab import files, userdata

# ========================== API KEYS ==========================
# OpenAI (for story extraction)
openai_api_key = None
try:
    openai_api_key = userdata.get('OPENAI_API_KEY')
    if openai_api_key and not isinstance(openai_api_key, str):
        openai_api_key = None  # userdata returned non-string
except Exception:
    openai_api_key = None

if not openai_api_key:
    print("OpenAI API key not found in Colab secrets.")
    print("Please enter it manually or add it to Colab Secrets.")
    openai_api_key = input("Enter your OpenAI API key: ")
    if isinstance(openai_api_key, str):
        openai_api_key = openai_api_key.strip()
    else:
        openai_api_key = str(openai_api_key).strip()

if not openai_api_key:
    raise ValueError("OpenAI API key is required!")

from openai import OpenAI
openai_client = OpenAI(api_key=openai_api_key)
OPENAI_MODEL = "gpt-5.1-2025-11-13"  # your original model

# Grok API (for location normalization)
grok_api_key = None
try:
    grok_api_key = userdata.get('GROK_API_KEY')
    if grok_api_key and not isinstance(grok_api_key, str):
        grok_api_key = None  # userdata returned non-string
except Exception:
    grok_api_key = None

if not grok_api_key:
    print("Grok API key not found in Colab secrets.")
    print("Please enter it manually or add it to Colab Secrets.")
    grok_api_key = input("Enter your Grok API key: ")
    if isinstance(grok_api_key, str):
        grok_api_key = grok_api_key.strip()
    else:
        grok_api_key = str(grok_api_key).strip()

if not grok_api_key:
    raise ValueError("Grok API key is required!")

# Grok uses OpenAI-compatible API
grok_client = OpenAI(
    api_key=grok_api_key,
    base_url="https://api.x.ai/v1"
)
GROK_MODEL = "grok-4-1-fast-reasoning"

# Load spaCy model
print("Loading spaCy model...")
nlp = spacy.load("en_core_web_trf")
print("spaCy model loaded!")

# ========================== DIRECTORY SETUP ==========================
books_dir = "/content/books/"
data_dir = "/content/data/"
cache_dir = "/content/cache/"
os.makedirs(books_dir, exist_ok=True)
os.makedirs(data_dir, exist_ok=True)
os.makedirs(cache_dir, exist_ok=True)

# Location cache (persists across books)
LOCATION_CACHE_PATH = os.path.join(cache_dir, "location_cache.json")

def load_location_cache() -> Dict:
    if os.path.exists(LOCATION_CACHE_PATH):
        with open(LOCATION_CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_location_cache(cache: Dict):
    with open(LOCATION_CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

print("Setup complete!")
