# backend/logic/entity_resolver.py
import re
from typing import Dict, Any, List, Optional, Tuple, Iterable
from rapidfuzz import process, fuzz
from backend.constants.domain_values import PROGRAMMES, SUBJECTS
from backend.constants.subjects_index import best_subject_match, quick_match, find_subjects_containing
import logging

logger = logging.getLogger(__name__)

# ---------- Canonicalization Setup ----------
# Lowercase canonical lists for faster lookup
PROGRAMMES_LC = {p.lower(): p for p in PROGRAMMES}
SUBJECTS_LC = {s.lower(): s for s in SUBJECTS}

# Common programme aliases mapping to full canonical names
PROGRAMME_ALIASES = {
    "computer science": "Bachelor of Science (Honours) in Computer Science",
    "cs": "Bachelor of Science (Honours) in Computer Science",
    "bsc computer science": "Bachelor of Science (Honours) in Computer Science",
    "bachelor of computer science": "Bachelor of Science (Honours) in Computer Science",
    
    "information technology": "Bachelor of Science (Honours) in Information Technology",
    "it": "Bachelor of Science (Honours) in Information Technology", 
    "info tech": "Bachelor of Science (Honours) in Information Technology",
    "information tech": "Bachelor of Science (Honours) in Information Technology",
    "bsc information technology": "Bachelor of Science (Honours) in Information Technology",
    
    "software engineering": "Bachelor of Software Engineering (Honours)",
    "se": "Bachelor of Software Engineering (Honours)",
    "software eng": "Bachelor of Software Engineering (Honours)",
    "bachelor of software engineering": "Bachelor of Software Engineering (Honours)",
    
    "information systems": "Bachelor of Science (Honours) in Information Systems",
    "is": "Bachelor of Science (Honours) in Information Systems",
    "info systems": "Bachelor of Science (Honours) in Information Systems",
    
    "data analytics": "Bachelor of Information Systems (Honours) in Data Analytics",
    "business analytics": "Bachelor of Information Systems (Honours) in Business Analytics",
    "mobile computing": "Bachelor of Information Systems (Honours) in Mobile Computing with Entrepreneurship",
    
    "chemical engineering": "Bachelor of Chemical Engineering with Honours",
    "civil engineering": "Bachelor of Civil Engineering with Honours", 
    "electrical engineering": "Bachelor of Electronic and Electrical Engineering with Honours",
    "electronic engineering": "Bachelor of Electronic and Electrical Engineering with Honours",
    "mechanical engineering": "Bachelor of Mechanical Engineering with Honours",
    "mechatronic engineering": "Bachelor of Mechatronic Engineering (Robotics) with Honours",
    "robotics": "Bachelor of Mechatronic Engineering (Robotics) with Honours",
}

def _best_match(value: str, candidates: Dict[str, str], cutoff: int = 80) -> Optional[str]:
    """Find best fuzzy match in candidates dictionary."""
    if not value:
        return None
    
    val = value.lower().strip()
    
    # Exact match first
    if val in candidates:
        return candidates[val]
    
    # Fuzzy match
    match, score, _ = process.extractOne(val, candidates.keys(), scorer=fuzz.WRatio)
    return candidates[match] if score >= cutoff else None

def canonicalize_programme(name: str) -> Optional[str]:
    """Convert programme name to canonical form."""
    if not name:
        return None
        
    # Try alias table first
    if name.lower() in PROGRAMME_ALIASES:
        result = PROGRAMME_ALIASES[name.lower()]
        logger.debug(f"Programme alias mapped '{name}' -> '{result}'")
        return result
    
    # Exact match in canonical set
    if name.lower() in PROGRAMMES_LC:
        result = PROGRAMMES_LC[name.lower()]
        logger.debug(f"Programme exact match '{name}' -> '{result}'")
        return result
    
    # Fuzzy match
    result = _best_match(name, PROGRAMMES_LC)
    if result:
        logger.debug(f"Programme fuzzy matched '{name}' -> '{result}'")
    else:
        logger.debug(f"Programme not found for '{name}'")
    return result

