# backend/constants/subjects_index.py
import os
import re
import logging
from functools import lru_cache
from typing import Optional, List, Dict
from rapidfuzz import process, fuzz
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── File-based Subject Loading ──────────────────────────────────────────────
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
SUBJECT_FILE = DATA_DIR / "unique_subjectnames.txt"

# In‑memory caches
ALL_SUBJECT_ROWS: List[Dict[str, str]] = []
SUBJECT_CANONICAL: List[str] = []
SUBJECT_LOOKUP: Dict[str, Dict[str, str]] = {}  # canonical -> full row

def load_subjects_from_file() -> None:
    """Load subjects straight from unique_subjectnames.txt (one per line)."""
    global ALL_SUBJECT_ROWS, SUBJECT_CANONICAL, SUBJECT_LOOKUP
    
    if not SUBJECT_FILE.exists():
        logger.error(f"Subject list not found: {SUBJECT_FILE}")
        return
    
    rows = []
    seen = set()
    
    for line in SUBJECT_FILE.read_text().splitlines():
        name = line.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        
        # assume your cleaned names are already in CamelCase form
        canonical = name
        rows.append({"subjectname": name, "canonical": canonical})
    
    ALL_SUBJECT_ROWS = rows
    SUBJECT_CANONICAL = [r["canonical"] for r in rows]
    SUBJECT_LOOKUP = {r["canonical"]: r for r in rows}
    
    logger.info(f"✅ Loaded {len(SUBJECT_CANONICAL)} subjects from file")

# ------------------------- Canonicalization ------------------------- #

def canonicalize(s: str) -> str:
    """
    Convert a natural-language subject string to a CamelCase-ish canonical form.
    "operating system fundamentals" -> "OperatingSystemFundamentals"
    """
    words = re.findall(r"[A-Za-z0-9]+", s)
    return "".join(w.capitalize() for w in words)

# ------------------------- Matching ------------------------- #

@lru_cache(maxsize=1000)
def best_subject_match(user_text: str, threshold: int = 70) -> Optional[str]:
    """
    Return the best matching canonical subject name using fuzzy matching.
    Uses the curated subject list from file.
    Cached by (user_text, threshold) implicitly because threshold is default-stable.
    """
    if not SUBJECT_CANONICAL:
        logger.warning("Subject index not loaded - call load_subjects_from_file() first")
        return None

    # Exact match first
    if user_text in SUBJECT_CANONICAL:
        logger.debug(f"Exact match: '{user_text}' -> '{user_text}'")
        return user_text

    # Quick abbreviation match
    quick = quick_match(user_text)
    if quick:
        return quick

    # Fuzzy matching directly on your curated list
    result = process.extractOne(
        user_text,
        SUBJECT_CANONICAL,
        scorer=fuzz.token_set_ratio
    )
    if result:
        match, score, _ = result
        logger.debug(f"Fuzzy match: '{user_text}' -> '{match}' (score {score})")
        if score >= threshold:
            return match

    # Try with canonicalized input as fallback
    canonical_input = canonicalize(user_text)
    if canonical_input != user_text:
        result = process.extractOne(
            canonical_input,
            SUBJECT_CANONICAL,
            scorer=fuzz.token_set_ratio
        )
        if result:
            match, score, _ = result
            logger.debug(f"Canonicalized fuzzy match: '{user_text}' -> '{match}' (score {score})")
            if score >= threshold:
                return match

    # Partial ratio fallback on raw text
    result = process.extractOne(
        user_text.lower(),
        [s.lower() for s in SUBJECT_CANONICAL],
        scorer=fuzz.partial_ratio
    )
    if result:
        match, score, idx = result
        if score >= threshold:
            return SUBJECT_CANONICAL[idx]

    # Token-based Jaccard fallback
    match = _token_based_match(user_text)
    if match:
        logger.debug(f"Token match: '{user_text}' -> '{match}'")
        return match

    logger.debug(f"No subject match for '{user_text}' (threshold {threshold})")
    return None

def _token_based_match(user_text: str) -> Optional[str]:
    """Token Jaccard similarity over CamelCase splits."""
    user_tokens = set(re.findall(r"\w+", user_text.lower()))
    if len(user_tokens) < 2:
        return None

    best_match, best_score = None, 0.0
    for subject in SUBJECT_CANONICAL:
        subject_tokens = set(re.findall(r"[A-Z][a-z]*|[0-9]+", subject))
        subject_tokens_lower = {t.lower() for t in subject_tokens}

        inter = len(user_tokens & subject_tokens_lower)
        union = len(user_tokens | subject_tokens_lower)
        if union == 0:
            continue

        score = inter / union
        if score > best_score and score >= 0.6:
            best_score, best_match = score, subject

    return best_match

def get_subject_variations(canonical_name: str) -> List[str]:
    """Return common textual variations for better matching."""
    if canonical_name not in SUBJECT_LOOKUP:
        return [canonical_name]

    variations = [canonical_name]

    words = re.findall(r"[A-Z][a-z]*|[0-9]+", canonical_name)
    natural = " ".join(words).lower()
    variations.append(natural)
    variations.append(natural.replace(" and ", " & "))

    abbrev_map = {
        "fundamentals": "101",
        "introduction": "intro",
        "management": "mgmt",
        "development": "dev",
        "application": "app",
        "computer": "comp",
        "engineering": "eng",
        "mathematics": "math",
    }
    for full, short in abbrev_map.items():
        if full in natural:
            variations.append(natural.replace(full, short))

    return variations

def find_subjects_containing(keyword: str) -> List[str]:
    """Find canonical names containing the keyword (loose)."""
    kw = keyword.lower()
    matches = []

    for subj in SUBJECT_CANONICAL:
        subj_low = subj.lower()
        if kw in subj_low:
            matches.append(subj)
            continue

        words = re.findall(r"[A-Z][a-z]*", subj)
        if any(kw in w.lower() for w in words):
            matches.append(subj)

    return matches

COMMON_MAPPINGS = {
    "os": "OperatingSystemFundamentals",
    "ds": "DataStructuresAndAlgorithms", 
    "algo": "DataStructuresAndAlgorithms",
    "db": "DatabaseFundamentals",
    "dbms": "DatabaseManagementSystems",
    "ai": "ArtificialIntelligence",
    "ml": "MachineLearning", 
    "oop": "Object-OrientedProgramming",
    "hci": "HumanComputerInteraction",
    "se": "SoftwareEngineering",
    "cn": "ComputerNetworks",
    "cg": "ComputerGraphics",
    "web": "WebProgramming",
    "mobile": "MobileApplicationDevelopment",
}

def quick_match(user_text: str) -> Optional[str]:
    """Fast path for common abbreviations."""
    key = user_text.lower().strip()
    if key in COMMON_MAPPINGS:
        canonical = COMMON_MAPPINGS[key]
        if canonical in SUBJECT_CANONICAL:
            return canonical
        # If mapping wasn't actually loaded, try fuzzy
        return best_subject_match(canonical, threshold=90)
    return None

__all__ = [
    "canonicalize",
    "best_subject_match", 
    "load_subjects_from_file",
    "find_subjects_containing",
    "get_subject_variations",
    "quick_match",
    "SUBJECT_CANONICAL",
    "SUBJECT_LOOKUP",
]