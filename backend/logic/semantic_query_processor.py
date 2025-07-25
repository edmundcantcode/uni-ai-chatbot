# backend/logic/semantic_query_processor.py
"""
Enhanced query processor with LLM-first approach and semantic fallbacks.
FIXED: Row iteration bug and status value normalization
ADDED: Pass/Fail student patterns
ADDED: CQL fallback system for when semantic processing fails
"""

import asyncio
import time
import json
import re
import sys
from typing import Dict, Any, List, Optional, Tuple

# CRITICAL: Setup logging first before any other imports
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s",
    stream=sys.stdout,
    force=True
)

logger = logging.getLogger(__name__)

# Import the fallback system
from backend.constants.fallback_queries import should_try_fallback, try_fallback_query

# FIXED: Move imports inside functions to avoid circular imports
def get_llama_llm():
    """Lazy import of LlamaLLM"""
    try:
        from backend.llm.llama_integration import LlamaLLM
        return LlamaLLM
    except ImportError as e:
        logger.error(f"Failed to import LlamaLLM: {e}")
        return None

def get_cassandra_session():
    """Lazy import of Cassandra session"""
    try:
        from backend.database.connect_cassandra import get_session
        return get_session
    except ImportError as e:
        logger.error(f"Failed to import Cassandra session: {e}")
        return None

def get_subjects_utils():
    """Lazy import of subjects utilities"""
    try:
        from backend.constants.subjects_index import load_subjects_from_file, SUBJECT_CANONICAL
        return load_subjects_from_file, SUBJECT_CANONICAL
    except ImportError as e:
        logger.error(f"Failed to import subjects utils: {e}")
        return None, {}

def get_entity_resolver():
    """Lazy import of entity resolver"""
    try:
        from .entity_resolver import resolve_entities, canonicalize_plan_steps
        return resolve_entities, canonicalize_plan_steps
    except ImportError as e:
        logger.error(f"Failed to import entity resolver: {e}")
        return None, None

def get_step_runner():
    """Lazy import of step runner"""
    try:
        from .step_runner import run_step, get_active_status_values
        return run_step, get_active_status_values
    except ImportError as e:
        logger.error(f"Failed to import step runner: {e}")
        return None, None

# Explicit column lists (Cassandra hates "*")
SELECT_STUDENTS = ["id","name","programme","overallcgpa","cohort","status","graduated"]
SELECT_SUBJECTS = ["id","subjectname","grade","overallpercentage","examyear","exammonth"]

# Safe integer conversion utility
def _safe_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None

# Cache for real status values
_cached_active_statuses = None

# Lazy import functions to avoid circular dependencies
def get_enhanced_processor():
    """Lazy import of EnhancedQueryProcessor to avoid circular imports"""
    try:
        from .query_processor import EnhancedQueryProcessor
        return EnhancedQueryProcessor
    except ImportError as e:
        logger.error(f"Failed to import EnhancedQueryProcessor: {e}")
        return None

def get_shared_functions():
    """Get shared functions from query_processor or core_executor"""
    try:
        # Try core_executor first if it exists
        from .core_executor import (
            execute_plan,
            create_error_response,
            create_security_error_response,
            format_response_message,
            PaginatedResponse
        )
        return execute_plan, create_error_response, create_security_error_response, format_response_message, PaginatedResponse
    except ImportError:
        try:
            # Fallback to query_processor
            from .query_processor import (
                execute_plan,
                create_error_response,
                format_response_message,
                PaginatedResponse
            )
            
            # Create missing security error function
            def create_security_error_response(query: str, user_role: str, start_time: float) -> Dict[str, Any]:
                return {
                    "success": False,
                    "message": f"🔒 **Access Denied**\n\nAs a {user_role}, you can only access your own academic records.",
                    "data": [],
                    "count": 0,
                    "error": True,
                    "query": query,
                    "intent": "security_error",
                    "execution_time": time.time() - start_time,
                    "security_level": user_role
                }
            
            return execute_plan, create_error_response, create_security_error_response, format_response_message, PaginatedResponse
        except ImportError as e:
            logger.error(f"Failed to import shared functions: {e}")
            return None, None, None, None, None

def prune_unmentioned_filters(plan: Dict[str, Any], user_query: str) -> Dict[str, Any]:
    """Remove filters for columns the user never mentioned - ENHANCED to handle nested filters"""
    q_lower = user_query.lower()
    
    # Build allowed columns based on what's mentioned in query
    allowed = set()
    
    # Always allow basic filters
    allowed.update(["id", "allow_filtering"])
    
    # Check for mentions of specific columns
    if any(word in q_lower for word in ["cohort", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]):
        allowed.add("cohort")
    if any(word in q_lower for word in ["active", "enrolled", "current", "status"]):
        allowed.add("status")
    if any(word in q_lower for word in ["graduated", "graduation"]):
        allowed.add("graduated")
    if any(word in q_lower for word in ["programme", "program", "computer science", "information technology", "cs", "it"]):
        allowed.add("programme")
    if any(word in q_lower for word in ["cgpa", "gpa"]):
        allowed.add("overallcgpa")
    if any(word in q_lower for word in ["gender", "male", "female", "men", "women"]):
        allowed.add("gender")
    if any(word in q_lower for word in ["country", "malaysia", "singapore", "india"]):
        allowed.add("country")
    if any(word in q_lower for word in ["subject", "grade", "score", "marks", "passed", "failed"]):
        allowed.add("subjectname")
        allowed.add("grade")  # Allow grade filter for pass/fail queries
    if any(word in q_lower for word in ["year", "2020", "2021", "2022", "2023", "2024"]):
        allowed.update(["examyear", "year"])
    
    def strip_where(where: Dict[str, Any]):
        """Helper to strip unwanted filters from where clauses"""
        for col in list(where.keys()):
            if col not in allowed:
                logger.debug(f"Removing unmentioned filter: {col}")
                where.pop(col, None)
    
    # Prune unmentioned filters from all steps
    for step in plan.get("steps", []):
        # Main where clause
        strip_where(step.get("where", {}))
        
        # If the LLM put a nested where under post_aggregation
        if "post_aggregation" in step and isinstance(step["post_aggregation"], dict):
            strip_where(step["post_aggregation"].get("where", {}))
    
    return plan