def canonicalize_subject(name: str) -> Optional[str]:
    """Convert subject name to canonical form."""
    if not name:
        return None
        
    # Exact match in canonical set
    if name.lower() in SUBJECTS_LC:
        result = SUBJECTS_LC[name.lower()]
        logger.debug(f"Subject exact match '{name}' -> '{result}'")
        return result
    
    # Try existing subject index first (if available)
    try:
        result = best_subject_match(name)
        if result:
            logger.debug(f"Subject index matched '{name}' -> '{result}'")
            return result
    except:
        pass
    
    # Fuzzy match
    result = _best_match(name, SUBJECTS_LC)
    if result:
        logger.debug(f"Subject fuzzy matched '{name}' -> '{result}'")
    else:
        logger.debug(f"Subject not found for '{name}'")
    return result

def guess_domain(value: str) -> Optional[str]:
    """Return 'programme' or 'subjectname' (or None) for the phrase."""
    if not value:
        return None
        
    if canonicalize_programme(value):
        return "programme"
    if canonicalize_subject(value):
        return "subjectname"
    return None

# ---------- Fuzzy Matching Setup (from first file) ----------
def _norm(txt: str) -> str:
    """Normalize text for fuzzy matching by lowercasing and cleaning whitespace."""
    return re.sub(r"\s+", " ", txt.lower()).strip()

# Create normalized lookup dictionaries
NORMALIZED_PROGRAMMES = {_norm(p): p for p in PROGRAMMES}
NORMALIZED_SUBJECTS   = {_norm(s): s for s in SUBJECTS}

# Make search lists once for performance
PROG_KEYS = list(NORMALIZED_PROGRAMMES.keys())
SUBJ_KEYS = list(NORMALIZED_SUBJECTS.keys())

def _best_fuzzy(term: str, choices: List[str]) -> Tuple[str, int]:
    """Return (choice_original, score). Score 0-100"""
    if not term:
        return "", 0
    match, score, _ = process.extractOne(term, choices, scorer=fuzz.token_sort_ratio)
    return match, score

# ---------- Phrase extraction (from first file) ----------
def _ngrams(words: List[str], n_min=1, n_max=5) -> Iterable[str]:
    """Generate n-grams from a list of words."""
    for n in range(n_min, min(n_max, len(words)) + 1):
        for i in range(len(words) - n + 1):
            yield " ".join(words[i:i+n])

def candidate_phrases(query: str) -> List[str]:
    """Extract candidate phrases from query, longest first."""
    qn = _norm(query)
    words = qn.split()
    # longest first helps early confident matches
    cands = sorted(_ngrams(words, 1, 5), key=lambda x: -len(x))
    # dedupe maintaining order
    seen, uniq = set(), []
    for c in cands:
        if c not in seen and len(c) >= 3:  # discard tiny tokens
            uniq.append(c)
            seen.add(c)
    return uniq

# ---------- Classification (from first file) ----------
THRESH = 80                 # Increased threshold for more precision
GAP = 8                     # Increased gap to reduce ambiguity

def classify_term(term: str) -> Dict[str, str]:
    """Classify a term as programme or subjectname based on fuzzy matching."""
    subj_key, s_score = _best_fuzzy(term, SUBJ_KEYS)
    prog_key, p_score = _best_fuzzy(term, PROG_KEYS)

    if max(s_score, p_score) < THRESH:
        return {}  # too fuzzy

    # Build result with scores and best matches
    result = {
        "scores": {"subjectname": s_score, "programme": p_score},
        "best_subject": NORMALIZED_SUBJECTS.get(subj_key) if subj_key else None,
        "best_programme": NORMALIZED_PROGRAMMES.get(prog_key) if prog_key else None
    }

    if s_score - p_score > GAP:
        return {"subjectname": result["best_subject"], **result}
    if p_score - s_score > GAP:
        return {"programme": result["best_programme"], **result}
    
    # Ambiguous: both scores are close
    return {"ambiguous": True, **result}

