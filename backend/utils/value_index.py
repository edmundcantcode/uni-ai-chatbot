# backend/utils/value_index.py
import json
import os
from typing import List, Dict, Set, Optional
from backend.utils.normalizers import build_alias_map, clean_string, canonical_key, resolve_subject_variants

# Where your json is mounted in docker-compose
UNIQUE_JSON = os.getenv("UNIQUE_VALUES_JSON", "/app/backend/utils/unique_values_prompt.json")

SUBJECT_ALIAS: Dict[str, Dict[str, Set[str]]] = {}
PROGRAMME_ALIAS: Dict[str, Dict[str, Set[str]]] = {}
COUNTRY_ALIAS: Dict[str, Dict[str, Set[str]]] = {}
RACE_ALIAS: Dict[str, Dict[str, Set[str]]] = {}
FINAID_ALIAS: Dict[str, Dict[str, Set[str]]] = {}

# Map "active" → these DB codes
ACTIVE_STATUSES = {"RP", "RP2", "RP3", "RP4", "RP5"}

_loaded = False

def _load():
    global _loaded, SUBJECT_ALIAS, PROGRAMME_ALIAS, COUNTRY_ALIAS, RACE_ALIAS, FINAID_ALIAS
    if _loaded:
        return
    
    try:
        with open(UNIQUE_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)

        SUBJECT_ALIAS = build_alias_map(data.get("subjectname", []))
        PROGRAMME_ALIAS = build_alias_map(data.get("programme", []))
        COUNTRY_ALIAS = build_alias_map(data.get("country", []))
        RACE_ALIAS = build_alias_map(data.get("race", []))
        FINAID_ALIAS = build_alias_map(data.get("financialaid", []))
        _loaded = True
        print(f"✅ Loaded normalization data from {UNIQUE_JSON}")
        print(f"   - Subjects: {len(SUBJECT_ALIAS)} canonical forms")
        print(f"   - Programmes: {len(PROGRAMME_ALIAS)} canonical forms")
        print(f"   - Countries: {len(COUNTRY_ALIAS)} canonical forms")
        print(f"   - Races: {len(RACE_ALIAS)} canonical forms")
        print(f"   - Financial Aid: {len(FINAID_ALIAS)} canonical forms")
    except FileNotFoundError:
        print(f"⚠️  Unique values file not found: {UNIQUE_JSON}")
        print("   Normalization will use fallback behavior")
        _loaded = True
    except Exception as e:
        print(f"⚠️  Error loading unique values: {e}")
        print("   Normalization will use fallback behavior")
        _loaded = True

def resolve_variants(alias_map: Dict[str, Dict[str, Set[str]]], user_text: str) -> List[str]:
    """Return list of exact DB variants that match the user text."""
    _load()
    key = canonical_key(user_text or "")
    hit = alias_map.get(key)
    if hit:
        return sorted(hit["variants"])
    # fallback: partial match
    parts = key.split()
    if parts:
        for k, blob in alias_map.items():
            if all(p in k for p in parts):
                return sorted(blob["variants"])
    ut = clean_string(user_text)
    return [ut] if ut else []

def subject_variants(name: str) -> List[str]:
    _load()
    return resolve_variants(SUBJECT_ALIAS, name)

def programme_variants(name: str) -> List[str]:
    _load()
    return resolve_variants(PROGRAMME_ALIAS, name)

def country_variants(name: str) -> List[str]:
    _load()
    return resolve_variants(COUNTRY_ALIAS, name)

def race_variants(name: str) -> List[str]:
    _load()
    return resolve_variants(RACE_ALIAS, name)

def finaid_variants(name: str) -> List[str]:
    _load()
    return resolve_variants(FINAID_ALIAS, name)

def get_active_statuses() -> Set[str]:
    """Get all statuses considered 'active'."""
    return ACTIVE_STATUSES

def is_loaded() -> bool:
    """Check if normalization data is loaded."""
    return _loaded

def get_stats() -> Dict[str, int]:
    """Get statistics about loaded normalization data."""
    _load()
    return {
        "subjects": len(SUBJECT_ALIAS),
        "programmes": len(PROGRAMME_ALIAS), 
        "countries": len(COUNTRY_ALIAS),
        "races": len(RACE_ALIAS),
        "financial_aid": len(FINAID_ALIAS)
    }