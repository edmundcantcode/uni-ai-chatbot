# backend/constants/subjects_index.py
import re
from typing import Optional, List, Dict, Tuple
from rapidfuzz import process, fuzz
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# This will be populated from database on startup
ALL_SUBJECT_ROWS: List[Dict[str, str]] = []
SUBJECT_CANONICAL: List[str] = []
SUBJECT_LOOKUP: Dict[str, Dict[str, str]] = {}  # canonical -> full row

def canonicalize(s: str) -> str:
    """
    Convert natural language to canonical form.
    "operating system fundamentals" -> "OperatingSystemFundamentals"
    """
    # Extract alphanumeric words and capitalize each
    words = re.findall(r"[A-Za-z0-9]+", s)
    return "".join(w.capitalize() for w in words)

def load_subjects_from_db(session):
    """Load all subjects from database into memory"""
    global ALL_SUBJECT_ROWS, SUBJECT_CANONICAL, SUBJECT_LOOKUP
    
    try:
        # Query all unique subject names
        query = "SELECT DISTINCT subjectname FROM subjects ALLOW FILTERING"
        result = session.execute(query)
        
        ALL_SUBJECT_ROWS = []
        for row in result:
            if row.subjectname:
                subject_data = {
                    "subjectname": row.subjectname,
                    "canonical": row.subjectname  # Already in canonical form in DB
                }
                ALL_SUBJECT_ROWS.append(subject_data)
        
        # Build canonical list and lookup
        SUBJECT_CANONICAL = [r["subjectname"] for r in ALL_SUBJECT_ROWS]
        SUBJECT_LOOKUP = {r["subjectname"]: r for r in ALL_SUBJECT_ROWS}
        
        logger.info(f"✅ Loaded {len(SUBJECT_CANONICAL)} unique subjects into memory")
        
        # Log some examples
        if SUBJECT_CANONICAL:
            logger.debug(f"Example subjects: {SUBJECT_CANONICAL[:5]}")
            
    except Exception as e:
        logger.error(f"Failed to load subjects: {e}")
        # Fallback to hardcoded examples
        _load_fallback_subjects()

def _load_fallback_subjects():
    """Load fallback subject data for testing"""
    global ALL_SUBJECT_ROWS, SUBJECT_CANONICAL, SUBJECT_LOOKUP
    
    # Common CS subjects as examples
    fallback_subjects = [
        "OperatingSystemFundamentals",
        "DataStructuresAndAlgorithms", 
        "DatabaseManagementSystems",
        "ComputerNetworks",
        "SoftwareEngineering",
        "WebDevelopment",
        "ArtificialIntelligence",
        "MachineLearning",
        "ComputerGraphics",
        "CyberSecurity",
        "MobileApplicationDevelopment",
        "CloudComputing",
        "DistributedSystems",
        "HumanComputerInteraction",
        "ProgrammingFundamentals",
        "ObjectOrientedProgramming",
        "FunctionalProgramming",
        "ComputerArchitecture",
        "DiscreteMathematics",
        "LinearAlgebra",
        "Calculus",
        "Statistics",
        "ProbabilityTheory",
        "NumericalMethods",
        "PhysicsForEngineers"
    ]
    
    ALL_SUBJECT_ROWS = [{"subjectname": s, "canonical": s} for s in fallback_subjects]
    SUBJECT_CANONICAL = fallback_subjects
    SUBJECT_LOOKUP = {s: {"subjectname": s, "canonical": s} for s in fallback_subjects}
    
    logger.warning(f"Using {len(SUBJECT_CANONICAL)} fallback subjects")

@lru_cache(maxsize=1000)
def best_subject_match(user_text: str, threshold: int = 70) -> Optional[str]:
    """
    Find best matching canonical subject name using fuzzy matching.
    
    Args:
        user_text: Natural language subject name (e.g., "operating system fundamentals")
        threshold: Minimum similarity score (0-100) - lowered to 70 for better matching
    
    Returns:
        Canonical subject name or None if no good match
    """
    if not SUBJECT_CANONICAL:
        logger.warning("Subject index not loaded")
        return None
    
    # First try exact match after canonicalization
    canonical_input = canonicalize(user_text)
    if canonical_input in SUBJECT_CANONICAL:
        logger.debug(f"Exact match found: '{user_text}' -> '{canonical_input}'")
        return canonical_input
    
    # Try quick abbreviation match
    quick = quick_match(user_text)
    if quick:
        return quick
    
    # Fuzzy match using token_set_ratio for better robustness
    result = process.extractOne(
        canonical_input, 
        SUBJECT_CANONICAL, 
        scorer=fuzz.token_set_ratio  # Better for word order variations
    )
    
    if result:
        match, score, _ = result
        logger.debug(f"Fuzzy match: '{user_text}' -> '{match}' (score: {score})")
        
        if score >= threshold:
            return match
    
    # Try partial ratio as fallback
    result = process.extractOne(
        user_text.lower(),  # Use original text lowercase
        [s.lower() for s in SUBJECT_CANONICAL],
        scorer=fuzz.partial_ratio
    )
    
    if result:
        match, score, idx = result
        if score >= threshold:
            return SUBJECT_CANONICAL[idx]
    
    # Try token-based matching as final fallback
    match = _token_based_match(user_text)
    if match:
        logger.debug(f"Token match: '{user_text}' -> '{match}'")
        return match
    
    logger.debug(f"No match found for: '{user_text}' (threshold: {threshold})")
    return None

