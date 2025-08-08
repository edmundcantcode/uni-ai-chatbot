# backend/constants/intent_config.py
"""
SINGLE SOURCE OF TRUTH for all intent configuration.
Add a new intent here and everything else is auto-generated.
"""

from typing import Dict, List, Any
import re

# Import normalization functions
from backend.utils.normalizers import normalize_cohort, normalize_grade, clean_string
from backend.utils.value_index import subject_variants, programme_variants

# Status normalization mapping
STATUS_NORMALIZE = {
    "active": "Active",
    "completed": "Completed", 
    "finished": "Finished",
    "withdraw": "Withdraw",
    "withdrawn": "Withdrawn", 
    "transfer out": "Transfer Out",
    "transferred out": "Transfer Out",
}

def normalize_status(s: str) -> str:
    """Normalize status text to canonical form."""
    key = (s or "").strip().lower()
    return STATUS_NORMALIZE.get(key, s.strip())

# Complete intent configuration in one place
INTENT_CONFIG = {
    "get_student_by_id": {
        "description": "Look up a specific student using their ID number",
        "base_query": "SELECT * FROM students WHERE id = {student_id}",
        "required_entities": ["student_id"],
        "optional_entities": [],
        "allow_count": False,
        "entity_rules": {
            "student_id": {
                "description": "Extract the student ID number",
                "examples": [
                    {"query": "Find student 12345", "entities": {"student_id": "12345"}},
                    {"query": "Get student ID ST001", "entities": {"student_id": "ST001"}},
                ]
            }
        }
    },

    # --- SELF-SERVICE / "MY" INTENTS ---

    "get_my_details": {
        "description": "Show the currently logged-in student's profile",
        "base_query": "SELECT * FROM students WHERE id = {student_id}",
        "required_entities": ["student_id"],
        "optional_entities": [],
        "allow_count": False,
        "entity_rules": {
            "student_id": {
                "description": "The caller's student id (auto-injected from session when role=student)",
                "examples": [
                    {"query": "show my details", "entities": {}},
                    {"query": "my profile", "entities": {}},
                    {"query": "show my info", "entities": {}},
                    {"query": "display my student record", "entities": {}},
                    {"query": "what are my student details?", "entities": {}}
                ]
            }
        }
    },

    "get_my_cgpa": {
        "description": "Show the logged-in student's current CGPA",
        "base_query": "SELECT id, name, overallcgpa FROM students WHERE id = {student_id}",
        "required_entities": ["student_id"],
        "optional_entities": [],
        "allow_count": False,
        "entity_rules": {
            "student_id": {
                "description": "The caller's student id (auto-injected from session when role=student)",
                "examples": [
                    {"query": "what's my CGPA?", "entities": {}},
                    {"query": "show my cgpa", "entities": {}},
                    {"query": "my GPA please", "entities": {}},
                    {"query": "current CGPA for me", "entities": {}}
                ]
            }
        }
    },

    "get_my_programme": {
        "description": "Show the logged-in student's programme information",
        "base_query": "SELECT id, name, programme, programmecode, cohort, year, sem, status FROM students WHERE id = {student_id}",
        "required_entities": ["student_id"],
        "optional_entities": [],
        "allow_count": False,
        "entity_rules": {
            "student_id": {
                "description": "The caller's student id (auto-injected)",
                "examples": [
                    {"query": "what programme am I in?", "entities": {}},
                    {"query": "show my programme info", "entities": {}},
                    {"query": "what's my cohort and semester?", "entities": {}},
                    {"query": "tell me my programme code", "entities": {}}
                ]
            }
        }
    },

    "get_my_subjects": {
        "description": "List the logged-in student's subjects",
        "base_query": "SELECT * FROM subjects WHERE id = {student_id}",
        "required_entities": ["student_id"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "student_id": {
                "description": "The caller's student id (auto-injected)",
                "examples": [
                    {"query": "list my subjects", "entities": {}},
                    {"query": "show my modules", "entities": {}},
                    {"query": "what courses am I taking?", "entities": {}},
                    {"query": "subjects I'm enrolled in", "entities": {}}
                ]
            },
            "limit": {
                "description": "Max number of rows to show",
                "examples": [
                    {"query": "list my subjects (top 5)", "entities": {"limit": "5"}},
                    {"query": "show 10 of my modules", "entities": {"limit": "10"}}
                ]
            }
        }
    },

    "get_my_grade_in_subject": {
        "description": "Return the logged-in student's grade for a specific subject",
        "base_query": "SELECT subjectname, grade, overallpercentage FROM subjects WHERE id = {student_id} AND subjectname LIKE '%{subject_name}%'",
        "required_entities": ["student_id", "subject_name"],
        "optional_entities": [],
        "allow_count": False,
        "entity_rules": {
            "student_id": {
                "description": "The caller's student id (auto-injected)",
                "examples": [
                    {"query": "what grade did I get in Database Fundamentals?", "entities": {"subject_name": "Database Fundamentals"}},
                    {"query": "my grade for Programming Principles", "entities": {"subject_name": "Programming Principles"}},
                    {"query": "show my mark in Computer Networks", "entities": {"subject_name": "Computer Networks"}}
                ]
            },
            "subject_name": {
                "description": "Subject name (messy variants OK; normalizer handles them)",
                "examples": [
                    {"query": "grade for Data Mining and Knowledge Discovery", "entities": {"subject_name": "Data Mining and Knowledge Discovery"}},
                    {"query": "grade in Web Programming", "entities": {"subject_name": "Web Programming"}}
                ]
            }
        }
    },

    "did_i_fail_subject": {
        "description": "Check if the logged-in student failed a specific subject",
        "base_query": "SELECT subjectname, grade FROM subjects WHERE id = {student_id} AND subjectname LIKE '%{subject_name}%' AND grade IN ('F','F*','F#','(F)','F^')",
        "required_entities": ["student_id", "subject_name"],
        "optional_entities": [],
        "allow_count": False,
        "entity_rules": {
            "student_id": {
                "description": "The caller's student id (auto-injected)",
                "examples": [
                    {"query": "did I fail Data Communications?", "entities": {"subject_name": "Data Communications"}},
                    {"query": "did I fail Programming Principles", "entities": {"subject_name": "Programming Principles"}},
                    {"query": "did I fail Web Programming?", "entities": {"subject_name": "Web Programming"}}
                ]
            },
            "subject_name": {
                "description": "Subject name to check",
                "examples": [
                    {"query": "did I fail Operating System Fundamentals?", "entities": {"subject_name": "Operating System Fundamentals"}}
                ]
            }
        }
    },

    "get_my_failed_subjects": {
        "description": "List all failed subjects for the logged-in student",
        "base_query": "SELECT subjectname, grade FROM subjects WHERE id = {student_id} AND grade IN ('F','F*','F#','(F)','F^')",
        "required_entities": ["student_id"],
        "optional_entities": [],
        "allow_count": True,
        "entity_rules": {
            "student_id": {
                "description": "The caller's student id (auto-injected)",
                "examples": [
                    {"query": "what subjects did I fail?", "entities": {}},
                    {"query": "show my failed modules", "entities": {}},
                    {"query": "list all my failed courses", "entities": {}}
                ]
            }
        }
    },

    
    "get_student_by_name": {
        "description": "Find a student by searching their name",
        "base_query": "SELECT * FROM students WHERE name = '{student_name}'",
        "required_entities": ["student_name"],
        "optional_entities": [],
        "allow_count": False,
        "entity_rules": {
            "student_name": {
                "description": "Extract the student's full name",
                "examples": [
                    {"query": "Find John Smith", "entities": {"student_name": "John Smith"}},
                    {"query": "Look up Mary Jane", "entities": {"student_name": "Mary Jane"}},
                ]
            }
        }
    },
    
    "filter_by_cgpa_greater_than": {
        "description": "Find students performing above a CGPA threshold",
        "base_query": "SELECT * FROM students WHERE overallcgpa > {cgpa_value}",
        "required_entities": ["cgpa_value"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "cgpa_value": {
                "description": "Extract CGPA threshold number",
                "examples": [
                    {"query": "CGPA above 3.5", "entities": {"cgpa_value": "3.5"}},
                    {"query": "Students with CGPA > 3.0", "entities": {"cgpa_value": "3.0"}},
                ]
            },
            "limit": {
                "description": "Extract number of results wanted (optional)",
                "examples": [
                    {"query": "Top 10 with CGPA > 3.0", "entities": {"cgpa_value": "3.0", "limit": "10"}},
                ]
            }
        }
    },
    
    "filter_by_cgpa_less_than": {
        "description": "Find students performing below a CGPA threshold (at-risk students)",
        "base_query": "SELECT * FROM students WHERE overallcgpa < {cgpa_value}",
        "required_entities": ["cgpa_value"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "cgpa_value": {
                "description": "Extract CGPA threshold number",
                "examples": [
                    {"query": "CGPA below 2.0", "entities": {"cgpa_value": "2.0"}},
                    {"query": "Poor performers under 2.5", "entities": {"cgpa_value": "2.5"}},
                ]
            }
        }
    },
    
    "get_top_students_by_cgpa_in_cohort": {
        "description": "Get the highest performing students within a specific cohort (Cassandra-legal ORDER BY)",
        "base_query": "SELECT id, name, overallcgpa FROM students WHERE cohort = '{cohort}' AND overallcgpa IS NOT NULL ORDER BY overallcgpa DESC",
        "required_entities": ["cohort"],
        "optional_entities": ["limit"],
        "default_values": {"limit": 10},
        "allow_count": False,
        "entity_rules": {
            "cohort": {
                "description": "Extract cohort/intake year or code",
                "examples": [
                    {"query": "Top 5 students in 2023 cohort", "entities": {"cohort": "2023", "limit": "5"}},
                    {"query": "Best performers from 202301 intake", "entities": {"cohort": "202301"}},
                ]
            },
            "limit": {
                "description": "Extract number of top students wanted",
                "examples": [
                    {"query": "Top 10 students in cohort", "entities": {"limit": "10"}},
                    {"query": "Best 5 performers", "entities": {"limit": "5"}},
                ]
            }
        }
    },
    
    "get_high_cgpa_students": {
        "description": "Get students with CGPA above threshold (alternative to 'top' for cross-cohort)",
        "base_query": "SELECT id, name, overallcgpa FROM students WHERE overallcgpa >= {cgpa_threshold}",
        "required_entities": ["cgpa_threshold"],
        "optional_entities": ["limit"],
        "default_values": {"cgpa_threshold": "3.5"},
        "allow_count": True,
        "entity_rules": {
            "cgpa_threshold": {
                "description": "Extract CGPA threshold for high performers",
                "examples": [
                    {"query": "Top students with CGPA 3.7+", "entities": {"cgpa_threshold": "3.7"}},
                    {"query": "High performers above 3.5", "entities": {"cgpa_threshold": "3.5"}},
                ]
            }
        }
    },
    
    "get_active_students": {
        "description": "List currently enrolled students",
        "base_query": "SELECT * FROM students WHERE status = 'Active'",
        "required_entities": [],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {}
    },
    
    "get_completed_students": {
        "description": "List students who have completed their studies",
        "base_query": "SELECT * FROM students WHERE status = 'Completed'",
        "required_entities": [],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {}
    },
    
    "get_finished_students": {
        "description": "List students who have finished their studies",
        "base_query": "SELECT * FROM students WHERE status = 'Finished'",
        "required_entities": [],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {}
    },
    
    "get_withdrawn_students": {
        "description": "List students who have withdrawn from studies",
        "base_query": "SELECT * FROM students WHERE status IN ('Withdraw', 'Withdrawn')",
        "required_entities": [],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {}
    },
    
    "get_transferred_out_students": {
        "description": "List students who have transferred out",
        "base_query": "SELECT * FROM students WHERE status = 'Transfer Out'",
        "required_entities": [],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {}
    },
    
    "get_graduated_students": {
        "description": "List all graduated students",
        "base_query": "SELECT * FROM students WHERE graduated = true",
        "required_entities": [],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {}
    },
    
    "get_failed_students": {
        "description": "List students who have failed (need intervention) - handles all F grade variants",
        "base_query": "SELECT DISTINCT id FROM subjects WHERE grade IN ('F', 'F*', 'F#', '(F)', 'F^')",
        "required_entities": [],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {}
    },
    
    "get_students_by_grade": {
        "description": "Find students with a specific grade (normalized)",
        "base_query": "SELECT DISTINCT id FROM subjects WHERE grade = '{grade}'",
        "required_entities": ["grade"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "grade": {
                "description": "Extract grade value (will be normalized)",
                "examples": [
                    {"query": "Students with grade A", "entities": {"grade": "A"}},
                    {"query": "Students who got F", "entities": {"grade": "F"}},
                ]
            }
        }
    },
    
    "filter_by_status": {
        "description": "Filter students by any status value",
        "base_query": "SELECT * FROM students WHERE status = '{status}'",
        "required_entities": ["status"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "status": {
                "description": "Extract student status",
                "examples": [
                    {"query": "Active students", "entities": {"status": "Active"}},
                    {"query": "Completed students", "entities": {"status": "Completed"}},
                    {"query": "Withdrawn students", "entities": {"status": "Withdrawn"}},
                ]
            }
        }
    },
    
    "filter_by_gender": {
        "description": "Generate gender-based reports and statistics",
        "base_query": "SELECT * FROM students WHERE gender = '{gender}'",
        "required_entities": ["gender"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "gender": {
                "description": "Extract gender (Male or Female)",
                "examples": [
                    {"query": "Male students", "entities": {"gender": "Male"}},
                    {"query": "Female students", "entities": {"gender": "Female"}},
                ]
            }
        }
    },
    
    "filter_by_cohort": {
        "description": "View students by their intake year/cohort",
        "base_query": "SELECT * FROM students WHERE cohort = '{cohort}'",
        "required_entities": ["cohort"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "cohort": {
                "description": "Extract cohort/intake year or code",
                "examples": [
                    {"query": "2023 cohort", "entities": {"cohort": "2023"}},
                    {"query": "Students from 202301 intake", "entities": {"cohort": "202301"}},
                ]
            }
        }
    },
    
    "filter_by_programme": {
        "description": "List students in a specific academic programme",
        "base_query": "SELECT * FROM students WHERE programme LIKE '%{programme}%'",
        "required_entities": ["programme"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "programme": {
                "description": "Extract programme name",
                "examples": [
                    {"query": "Computer Science students", "entities": {"programme": "Computer Science"}},
                    {"query": "Software Engineering programme", "entities": {"programme": "Software Engineering"}},
                ]
            }
        }
    },
    
    "get_all_programmes": {
        "description": "Get complete list of all academic programmes",
        "base_query": "SELECT DISTINCT programme FROM students",
        "required_entities": [],
        "optional_entities": [],
        "allow_count": False,
        "entity_rules": {}
    },
    
    "get_students_in_subject": {
        "description": "Find all students enrolled in a specific subject/course",
        "base_query": "SELECT DISTINCT id FROM subjects WHERE subjectname LIKE '%{subject_name}%'",
        "required_entities": ["subject_name"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "subject_name": {
                "description": "Extract subject/course name",
                "examples": [
                    {"query": "Students in Database Fundamentals", "entities": {"subject_name": "Database Fundamentals"}},
                    {"query": "Programming Principles class", "entities": {"subject_name": "Programming Principles"}},
                ]
            }
        }
    },
    
    "get_active_students_by_cohort": {
        "description": "Active students in a specific cohort",
        "base_query": "SELECT * FROM students WHERE status = 'Active' AND cohort = '{cohort}'",
        "required_entities": ["cohort"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "cohort": {
                "description": "Extract cohort/intake year or code",
                "examples": [
                    {"query": "Active students from 2023 cohort", "entities": {"cohort": "2023"}},
                    {"query": "Current students from March 2022", "entities": {"cohort": "March 2022"}},
                ]
            }
        }
    },
    
    "filter_active_by_cgpa_greater_than": {
        "description": "Active students with CGPA above threshold",
        "base_query": "SELECT * FROM students WHERE status = 'Active' AND overallcgpa > {cgpa_value}",
        "required_entities": ["cgpa_value"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "cgpa_value": {
                "description": "Extract CGPA threshold number",
                "examples": [
                    {"query": "Active students with CGPA above 3.5", "entities": {"cgpa_value": "3.5"}},
                    {"query": "Current students CGPA > 3.0", "entities": {"cgpa_value": "3.0"}},
                ]
            }
        }
    },
    
    "filter_active_by_cgpa_less_than": {
        "description": "Active students with CGPA below threshold",
        "base_query": "SELECT * FROM students WHERE status = 'Active' AND overallcgpa < {cgpa_value}",
        "required_entities": ["cgpa_value"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "cgpa_value": {
                "description": "Extract CGPA threshold number",
                "examples": [
                    {"query": "Active students with CGPA below 2.0", "entities": {"cgpa_value": "2.0"}},
                    {"query": "Current at-risk students under 2.5", "entities": {"cgpa_value": "2.5"}},
                ]
            }
        }
    },
    
    "get_active_students_by_programme": {
        "description": "Active students by programme",
        "base_query": "SELECT * FROM students WHERE status = 'Active' AND programme LIKE '%{programme}%'",
        "required_entities": ["programme"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "programme": {
                "description": "Extract programme name",
                "examples": [
                    {"query": "Active Computer Science students", "entities": {"programme": "Computer Science"}},
                    {"query": "Current Software Engineering students", "entities": {"programme": "Software Engineering"}},
                ]
            }
        }
    },
    
    "get_active_students_by_gender": {
        "description": "Active students by gender",
        "base_query": "SELECT * FROM students WHERE status = 'Active' AND gender = '{gender}'",
        "required_entities": ["gender"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "gender": {
                "description": "Extract gender (Male or Female)",
                "examples": [
                    {"query": "Active male students", "entities": {"gender": "Male"}},
                    {"query": "Current female students", "entities": {"gender": "Female"}},
                ]
            }
        }
    },
    
    "get_active_students_by_cohort_failed_subject": {
        "description": "Active students in a cohort who failed a subject",
        "base_query": "SELECT DISTINCT id FROM subjects WHERE grade IN ('F','F*','F#','(F)','F^') AND subjectname LIKE '%{subject_name}%'",
        "required_entities": ["cohort", "subject_name"],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {
            "cohort": {
                "description": "Extract cohort/intake year or code",
                "examples": [
                    {"query": "Active 2023 students who failed Database", "entities": {"cohort": "2023", "subject_name": "Database"}},
                ]
            },
            "subject_name": {
                "description": "Extract subject/course name",
                "examples": [
                    {"query": "Active students in cohort who failed Programming", "entities": {"subject_name": "Programming"}},
                ]
            }
        }
    },
    
    "get_sponsored_students": {
        "description": "List students receiving financial aid/sponsorship",
        "base_query": "SELECT * FROM students WHERE sponsorname IS NOT NULL AND sponsorname != ''",
        "required_entities": [],
        "optional_entities": ["limit"],
        "allow_count": True,
        "entity_rules": {}
    },
}

