# backend/constants/subjects_index.py
import re
import logging
from functools import lru_cache
from typing import Optional, List, Dict
from rapidfuzz import process, fuzz
from cassandra.query import SimpleStatement

logger = logging.getLogger(__name__)

# In‑memory caches
ALL_SUBJECT_ROWS: List[Dict[str, str]] = []
SUBJECT_CANONICAL: List[str] = []
SUBJECT_LOOKUP: Dict[str, Dict[str, str]] = {}  # canonical -> full row

# ------------------------- Canonicalization ------------------------- #

def canonicalize(s: str) -> str:
    """
    Convert a natural-language subject string to a CamelCase-ish canonical form.
    "operating system fundamentals" -> "OperatingSystemFundamentals"
    """
    words = re.findall(r"[A-Za-z0-9]+", s)
    return "".join(w.capitalize() for w in words)

# ------------------------- DB Loader ------------------------- #

def load_subjects_from_db(session) -> None:
    """
    Load all subjects into memory. Avoids SELECT DISTINCT (illegal for non-PK cols).
    We scan the table and dedupe in Python.
    """
    global ALL_SUBJECT_ROWS, SUBJECT_CANONICAL, SUBJECT_LOOKUP

    try:
        stmt = SimpleStatement("SELECT subjectname FROM subjects", fetch_size=5000)
        seen = set()
        rows_local: List[Dict[str, str]] = []

        for row in session.execute(stmt):
            name = getattr(row, "subjectname", None)
            if not name:
                continue
            name = name.strip()
            if name in seen:
                continue
            seen.add(name)

            canon = canonicalize(name)
            rows_local.append({"subjectname": name, "canonical": canon})

        ALL_SUBJECT_ROWS = rows_local
        SUBJECT_CANONICAL = [r["canonical"] for r in rows_local]
        SUBJECT_LOOKUP = {r["canonical"]: r for r in rows_local}

        logger.info(f"✅ Loaded {len(SUBJECT_CANONICAL)} unique subjects into memory")

        if not SUBJECT_CANONICAL:
            logger.warning("No subjects loaded from DB; falling back to hardcoded list.")
            _load_fallback_subjects()

    except Exception as e:
        logger.error(f"Failed to load subjects: {e}")
        _load_fallback_subjects()

def _load_fallback_subjects() -> None:
    """Fallback list so system still runs."""
    global ALL_SUBJECT_ROWS, SUBJECT_CANONICAL, SUBJECT_LOOKUP

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
        "PhysicsForEngineers",
    ]

    ALL_SUBJECT_ROWS = [{"subjectname": s, "canonical": s} for s in fallback_subjects]
    SUBJECT_CANONICAL = fallback_subjects
    SUBJECT_LOOKUP = {s: {"subjectname": s, "canonical": s} for s in fallback_subjects}

    logger.warning(f"Using {len(SUBJECT_CANONICAL)} fallback subjects")

# ------------------------- Matching ------------------------- #

@lru_cache(maxsize=1000)
def best_subject_match(user_text: str, threshold: int = 70) -> Optional[str]:
    """
    Return the best matching canonical subject name using fuzzy matching.
    Cached by (user_text, threshold) implicitly because threshold is default-stable.
    """
    if not SUBJECT_CANONICAL:
        logger.warning("Subject index not loaded")
        return None

    canonical_input = canonicalize(user_text)

    # Exact canonical match
    if canonical_input in SUBJECT_CANONICAL:
        logger.debug(f"Exact match: '{user_text}' -> '{canonical_input}'")
        return canonical_input

    # Quick abbreviation match
    quick = quick_match(user_text)
    if quick:
        return quick

    # Fuzzy (token_set_ratio handles order/duplicates)
    result = process.extractOne(
        canonical_input,
        SUBJECT_CANONICAL,
        scorer=fuzz.token_set_ratio
    )
    if result:
        match, score, _ = result
        logger.debug(f"Fuzzy match: '{user_text}' -> '{match}' (score {score})")
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
    "db": "DatabaseManagementSystems",
    "dbms": "DatabaseManagementSystems",
    "ai": "ArtificialIntelligence",
    "ml": "MachineLearning",
    "oop": "ObjectOrientedProgramming",
    "hci": "HumanComputerInteraction",
    "se": "SoftwareEngineering",
    "cn": "ComputerNetworks",
    "cg": "ComputerGraphics",
    "web": "WebDevelopment",
    "mobile": "MobileApplicationDevelopment",
}

def quick_match(user_text: str) -> Optional[str]:
    """Fast path for common abbreviations."""
    key = user_text.lower().strip()
    if key in COMMON_MAPPINGS:
        canonical = COMMON_MAPPINGS[key]
        if canonical in SUBJECT_CANONICAL:
            return canonical
        # If mapping wasn’t actually loaded, try fuzzy
        return best_subject_match(canonical, threshold=90)
    return None

__all__ = [
    "canonicalize",
    "best_subject_match",
    "load_subjects_from_db",
    "find_subjects_containing",
    "get_subject_variations",
    "quick_match",
    "SUBJECT_CANONICAL",
    "SUBJECT_LOOKUP",
]
