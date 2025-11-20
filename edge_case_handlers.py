# Comprehensive Edge Case Handlers for Preprocessing Pipeline

import re
import unicodedata
from typing import List, Tuple, Dict
import logging

logger = logging.getLogger(__name__)

class RobustPreprocessor:
    """Enhanced preprocessor that handles edge cases"""
    
    def __init__(self):
        self.encoding_errors = []
        self.page_anomalies = []
        self.sentence_warnings = []
    
    def detect_and_preserve_special_formatting(self, text: str) -> Tuple[str, Dict]:
        """Preserve special characters and formatting"""
        # Create a map of special sequences
        special_map = {}
        counter = 0
        
        # Patterns to preserve
        patterns = [
            (r'«([^»]+)»', 'guillemets'),  # French quotes
            (r'"([^"]+)"', 'smart_quotes'),  # Smart quotes
            (r'\[([^\]]+)\]', 'brackets'),   # Editorial brackets
            (r'<([^>]+)>', 'angles'),        # Angle brackets
        ]
        
        preserved_text = text
        for pattern, ptype in patterns:
            for match in re.finditer(pattern, text):
                key = f"__PRESERVE_{counter}__"
                special_map[key] = {
                    'original': match.group(0),
                    'content': match.group(1),
                    'type': ptype
                }
                preserved_text = preserved_text.replace(match.group(0), key)
                counter += 1
        
        return preserved_text, special_map
    
    def restore_special_formatting(self, text: str, special_map: Dict) -> str:
        """Restore preserved special formatting"""
        restored = text
        for key, value in special_map.items():
            restored = restored.replace(key, value['original'])
        return restored
    
    def validate_sentence_boundaries(self, sentences: List[str]) -> List[Dict]:
        """Validate sentence detection worked correctly"""
        issues = []
        
        for i, sent in enumerate(sentences):
            # Check for likely mis-splits
            if len(sent) < 10:  # Very short sentence
                if i > 0 and not sentences[i-1].rstrip().endswith(('.', '!', '?', '"')):
                    issues.append({
                        'type': 'possible_mis_split',
                        'sentence_idx': i,
                        'sentence': sent,
                        'previous': sentences[i-1][-50:] if i > 0 else None
                    })
            
            # Check for sentences starting with lowercase (might be continuation)
            if sent and sent[0].islower() and i > 0:
                issues.append({
                    'type': 'lowercase_start',
                    'sentence_idx': i,
                    'sentence': sent[:50]
                })
            
            # Check for unmatched quotes
            quote_count = sent.count('"') + sent.count("'")
            if quote_count % 2 != 0:
                issues.append({
                    'type': 'unmatched_quotes',
                    'sentence_idx': i,
                    'sentence': sent[:50]
                })
        
        return issues
    
    def create_safe_chunks_with_overlap(
        self, 
        text: str, 
        chunk_size: int = 35000,  # ~12 pages
        overlap_size: int = 3000   # ~1 page overlap
    ) -> List[Dict]:
        """Create overlapping chunks to catch boundary stories"""
        chunks = []
        
        # First, find natural break points (chapter breaks, etc.)
        break_patterns = [
            r'\n\s*Chapter\s+[IVXLCDM\d]+',
            r'\n\s*CHAPTER\s+[IVXLCDM\d]+',
            r'\n\s*\*\s*\*\s*\*\s*\n',  # Scene breaks
            r'\n\s*†\s*†\s*†\s*\n',    # Religious texts often use these
        ]
        
        break_points = [0]
        for pattern in break_patterns:
            for match in re.finditer(pattern, text):
                break_points.append(match.start())
        break_points.append(len(text))
        break_points = sorted(set(break_points))
        
        # Create chunks respecting natural breaks where possible
        current_pos = 0
        chunk_idx = 0
        
        while current_pos < len(text):
            # Find the ideal end point
            ideal_end = current_pos + chunk_size
            
            # Look for natural break near ideal end
            best_break = ideal_end
            for bp in break_points:
                if current_pos + (chunk_size * 0.8) <= bp <= current_pos + (chunk_size * 1.2):
                    best_break = bp
                    break
            
            # If no natural break, find sentence boundary
            if best_break == ideal_end:
                # Look for sentence end
                search_start = max(0, ideal_end - 500)
                search_end = min(len(text), ideal_end + 500)
                search_text = text[search_start:search_end]
                
                sentence_ends = []
                for match in re.finditer(r'[.!?]["\']*\s+[A-Z]', search_text):
                    sentence_ends.append(search_start + match.start() + 1)
                
                if sentence_ends:
                    # Find closest to ideal_end
                    best_break = min(sentence_ends, key=lambda x: abs(x - ideal_end))
                else:
                    best_break = ideal_end
            
            # Create chunk with metadata
            chunk_end = best_break
            chunk_text = text[current_pos:chunk_end]
            
            # Add overlap from previous chunk if not first chunk
            if chunk_idx > 0 and current_pos > overlap_size:
                overlap_start = current_pos - overlap_size
                overlap_text = text[overlap_start:current_pos]
                chunk_text = overlap_text + chunk_text
                actual_start = overlap_start
            else:
                actual_start = current_pos
            
            chunks.append({
                'text': chunk_text,
                'chunk_idx': chunk_idx,
                'start_pos': actual_start,
                'end_pos': chunk_end,
                'has_overlap': chunk_idx > 0,
                'overlap_size': overlap_size if chunk_idx > 0 else 0
            })
            
            # Move to next chunk (with overlap)
            current_pos = chunk_end - (overlap_size // 2)
            chunk_idx += 1
        
        return chunks
    
    def intelligent_page_detection(
        self, 
        text: str, 
        current_page: int, 
        chunk_idx: int
    ) -> List[Tuple[int, int]]:  # Returns [(char_position, page_number)]
        """More intelligent page detection with validation"""
        page_markers = []
        
        # Extended patterns
        patterns = [
            # Standard patterns
            (r'\[Page\s+(\d+)\]', 1.0),
            (r'\bPage\s+(\d+)\b', 0.9),
            (r'\bp\.\s*(\d+)\b', 0.9),
            (r'—\s*(\d+)\s*—', 0.8),
            (r'\((\d+)\)', 0.7),
            
            # Footnote patterns (should not be page numbers)
            (r'\[\^(\d+)\]', -1.0),  # Negative weight
            (r'<sup>(\d+)</sup>', -1.0),
            
            # Year patterns (should not be page numbers)
            (r'\b(1[0-9]{3})\b', -0.5),  # 1000-1999
            (r'\b(20[0-9]{2})\b', -0.5),  # 2000-2099
        ]
        
        candidates = []
        
        for pattern, weight in patterns:
            for match in re.finditer(pattern, text):
                num = int(match.group(1))
                pos = match.start()
                
                # Context analysis
                context_before = text[max(0, pos-50):pos]
                context_after = text[pos:min(len(text), pos+50)]
                
                # Adjust weight based on context
                final_weight = weight
                
                # Positive indicators
                if re.search(r'(continued from|see|refer to|on page)', context_before.lower()):
                    final_weight *= 0.5  # Likely a reference, not current page
                
                # Year indicators
                if re.search(r'(year|date|century|A\.D\.|B\.C\.)', context_before):
                    final_weight = -1.0
                
                # Check if it's a reasonable page progression
                if 0 < num < current_page - 10:
                    final_weight *= 0.3  # Probably a back-reference
                elif num > current_page + 50:
                    final_weight *= 0.3  # Too big a jump
                
                if final_weight > 0:
                    candidates.append({
                        'pos': pos,
                        'page': num,
                        'weight': final_weight,
                        'pattern': pattern
                    })
        
        # Sort by position and filter by weight
        candidates.sort(key=lambda x: x['pos'])
        
        # Apply smoothing - pages should generally increase
        smoothed = []
        last_page = current_page
        
        for cand in candidates:
            if cand['weight'] > 0.5:  # High confidence
                if cand['page'] >= last_page - 2:  # Allow small backsteps
                    smoothed.append((cand['pos'], cand['page']))
                    last_page = cand['page']
                else:
                    logger.warning(
                        f"Rejected page {cand['page']} at pos {cand['pos']} "
                        f"(current page: {last_page})"
                    )
        
        return smoothed
    
    def handle_cross_chunk_stories(
        self,
        extractions: List[Dict],
        overlap_size: int = 3000
    ) -> List[Dict]:
        """Intelligently merge stories across chunks"""
        merged = []
        
        for i, extraction in enumerate(extractions):
            # Parse stories from this extraction
            stories = self.parse_extraction(extraction)
            
            for story in stories:
                # Check if this might be a continuation
                is_continuation = False
                
                # Look for explicit markers
                if 'CONTINUES FROM PREVIOUS' in story['text']:
                    is_continuation = True
                    story['text'] = story['text'].replace('CONTINUES FROM PREVIOUS', '').strip()
                
                # Look for implicit continuation (starts with lowercase or pronoun)
                first_sentence = story['text'].split('.')[0]
                if re.match(r'^(he|she|it|they|this|that|which|who)', first_sentence.lower()):
                    is_continuation = True
                
                # Try to match with previous chunk's stories
                if is_continuation and merged:
                    # Find best match from recent stories
                    best_match = None
                    best_score = 0
                    
                    for j in range(max(0, len(merged) - 5), len(merged)):
                        prev_story = merged[j]
                        
                        # Calculate similarity
                        score = self.calculate_story_similarity(prev_story, story)
                        
                        # Check if previous story indicated continuation
                        if 'CONTINUES TO NEXT' in prev_story.get('text', ''):
                            score += 0.3
                        
                        if score > best_score:
                            best_score = score
                            best_match = j
                    
                    if best_score > 0.7 and best_match is not None:
                        # Merge stories
                        merged[best_match]['text'] += ' --- ' + story['text']
                        merged[best_match]['pages'] = self.merge_page_ranges(
                            merged[best_match]['pages'], 
                            story['pages']
                        )
                        continue
                
                # Add as new story
                merged.append(story)
        
        return merged
    
    def calculate_story_similarity(self, story1: Dict, story2: Dict) -> float:
        """Calculate similarity between two stories"""
        # Simple approach - can be enhanced with better NLP
        text1 = story1.get('text', '').lower()
        text2 = story2.get('text', '').lower()
        
        # Extract key terms
        key_terms1 = set(re.findall(r'\b\w{4,}\b', text1))
        key_terms2 = set(re.findall(r'\b\w{4,}\b', text2))
        
        if not key_terms1 or not key_terms2:
            return 0.0
        
        intersection = key_terms1 & key_terms2
        union = key_terms1 | key_terms2
        
        return len(intersection) / len(union)
    
    def parse_extraction(self, extraction: Dict) -> List[Dict]:
        """Parse extraction output into structured stories"""
        # Implementation depends on extraction format
        stories = []
        
        # ... parsing logic ...
        
        return stories
    
    def merge_page_ranges(self, range1: str, range2: str) -> str:
        """Merge two page range strings"""
        # Extract all numbers from both ranges
        nums1 = [int(x) for x in re.findall(r'\d+', range1)]
        nums2 = [int(x) for x in re.findall(r'\d+', range2)]
        
        all_nums = nums1 + nums2
        if not all_nums:
            return range1 or range2
        
        return f"{min(all_nums)}-{max(all_nums)}"