# Auto-generated lists from the config above
BASE_INTENTS = list(INTENT_CONFIG.keys())

INTENT_DESCRIPTIONS = {
    intent: config["description"] 
    for intent, config in INTENT_CONFIG.items()
}

INTENT_QUERY_CONFIG = {
    intent: {
        "base_query": config["base_query"],
        "required_entities": config["required_entities"],
        "optional_entities": config["optional_entities"],
        "allow_count": config.get("allow_count", True),
        "default_values": config.get("default_values", {})
    }
    for intent, config in INTENT_CONFIG.items()
}

# Query types
QUERY_TYPES = ["count", "list"]

def get_intents_for_prompt():
    """Auto-generate formatted intents for LLM prompt"""
    formatted = []
    for intent in BASE_INTENTS:
        desc = INTENT_DESCRIPTIONS.get(intent, "")
        formatted.append(f"- {intent}: {desc}")
    return "\n".join(formatted)

def get_entity_extraction_config(intent: str) -> Dict[str, Any]:
    """Get entity extraction configuration for a specific intent"""
    config = INTENT_CONFIG.get(intent, {})
    return config.get("entity_rules", {})

def get_query_config(intent: str) -> Dict[str, Any]:
    """Get query configuration for a specific intent"""
    return INTENT_QUERY_CONFIG.get(intent, {})