def _cast_value(col: str, val):
    """Cast values to appropriate types for Cassandra columns."""
    if col in BOOLEAN_COLS:
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.strip().lower() in ("true", "1", "yes", "y", "t", "active", "enrolled", "false", "0", "no", "n", "f")
        return bool(val)
    
    if col in INT_COLS:
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str) and val.isdigit():
            return int(val)
        return val
    
    # Note: cohort normalization is now handled separately in enhance_step_with_entities
    return val

# ---------- Keywords and Constants (from second file) ----------
# Keywords that suggest different tables
GRADE_KEYWORDS = {"grade", "grades", "score", "result", "marks", "performance", "scored"}
STUDENT_KEYWORDS = {"student", "students", "learner", "pupil", "enrolled"}
CGPA_KEYWORDS = {"cgpa", "gpa", "average", "cumulative"}
STATUS_KEYWORDS = {"graduated", "active", "status", "enrolled", "completed"}

# ---------- Type Normalization Constants ----------
BOOLEAN_COLS = {"graduated"}
INT_COLS = {"year", "examyear", "id"}

# Cohort normalization: convert month names to numbers for YYYYMM format
MONTH_NUM = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",  # Fixed: was "July", now "07"
    "aug": "08", "august": "08",
    "sep": "09", "sept": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12",
}

def normalize_cohort(value_month, value_year) -> Optional[str]:
    """
    Build YYYYMM string from month and year inputs.
    
    Accepts:
    - value_month: 'march', '03', '3', etc.
    - value_year: '2022', 2022, etc.
    
    Returns: '202203' or None if not enough info.
    """
    if value_year is None or value_month is None:
        return None
    
    # Parse year
    try:
        year = int(str(value_year))
    except:
        return None
    
    # Parse month
    m = str(value_month).strip().lower()
    
    # Check if already YYYYMM format
    if len(m) == 6 and m.isdigit():
        return m
    
    # Convert month to 2-digit number
    if m.isdigit():
        mm = f"{int(m):02d}"
    else:
        mm = MONTH_NUM.get(m)
    
    if not mm:
        return None
    
    return f"{year}{mm}"

# Month names for cohort matching
MONTHS = ["january", "february", "march", "april", "may", "june", 
          "july", "august", "september", "october", "november", "december"]
MONTH_ABBREV = {"jan": "January", "feb": "February", "mar": "March", "apr": "April",
                "may": "May", "jun": "June", "jul": "July", "aug": "August",
                "sep": "September", "oct": "October", "nov": "November", "dec": "December"}

