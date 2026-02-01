# ==================================================================================
# BLOCK 3: METADATA EXTRACTION FUNCTIONS (Grok-Powered)
# ==================================================================================
# This block defines functions for extracting structured metadata:
# - Temporal (years, centuries) - Rule-based for accuracy
# - Locations (cities, regions, countries) - Grok + WikiData
# - Topics (phenomena, entities, context) - Grok intelligent analysis
# - Keyword synthesis
# - Confidence calculation

# ========================== TEMPORAL EXTRACTION ==========================

CENTURY_WORDS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "twenty-first": 21
}

# Map historical period names to century ranges
HISTORICAL_PERIODS = {
    "medieval": (5, 15),
    "middle ages": (5, 15),
    "dark ages": (5, 10),
    "early medieval": (5, 10),
    "high medieval": (11, 13),
    "late medieval": (14, 15),
    "renaissance": (14, 17),
    "reformation": (16, 17),
    "enlightenment": (17, 18),
    "victorian": (19, 19),
    "baroque": (17, 18),
    "gothic": (12, 16),
    "carolingian": (8, 9),
    "merovingian": (5, 8),
    "byzantine": (4, 15),
    "crusades": (11, 13),
    "counter-reformation": (16, 17),
    "early modern": (15, 18),
    "ancient": (1, 5)
}

def extract_temporal(content: str) -> Dict:
    """Extract temporal metadata from story content."""
    temporal = {
        "years": [],
        "centuries": [],
        "decades": []
    }
    
    content_lower = content.lower()
    
    # 1. Years: 4-digit years
    year_patterns = [
        r'\b(1[0-9]{3})\b',  # 1000-1999
        r'\b(20[0-2][0-9])\b',  # 2000-2029
        r'A\.?D\.?\s*(\d{3,4})',  # A.D. years
        r'(\d{3,4})\s*A\.?D\.?',
    ]
    years_found = set()
    for pattern in year_patterns:
        matches = re.findall(pattern, content, re.I)
        for m in matches:
            try:
                year = int(m)
                if 500 <= year <= 2030:
                    years_found.add(year)
            except:
                pass
    
    # 2. Early medieval years (500-999) with context
    early_year_pattern = r'(?:died in|born in|year|in the year|circa|c\.)\s*(\d{3})'
    early_matches = re.findall(early_year_pattern, content, re.I)
    for m in early_matches:
        try:
            year = int(m)
            if 500 <= year <= 999:
                years_found.add(year)
        except:
            pass
    
    # 3. Date ranges
    range_patterns = [
        r'(\d{4})\s*[-–—]\s*(\d{4})',
        r'from\s+(\d{4})\s+to\s+(\d{4})',
        r'between\s+(\d{4})\s+and\s+(\d{4})',
    ]
    for pattern in range_patterns:
        matches = re.findall(pattern, content, re.I)
        for start, end in matches:
            try:
                start_year, end_year = int(start), int(end)
                if 500 <= start_year <= 2030 and 500 <= end_year <= 2030:
                    for y in range(start_year, min(end_year + 1, start_year + 20)):
                        years_found.add(y)
            except:
                pass
    
    # 4. Centuries
    centuries_found = set()
    century_num = re.findall(r'(\d{1,2})(?:st|nd|rd|th)[\s-]+century', content, re.I)
    for c in century_num:
        try:
            centuries_found.add(int(c))
        except:
            pass
    
    for word, num in CENTURY_WORDS.items():
        if re.search(rf'\b{word}\s+century\b', content_lower):
            centuries_found.add(num)
    
    # 4a. Early/Mid/Late century patterns (e.g., "mid-18th century", "late sixteenth century")
    early_mid_late_patterns = [
        r'(?:early|mid|late)[\s-]+(\d{1,2})(?:st|nd|rd|th)[\s-]+century',
    ]
    for pattern in early_mid_late_patterns:
        matches = re.findall(pattern, content, re.I)
        for c in matches:
            try:
                centuries_found.add(int(c))
            except:
                pass
    
    # Match "early/mid/late" with spelled-out centuries
    for word, num in CENTURY_WORDS.items():
        if re.search(rf'\b(?:early|mid|late)[\s-]+{word}\s+century\b', content_lower):
            centuries_found.add(num)
    
    # 4b. Historical period names
    for period_name, (start_century, end_century) in HISTORICAL_PERIODS.items():
        pattern = rf'\b{re.escape(period_name)}(?:\s+(?:period|era|age))?\b'
        if re.search(pattern, content_lower):
            # Add all centuries in the range
            for c in range(start_century, end_century + 1):
                centuries_found.add(c)
    
    # Infer centuries from years
    for year in years_found:
        century = (year - 1) // 100 + 1
        centuries_found.add(century)
    
    # 5. Use Grok to infer dates from historical figures if no explicit dates found
    if not years_found and not centuries_found:
        inferred_temporal = infer_temporal_from_figures(content)
        years_found.update(inferred_temporal.get("years", []))
        centuries_found.update(inferred_temporal.get("centuries", []))
    
    temporal["years"] = sorted(list(years_found))
    temporal["centuries"] = sorted(list(centuries_found))
    
    return temporal


