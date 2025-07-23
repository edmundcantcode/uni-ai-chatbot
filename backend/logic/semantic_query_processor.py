# backend/logic/semantic_query_processor.py
"""
Enhanced query processor with LLM-first approach and semantic fallbacks.
"""

import asyncio
import time
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from backend.llm.llama_integration import LlamaLLM
from backend.database.connect_cassandra import get_session
from backend.constants.subjects_index import load_subjects_from_db, SUBJECT_CANONICAL

# FIXED: Use relative imports within the logic package
from .entity_resolver import (
    resolve_entities,
    enhance_step_with_entities, 
    fix_subject_names_in_step,
)
from .step_runner import run_step
import logging

logger = logging.getLogger(__name__)

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

def _safe_captures(m: re.Match) -> Dict[str, str]:
    """Safely extract capture groups from regex match"""
    if not m or m.lastindex is None:
        return {}
    return {f"group_{i}": m.group(i) for i in range(1, m.lastindex + 1)}

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
        
        # LIST PATTERNS (after count patterns)
        SemanticPattern(
            r"(?:list|show)\s+(?:active|enrolled|current)\s+students?",
            "list_active_students",
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
                    
                    # Enhance with entities just in case
                    steps = analysis_result.get("steps", [])
                    for i, step in enumerate(steps):
                        # Force allow_filtering for now
                        step.setdefault("allow_filtering", True)
                        step = enhance_step_with_entities(step, entities)
                        step = fix_subject_names_in_step(step)
                        steps[i] = step
                    
                    analysis_result["query"] = query
                    analysis_result["start_time"] = start_time
                    
                    exec_result = await execute_plan(analysis_result, user_id, user_role, self.llm)
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
                
                execution_result = await execute_plan(
                    fallback_result, user_id, user_role, self.llm
                )
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
        
        # Security check for students
        student_allowed_intents = ["get_subject_grade"]
        if user_role == "student" and pattern.intent not in student_allowed_intents:
            return create_security_error_response(query, user_role, start_time)
        
        # Build step based on pattern and entities
        if pattern.handler == "handle_subject_grade":
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
            
        elif pattern.handler == "handle_cgpa_filter":
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
            
        elif pattern.handler == "handle_count_students":
            where = {}
            
            # FIXED: Use status column for active students, graduated for completed
            ACTIVE_STATUSES = ["Active", "Enrolled", "Current"]
            
            if pattern.intent == "count_active_students":
                where = {"status": {"op": "IN", "value": ACTIVE_STATUSES}}
            elif pattern.intent == "count_graduated_students":
                where = {"graduated": {"op": "=", "value": True}}
            elif "female" in pattern.intent:
                where["gender"] = {"op": "=", "value": "Female"}
            elif "male" in pattern.intent:
                where["gender"] = {"op": "=", "value": "Male"}
            elif "all" in pattern.intent:
                pass  # No filter for all students
            
            steps = [{
                "table": "students",
                "select": ["COUNT(*)"],
                "where": where,
                "allow_filtering": True
            }]
            
            plan = {
                "intent": pattern.intent,
                "entities": entities,
                "steps": steps,
                "query": query,
                "start_time": start_time
            }
            logger.info(f"📋 Built count plan: {plan}")
            
            # Execute the plan
            result = await execute_plan(plan, user_id, user_role, self.llm)
            
            # FALLBACK: If count is 0 and we used status filter, retry with graduated=False
            if (pattern.intent == "count_active_students" and 
                result.get("count") == 0 and 
                "status" in plan["steps"][0]["where"]):
                
                logger.info("🔄 Count was 0 with status filter, retrying with graduated=False")
                
                # Retry with graduated filter
                fallback_plan = {
                    "intent": pattern.intent,
                    "entities": entities,
                    "steps": [{
                        "table": "students",
                        "select": ["COUNT(*)"],
                        "where": {"graduated": {"op": "=", "value": False}},
                        "allow_filtering": True
                    }],
                    "query": query,
                    "start_time": start_time
                }
                
                result = await execute_plan(fallback_plan, user_id, user_role, self.llm)
                logger.debug(f"FALLBACK COUNT RESULT -> {result}")
            
            return result

        elif pattern.handler == "handle_list_students":
            where = {}
            
            # Handle active student listing using status
            ACTIVE_STATUSES = ["Active", "Enrolled", "Current"]
            
            if "active" in pattern.intent or "enrolled" in pattern.intent or "current" in pattern.intent:
                where["status"] = {"op": "IN", "value": ACTIVE_STATUSES}
            
            steps = [{
                "table": "students",
                "select": ["id", "name", "programme", "overallcgpa", "status"],
                "where": where,
                "limit": 100,
                "allow_filtering": True
            }]
            
            plan = {
                "intent": pattern.intent,
                "entities": entities,
                "steps": steps,
                "query": query,
                "start_time": start_time
            }
            
            # Execute the plan
            result = await execute_plan(plan, user_id, user_role, self.llm)
            
            # FALLBACK: If no results with status filter, retry with graduated=False
            if ("active" in pattern.intent and 
                result.get("count", len(result.get("data", []))) == 0 and 
                "status" in plan["steps"][0]["where"]):
                
                logger.info("🔄 No results with status filter, retrying with graduated=False")
                
                # Retry with graduated filter
                fallback_plan = {
                    "intent": pattern.intent,
                    "entities": entities,
                    "steps": [{
                        "table": "students",
                        "select": ["id", "name", "programme", "overallcgpa", "graduated"],
                        "where": {"graduated": {"op": "=", "value": False}},
                        "limit": 100,
                        "allow_filtering": True
                    }],
                    "query": query,
                    "start_time": start_time
                }
                
                result = await execute_plan(fallback_plan, user_id, user_role, self.llm)
                logger.debug(f"FALLBACK LIST RESULT -> count: {len(result.get('data', []))}")
            
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
            
            # SAFETY NET: Check if this should be a count query
            is_count_query = ("how many" in query.lower() or 
                            "count" in query.lower() or 
                            "total" in query.lower())
            
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
                "intent": "count_query" if is_count_query else "filter_query",
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