def remove_duplicate_steps(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Remove duplicate steps from plan"""
    if "steps" not in plan:
        return plan
    
    unique = []
    for s in plan["steps"]:
        if s not in unique:  # naive but works
            unique.append(s)
        else:
            logger.debug("Removed duplicate step")
    
    plan["steps"] = unique
    return plan

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_real_active_statuses():
    """Get real active status values from database (with caching)"""
    global _cached_active_statuses
    
    if _cached_active_statuses is None:
        try:
            get_session = get_cassandra_session()
            _, get_active_status_values = get_step_runner()
            if get_session and get_active_status_values:
                session = get_session()
                _cached_active_statuses = get_active_status_values(session)
                logger.info(f"✅ Cached active status values: {_cached_active_statuses}")
            else:
                raise Exception("Could not import required functions")
        except Exception as e:
            logger.warning(f"Could not load active status values: {e}")
            _cached_active_statuses = ["Active", "Enrolled", "Current"]  # Fallback
    
    return _cached_active_statuses

def _safe_captures(m: re.Match) -> Dict[str, str]:
    """Safely extract capture groups from regex match"""
    if not m or m.lastindex is None:
        return {}
    return {f"group_{i}": m.group(i) for i in range(1, m.lastindex + 1)}

# Intent detection keywords and helpers - FIXED: Use word boundaries
LIST_WORDS = (r"\blist\b", r"\bshow\b", r"\bdisplay\b", r"\bgive me\b", r"\bshow me\b", r"\bretrieve\b")
COUNT_WORDS = (r"\bcount\b", r"\bhow many\b", r"\btotal\b", r"\bnumber of\b")

def wants_list(q: str) -> bool:
    """Check if user wants a list of records (not a count)"""
    return any(re.search(w, q, re.I) for w in LIST_WORDS) and not any(re.search(w, q, re.I) for w in COUNT_WORDS)

def wants_count(q: str) -> bool:
    """Check if user wants a count (not a list)"""
    return any(re.search(w, q, re.I) for w in COUNT_WORDS)

# ============================================================================
# SEMANTIC PATTERNS
# ============================================================================

class SemanticPattern:
    """Enhanced pattern matching with entity resolution"""
    
    def __init__(self, pattern: str, intent: str, handler: str):
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.intent = intent
        self.handler = handler

class SemanticRouter:
    """Router with semantic understanding"""
    
    PATTERNS = [
        # "What are my grades?" → list_student_subjects
        SemanticPattern(
            r"(?:what|show|list)\s+(?:are\s+)?my\s+grades\b",
            "list_student_subjects",
            "handle_list_student_subjects"
        ),
        
        # "What's my grade for X?" → get_subject_grade
        SemanticPattern(
            r"(?:what|show|get)(?:'s| is)?\s+my\s+grades?\s+for\s+(.+)",
            "get_subject_grade",
            "handle_subject_grade"
        ),
        
        # "List subjects that I take" → list_student_subjects
        SemanticPattern(
            r"(?:list|show)\s+(?:all\s+)?subjects\s+(?:that\s+)?(?:I|i)\s+(?:take|am taking|am enrolled in|have)",
            "list_student_subjects",
            "handle_list_student_subjects"
        ),
        
        # "Show my subjects" → list_student_subjects  
        SemanticPattern(
            r"(?:show|list|what are)\s+my\s+subjects\b",
            "list_student_subjects",
            "handle_list_student_subjects"
        ),
        
        # NEW: Pass/Fail patterns - ENHANCED with broader matching
        SemanticPattern(
            r"(?:list|show)\s+(?:me\s+)?students\s+who\s+passed\s+(.+)",
            "list_passed_students",
            "handle_list_passed_students"
        ),
        SemanticPattern(
            r"(?:list|show)\s+(?:me\s+)?students\s+who\s+failed\s+(.+)",
            "list_failed_students", 
            "handle_list_failed_students"
        ),
        
        # Subject grade queries
        SemanticPattern(
            r"(?:my |show |get )?(?:grade|score|marks?|result)s?\s+(?:for|in|of)\s+(.+)",
            "get_subject_grade",
            "handle_subject_grade"
        ),
        SemanticPattern(
            r"(?:what|how)(?:'s| is)?\s+my\s+(.+?)\s+(?:grade|score|mark)",
            "get_subject_grade",
            "handle_subject_grade"
        ),
        
        # Student subject listing (PUT BEFORE count/list patterns)
        SemanticPattern(
            r"(?:show|list)\s+(?:all\s+)?subjects?\s+(?:for|of)\s+student\s+(\d+)",
            "list_student_subjects",
            "handle_list_student_subjects"
        ),
        
        # COUNT PATTERNS - PUT THESE FIRST TO MATCH BEFORE GENERIC FILTERS
        SemanticPattern(
            r"(?:count|how many|total)\s+(?:active|currently active|currently enrolled|enrolled|current)\s+students?",
            "count_active_students",
            "handle_count_students"
        ),
        SemanticPattern(
            r"(?:count|how many|total)\s+graduated\s+students?",
            "count_graduated_students",
            "handle_count_students"
        ),
        SemanticPattern(
            r"(?:count|how many|total)\s+(?:all\s+)?students?",
            "count_all_students",
            "handle_count_students"
        ),
        SemanticPattern(
            r"(?:count|how many|total)\s+(?:female|women)\s+students?",
            "count_female_students",
            "handle_count_students"
        ),
        SemanticPattern(
            r"(?:count|how many|total)\s+(?:male|men)\s+students?",
            "count_male_students",
            "handle_count_students"
        ),
        
        # CGPA queries with operators
        SemanticPattern(
            r"students?\s+(?:with\s+)?cgpa\s*([><=])([><=]?)\s*([0-9.]+)",
            "filter_by_cgpa",
            "handle_cgpa_filter"
        ),
        SemanticPattern(
            r"students?\s+(?:with\s+)?cgpa\s+between\s+([0-9.]+)\s+and\s+([0-9.]+)",
            "filter_by_cgpa_range",
            "handle_cgpa_range"
        ),
        
        # LIST PATTERNS (after count patterns) - FIXED TO PRESERVE FILTERS
        SemanticPattern(
            r"(?:list|show)\s+(?:active|enrolled|current)\s+students?",
            "list_active_students",
            "handle_list_students"
        ),
        SemanticPattern(
            r"(?:list|show)\s+(?:all\s+)?students?",
            "list_all_students", 
            "handle_list_students"
        ),
        
        # Cohort queries
        SemanticPattern(
            r"students?\s+(?:from|in)\s+(?:cohort\s+)?([a-zA-Z]+\.?)\s+(\d{4})",
            "filter_by_cohort",
            "handle_cohort_filter"
        ),
        
        # Subject listing
        SemanticPattern(
            r"(?:list|show)\s+(?:all\s+)?subjects?\s+(?:containing|with|like)\s+(.+)",
            "search_subjects",
            "handle_subject_search"
        ),
        
        # Student results by name
        SemanticPattern(
            r"(?:show|list|get|display).*(?:results?|grades?|subjects?)\s+(?:of|for)\s+(.+)",
            "list_student_subjects_by_name",
            "handle_list_student_subjects_by_name"
        ),
        SemanticPattern(
            r"(.+?)(?:'s|s')\s+(?:results?|grades?|subjects?)",
            "list_student_subjects_by_name", 
            "handle_list_student_subjects_by_name"
        ),
    ]
    
    def match(self, query: str, entities: Dict[str, Any]) -> Optional[Tuple[Any, Dict[str, str]]]:
        """Match query against patterns with entity context"""
        
        for pattern in self.PATTERNS:
            match = pattern.pattern.search(query)
            if match:
                # Use safe capture extraction
                captures = _safe_captures(match)
                return pattern, captures
        
        return None

# ============================================================================
# SEMANTIC QUERY PROCESSOR
# ============================================================================

class SemanticQueryProcessor:
    """Query processor with LLM-first approach and semantic understanding"""
    
    def __init__(self):
        # Lazy initialize parent processor to avoid circular imports
        self._enhanced_processor = None
        self.semantic_router = SemanticRouter()
        self.llm = None
        self._initialize()
        self._load_semantic_data()
    
    def _initialize(self):
        """Initialize the processor"""
        try:
            LlamaLLM = get_llama_llm()
            if LlamaLLM:
                self.llm = LlamaLLM()
                logger.info("✅ Semantic Query Processor initialized")
            else:
                logger.warning("⚠️ LLM not available")
        except Exception as e:
            logger.error(f"⚠️ LLM initialization failed: {e}")
    
    @property
    def enhanced_processor(self):
        """Lazy load enhanced processor"""
        if self._enhanced_processor is None:
            EnhancedProcessorClass = get_enhanced_processor()
            if EnhancedProcessorClass:
                self._enhanced_processor = EnhancedProcessorClass()
        return self._enhanced_processor
    
    def _load_semantic_data(self):
        """Load semantic data like subject index"""
        try:
            # Import the file-based loader instead of DB loader
            from backend.constants.subjects_index import load_subjects_from_file, SUBJECT_CANONICAL
            
            # Load subjects from file instead of Cassandra
            load_subjects_from_file()
            
            # Re-import SUBJECT_CANONICAL after loading to get updated list
            from backend.constants.subjects_index import SUBJECT_CANONICAL
            logger.info(f"✅ Loaded {len(SUBJECT_CANONICAL)} subjects for semantic matching")
            
            # Also load active statuses (this can stay as is since it's still using DB)
            get_real_active_statuses()
            
        except Exception as e:
            logger.error(f"Failed to load semantic data: {e}")
    
    async def process_with_semantics(
        self,
        query: str,
        user_id: str,
        user_role: str,
        pre_resolved_entities: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process query with LLM-first approach and semantic fallbacks"""
        
        start_time = time.time()
        
        try:
            # Get required functions
            resolve_entities, canonicalize_plan_steps = get_entity_resolver()
            execute_plan, create_error_response, create_security_error_response, format_response_message, PaginatedResponse = get_shared_functions()
            
            if not all([resolve_entities, canonicalize_plan_steps, execute_plan, create_error_response]):
                return {
                    "success": False,
                    "message": "System initialization error - required modules not available",
                    "data": [],
                    "count": 0,
                    "error": True,
                    "execution_time": time.time() - start_time
                }
            
            # Step 1: Entity resolution (or use pre-resolved)
            if pre_resolved_entities:
                entities = pre_resolved_entities
                logger.info(f"🧠 Using pre-resolved entities: {entities}")
            else:
                entities = resolve_entities(query)
                logger.info(f"🧠 Resolved entities: {entities}")
            
            # SHORT-CIRCUIT FOR DISAMBIGUATION (before LLM/patterns)
            if entities.get("needs_disambiguation"):
                opts = []
                for amb in entities["ambiguous_terms"]:
                    if amb.get("best_programme"):
                        opts.append({
                            "column": "programme",
                            "value": amb["best_programme"],
                            "description": amb["phrase"]
                        })
                    if amb.get("best_subject"):
                        opts.append({
                            "column": "subjectname", 
                            "value": amb["best_subject"],
                            "description": amb["phrase"]
                        })
                
                # 🔧 DEBUG LOGGING: Add requested logging
                logger.info("CLARIFY OPTS %s", opts)
                
                return {
                    "success": True,
                    "intent": "clarify_column",
                    "message": "I found a term that could be a **programme** or a **subject**. Please pick one:",
                    "options": opts,
                    "ambiguous_terms": entities["ambiguous_terms"],
                    "execution_time": time.time() - start_time
                }
            
            # 👉 SHORT-CIRCUIT: Force pass/fail queries to use pattern handlers
            if re.search(r"\bpassed\b|\bfailed\b", query, re.I):
                logger.info("🎯 Pass/Fail query detected, skipping LLM and using pattern handler")
                pattern_result = await self._try_semantic_patterns(query, entities, user_id, user_role, start_time)
                if pattern_result:
                    pattern_result["execution_time"] = time.time() - start_time
                    pattern_result["semantic_entities"] = entities
                    pattern_result["processor_used"] = "semantic_patterns_pass_fail"
                    return pattern_result
            
            # 👉 Try LLM FIRST (before patterns) for non-pass/fail queries
            if self.llm and self.enhanced_processor:
                logger.info("🤖 Trying LLM first...")
                analysis_result = await self.enhanced_processor.analyze_with_llm(query, user_id, user_role)
                
                if analysis_result:
                    logger.info("✅ LLM analysis successful")
                    
                    # FIX 1: Merge the resolver's filters back in
                    analysis_result.setdefault("entities", {}).setdefault("filters", {}).update(
                        entities.get("filters", {})
                    )
                    
                    # POST-PROCESSOR SAFEGUARD: Clean up unwanted LLM additions
                    for step in analysis_result.get("steps", []):
                        # Strip status filter unless user actually asked for it
                        if ("status" in step.get("where", {}) and 
                            "active" not in query.lower() and 
                            "current" not in query.lower() and 
                            "enrolled" not in query.lower()):
                            step["where"].pop("status")
                            logger.debug("Removed unwanted status filter from LLM plan")
                    
                    # Collapse to a single step for simple COUNT queries
                    if (len(analysis_result.get("steps", [])) > 1 and 
                        analysis_result["steps"][0].get("select") == ["COUNT(*)"]):
                        analysis_result["steps"] = [analysis_result["steps"][0]]
                        logger.debug("Collapsed multi-step plan to single COUNT step")
                    
                    # VALIDATION LAYER: Remove unmentioned filters
                    analysis_result = prune_unmentioned_filters(analysis_result, query)
                    
                    # DUPLICATE DETECTION: Remove duplicate steps
                    analysis_result = remove_duplicate_steps(analysis_result)
                    
                    # --- CONVERT COUNT TO LIST IF NEEDED ---
                    if wants_list(query):
                        for step in analysis_result.get("steps", []):
                            if step.get("select") == ["COUNT(*)"]:
                                logger.debug("LLM returned COUNT but user asked for LIST. Converting...")
                                step["select"] = ["id", "name", "programme", "overallcgpa", "cohort", "status", "graduated"]
                                step.setdefault("limit", 100)
                        
                        # Remove any post_aggregation that forces count
                        analysis_result.pop("post_aggregation", None)
                        analysis_result["intent"] = "list_students"
                        logger.info(f"🔄 Converted LLM plan to list_students intent")
                    
                    # One-shot cleanup using centralized canonicalizer
                    entities.update({"user_id": user_id, "user_role": user_role})
                    analysis_result = canonicalize_plan_steps(analysis_result, entities)
                    
                    # 🔧 ENHANCED POST-PROCESSING: Prune again after canonicalization
                    analysis_result = prune_unmentioned_filters(analysis_result, query)
                    analysis_result = remove_duplicate_steps(analysis_result)
                    
                    # 🔧 Remove empty or meaningless steps
                    analysis_result["steps"] = [
                        s for s in analysis_result["steps"] 
                        if s.get("where") not in (None, {}, {"id": {"op": "=", "value": int(user_id) if user_id.isdigit() else user_id}})
                    ]
                    
                    analysis_result["query"] = query
                    analysis_result["start_time"] = start_time
                    
                    logger.info("PLAN ▶ %s", json.dumps(analysis_result, indent=2, default=str))
                    
                    exec_result = await execute_plan(analysis_result, user_id, user_role, self.llm)
                    
                    # 🔧 INJECT COUNT MESSAGES: Add descriptive messages for count results
                    if exec_result.get("message") in (None, "") and exec_result.get("count") is not None:
                        intent = exec_result.get("intent", "")
                        if intent.startswith("count_"):
                            noun = "students"
                            if "female" in intent:
                                noun = "female students"
                            elif "male" in intent:
                                noun = "male students" 
                            elif "graduated" in intent:
                                noun = "graduated students"
                            elif "active" in intent:
                                noun = "currently enrolled students"
                            exec_result["message"] = f"📊 **{exec_result['count']:,}** {noun}"
                    
                    logger.info("RESULT ◀ count=%s, len(data)=%s, intent=%s", 
                              exec_result.get("count"), len(exec_result.get("data", [])), exec_result.get("intent"))
                    
                    exec_result["execution_time"] = time.time() - start_time
                    exec_result["semantic_entities"] = entities
                    exec_result["processor_used"] = "llm_first"
                    return exec_result
                else:
                    logger.info("❌ LLM analysis failed, falling back to patterns")
            
            # Step 2: Try semantic pattern matching (fallback)
            logger.info("🎯 Trying semantic patterns...")
            pattern_result = await self._try_semantic_patterns(
                query, entities, user_id, user_role, start_time
            )
            
            if pattern_result:
                pattern_result["execution_time"] = time.time() - start_time
                pattern_result["semantic_entities"] = entities
                pattern_result["processor_used"] = "semantic_patterns"
                return pattern_result
            
            # Step 3: Semantic fallback
            logger.info("🔄 Using semantic fallback...")
            fallback_result = self._semantic_fallback(
                query, entities, user_id, user_role
            )
            
            if fallback_result:
                fallback_result["query"] = query
                fallback_result["start_time"] = start_time
                
                logger.debug("FINAL FALLBACK PLAN >>> %s", json.dumps(fallback_result, indent=2, default=str))
                
                logger.info("PLAN ▶ %s", json.dumps(fallback_result, indent=2, default=str))
                
                execution_result = await execute_plan(
                    fallback_result, user_id, user_role, self.llm
                )
                
                # 🔧 INJECT COUNT MESSAGES: Add descriptive messages for count results  
                if execution_result.get("message") in (None, "") and execution_result.get("count") is not None:
                    intent = execution_result.get("intent", "")
                    if intent.startswith("count_"):
                        noun = "students"
                        if "female" in intent:
                            noun = "female students"
                        elif "male" in intent:
                            noun = "male students"
                        elif "graduated" in intent:
                            noun = "graduated students"
                        elif "active" in intent:
                            noun = "currently enrolled students"
                        execution_result["message"] = f"📊 **{execution_result['count']:,}** {noun}"
                
                logger.info("RESULT ◀ count=%s, len(data)=%s, intent=%s", 
                          execution_result.get("count"), len(execution_result.get("data", [])), execution_result.get("intent"))
                execution_result["execution_time"] = time.time() - start_time
                execution_result["semantic_entities"] = entities
                execution_result["processor_used"] = "semantic_fallback"
                return execution_result
            
            return create_error_response(
                query,
                "Could not understand your query. Try being more specific about subjects or filters.",
                start_time
            )
            
        except Exception as e:
            logger.error(f"Semantic processing error: {e}")
            return {
                "success": False,
                "message": f"Processing error: {str(e)}",
                "data": [],
                "count": 0,
                "error": True,
                "execution_time": time.time() - start_time
            }
    
    async def _try_semantic_patterns(
        self,
        query: str,
        entities: Dict[str, Any],
        user_id: str,
        user_role: str,
        start_time: float
    ) -> Optional[Dict[str, Any]]:
        """Try semantic pattern matching"""
        
        # Get required functions
        resolve_entities, canonicalize_plan_steps = get_entity_resolver()
        execute_plan, create_error_response, create_security_error_response, format_response_message, PaginatedResponse = get_shared_functions()
        
        if not all([execute_plan, create_error_response, create_security_error_response]):
            return None
        
        match = self.semantic_router.match(query, entities)
        if not match:
            return None
        
        pattern, captures = match
        logger.info(f"🎯 Matched pattern: {pattern.intent} for query: '{query}'")
        
        # --- OVERRIDE: Don't mutate global pattern object ---
        intent = pattern.intent
        handler = pattern.handler
        
        if intent.startswith("count_") and wants_list(query):
            logger.info("🔁 Overriding count intent to list_students due to query phrasing")
            intent = "list_students"
            handler = "handle_list_students"
        elif intent.startswith("list_") and wants_count(query):
            logger.info("🔁 Overriding list intent to count due to query phrasing")
            intent = "count_all_students"
            handler = "handle_count_students"
        
        # Security check for students
        student_allowed_intents = ["get_subject_grade", "list_student_subjects"]
        if user_role == "student" and intent not in student_allowed_intents:
            return create_security_error_response(query, user_role, start_time)
        
        # Build step based on pattern and entities
        if handler == "handle_subject_grade":
            subject = entities.get("subjectname")
            
            if not subject:
                return create_error_response(
                    query,
                    f"Could not identify the subject. Please use the exact subject name.",
                    start_time
                )
            
            uid = _safe_int(user_id)
            steps = [{
                "table": "subjects",
                "select": ["id", "subjectname", "grade", "overallpercentage"],
                "where": {
                    "subjectname": {"op": "=", "value": subject}
                },
                "limit": 10,
                "allow_filtering": True
            }]
            
            # Add ID filter only for valid user IDs
            if uid is not None:
                steps[0]["where"]["id"] = {"op": "=", "value": uid}
            
            plan = {
                "intent": "get_subject_grade",
                "entities": {"subjectname": subject},
                "steps": steps,
                "query": query,
                "start_time": start_time
            }
            
            # Use centralized canonicalizer
            if canonicalize_plan_steps:
                entities.update({"user_id": user_id, "user_role": user_role})
                plan = canonicalize_plan_steps(plan, entities)
            
            logger.debug("FINAL SUBJECT GRADE PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            return await execute_plan(plan, user_id, user_role, self.llm)
            
        elif handler == "handle_list_student_subjects":
            # Handle listing subjects for a specific student
            uid = _safe_int(captures.get("group_1", user_id))  # Use captured student ID or default to current user
            
            step = {
                "table": "subjects",
                "select": ["id", "subjectname", "grade", "overallpercentage", "examyear", "exammonth"],
                "where": {},
                "limit": 200,
                "allow_filtering": True
            }
            
            # Add ID filter only if we have a valid numeric ID
            if uid is not None:
                step["where"]["id"] = {"op": "=", "value": uid}
            
            plan = {
                "intent": "list_student_subjects",
                "entities": {"id": uid} if uid is not None else {},
                "steps": [step],
                "query": query,
                "start_time": start_time
            }
            
            logger.info("📋 Built student subjects plan: %s", plan)
            logger.debug("FINAL STUDENT SUBJECTS PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            
            return await execute_plan(plan, user_id, user_role, self.llm)
            
        elif handler == "handle_list_passed_students":
            # Import subjects index for fuzzy matching
            try:
                from backend.constants.subjects_index import best_subject_match, SUBJECT_LOOKUP
            except ImportError:
                logger.error("Failed to import subjects index for fuzzy matching")
                return create_error_response(
                    query,
                    "Subject matching system not available.",
                    start_time
                )
            
            # 1) Get raw capture from user input
            raw = captures.get("group_1", "").strip()
            
            if not raw:
                return create_error_response(
                    query,
                    "Could not identify the subject name.",
                    start_time
                )
            
            # 2) Use fuzzy matching to find the canonical form
            canon = best_subject_match(raw, threshold=80)
            
            if not canon:
                return create_error_response(
                    query,
                    f"Could not recognize the subject \"{raw}\". Please check the spelling or try a different name.",
                    start_time
                )
            
            # 3) Get the exact DB value (which is the same as canonical - camelCase without spaces)
            db_name = SUBJECT_LOOKUP[canon]["subjectname"]  # This is "ArtificialIntelligence", not "Artificial Intelligence"
            
            logger.info(f"🔍 Fuzzy matched \"{raw}\" → canonical \"{canon}\" → DB value \"{db_name}\"")
            
            # 4) Build your two-step plan using the exact database subjectname
            step0 = {
                "table": "subjects",
                "select": ["id"],
                "where": {
                    "subjectname": {"op": "=", "value": db_name},  # Use camelCase DB value
                    "grade": {"op": "!=", "value": "F"}
                },
                "allow_filtering": True
            }
            
            # Step 1: fetch full student records for those IDs
            step1 = {
                "table": "students",
                "select": ["id", "name", "programme", "overallcgpa", "cohort", "status", "graduated"],
                "where_in_ids_from_step": 0,
                "allow_filtering": True
            }
            
            plan = {
                "intent": "list_passed_students",
                "entities": {"subjectname": db_name, "canonical": canon, "user_input": raw},
                "steps": [step0, step1],
                "query": query,
                "start_time": start_time
            }
            
            logger.info(f"📋 Built passed students plan for DB subject: {db_name}")
            logger.debug("FINAL PASSED STUDENTS PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            
            return await execute_plan(plan, user_id, user_role, self.llm)

        elif handler == "handle_list_failed_students":
            # Import subjects index for fuzzy matching
            try:
                from backend.constants.subjects_index import best_subject_match, SUBJECT_LOOKUP
            except ImportError:
                logger.error("Failed to import subjects index for fuzzy matching")
                return create_error_response(
                    query,
                    "Subject matching system not available.",
                    start_time
                )
            
            # 1) Get raw capture from user input
            raw = captures.get("group_1", "").strip()
            
            if not raw:
                return create_error_response(
                    query,
                    "Could not identify the subject name.",
                    start_time
                )
            
            # 2) Use fuzzy matching to find the canonical form
            canon = best_subject_match(raw, threshold=80)
            
            if not canon:
                return create_error_response(
                    query,
                    f"Could not recognize the subject \"{raw}\". Please check the spelling or try a different name.",
                    start_time
                )
            
            # 3) Get the exact DB value (which is the same as canonical - camelCase without spaces)
            db_name = SUBJECT_LOOKUP[canon]["subjectname"]  # This is "ArtificialIntelligence", not "Artificial Intelligence"
            
            logger.info(f"🔍 Fuzzy matched \"{raw}\" → canonical \"{canon}\" → DB value \"{db_name}\"")
            
            # 4) Build your two-step plan using the exact database subjectname
            step0 = {
                "table": "subjects",
                "select": ["id"],
                "where": {
                    "subjectname": {"op": "=", "value": db_name},  # Use camelCase DB value
                    "grade": {"op": "=", "value": "F"}
                },
                "allow_filtering": True
            }
            
            # Step 1: fetch full student records for those IDs
            step1 = {
                "table": "students",
                "select": ["id", "name", "programme", "overallcgpa", "cohort", "status", "graduated"],
                "where_in_ids_from_step": 0,
                "allow_filtering": True
            }
            
            plan = {
                "intent": "list_failed_students",
                "entities": {"subjectname": db_name, "canonical": canon, "user_input": raw},
                "steps": [step0, step1],
                "query": query,
                "start_time": start_time
            }
            
            logger.info(f"📋 Built failed students plan for DB subject: {db_name}")
            logger.debug("FINAL FAILED STUDENTS PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            
            return await execute_plan(plan, user_id, user_role, self.llm)
            
        elif handler == "handle_cohort_filter":
            step = {"table":"students","select":SELECT_STUDENTS,"where":{},"limit":100,"allow_filtering":True}
            plan = {"intent":"filter_by_cohort","entities":entities,"steps":[step],"query":query,"start_time":start_time}
            if canonicalize_plan_steps:
                entities.update({"user_id":user_id,"user_role":user_role})
                plan = canonicalize_plan_steps(plan, entities)
            return await execute_plan(plan, user_id, user_role, self.llm)
            
        elif handler == "handle_subject_search":
            step = {"table":"subjects","select":SELECT_SUBJECTS,"where":{},"limit":100,"allow_filtering":True}
            plan = {"intent":"search_subjects","entities":entities,"steps":[step],"query":query,"start_time":start_time}
            if canonicalize_plan_steps:
                entities.update({"user_id":user_id,"user_role":user_role})
                plan = canonicalize_plan_steps(plan, entities)
            return await execute_plan(plan, user_id, user_role, self.llm)
            
        elif handler == "handle_cgpa_filter":
            filters = entities.get("filters", {})
            operators = entities.get("operators", {})
            
            if "overallcgpa" not in filters:
                return None
            
            steps = [{
                "table": "students",
                "select": ["id", "name", "overallcgpa", "programme"],
                "where": {
                    "overallcgpa": {"op": operators.get("overallcgpa", ">"), "value": filters["overallcgpa"]}
                },
                "limit": 100,
                "allow_filtering": True
            }]
            
            plan = {
                "intent": "filter_by_cgpa",
                "entities": entities,
                "steps": steps,
                "query": query,
                "start_time": start_time
            }
            
            if canonicalize_plan_steps:
                ctx_entities = {**entities, "user_id": user_id, "user_role": user_role}
                plan = canonicalize_plan_steps(plan, ctx_entities)
            logger.debug("FINAL CGPA FILTER PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            return await execute_plan(plan, user_id, user_role, self.llm)
            
        elif handler == "handle_count_students":
            where = {}
            
            if intent == "count_active_students":
                real_active_statuses = get_real_active_statuses()
                where = {"status": {"op": "IN", "value": real_active_statuses}}
                logger.info(f"Using real active statuses: {real_active_statuses}")
            elif intent == "count_graduated_students":
                where = {"graduated": {"op": "=", "value": True}}
            elif "female" in intent:
                where["gender"] = {"op": "=", "value": "Female"}
            elif "male" in intent:
                where["gender"] = {"op": "=", "value": "Male"}
            elif "all" in intent:
                pass  # No filter for all students
             
            step = {
                "table": "students",
                "select": ["COUNT(*)"],
                "where": where,
                "allow_filtering": True
            }
            
            # Apply entity filters using centralized canonicalizer
            if canonicalize_plan_steps:
                entities.update({"user_id": user_id, "user_role": user_role})
                step = canonicalize_plan_steps({"steps":[step]}, entities)["steps"][0]
            
            steps = [step]
            
            plan = {
                "intent": intent,
                "entities": entities,
                "steps": steps,
                "query": query,
                "start_time": start_time
            }
            logger.info(f"📋 Built count plan with filters: {plan}")
            logger.debug("FINAL COUNT PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            
            # Execute the plan
            result = await execute_plan(plan, user_id, user_role, self.llm)
            
            if result.get("message") in (None, "") and result.get("count") is not None:
                intent = result.get("intent", "")
                if intent.startswith("count_"):
                    noun = "students"
                    if "female" in intent:
                        noun = "female students"
                    elif "male" in intent:
                        noun = "male students"
                    elif "graduated" in intent:
                        noun = "graduated students"
                    elif "active" in intent:
                        noun = "currently enrolled students"
                    result["message"] = f"📊 **{result['count']:,}** {noun}"
            
            # IMPROVED FALLBACK: If count is 0 and we used status filter, try graduated=False
            if (intent == "count_active_students" and 
                result.get("count") == 0 and 
                "status" in plan["steps"][0]["where"]):
                
                logger.info("🔄 Count was 0 with status filter, retrying with graduated=False")
                
                # Retry with graduated filter but preserve other entity filters
                fallback_step = {
                    "table": "students",
                    "select": ["COUNT(*)"],
                    "where": {"graduated": {"op": "=", "value": False}},
                    "allow_filtering": True
                }
                
                # Re-apply entity filters using centralized canonicalizer
                if canonicalize_plan_steps:
                    entities.update({"user_id": user_id, "user_role": user_role})
                    fallback_step = canonicalize_plan_steps({"steps":[fallback_step]}, entities)["steps"][0]
                
                fallback_plan = {
                    "intent": intent,
                    "entities": entities,
                    "steps": [fallback_step],
                    "query": query,
                    "start_time": start_time
                }
                
                result = await execute_plan(fallback_plan, user_id, user_role, self.llm)
                
                # INJECT COUNT MESSAGES: Add descriptive messages for fallback count results
                if result.get("message") in (None, "") and result.get("count") is not None:
                    intent = result.get("intent", "")
                    if intent.startswith("count_"):
                        noun = "students"
                        if "female" in intent:
                            noun = "female students"
                        elif "male" in intent:
                            noun = "male students"
                        elif "graduated" in intent:
                            noun = "graduated students"
                        elif "active" in intent:
                            noun = "currently enrolled students"
                        result["message"] = f"📊 **{result['count']:,}** {noun}"
                
                logger.debug("FALLBACK COUNT RESULT -> %s", result)
            
            return result

        elif handler == "handle_list_students":
            # 🔧 CRITICAL FIX: Build step with entity filters preserved!
            step = {
                "table": "students",
                "select": ["id", "name", "programme", "overallcgpa", "cohort", "status", "graduated"],
                "where": {},
                "limit": 100,
                "allow_filtering": True
            }
            
            # 🔧 FIXED: Use real active status values from database
            if "active" in intent or "enrolled" in intent or "current" in intent:
                real_active_statuses = get_real_active_statuses()
                step["where"]["status"] = {"op": "IN", "value": real_active_statuses}
                logger.info(f"Using real active statuses for list: {real_active_statuses}")
            
            # 🔧 FORCE LIST INTENT (not count)
            plan = {
                "intent": "list_students",  # Hard-set to ensure UI treats as list
                "entities": entities,
                "steps": [step],
                "query": query,
                "start_time": start_time
            }
            
            # Use centralized canonicalizer
            if canonicalize_plan_steps:
                entities.update({"user_id": user_id, "user_role": user_role})
                plan = canonicalize_plan_steps(plan, entities)
            
            logger.info(f"📋 Built list plan with filters: {plan}")
            logger.debug("FINAL LIST PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            
            # Execute the plan directly and return
            result = await execute_plan(plan, user_id, user_role, self.llm)
            
            # 🔧 FALLBACK: If result is empty with status filter, try graduated=False
            if ("active" in intent or "enrolled" in intent or "current" in intent) and len(result.get("data", [])) == 0:
                logger.info(" Empty result with status filter, retrying with graduated=False")
                
                # Retry with graduated filter
                fallback_step = dict(step)
                fallback_step["where"] = dict(step["where"])
                fallback_step["where"]["graduated"] = {"op": "=", "value": False}
                fallback_step["where"].pop("status", None)  # Remove status filter
                
                fallback_plan = {
                    "intent": "list_students",
                    "entities": entities,
                    "steps": [fallback_step],
                    "query": query,
                    "start_time": start_time
                }
                
                result = await execute_plan(fallback_plan, user_id, user_role, self.llm)
                logger.debug("FALLBACK LIST RESULT -> %d rows", len(result.get("data", [])))
            
            return result
            
        elif handler == "handle_list_student_subjects_by_name":
            # Handle looking up student subjects by student name
            name = captures.get("group_1", "").strip()
            
            if not name:
                return create_error_response(
                    query,
                    "Could not identify the student name.",
                    start_time
                )
            
            # Clean up the name - remove common words that might be captured
            name_words = name.split()
            # Remove common trailing words that might get captured
            exclude_words = ['grades', 'results', 'subjects', 'transcript', 'performance']
            cleaned_name_words = [word for word in name_words if word.lower() not in exclude_words]
            cleaned_name = ' '.join(cleaned_name_words).strip()
            
            if not cleaned_name:
                return create_error_response(
                    query,
                    "Could not identify a valid student name.",
                    start_time
                )
            
            logger.info(f"Looking up student subjects for: '{cleaned_name}'")
            
            # Step 0: Look up student ID by name
            step0 = {
                "table": "students", 
                "select": ["id", "name"],
                "where": {
                    "name": {"op": "=", "value": cleaned_name}
                },
                "allow_filtering": True
            }
            
            # Step 1: Fetch their subjects using the ID from step 0
            step1 = {
                "table": "subjects",
                "select": ["id", "subjectname", "grade", "overallpercentage", "examyear", "exammonth"],
                "where_in_ids_from_step": 0,
                "allow_filtering": True
            }
            
            plan = {
                "intent": "list_student_subjects_by_name",
                "entities": {"student_name": cleaned_name},
                "steps": [step0, step1],
                "query": query,
                "start_time": start_time
            }
            
            logger.info(f" Built student lookup plan for: {cleaned_name}")
            logger.debug("FINAL STUDENT NAME LOOKUP PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            
            return await execute_plan(plan, user_id, user_role, self.llm)
            
        else:
            return None
    
    def _semantic_fallback(
        self,
        query: str,
        entities: Dict[str, Any],
        user_id: str,
        user_role: str
    ) -> Optional[Dict[str, Any]]:
        """Semantic-aware fallback when LLM and patterns fail"""
        
        # Get required functions
        resolve_entities, canonicalize_plan_steps = get_entity_resolver()
        
        # 🔧 SPECIAL CASE: "my grades" → list all subjects for user
        if re.search(r"\bmy\s+grades\b", query, re.I):
            uid = _safe_int(user_id)
            step_where = {}
            if uid is not None:
                step_where["id"] = {"op": "=", "value": uid}
                
            return {
                "intent": "list_student_subjects",
                "entities": {"id": uid} if uid is not None else {},
                "steps": [{
                    "table": "subjects",
                    "select": ["id","subjectname","grade","overallpercentage","examyear","exammonth"],
                    "where": step_where,
                    "limit": 200,
                    "allow_filtering": True
                }]
            }
        
        # 🔧 SPECIAL CASE: "my subjects" or "subjects that I take"
        if (re.search(r"\bmy\s+subjects\b", query, re.I) or 
            re.search(r"\b(?:list|show)\s+subjects\s+(?:that\s+)?I\s+(?:take|am taking|am enrolled in|have)\b", query, re.I)):
            uid = _safe_int(user_id)
            step_where = {}
            if uid is not None:
                step_where["id"] = {"op": "=", "value": uid}
                
            return {
                "intent": "list_student_subjects",
                "entities": {"id": uid} if uid is not None else {},
                "steps": [{
                    "table": "subjects",
                    "select": ["id","subjectname","grade","overallpercentage","examyear","exammonth"],
                    "where": step_where,
                    "limit": 200,
                    "allow_filtering": True
                }]
            }
        
        # 🔧 SPECIAL CASE: "my grade for X" → specific subject grade
        m = re.search(r"\bmy\s+grades?\s+for\s+(.+)", query, re.I)
        if m:
            subj = m.group(1).strip()
            uid = _safe_int(user_id)
            step_where = {"subjectname": {"op": "=", "value": subj}}
            if uid is not None:
                step_where["id"] = {"op": "=", "value": uid}
                
            return {
                "intent": "get_subject_grade",
                "entities": {"subjectname": subj},
                "steps": [{
                    "table": "subjects",
                    "select": ["id","subjectname","grade","overallpercentage"],
                    "where": step_where,
                    "limit": 10,
                    "allow_filtering": True
                }]
            }
        
        # Handle clarification scenarios first
        if entities.get("force_programme"):
            # User clarified they meant programme, not subject
            entities.pop("subjectname", None)  # Remove subject interpretation
            entities["table_hint"] = entities.get("table_hint") or "students"
            logger.info("🎯 Forced programme interpretation after clarification")
            
        elif entities.get("force_subject"):
            # User clarified they meant subject, not programme
            entities.get("filters", {}).pop("programme", None)  # Remove programme filter
            entities["table_hint"] = "subjects"
            logger.info("🎯 Forced subject interpretation after clarification")
        
        # If we have a subject name, assume grade query
        if entities.get("subjectname"):
            uid = _safe_int(user_id)
            step_where = {"subjectname": {"op": "=", "value": entities["subjectname"]}}
            if uid is not None:
                step_where["id"] = {"op": "=", "value": uid}
                
            return {
                "intent": "get_subject_grade",
                "entities": entities,
                "steps": [{
                    "table": "subjects",
                    "select": ["id", "subjectname", "grade", "overallpercentage"],
                    "where": step_where,
                    "limit": 10,
                    "allow_filtering": True
                }]
            }
        
        # If we have filters, create a filter query
        if entities.get("filters"):
            table = entities.get("table_hint", "students")
            
            # 🔧 IMPROVED COUNT DETECTION: Check both keywords and query structure
            count_keywords = ["how many", "count", "total", "number of"]
            list_keywords = ["list", "show", "display", "get"]
            
            has_count_keyword = any(keyword in query.lower() for keyword in count_keywords)
            has_list_keyword = any(keyword in query.lower() for keyword in list_keywords)
            
            # Force list if explicit list keyword, otherwise use count detection
            is_count_query = has_count_keyword and not has_list_keyword
            
            # 🔧 FORCE LIST AFTER CLARIFICATION: If user clarified via clicking cards, assume they want to see results
            if entities.get("force_programme") or entities.get("force_subject"):
                is_count_query = False
                logger.info("🔄 Forcing list view after clarification")
            
            steps = [{
                "table": table,
                "select": ["COUNT(*)"] if is_count_query else (SELECT_STUDENTS if table=="students" else SELECT_SUBJECTS),
                "where": {},
                "limit": None if is_count_query else 100,
                "allow_filtering": True
            }]
            
            # Use centralized canonicalizer
            if canonicalize_plan_steps:
                entities.update({"user_id": user_id, "user_role": user_role})
                plan = {
                    "intent": "count_query" if is_count_query else "list_students",
                    "entities": entities,
                    "steps": steps
                }
                plan = canonicalize_plan_steps(plan, entities)
                
                # 🔧 ENHANCED POST-PROCESSING: Apply same fixes as LLM branch
                plan = prune_unmentioned_filters(plan, query)
                plan = remove_duplicate_steps(plan)
                
                # 🔧 Remove empty or meaningless steps
                plan["steps"] = [
                    s for s in plan["steps"] 
                    if s.get("where") not in (None, {}, {"id": {"op": "=", "value": int(user_id) if user_id.isdigit() else user_id}})
                ]
                
                return plan
        
        return None

# ============================================================================
# PUBLIC API
# ============================================================================

# Global processor instance
_semantic_processor = None

def get_semantic_processor():
    """Get global semantic processor instance"""
    global _semantic_processor
    if _semantic_processor is None:
        _semantic_processor = SemanticQueryProcessor()
        logger.info("✅ Global Semantic Query Processor initialized")
    return _semantic_processor

async def process_query(
    query: str,
    user_id: str,
    user_role: str = "admin",
    page: int = 1,
    page_size: int = 100,
    clarification: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Main entry point for semantic query processing with fallback support"""
    
    try:
        processor = get_semantic_processor()
        
        # Get required functions
        resolve_entities, canonicalize_plan_steps = get_entity_resolver()
        execute_plan, create_error_response, create_security_error_response, format_response_message, PaginatedResponse = get_shared_functions()
        
        if not resolve_entities:
            return {
                "success": False,
                "message": "System initialization error - entity resolver not available",
                "data": [],
                "count": 0,
                "error": True,
                "execution_time": 0
            }
        
        # Handle clarification by pre-resolving entities
        pre_resolved_entities = None
        if clarification:
            logger.info(f"🎯 Processing clarification: {clarification}")
            # Run entity resolver once to have a base dict
            entities = resolve_entities(query)
            
            if clarification.get("column") == "programme":
                entities.setdefault("filters", {})["programme"] = clarification["value"]
                entities["force_programme"] = True
            elif clarification.get("column") == "subjectname":
                entities["subjectname"] = clarification["value"]
                entities["force_subject"] = True
            elif clarification.get("type") == "student_selection":
                # Handle student disambiguation
                entities["selected_student_id"] = clarification["student_id"]
                entities["selected_student_name"] = clarification["student_name"]
                entities["force_student_selection"] = True
                logger.info(f"🎯 Student selected: {clarification['student_name']} (ID: {clarification['student_id']})")
            
            # Remove disambiguation flags
            entities.pop("needs_disambiguation", None)
            entities.pop("ambiguous_terms", None)
            
            pre_resolved_entities = entities
            logger.info(f"🔧 Pre-resolved entities after clarification: {pre_resolved_entities}")
        
        # Process query with LLM-first approach
        result = await processor.process_with_semantics(query, user_id, user_role, pre_resolved_entities)
        
        # 🔧 NEW: Try fallback queries if semantic processing failed or returned no results
        if should_try_fallback(result):
            logger.info(f"🔄 Semantic processing returned empty/failed result, trying fallback queries...")
            
            # Get Cassandra session for fallback queries
            get_session = get_cassandra_session()
            if get_session:
                session = get_session()
                fallback_result = await try_fallback_query(session, query, user_id, user_role)
                
                if fallback_result and fallback_result.get("success"):
                    logger.info(f" Fallback query succeeded: {fallback_result.get('intent')}")
                    result = fallback_result
                else:
                    logger.info(" Fallback query also failed or found no matches")
        
        # Apply pagination if requested and PaginatedResponse is available
        if PaginatedResponse and (page > 1 or page_size != 100):
            data = result.get("data", [])
            paginated = PaginatedResponse.paginate(data, page, page_size)
            result["data"] = paginated["data"]
            result["pagination"] = paginated["pagination"]
        
        return result
        
    except Exception as e:
        logger.error(f"Error in process_query: {e}")
        return {
            "success": False,
            "message": f"Processing error: {str(e)}",
            "data": [],
            "count": 0,
            "error": True,
            "execution_time": 0
        }