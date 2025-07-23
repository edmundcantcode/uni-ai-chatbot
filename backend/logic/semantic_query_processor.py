# backend/logic/semantic_query_processor.py
"""
Enhanced query processor with LLM-first approach and semantic fallbacks.
FIXED: Row iteration bug and status value normalization
"""

import asyncio
import time
import json
import re
import sys
from typing import Dict, Any, List, Optional, Tuple
from backend.llm.llama_integration import LlamaLLM
from backend.database.connect_cassandra import get_session
from backend.constants.subjects_index import load_subjects_from_db, SUBJECT_CANONICAL

# CRITICAL: Setup logging first before any other imports
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s:%(lineno)d - %(message)s",
    stream=sys.stdout,
    force=True
)

# FIXED: Use relative imports within the logic package
from .entity_resolver import (
    resolve_entities,
    enhance_step_with_entities, 
    fix_subject_names_in_step,
)
from .step_runner import run_step, get_active_status_values

logger = logging.getLogger(__name__)

# Cache for real status values
_cached_active_statuses = None

# Lazy import functions to avoid circular dependencies
def get_enhanced_processor():
    """Lazy import of EnhancedQueryProcessor to avoid circular imports"""
    from .query_processor import EnhancedQueryProcessor
    return EnhancedQueryProcessor

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

# Get the functions once at module level
execute_plan, create_error_response, create_security_error_response, format_response_message, PaginatedResponse = get_shared_functions()

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_real_active_statuses():
    """Get real active status values from database (with caching)"""
    global _cached_active_statuses
    
    if _cached_active_statuses is None:
        try:
            session = get_session()
            _cached_active_statuses = get_active_status_values(session)
            logger.info(f"✅ Cached active status values: {_cached_active_statuses}")
        except Exception as e:
            logger.warning(f"Could not load active status values: {e}")
            _cached_active_statuses = ["Active", "Enrolled", "Current"]  # Fallback
    
    return _cached_active_statuses

def _safe_captures(m: re.Match) -> Dict[str, str]:
    """Safely extract capture groups from regex match"""
    if not m or m.lastindex is None:
        return {}
    return {f"group_{i}": m.group(i) for i in range(1, m.lastindex + 1)}

# Intent detection keywords and helpers
LIST_WORDS = ("list", "show", "display", "give me", "show me", "retrieve")
COUNT_WORDS = ("count", "how many", "total", "number of")

def wants_list(q: str) -> bool:
    """Check if user wants a list of records (not a count)"""
    ql = q.lower()
    return any(w in ql for w in LIST_WORDS) and not any(w in ql for w in COUNT_WORDS)