def resolve_entities(user_query: str) -> Dict[str, Any]:
    """
    Extract and resolve entities from natural language query.
    
    Combines fuzzy matching classification with comprehensive entity extraction.
    
    Returns dict with:
    - table_hint: Suggested table based on keywords
    - subjectname: Canonical subject name if found
    - filters: Extracted filter conditions
    - operators: Extracted comparison operators
    - raw_query: Original query
    """
    entities = {
        "table_hint": None,
        "subjectname": None,
        "filters": {},
        "operators": {},
        "raw_query": user_query
    }
    
    q_lower = user_query.lower()
    
    # Determine table hint
    entities["table_hint"] = _determine_table_hint(q_lower)
    
    # Track ambiguous choices for clarification
    ambiguous_choices = []
    
    # NEW: Fuzzy classification of academic phrases (from first file)
    for phrase in candidate_phrases(user_query):
        classified = classify_term(phrase)
        if not classified:
            continue
            
        if classified.get("ambiguous"):
            # Store ambiguous choice for user clarification
            ambiguous_choices.append({
                "phrase": phrase,
                "programme": classified["best_programme"],
                "subjectname": classified["best_subject"],
                "scores": classified["scores"]
            })
            continue
            
        if "programme" in classified and "programme" not in entities["filters"]:
            entities["filters"]["programme"] = classified["programme"]
            entities["operators"]["programme"] = "="
            entities["table_hint"] = entities["table_hint"] or "students"
            logger.info(f"Fuzzy matched programme: '{phrase}' -> '{classified['programme']}'")
        elif "subjectname" in classified and not entities.get("subjectname"):
            entities["subjectname"] = classified["subjectname"]
            entities["table_hint"] = entities["table_hint"] or "subjects"
            logger.info(f"Fuzzy matched subject: '{phrase}' -> '{classified['subjectname']}'")
    
    # Handle ambiguous terms
    if ambiguous_choices:
        entities["ambiguous_terms"] = ambiguous_choices
        entities["needs_disambiguation"] = True
        logger.info(f"Found {len(ambiguous_choices)} ambiguous terms requiring clarification")
    if not entities.get("subjectname"):
        subject = _extract_subject_name(user_query, q_lower)
        if subject:
            entities["subjectname"] = subject
            entities["table_hint"] = entities["table_hint"] or "subjects"
            logger.info(f"Pattern matched subject: '{subject}'")
    
    # Extract filters and operators (from second file)
    filters, operators = _extract_filters(q_lower)
    entities["filters"].update(filters)
    entities["operators"].update(operators)
    
    # Extract cohort information (from second file)
    cohort_info = _extract_cohort(q_lower)
    if cohort_info:
        entities["filters"].update(cohort_info)
    
    # Extract country/location (from second file)
    country = _extract_country(q_lower)
    if country:
        entities["filters"]["country"] = country
    
    # Fix subject/programme confusion: if we matched a programme, 
    # drop any accidental subject match that might be similar
    if entities.get("filters", {}).get("programme") and entities.get("subjectname"):
        logger.info(f"Removing conflicting subject '{entities['subjectname']}' in favor of programme '{entities['filters']['programme']}'")
        del entities["subjectname"]
        entities["table_hint"] = "students"
    
    # Also check the inverse: if we matched a subject but accidentally put it in programme
    elif entities.get("subjectname") and entities.get("filters", {}).get("programme"):
        # This is less common but could happen
        subj_confidence = canonicalize_subject(entities["subjectname"])
        prog_confidence = canonicalize_programme(entities["filters"]["programme"])
        
        # If both are valid but subject is in programme field, we already handle this in enhance_step_with_entities
        if subj_confidence and not prog_confidence:
            logger.info(f"Moving invalid programme '{entities['filters']['programme']}' - keeping subject '{entities['subjectname']}'")
            del entities["filters"]["programme"]
            entities["table_hint"] = "subjects"
    
    return entities

def _determine_table_hint(q_lower: str) -> Optional[str]:
    """Determine which table to query based on keywords"""
    if any(keyword in q_lower for keyword in GRADE_KEYWORDS):
        if "subject" in q_lower or "for" in q_lower or "in" in q_lower:
            return "subjects"
    
    if any(keyword in q_lower for keyword in STUDENT_KEYWORDS):
        return "students"
    
    if any(keyword in q_lower for keyword in CGPA_KEYWORDS):
        return "students"
    
    return None

def _extract_subject_name(query: str, q_lower: str) -> Optional[str]:
    """Extract and resolve subject name from query"""
    
    # Try quick abbreviation match first
    quick = quick_match(query)
    if quick:
        return quick
    
    # Patterns to extract subject phrases
    patterns = [
        r"(?:grade|score|marks?|result)\s+(?:for|in|of)\s+([^,\.]+)",
        r"(?:my|show|get)\s+(\w+(?:\s+\w+)*)\s+(?:grade|score|marks?)",
        r'"([^"]+)"',  # Quoted strings
        r"'([^']+)'",  # Single quoted
        r"subject\s+(?:called|named)?\s*:?\s*([^,\.]+)",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, q_lower)
        if match:
            subject_phrase = match.group(1).strip()
            
            # Clean up the phrase
            subject_phrase = subject_phrase.strip(" .?!\"'")
            
            # Remove trailing words like "please", "thanks"
            subject_phrase = re.sub(r"\s+(please|thanks|thank you)$", "", subject_phrase)
            
            # Try to match
            canonical = best_subject_match(subject_phrase)
            if canonical:
                return canonical
    
    # Try to find subject by looking for capitalized phrases
    cap_pattern = r"[A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*"
    cap_matches = re.findall(cap_pattern, query)
    for phrase in cap_matches:
        if len(phrase) > 3:  # Skip short matches
            canonical = best_subject_match(phrase)
            if canonical:
                return canonical
    
    return None