def infer_temporal_from_figures(content: str) -> Dict:
    """Use Grok to infer temporal context from named historical figures."""
    try:
        client = globals().get('grok_client')
        model = globals().get('GROK_MODEL', 'grok-4-1-fast-reasoning')
        if not client:
            return {"years": [], "centuries": []}
    except Exception:
        return {"years": [], "centuries": []}
    
    prompt = f"""Analyze this historical text and identify any named historical figures (saints, popes, monarchs, etc.).
For each figure, provide their approximate time period.

Text:
{content[:1500]}

Return ONLY a JSON object:
{{
  "figures": [
    {{"name": "Saint Walbert", "estimated_year": 670, "century": 7, "confidence": 0.8}},
    {{"name": "Pope Gregory VII", "estimated_year": 1077, "century": 11, "confidence": 0.95}}
  ]
}}

If no identifiable historical figures are found, return: {{"figures": []}}"""
    
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        result_text = response.choices[0].message.content.strip()
        
        if "```json" in result_text:
            result_text = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
            if result_text:
                result_text = result_text.group(1)
        elif "```" in result_text:
            result_text = re.search(r'```\s*(.*?)\s*```', result_text, re.DOTALL)
            if result_text:
                result_text = result_text.group(1)
        
        data = json.loads(result_text)
        figures = data.get("figures", [])
        
        years = set()
        centuries = set()
        for fig in figures:
            if fig.get("confidence", 0) >= 0.7:
                if fig.get("estimated_year"):
                    years.add(fig["estimated_year"])
                if fig.get("century"):
                    centuries.add(fig["century"])
        
        return {"years": list(years), "centuries": list(centuries)}
        
    except Exception as e:
        print(f"Grok temporal inference failed: {e}")
        return {"years": [], "centuries": []}


# ========================== LOCATION EXTRACTION ==========================

def extract_raw_locations(content: str) -> List[str]:
    """Extract raw location mentions using spaCy NER."""
    doc = nlp(content[:10000])
    
    locations = set()
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC", "FAC"]:
            clean_text = ent.text.strip()
            if len(clean_text) > 2 and not clean_text.isdigit():
                locations.add(clean_text)
    
    return list(locations)