def get_query_type_prompt(query: str) -> str:
    """Generate prompt for query type classification (count vs list)"""
    return f"""Classify this query as either 'count' or 'list':

Rules:
- 'count': User wants a NUMBER (how many, count, total, number of, amount)
- 'list': User wants to see DATA/RECORDS (show, list, get, find, display, who, which)

Examples:
- "How many students are enrolled?" → count
- "Show me all students with CGPA > 3.0" → list
- "Count male students in 2023 cohort" → count
- "List female students with high attendance" → list
- "What's the total number of failed students?" → count
- "Get student details for ID 12345" → list

Query: "{query}"

Respond with ONLY one word: either 'count' or 'list'"""

def get_intent_classification_prompt(query: str) -> str:
    intents_formatted = get_intents_for_prompt()
    return f"""You are classifying a student management system query AND extracting entities.

AVAILABLE INTENTS:
{intents_formatted}

Return ONLY valid JSON with ALL THREE keys exactly:
{{"intent": "<one of the intents>", "confidence": 0.0-1.0, "entities": {{...}}}}

If an intent requires entities (e.g., cgpa_value), you MUST include them in "entities".

EXAMPLES:
- "Students with CGPA above 3.5" → {{"intent": "filter_by_cgpa_greater_than", "confidence": 0.9, "entities": {{"cgpa_value": "3.5"}}}}
- "Top 10 students" → {{"intent": "get_top_students_by_cgpa", "confidence": 0.95, "entities": {{"limit": "10"}}}}
- "Male students" → {{"intent": "filter_by_gender", "confidence": 0.9, "entities": {{"gender": "Male"}}}}
- "show currently active students" → {{"intent": "get_active_students", "confidence": 0.95, "entities": {{}}}}
- "show currently enrolled students" → {{"intent": "get_active_students", "confidence": 0.95, "entities": {{}}}}

Query: "{query}" """