def _extract_filters(q_lower: str) -> Tuple[Dict[str, Any], Dict[str, str]]:
    """Extract filter conditions and operators from query"""
    filters = {}
    operators = {}
    
    # CGPA filters with operators
    cgpa_patterns = [
        (r"cgpa\s*>\s*([0-9.]+)", ">"),
        (r"cgpa\s*>=\s*([0-9.]+)", ">="),
        (r"cgpa\s*<\s*([0-9.]+)", "<"),
        (r"cgpa\s*<=\s*([0-9.]+)", "<="),
        (r"cgpa\s*=\s*([0-9.]+)", "="),
        (r"cgpa\s+(?:above|greater than|over)\s+([0-9.]+)", ">"),
        (r"cgpa\s+(?:below|less than|under)\s+([0-9.]+)", "<"),
        (r"cgpa\s+(?:between|from)\s+([0-9.]+)\s+(?:and|to)\s+([0-9.]+)", "BETWEEN"),
    ]
    
    for pattern, op in cgpa_patterns:
        match = re.search(pattern, q_lower)
        if match:
            if op == "BETWEEN":
                filters["overallcgpa"] = [float(match.group(1)), float(match.group(2))]
                operators["overallcgpa"] = op
            else:
                filters["overallcgpa"] = float(match.group(1))
                operators["overallcgpa"] = op
            break
    
    # Status and graduation filters
    ACTIVE_WORDS = {"active", "enrolled", "current", "currently enrolled", "currently active"}
    
    if "graduated" in q_lower and "not" not in q_lower:
        filters["graduated"] = True
    elif any(w in q_lower for w in ACTIVE_WORDS):
        # Map active words to status filter
        filters["status"] = ["Active", "Enrolled", "Current"]
        operators["status"] = "IN"
    elif "not graduated" in q_lower:
        filters["graduated"] = False
    
    # Gender filters
    if "female" in q_lower or "women" in q_lower:
        filters["gender"] = "Female"
    elif "male" in q_lower or "men" in q_lower:
        filters["gender"] = "Male"
    
    # Legacy programme filters - REMOVED since fuzzy matching handles these better
    # The canonicalize_programme() function will handle all programme name variations
    
    return filters, operators

def _extract_cohort(q_lower: str) -> Dict[str, Any]:
    """Extract cohort information (month/year) for YYYYMM format."""
    cohort_info = {}
    
    # Extract year (prioritize 4-digit years)
    year_match = re.search(r"\b(20\d{2})\b", q_lower)
    if year_match:
        cohort_info["year"] = int(year_match.group(1))
    
    # Extract months
    found_months = []
    
    # Full month names
    for month in MONTHS:
        if month in q_lower:
            found_months.append(month.lower())
    
    # Abbreviated month names
    for abbrev in MONTH_NUM.keys():
        if abbrev in q_lower.split():
            found_months.append(abbrev)
    
    # Check for direct YYYYMM format
    yyyymm_match = re.search(r"\b(20\d{4})\b", q_lower)
    if yyyymm_match:
        cohort_info["cohort"] = yyyymm_match.group(1)
        return cohort_info
    
    # Store month for later normalization
    if found_months:
        # Take the first month found
        cohort_info["cohort"] = found_months[0]
    
    return cohort_info