def lookup_wikidata(location: str) -> Dict:
    """Query WikiData for location normalization."""
    try:
        url = f"https://www.wikidata.org/w/api.php"
        params = {
            "action": "wbsearchentities",
            "format": "json",
            "language": "en",
            "search": location,
            "limit": 1
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        
        if data.get("search"):
            result = data["search"][0]
            return {
                "name": result.get("label", location),
                "type": "city",
                "confidence": 0.7
            }
    except:
        pass
    return None


def extract_locations_with_grok(content: str, story_title: str) -> List[Dict]:
    """Use Grok to directly extract and normalize locations."""
    try:
        client = globals().get('grok_client')
        model = globals().get('GROK_MODEL', 'grok-4-1-fast-reasoning')
        if not client:
            return []
    except Exception:
        return []
    
    prompt = f"""Extract all location references from this historical text titled "{story_title}".

Text:
{content[:1500]}  

For each location found, return:
1. The exact name as it appears
2. Type: "city", "region", "country", or "landmark"
3. Modern name if different
4. Country it's in
5. Confidence (0-1)

IMPORTANT: Be sure to extract:
- Specific cities (e.g., "Loudun", "Mur")
- Regions/provinces (e.g., "Tuscany", "Bavaria", "Rhineland", "Eichsfeld")
- Countries
- Religious sites (monasteries, shrines)

Return ONLY a JSON array:
[
  {{"original": "Tuscany", "name": "Tuscany", "type": "region", "country": "Italy", "confidence": 0.95}},
  {{"original": "Mur", "name": "Mur", "type": "city", "country": "Austria", "confidence": 0.8}}
]

Return empty array [] if no locations found."""
    
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        result_text = response.choices[0].message.content.strip()
        
        if "```json" in result_text:
            result_text = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
            if result_text:
                result_text = result_text.group(1)
        elif "```" in result_text:
            result_text = re.search(r'```\s*(.*?)\s*```', result_text, re.DOTALL)
            if result_text:
                result_text = result_text.group(1)
        
        locations = json.loads(result_text)
        return locations if isinstance(locations, list) else []
        
    except Exception as e:
        print(f"Grok location extraction failed: {e}")
        return []


def normalize_with_grok(locations: List[str], story_title: str) -> List[Dict]:
    """Use Grok to normalize unknown locations."""
    if not locations:
        return []
    
    try:
        client = globals().get('grok_client')
        model = globals().get('GROK_MODEL', 'grok-4-1-fast-reasoning')
        if not client:
            print("Grok client not initialized, skipping normalization")
            return []
    except Exception as e:
        print(f"Grok client not available: {e}")
        return []
    
    prompt = f"""I have these location names extracted from a historical supernatural/religious text titled "{story_title}". 
For each location, provide:
1. The modern/canonical name
2. Type: "city", "region", or "country"
3. The country it's in (if city or region)
4. Any historical context if the name is archaic

Locations to normalize:
{json.dumps(locations, indent=2)}

Return ONLY a JSON array with objects like:
[
  {{"original": "Loudun", "name": "Loudun", "type": "city", "region": "Nouvelle-Aquitaine", "country": "France", "confidence": 0.95}},
  {{"original": "the Rhineland", "name": "Rhineland", "type": "region", "country": "Germany", "confidence": 0.9}},
  {{"original": "the monastery", "name": null, "type": null, "country": null, "confidence": 0.0, "note": "Too vague to identify"}}
]

If a location cannot be identified, set confidence to 0 and name to null.
Return ONLY the JSON array, no other text."""

    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        result_text = response.choices[0].message.content.strip()
        
        if "```json" in result_text:
            result_text = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
            if result_text:
                result_text = result_text.group(1)
        elif "```" in result_text:
            result_text = re.search(r'```\s*(.*?)\s*```', result_text, re.DOTALL)
            if result_text:
                result_text = result_text.group(1)
        
        normalized = json.loads(result_text)
        return normalized
        
    except Exception as e:
        print(f"Grok normalization failed: {e}")
        return []


# Location cache management
def load_location_cache() -> Dict:
    """Load cached location normalizations."""
    cache_file = os.path.join(cache_dir, "location_cache.json")
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_location_cache(cache: Dict):
    """Save location cache to disk."""
    cache_file = os.path.join(cache_dir, "location_cache.json")
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def extract_and_normalize_locations(content: str, story_title: str, cache: Dict) -> Dict:
    """
    Full location extraction pipeline:
    1. spaCy NER for raw mentions
    2. Check cache for known locations
    3. WikiData for unknown locations
    4. Grok fallback for remaining
    """
    raw_locations = extract_raw_locations(content)
    
    # If spaCy found very few locations, use Grok to extract directly
    if len(raw_locations) < 3:
        print("  Low spaCy coverage, using Grok for location extraction...")
        grok_locs = extract_locations_with_grok(content, story_title)
        if grok_locs:
            for loc in grok_locs:
                if loc.get('confidence', 0) >= 0.6:
                    raw_locations.append(loc.get('original', loc.get('name', '')))
    
    if not raw_locations:
        return {
            "cities": [],
            "regions": [],
            "countries": [],
            "raw_mentions": [],
            "normalized": []
        }
    
    normalized = []
    unknown = []
    
    # Check cache first
    for loc in raw_locations:
        loc_key = loc.lower().strip()
        if loc_key in cache:
            normalized.append(cache[loc_key])
        else:
            # Try WikiData
            wiki_result = lookup_wikidata(loc)
            if wiki_result and wiki_result.get("confidence", 0) >= 0.5:
                wiki_result["original"] = loc
                cache[loc_key] = wiki_result
                normalized.append(wiki_result)
            else:
                unknown.append(loc)
    
    # Grok fallback for remaining unknowns
    if unknown:
        grok_results = normalize_with_grok(unknown, story_title)
        for result in grok_results:
            if result.get("confidence", 0) >= 0.5:
                original = result.get("original", "").lower().strip()
                cache[original] = result
                normalized.append(result)
    
    # Build structured output
    cities = []
    regions = []
    countries = set()
    
    for loc in normalized:
        if loc.get("type") == "city":
            cities.append(loc.get("name"))
            if loc.get("country"):
                countries.add(loc.get("country"))
        elif loc.get("type") == "region":
            regions.append(loc.get("name"))
            if loc.get("country"):
                countries.add(loc.get("country"))
        elif loc.get("type") == "country":
            countries.add(loc.get("name"))
    
    return {
        "cities": list(set(cities)),
        "regions": list(set(regions)),
        "countries": sorted(list(countries)),
        "raw_mentions": raw_locations,
        "normalized": normalized
    }


# ========================== TOPIC EXTRACTION (GROK-POWERED) ==========================

def extract_topics_with_grok(content: str) -> Dict[str, List[str]]:
    """
    Use Grok to perform intelligent topic extraction.
    Replaces brittle keyword matching with semantic understanding.
    """
    try:
        client = globals().get('grok_client')
        model = globals().get('GROK_MODEL', 'grok-4-1-fast-reasoning')
        if not client:
            print("Warning: Grok client missing, skipping topic extraction")
            return {"primary": [], "secondary": []}
    except Exception:
        return {"primary": [], "secondary": []}

    prompt = f"""Analyze this supernatural/historical story and extract relevant tags.
    
Story Content:
{content[:2500]}

Extract terms for:
1. Phenomena (e.g., Possession, Exorcism, Levitation, Stigmata, Visions, Miracles, Witchcraft)
   - Include symptom descriptors: Howling, Lamentations, Convulsions, Levitation
2. Entities (e.g., Demon, Angel, Saint, Ghost, Witch, Monk, Oppressed Spirits)
3. Implements/Objects (e.g., Relic, Cross, Charm, Holy Water, Bone, Cursed Object)
4. Context (e.g., Monastery, Church, Witch Trial, Inquisition, Graveyard)
5. People - Extract ALL named individuals:
   - Saints (Saint Walbert, St. Boniface, St. Amalberga)
   - Historical figures (Gregory VII, Charlemagne, Heizzo)
   - Authors/witnesses (Laurentius, Hieronymus, Stephen)
6. Functional Purpose (e.g., Testing/Diagnosis, Protection, Curse, Healing, Binding)
7. Historical Groups (e.g., Saxons, Camaldolese, Franks)

Rules:
- Be specific (e.g., "Violent Possession" vs "Possession")
- Extract ALL named people, even minor mentions
- Include symptom descriptors (howling, lamentations)
- Capture historical/ethnic groups (Saxons, etc.)
- Infer topics from context
- Use standard English terms

Return ONLY a JSON object:
{{
  "phenomena": ["...", "..."],
  "entities": ["...", "..."],
  "implements": ["...", "..."],
  "context": ["...", "..."],
  "people": ["...", "..."],
  "functional_purpose": ["...", "..."],
  "historical_groups": ["...", "..."]
}}
"""
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Clean markdown
        if "```json" in result_text:
            result_text = re.search(r'```json\s*(.*?)\s*```', result_text, re.DOTALL)
            if result_text:
                result_text = result_text.group(1)
        elif "```" in result_text:
            result_text = re.search(r'```\s*(.*?)\s*```', result_text, re.DOTALL)
            if result_text:
                result_text = result_text.group(1)
        
        data = json.loads(result_text)
        
        # Flatten for downstream
        primary = data.get("phenomena", []) + data.get("context", []) + data.get("functional_purpose", [])
        secondary = (data.get("entities", []) + data.get("implements", []) + 
                    data.get("people", []) + data.get("historical_groups", []))
        
        return {
            "primary": [x.lower() for x in primary if x],
            "secondary": [x.lower() for x in secondary if x],
            "raw_analysis": data
        }
        
    except Exception as e:
        print(f"Grok topic extraction failed: {e}")
        return {"primary": [], "secondary": []}


def extract_domain_topics(content: str) -> Dict:
    """Main entry point for topic extraction (Grok-powered)."""
    return extract_topics_with_grok(content)


# ========================== KEYWORD SYNTHESIS ==========================

def synthesize_keywords(title: str, temporal: Dict, locations: Dict, 
                       topics: Dict, existing_keywords: List[str]) -> List[str]:
    """
    Synthesize rich keywords from all extracted metadata.
    Prioritizes: people > locations > topics > temporal.
    """
    # Use lists to preserve priority order instead of sets
    keywords = []
    seen = set()
    
    def add_unique(term):
        """Helper to add term only if not seen."""
        term_lower = term.lower().strip()
        if term_lower and term_lower not in seen and len(term_lower) > 1:
            keywords.append(term_lower)
            seen.add(term_lower)
    
    raw_topics = topics.get("raw_analysis", {})
    
    # PRIORITY 1: Named People (highest value)
    for person in raw_topics.get("people", []):
        add_unique(person)
    
    # PRIORITY 2: All Locations (cities, regions, countries)
    for city in locations.get("cities", []):
        add_unique(city)
    for region in locations.get("regions", []):
        add_unique(region)
    for country in locations.get("countries", []):
        add_unique(country)
    
    # PRIORITY 3: Functional Purposes
    for purpose in raw_topics.get("functional_purpose", []):
        add_unique(purpose.replace("_", " "))
    
    # PRIORITY 4: Primary Topics (phenomena + context)
    for topic in topics.get("primary", [])[:12]:  # Increased from 8
        add_unique(topic.replace("_", " "))
    
    # PRIORITY 5: Secondary Topics (entities + implements)
    for topic in topics.get("secondary", [])[:10]:  # Increased from 6
        add_unique(topic.replace("_", " "))
    
    # PRIORITY 6: Temporal - ALL Centuries (important for historical search)
    for century in temporal.get("centuries", []):
        add_unique(f"{century}th century")
    
    # PRIORITY 7: ALL Years (important for precise dating)
    for year in temporal.get("years", []):
        add_unique(str(year))
    
    # Return in priority order, cap at 50 keywords (user increased from 30)
    return keywords[:50]


# ========================== CONFIDENCE & VALIDATION ==========================

def calculate_confidence(temporal: Dict, locations: Dict, topics: Dict) -> float:
    """
    Calculate confidence score (0-1) based on extraction quality.
    Equal weighting: 33% temporal, 33% locations, 33% topics.
    """
    score = 0.0
    
    # Temporal (33%)
    has_temporal = bool(temporal.get("years") or temporal.get("centuries"))
    if has_temporal:
        score += 0.33
    
    # Locations (33%)
    has_locations = bool(locations.get("cities") or locations.get("countries"))
    if has_locations:
        score += 0.33
    
    # Topics (33%)
    has_topics = bool(topics.get("primary"))
    if has_topics:
        score += 0.33
    
    # Small bonus for having rich data
    if len(temporal.get("years", [])) > 0 and len(locations.get("cities", [])) > 0 and len(topics.get("primary", [])) > 1:
        score += 0.1
    
    return min(score, 1.0)


def generate_warnings(temporal: Dict, locations: Dict, topics: Dict) -> List[str]:
    """Generate human-readable warnings for low-confidence extractions."""
    warnings = []
    
    if not temporal.get("years") and not temporal.get("centuries"):
        warnings.append("No temporal data extracted")
    
    if not locations.get("cities") and not locations.get("countries"):
        warnings.append("No specific locations identified")
    
    if not topics.get("primary"):
        warnings.append("No primary topics detected")
    elif len(topics.get("primary", [])) < 2:
        warnings.append("Very few topics identified - may need manual review")
    
    return warnings


# ==================================================================================
# UNCOMMENT TO TEST:
# ==================================================================================
# sample_text = "In 1632, at Loudun in France, a possessed nun began levitating..."
# print(extract_temporal(sample_text))
# print(extract_domain_topics(sample_text))