def build_query(intent: str, query_type: str, entities: dict) -> str:
    """
    Build the actual CQL query from intent and entities with normalization.
    THIS IS CQL SO REMEMBER THERE IS NO "DISTINCY, LIKE, etc"
    """
    config = INTENT_QUERY_CONFIG.get(intent)
    if not config:
        raise ValueError(f"No query configuration found for intent: {intent}")
    
    # Get base query
    base_query = config["base_query"]
    
    # Handle count queries
    if query_type == "count":
        if not config.get("allow_count", True):
            raise ValueError(f"Intent '{intent}' does not support count queries")
        
        # Convert to count query
        if "SELECT DISTINCT" in base_query:
            # Handle COUNT(DISTINCT ...) - more reliable approach
            base_query = base_query.replace("SELECT DISTINCT", "SELECT COUNT(DISTINCT", 1)
            base_query = base_query.replace(" FROM", ") FROM", 1)
        else:
            # Handle regular COUNT(*) using regex for better matching
            base_query = re.sub(r'SELECT\s+.*?\s+FROM', 'SELECT COUNT(*) FROM', base_query, count=1)
    
    # Apply default values for optional entities
    for key, value in config.get("default_values", {}).items():
        if key not in entities:
            entities[key] = value
    
    # Check required entities
    for required in config.get("required_entities", []):
        if required not in entities:
            raise ValueError(f"Missing required entity: {required}")
    
    # ---- NORMALIZATION LAYER ----
    
    # cohort: "March 2022" -> "202203"
    if "cohort" in entities:
        norm = normalize_cohort(str(entities["cohort"]))
        if norm:
            entities["cohort"] = norm
    
    # grade: "A+^" -> "A+", "F*" -> "F", etc.
    if "grade" in entities:
        g = normalize_grade(entities["grade"])
        if g:
            entities["grade"] = g
            # Special handling for failed grades - expand to all variants
            if g == "F" and "grade = '{grade}'" in base_query:
                base_query = base_query.replace(
                    "grade = '{grade}'", 
                    "grade IN ('F', 'F*', 'F#', '(F)', 'F^')"
                )
                entities.pop("grade", None)
    
    # status: normalize "active/Active/ACTIVE" -> "Active", etc.
    if "status" in entities:
        entities["status"] = normalize_status(str(entities["status"]))
    
    # subject_name -> IN (variants...) if we have variants
    # works for intents that refer to subjectname
    if "subject_name" in entities:
        variants = subject_variants(entities["subject_name"])
        if variants and "subjectname" in base_query:
            # swap any equality/LIKE on subjectname into an IN clause
            placeholders = ", ".join("'" + v.replace("'", "''") + "'" for v in variants)
            # handle either = '{subject_name}' or LIKE '%{subject_name}%'
            base_query = (
                base_query
                .replace("subjectname = '{subject_name}'", f"subjectname IN ({placeholders})")
                .replace("subjectname LIKE '%{subject_name}%'", f"subjectname IN ({placeholders})")
            )
            entities.pop("subject_name", None)
    
    # programme: map messy names to exact variants; prefer IN (...) over LIKE
    if "programme" in entities and "programme" in base_query:
        pvars = programme_variants(entities["programme"])
        if pvars:
            ph = ", ".join("'" + v.replace("'", "''") + "'" for v in pvars)
            base_query = base_query.replace("programme LIKE '%{programme}%'", f"programme IN ({ph})")
            base_query = base_query.replace("programme = '{programme}'", f"programme IN ({ph})")
            entities.pop("programme", None)
        else:
            # fallback: keep LIKE but clean
            entities["programme"] = clean_string(entities["programme"]) or entities["programme"]
    
    # Sanitize string entities to prevent injection
    sanitized_entities = {}
    for key, value in entities.items():
        if isinstance(value, str):
            # Escape single quotes by doubling them (CQL standard)
            sanitized_entities[key] = value.replace("'", "''")
        else:
            sanitized_entities[key] = value
    
    # Format the query with entities
    try:
        query = base_query.format(**sanitized_entities)
    except KeyError as e:
        raise ValueError(f"Missing entity in query template: {e}")
    
    # Add LIMIT if specified and not already in query (case-insensitive check)
    if "limit" in entities and "LIMIT" not in query.upper():
        query += f" LIMIT {entities['limit']}"
    
    # Cassandra needs ALLOW FILTERING for non-key filtering
    if "WHERE" in query.upper() and "ALLOW FILTERING" not in query.upper():
        query += " ALLOW FILTERING"
    
    return query