def _extract_country(q_lower: str) -> Optional[str]:
    """Extract country name from query"""
    
    # Common countries in the system
    countries = {
        "malaysia": "Malaysia",
        "singapore": "Singapore",
        "indonesia": "Indonesia",
        "thailand": "Thailand",
        "philippines": "Philippines",
        "vietnam": "Vietnam",
        "india": "India",
        "china": "China",
        "nigeria": "Nigeria",
        "kenya": "Kenya",
        "ghana": "Ghana",
        "usa": "United States",
        "uk": "United Kingdom",
        "australia": "Australia"
    }
    
    for key, value in countries.items():
        if key in q_lower:
            return value
    
    # Pattern: "from [Country]"
    from_pattern = r"from\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)"
    match = re.search(from_pattern, q_lower)
    if match:
        country = match.group(1).strip()
        # Capitalize properly
        return " ".join(word.capitalize() for word in country.split())
    
    return None

def enhance_step_with_entities(step: Dict[str, Any], entities: Dict[str, Any]) -> Dict[str, Any]:
    """
    Inject resolved filters into a step dict safely.
    
    Enhanced version that handles canonicalization and type normalization.
    """
    enhanced_step = dict(step)
    where = enhanced_step.setdefault("where", {})
    filters = dict(entities.get("filters", {}))  # Copy to avoid mutation
    operators = entities.get("operators", {})
    
    # Fix programme/subjectname confusion and canonicalize names
    if "programme" in filters:
        raw_prog = filters["programme"]
        canon_prog = canonicalize_programme(raw_prog)
        if canon_prog:
            filters["programme"] = canon_prog
            logger.debug(f"Programme canonicalized '{raw_prog}' -> '{canon_prog}'")
        else:
            # Maybe it was actually a subject, move it
            canon_subj = canonicalize_subject(raw_prog)
            if canon_subj:
                filters.pop("programme")
                filters["subjectname"] = canon_subj
                logger.debug(f"Moved programme to subject '{raw_prog}' -> '{canon_subj}'")
            else:
                logger.warning(f"Could not canonicalize programme '{raw_prog}'")
    
    if "subjectname" in filters:
        raw_subj = filters["subjectname"]
        canon_subj = canonicalize_subject(raw_subj)
        if canon_subj:
            filters["subjectname"] = canon_subj
            logger.debug(f"Subject canonicalized '{raw_subj}' -> '{canon_subj}'")
        else:
            logger.warning(f"Could not canonicalize subject '{raw_subj}'")
    
    # Handle entity subjectname (from resolve_entities)
    if entities.get("subjectname") and enhanced_step.get("table") == "subjects":
        canon_subj = canonicalize_subject(entities["subjectname"])
        if canon_subj:
            where.setdefault("subjectname", {"op": "=", "value": canon_subj})
            logger.debug(f"Entity subject canonicalized '{entities['subjectname']}' -> '{canon_subj}'")
    
    # Special handling for cohort: combine month and year into YYYYMM format
    if "cohort" in filters or "year" in filters:
        cohort_code = None
        
        # Case A: user already gave 6 digits (YYYYMM)
        if "cohort" in filters and str(filters["cohort"]).isdigit() and len(str(filters["cohort"])) == 6:
            cohort_code = str(filters["cohort"])
        else:
            # Case B: normalize from month + year
            cohort_code = normalize_cohort(filters.get("cohort"), filters.get("year"))
        
        if cohort_code:
            where["cohort"] = {"op": "=", "value": cohort_code}
            logger.debug(f"Cohort normalized to '{cohort_code}'")
            # Remove raw pieces so they don't get added again
            filters = {k: v for k, v in filters.items() if k not in ["cohort", "year"]}
    
    # Apply remaining filters
    for field, value in filters.items():
        # Map field names
        field_map = {
            "examyear": "examyear"  # Keep as is, but ensure it's an int
        }
        
        actual_field = field_map.get(field, field)
        
        # Skip if field doesn't apply to this table
        if enhanced_step.get("table") == "students":
            if actual_field in ["examyear", "exammonth", "subjectname"]:
                continue
        elif enhanced_step.get("table") == "subjects":
            if actual_field in ["graduated", "programme", "gender", "country"]:
                continue
        
        # Build where clause entry with proper type casting
        if field in operators:
            op = operators[field]
            where[actual_field] = {"op": op, "value": _cast_value(actual_field, value)}
        elif isinstance(value, list):
            where[actual_field] = {"op": "IN", "value": [_cast_value(actual_field, v) for v in value]}
        else:
            where[actual_field] = {"op": "=", "value": _cast_value(actual_field, value)}
    
    # Final type normalization pass for all where conditions
    for col, spec in where.items():
        if isinstance(spec, dict) and "value" in spec:
            spec["value"] = _cast_value(col, spec["value"])
        elif isinstance(spec, dict) and "values" in spec:  # Handle IN operations
            spec["values"] = [_cast_value(col, v) for v in spec["values"]]
    
    enhanced_step["where"] = where
    enhanced_step["allow_filtering"] = True  # keep current behaviour
    
    # Debug logging
    logger.debug("Filters after canonicalization: %s", where)
    
    return enhanced_step