def _token_based_match(user_text: str) -> Optional[str]:
    """
    Token-based matching for better handling of word order variations.
    "system operating fundamentals" matches "OperatingSystemFundamentals"
    """
    user_tokens = set(re.findall(r"\w+", user_text.lower()))
    if len(user_tokens) < 2:
        return None
    
    best_match = None
    best_score = 0
    
    for subject in SUBJECT_CANONICAL:
        # Extract tokens from canonical form
        subject_tokens = set(re.findall(r"[A-Z][a-z]*|[0-9]+", subject))
        subject_tokens_lower = {t.lower() for t in subject_tokens}
        
        # Calculate Jaccard similarity
        intersection = len(user_tokens & subject_tokens_lower)
        union = len(user_tokens | subject_tokens_lower)
        
        if union > 0:
            score = intersection / union
            if score > best_score and score >= 0.6:  # 60% token overlap
                best_score = score
                best_match = subject
    
    return best_match

def get_subject_variations(canonical_name: str) -> List[str]:
    """Get common variations of a subject name for better matching"""
    if canonical_name not in SUBJECT_LOOKUP:
        return [canonical_name]
    
    # Generate variations
    variations = [canonical_name]
    
    # Split camelCase into words
    words = re.findall(r"[A-Z][a-z]*|[0-9]+", canonical_name)
    
    # Natural language version
    natural = " ".join(words).lower()
    variations.append(natural)
    
    # With "and" instead of "And"
    natural_with_and = natural.replace(" and ", " & ")
    variations.append(natural_with_and)
    
    # Common abbreviations
    abbrev_map = {
        "fundamentals": "101",
        "introduction": "intro",
        "management": "mgmt",
        "development": "dev",
        "application": "app",
        "computer": "comp",
        "engineering": "eng",
        "mathematics": "math"
    }
    
    for full, short in abbrev_map.items():
        if full in natural:
            variations.append(natural.replace(full, short))
    
    return variations

def find_subjects_containing(keyword: str) -> List[str]:
    """Find all subjects containing a keyword"""
    keyword_lower = keyword.lower()
    matches = []
    
    for subject in SUBJECT_CANONICAL:
        subject_lower = subject.lower()
        if keyword_lower in subject_lower:
            matches.append(subject)
            continue
        
        # Check word boundaries
        words = re.findall(r"[A-Z][a-z]*", subject)
        if any(keyword_lower in word.lower() for word in words):
            matches.append(subject)
    
    return matches

# Precomputed common mappings for speed
COMMON_MAPPINGS = {
    "os": "OperatingSystemFundamentals",
    "ds": "DataStructures",
    "algo": "Algorithms",
    "db": "Database",
    "dbms": "DatabaseManagementSystems",
    "ai": "ArtificialIntelligence",
    "ml": "MachineLearning",
    "oop": "ObjectOrientedProgramming",
    "hci": "HumanComputerInteraction",
    "se": "SoftwareEngineering",
    "cn": "ComputerNetworks",
    "cg": "ComputerGraphics",
    "web": "WebDevelopment",
    "mobile": "MobileApplicationDevelopment"
}

def quick_match(user_text: str) -> Optional[str]:
    """Quick matching for common abbreviations"""
    user_lower = user_text.lower().strip()
    
    # Direct abbreviation match
    if user_lower in COMMON_MAPPINGS:
        canonical = COMMON_MAPPINGS[user_lower]
        if canonical in SUBJECT_CANONICAL:
            return canonical
        # Try to find it with fuzzy match
        return best_subject_match(canonical, threshold=90)
    
    return None

# Export main functions
__all__ = [
    'canonicalize',
    'best_subject_match',
    'load_subjects_from_db',
    'find_subjects_containing',
    'get_subject_variations',
    'quick_match',
    'SUBJECT_CANONICAL',
    'SUBJECT_LOOKUP'
]