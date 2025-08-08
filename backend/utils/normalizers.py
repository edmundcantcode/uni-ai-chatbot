# backend/utils/normalizers.py
import re, unicodedata
from typing import List, Dict, Set, Optional

MONTHS = {
    "jan": "01","january":"01",
    "feb": "02","february":"02",
    "mar": "03","march":"03",
    "apr": "04","april":"04",
    "may": "05",
    "jun": "06","june":"06",
    "jul": "07","july":"07",
    "aug": "08","august":"08",
    "sep": "09","sept":"09","september":"09",
    "oct": "10","october":"10",
    "nov": "11","november":"11",
    "dec": "12","december":"12",
}

NULLISH = {"", " ", "null", None}

def _nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)

def clean_string(s: Optional[str]) -> Optional[str]:
    """Unicode-normalize, strip weird spaces/symbols, collapse whitespace."""
    if s is None: return None
    s = _nfkc(s)
    s = s.replace("\u00A0", " ")  # NBSP → space
    s = s.replace("§", "")        # common junk char in your data
    s = re.sub(r"\s+", " ", s).strip()
    return None if s.lower() in NULLISH else s

def canonical_key(s: str) -> str:
    """Lowercase alnum-only key for matching/alias maps."""
    s = clean_string(s) or ""
    s = s.casefold()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def normalize_grade(g: Optional[str]) -> Optional[str]:
    """Drop suffixes like ^, *, #, (Z), etc. Map '-' and nullish to None."""
    g = clean_string(g)
    if not g or g in {"-"}: return None
    g = g.upper()
    # keep A, A+, A-, B+, ... D, F, P, AU, EX, INC
    # strip decorations
    g = re.sub(r"[^\w\+\-]", "", g)      # remove ^, *, (), etc
    # compress exotic like 'A+^' -> 'A+', 'F#' -> 'F'
    g = g.replace("#","")
    # basic sanity
    if g in {"A","A+","A-","B+","B","B-","C+","C","C-","D+","D","F","P","AU","EX","INC"}:
        return g
    # fallbacks: coerce e.g. 'D**' -> 'D'
    m = re.match(r"^([ABCDFP])(\+|-)?", g)
    return m.group(0) if m else None

def normalize_cohort(human: str) -> Optional[str]:
    """
    Accept: '202203', '2022-03', '2022/03', '03/2022', 'March 2022', 'Sept 2024', '2025 02'
    Return yyyymm (e.g., '202203') or None.
    """
    if not human: return None
    s = canonical_key(human)  # lower, alnum+spaces
    # direct yyyymm
    m = re.match(r"^(20\d{2})\s*(\d{2})$", s)
    if m: 
        yyyy, mm = m.groups()
        if "01" <= mm <= "12": return f"{yyyy}{mm}"
    # yyyy[-/]mm or mm[-/]yyyy
    m = re.match(r"^(20\d{2})\s*[/-]\s*(\d{1,2})$", s) or re.match(r"^(\d{1,2})\s*[/-]\s*(20\d{2})$", s)
    if m:
        a, b = m.groups()
        if len(a) == 4: yyyy, mm = a, int(b)
        else:           yyyy, mm = b, int(a)
        if 1 <= mm <= 12: return f"{yyyy}{mm:02d}"
    # month name + year (any order)
    tokens = s.split()
    if len(tokens) == 2:
        a, b = tokens
        if a in MONTHS and re.match(r"^20\d{2}$", b):
            return f"{b}{MONTHS[a]}"
        if b in MONTHS and re.match(r"^20\d{2}$", a):
            return f"{a}{MONTHS[b]}"
    # '2022 march' (already canonical_key'd)
    if len(tokens) == 2 and re.match(r"^20\d{2}$", tokens[0]) and tokens[1] in MONTHS:
        return f"{tokens[0]}{MONTHS[tokens[1]]}"
    return None

def build_alias_map(values: List[str]) -> Dict[str, Dict[str, Set[str]]]:
    """
    Group messy strings by canonical_key. 
    Returns { key: { 'canonical': best_display, 'variants': {…} } }
    """
    buckets: Dict[str, Set[str]] = {}
    for v in values:
        cs = clean_string(v)
        if not cs: continue
        k = canonical_key(cs)
        buckets.setdefault(k, set()).add(cs)

    def pick_display(variants: Set[str]) -> str:
        # Prefer one with spaces, fewer weird chars, longer (but reasonable)
        ranked = sorted(
            variants,
            key=lambda x: (
                -x.count(" "),                    # more word boundaries
                sum(c.isalpha() for c in x),      # more letters
                -sum(ord(c) > 127 for c in x),    # fewer non-ascii
                -len(x)                           # then length
            )
        )
        # Title-case if it looks shouty
        disp = ranked[0]
        if disp.isupper():
            disp = disp.title()
        return disp

    alias: Dict[str, Dict[str, Set[str]]] = {}
    for k, vs in buckets.items():
        alias[k] = {"canonical": pick_display(vs), "variants": vs}
    return alias

def resolve_subject_variants(user_text: str, subject_alias: Dict[str, Dict[str, Set[str]]]) -> List[str]:
    """Map user text -> list of exact subjectname variants to query with IN (...)."""
    k = canonical_key(user_text)
    hit = subject_alias.get(k)
    if hit: 
        return sorted(hit["variants"])
    # fallback: try contains on key (coarse)
    parts = k.split()
    if parts:
        for key, blob in subject_alias.items():
            if all(p in key for p in parts):
                return sorted(blob["variants"])
    return [clean_string(user_text)] if user_text else []