def fix_subject_names_in_step(step: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fix subject names in a step's where clause.
    
    Enhanced with canonicalization system.
    """
    where = step.get("where", {})
    
    # Check all where conditions for canonicalization
    for field, condition in where.items():
        if field == "subjectname":
            if isinstance(condition, dict) and "value" in condition:
                # Fix the value inside operator dict
                natural_name = condition["value"]
                if isinstance(natural_name, str):
                    canonical = canonicalize_subject(natural_name)
                    if canonical:
                        condition["value"] = canonical
                        logger.debug(f"Fixed subject name: '{natural_name}' -> '{canonical}'")
            elif isinstance(condition, str):
                # Legacy format - direct value
                canonical = canonicalize_subject(condition)
                if canonical:
                    where[field] = {"op": "=", "value": canonical}
                    logger.debug(f"Fixed subject name: '{condition}' -> '{canonical}'")
        
        elif field == "programme":
            if isinstance(condition, dict) and "value" in condition:
                # Fix the value inside operator dict
                natural_name = condition["value"]
                if isinstance(natural_name, str):
                    canonical = canonicalize_programme(natural_name)
                    if canonical:
                        condition["value"] = canonical
                        logger.debug(f"Fixed programme name: '{natural_name}' -> '{canonical}'")
            elif isinstance(condition, str):
                # Legacy format - direct value
                canonical = canonicalize_programme(condition)
                if canonical:
                    where[field] = {"op": "=", "value": canonical}
                    logger.debug(f"Fixed programme name: '{condition}' -> '{canonical}'")
    
    step["where"] = where
    return step

# ---------- Plan Canonicalization Helper ----------
def canonicalize_plan_steps(plan: Dict[str, Any], entities: Dict[str, Any]) -> Dict[str, Any]:
    """
    Always run canonicalization on all steps in a plan before execution.
    
    This should be called for every plan: pattern handlers, fallback, LLM plans.
    """
    if "steps" not in plan:
        return plan
    
    logger.debug("Canonicalizing plan with %d steps", len(plan["steps"]))
    
    for i, step in enumerate(plan["steps"]):
        # First enhance with entities (handles canonicalization)
        plan["steps"][i] = enhance_step_with_entities(step, entities)
        # Then fix any remaining subject/programme names
        plan["steps"][i] = fix_subject_names_in_step(plan["steps"][i])
        
        logger.debug("Step %d after canonicalization: %s", i, plan["steps"][i])
    
    return plan

# Export functions
__all__ = [
    'resolve_entities',
    'enhance_step_with_entities',
    'fix_subject_names_in_step',
    'canonicalize_programme',
    'canonicalize_subject', 
    'guess_domain',
    'canonicalize_plan_steps'
]