def wants_count(q: str) -> bool:
    """Check if user wants a count (not a list)"""
    ql = q.lower()
    return any(w in ql for w in COUNT_WORDS)

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
            self.llm = LlamaLLM()
            logger.info("✅ Semantic Query Processor initialized")
        except Exception as e:
            logger.error(f"⚠️ LLM initialization failed: {e}")
    
    @property
    def enhanced_processor(self):
        """Lazy load enhanced processor"""
        if self._enhanced_processor is None:
            EnhancedProcessorClass = get_enhanced_processor()
            self._enhanced_processor = EnhancedProcessorClass()
        return self._enhanced_processor
    
    def _load_semantic_data(self):
        """Load semantic data like subject index"""
        try:
            session = get_session()
            load_subjects_from_db(session)
            logger.info(f"✅ Loaded {len(SUBJECT_CANONICAL)} subjects for semantic matching")
            
            # Also load active statuses
            get_real_active_statuses()
            
        except Exception as e:
            logger.error(f"Failed to load semantic data: {e}")
    
    async def process_with_semantics(
        self,
        query: str,
        user_id: str,
        user_role: str
    ) -> Dict[str, Any]:
        """Process query with LLM-first approach and semantic fallbacks"""
        
        start_time = time.time()
        
        try:
            # Step 1: Entity resolution (keep)
            entities = resolve_entities(query)
            logger.info(f"🧠 Resolved entities: {entities}")
            
            # 👉 NEW: Try LLM FIRST (before patterns)
            if self.llm:
                logger.info("🤖 Trying LLM first...")
                analysis_result = await self.enhanced_processor.analyze_with_llm(query, user_id, user_role)
                
                if analysis_result:
                    logger.info("✅ LLM analysis successful")
                    
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
                    
                    # Enhance with entities
                    steps = analysis_result.get("steps", [])
                    for i, step in enumerate(steps):
                        # Force allow_filtering for now
                        step.setdefault("allow_filtering", True)
                        step = enhance_step_with_entities(step, entities)
                        step = fix_subject_names_in_step(step)
                        steps[i] = step
                    
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
            return create_error_response(query, str(e), start_time)
    
    async def _try_semantic_patterns(
        self,
        query: str,
        entities: Dict[str, Any],
        user_id: str,
        user_role: str,
        start_time: float
    ) -> Optional[Dict[str, Any]]:
        """Try semantic pattern matching"""
        
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
            intent = "count_students"
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
            
            steps = [{
                "table": "subjects",
                "select": ["id", "subjectname", "grade", "overallpercentage"],
                "where": {
                    "id": {"op": "=", "value": int(user_id)},
                    "subjectname": {"op": "=", "value": subject}
                },
                "limit": 10,
                "allow_filtering": True
            }]
            
            plan = {
                "intent": "get_subject_grade",
                "entities": {"subjectname": subject},
                "steps": steps,
                "query": query,
                "start_time": start_time
            }
            
            logger.debug("FINAL SUBJECT GRADE PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            
        elif handler == "handle_list_student_subjects":
            # NEW: Handle listing subjects for a specific student
            sid = int(captures.get("group_1", user_id))  # Use captured student ID or default to current user
            
            step = {
                "table": "subjects",
                "select": ["id", "subjectname", "grade", "overallpercentage", "examyear", "exammonth"],
                "where": {"id": {"op": "=", "value": sid}},
                "limit": 200,
                "allow_filtering": True
            }
            
            plan = {
                "intent": "list_student_subjects",
                "entities": {"id": sid},
                "steps": [step],
                "query": query,
                "start_time": start_time
            }
            
            logger.info("📋 Built student subjects plan: %s", plan)
            logger.debug("FINAL STUDENT SUBJECTS PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            
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
            
            logger.debug("FINAL CGPA FILTER PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            
        elif handler == "handle_count_students":
            where = {}
            
            # 🔧 FIXED: Use real active status values from database
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
            
            # 🔧 CRITICAL FIX: Apply entity filters to count queries too!
            step = {
                "table": "students",
                "select": ["COUNT(*)"],
                "where": where,
                "allow_filtering": True
            }
            
            # Apply entity filters (programme, cohort, etc.)
            step = enhance_step_with_entities(step, entities)
            step = fix_subject_names_in_step(step)
            
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
            
            # 🔧 INJECT COUNT MESSAGES: Add descriptive messages for count results
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
            
            # 🔧 IMPROVED FALLBACK: If count is 0 and we used status filter, try graduated=False
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
                
                # Re-apply entity filters
                fallback_step = enhance_step_with_entities(fallback_step, entities)
                fallback_step = fix_subject_names_in_step(fallback_step)
                
                fallback_plan = {
                    "intent": intent,
                    "entities": entities,
                    "steps": [fallback_step],
                    "query": query,
                    "start_time": start_time
                }
                
                result = await execute_plan(fallback_plan, user_id, user_role, self.llm)
                
                # 🔧 INJECT COUNT MESSAGES: Add descriptive messages for fallback count results
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
            
            # 🔧 APPLY ALL ENTITY FILTERS (this was missing!)
            step = enhance_step_with_entities(step, entities)
            step = fix_subject_names_in_step(step)
            
            # 🔧 ENSURE NO COUNT(*) SLIPS IN
            if step.get("select") == ["COUNT(*)"]:
                logger.warning("⚠️ COUNT(*) detected in list handler, fixing...")
                step["select"] = ["id", "name", "programme", "overallcgpa", "cohort", "status", "graduated"]
            
            # 🔧 FORCE LIST INTENT (not count)
            plan = {
                "intent": "list_students",  # Hard-set to ensure UI treats as list
                "entities": entities,
                "steps": [step],
                "query": query,
                "start_time": start_time
            }
            
            # 🔧 REMOVE ANY POST_AGGREGATION
            plan.pop("post_aggregation", None)
            
            logger.info(f"📋 Built list plan with filters: {plan}")
            logger.debug("FINAL LIST PLAN >>> %s", json.dumps(plan, indent=2, default=str))
            
            # Execute the plan directly and return
            result = await execute_plan(plan, user_id, user_role, self.llm)
            
            # 🔧 FALLBACK: If result is empty with status filter, try graduated=False
            if ("active" in intent or "enrolled" in intent or "current" in intent) and len(result.get("data", [])) == 0:
                logger.info("🔄 Empty result with status filter, retrying with graduated=False")
                
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
            return {
                "intent": "get_subject_grade",
                "entities": entities,
                "steps": [{
                    "table": "subjects",
                    "select": ["id", "subjectname", "grade", "overallpercentage"],
                    "where": {
                        "id": {"op": "=", "value": int(user_id)},
                        "subjectname": {"op": "=", "value": entities["subjectname"]}
                    },
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
                "select": ["COUNT(*)"] if is_count_query else ["*"],
                "where": {},
                "limit": None if is_count_query else 100,
                "allow_filtering": True
            }]
            
            # Apply entity enhancements
            steps[0] = enhance_step_with_entities(steps[0], entities)
            
            # Add user constraint for students
            if user_role == "student" and table in ["students", "subjects"]:
                steps[0]["where"]["id"] = {"op": "=", "value": int(user_id)}
            
            return {
                "intent": "count_query" if is_count_query else "list_students",
                "entities": entities,
                "steps": steps
            }
        
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
    page_size: int = 100
) -> Dict[str, Any]:
    """Main entry point for semantic query processing"""
    
    processor = get_semantic_processor()
    
    # Process query with LLM-first approach
    result = await processor.process_with_semantics(query, user_id, user_role)
    
    # Apply pagination if requested
    if page > 1 or page_size != 100:
        data = result.get("data", [])
        paginated = PaginatedResponse.paginate(data, page, page_size)
        result["data"] = paginated["data"]
        result["pagination"] = paginated["pagination"]
    
    return result