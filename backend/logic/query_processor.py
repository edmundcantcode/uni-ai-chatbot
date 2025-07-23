import asyncio
import time
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from backend.llm.llama_integration import LlamaLLM
from backend.database.connect_cassandra import get_session
from backend.constants.schema_columns import STUDENT_COLUMNS, SUBJECT_COLUMNS, COLUMN_DESCRIPTIONS
from backend.logic.prompt_generator import get_analysis_prompt, get_response_prompt
from backend.logic.step_runner import run_step, validate_step, QueryOperator
import statistics
from dataclasses import dataclass
from enum import Enum
from backend.logic.core_executor import (
    execute_plan,
    create_error_response,
    format_response_message,
    create_help_response,
    PaginatedResponse
)
import logging

logger = logging.getLogger(__name__)

@dataclass
class IntentPattern:
    """Intent pattern with regex and handler"""
    pattern: str
    intent: str
    role: str  # "student", "admin", "any"
    handler: str  # Handler function name
    capture_groups: List[str] = None

class IntentRouter:
    """Improved intent routing with regex patterns"""
    
    PATTERNS = [
        # Student patterns
        IntentPattern(r"(?:what is |show |get )?my cgpa", "get_student_cgpa", "student", "handle_student_cgpa"),
        IntentPattern(r"(?:show |list |get )?my grades?", "get_student_grades", "student", "handle_student_grades"),
        IntentPattern(r"my (?:graduation )?status|am i graduated", "get_student_status", "student", "handle_student_status"),
        
        # Admin count patterns (specific first)
        IntentPattern(r"(?:count|how many) (?:active|currently active) students?", "count_active_students", "admin", "handle_count_students"),
        IntentPattern(r"(?:count|how many) graduated students?", "count_graduated_students", "admin", "handle_count_students"),
        IntentPattern(r"(?:count|how many) female students?", "count_female_students", "admin", "handle_count_students"),
        IntentPattern(r"(?:count|how many) male students?", "count_male_students", "admin", "handle_count_students"),
        IntentPattern(r"(?:count|how many) students? (?:from|in) (\w+)", "count_students_by_country", "admin", "handle_count_students", ["country"]),
        IntentPattern(r"(?:count|how many) students?$", "count_all_students", "admin", "handle_count_students"),
        
        # Admin filter patterns with operators
        IntentPattern(r"students? (?:with |having )?cgpa\s*>\s*([0-9.]+)", "students_cgpa_gt", "admin", "handle_students_filter", ["cgpa"]),
        IntentPattern(r"students? (?:with |having )?cgpa\s*>=\s*([0-9.]+)", "students_cgpa_gte", "admin", "handle_students_filter", ["cgpa"]),
        IntentPattern(r"students? (?:with |having )?cgpa\s*<\s*([0-9.]+)", "students_cgpa_lt", "admin", "handle_students_filter", ["cgpa"]),
        IntentPattern(r"students? (?:with |having )?cgpa\s*between\s*([0-9.]+)\s*and\s*([0-9.]+)", "students_cgpa_between", "admin", "handle_students_filter", ["cgpa_min", "cgpa_max"]),
        
        # List patterns
        IntentPattern(r"(?:list|show) all students?", "list_all_students", "admin", "handle_list_students"),
        IntentPattern(r"(?:list|show) all subjects?", "list_all_subjects", "admin", "handle_list_subjects"),
        
        # Help patterns
        IntentPattern(r"help|what can you do|commands", "help", "any", "handle_help"),
    ]
    
    @classmethod
    def match(cls, query: str, user_role: str) -> Optional[Tuple[IntentPattern, Dict[str, str]]]:
        """Match query against patterns and extract captures"""
        query_clean = re.sub(r'[^\w\s<>=]', ' ', query.lower()).strip()
        
        for pattern in cls.PATTERNS:
            if pattern.role != "any" and pattern.role != user_role:
                continue
                
            match = re.search(pattern.pattern, query_clean)
            if match:
                captures = {}
                if pattern.capture_groups:
                    for i, group_name in enumerate(pattern.capture_groups):
                        captures[group_name] = match.group(i + 1)
                return pattern, captures
        
        return None

# ============================================================================
# ENHANCED JSON VALIDATION
# ============================================================================

class StepSchema:
    """Validate step structure with Pydantic-like validation"""
    
    @staticmethod
    def validate_where_spec(spec: Any, column: str) -> List[str]:
        """Validate a where clause specification"""
        errors = []
        
        if isinstance(spec, dict):
            if "op" not in spec:
                errors.append(f"Missing 'op' in where clause for {column}")
            if "value" not in spec:
                errors.append(f"Missing 'value' in where clause for {column}")
            
            op = spec.get("op", "").upper()
            if op == "BETWEEN":
                val = spec.get("value")
                if not isinstance(val, list) or len(val) != 2:
                    errors.append(f"BETWEEN requires 2 values for {column}")
            elif op == "IN":
                val = spec.get("value")
                if not isinstance(val, list):
                    errors.append(f"IN requires a list for {column}")
        
        return errors
    
    @classmethod
    def validate_step(cls, step: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate complete step structure"""
        errors = []
        
        # Required fields
        if "table" not in step:
            errors.append("Missing required field: table")
        
        # Validate where clause
        where = step.get("where", {})
        for col, spec in where.items():
            errors.extend(cls.validate_where_spec(spec, col))
        
        # Validate select
        select = step.get("select", [])
        if select and not isinstance(select, list):
            errors.append("'select' must be a list")
        
        # Remove invalid fields
        if "id" in where and where["id"] == "admin":
            errors.append("Invalid ID 'admin' in where clause")
        
        return len(errors) == 0, errors

# ============================================================================
# ENHANCED QUERY PROCESSOR
# ============================================================================

class EnhancedQueryProcessor:
    """Query processor with all improvements"""
    
    def __init__(self):
        self.llm = None
        self.intent_router = IntentRouter()
        self._initialize()
    
    def _initialize(self):
        """Initialize the processor"""
        try:
            self.llm = LlamaLLM()
            logger.info("✅ Enhanced Query Processor initialized")
        except Exception as e:
            logger.error(f"⚠️ LLM initialization failed: {e}")
    
    async def analyze_with_llm(self, query: str, user_id: str, user_role: str, retry_count: int = 2) -> Dict[str, Any]:
        """Analyze query with LLM, with retry on validation failure"""
        
        for attempt in range(retry_count):
            # Generate prompt
            prompt = self._get_enhanced_analysis_prompt(query, user_id, user_role)
            
            try:
                # Get LLM response
                llm_raw = await self.llm.generate_response(prompt, f"{user_role}_analysis_{user_id}")
                
                # Extract JSON
                result = self._extract_json_robust(llm_raw)
                if not result:
                    logger.warning(f"Failed to extract JSON on attempt {attempt + 1}")
                    continue
                
                # Validate and clean result
                cleaned_result = self._validate_and_clean_result(result, user_role, user_id)
                
                # Validate steps
                all_valid = True
                for step in cleaned_result.get("steps", []):
                    valid, errors = StepSchema.validate_step(step)
                    if not valid:
                        logger.warning(f"Step validation failed: {errors}")
                        all_valid = False
                        break
                
                if all_valid:
                    return cleaned_result
                
                # If validation failed and we have retries left, try again with error feedback
                if attempt < retry_count - 1:
                    error_prompt = f"Your previous response had validation errors: {errors}. Please provide a corrected JSON response."
                    prompt = prompt + "\n\n" + error_prompt
                    
            except Exception as e:
                logger.error(f"LLM analysis failed on attempt {attempt + 1}: {e}")
        
        # All attempts failed
        return None
    
    def _get_enhanced_analysis_prompt(self, query: str, user_id: str, user_role: str) -> str:
        """Enhanced prompt with operator schema"""
        base_prompt = get_analysis_prompt(query, user_id, user_role)
        
        # Add operator schema documentation
        operator_docs = """
IMPORTANT: Use the new operator schema for WHERE clauses:

{
  "where": {
    "column_name": {"op": "OPERATOR", "value": VALUE}
  }
}

Supported operators:
- "=": Equality (default)
- ">", ">=", "<", "<=": Comparisons
- "!=": Not equal
- "IN": Match any value in list, e.g., {"op": "IN", "value": ["A", "B", "C"]}
- "BETWEEN": Range query, e.g., {"op": "BETWEEN", "value": [1.0, 3.0]}
- "CONTAINS": Substring search (will use Python filtering)
- "LIKE": Pattern matching with % wildcards (will use Python filtering)

Examples:
- Students with CGPA > 3.0: {"overallcgpa": {"op": ">", "value": 3.0}}
- Students in CS or IT: {"programme": {"op": "IN", "value": ["Computer Science", "Information Technology"]}}
- Subjects containing "Math": {"subjectname": {"op": "CONTAINS", "value": "Math"}}

NEVER include user_id or "admin" as values in WHERE clauses.
Always return valid JSON only, no explanations.
"""
        
        return base_prompt + "\n\n" + operator_docs
    
    def _extract_json_robust(self, text: str) -> Optional[Dict[str, Any]]:
        """Robust JSON extraction with multiple methods"""
        
        # Method 1: Find complete JSON blocks
        json_pattern = r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}'
        matches = list(re.finditer(json_pattern, text, re.DOTALL))
        
        # Try matches from longest to shortest
        matches.sort(key=lambda m: len(m.group(0)), reverse=True)
        
        for match in matches[:5]:  # Try top 5 candidates
            json_str = match.group(0)
            try:
                result = json.loads(json_str)
                if isinstance(result, dict) and "steps" in result:
                    logger.debug("✅ JSON extracted successfully")
                    return result
            except json.JSONDecodeError:
                continue
        
        # Method 2: Manual extraction with brace counting
        brace_count = 0
        start_pos = None
        
        for i, char in enumerate(text):
            if char == '{':
                if start_pos is None:
                    start_pos = i
                brace_count += 1
            elif char == '}' and start_pos is not None:
                brace_count -= 1
                if brace_count == 0:
                    json_str = text[start_pos:i+1]
                    try:
                        result = json.loads(json_str)
                        if isinstance(result, dict):
                            logger.debug("✅ JSON extracted using brace counting")
                            return result
                    except json.JSONDecodeError:
                        pass
                    start_pos = None
        
        logger.error("❌ Failed to extract valid JSON")
        return None
    
    def _validate_and_clean_result(self, result: Dict[str, Any], user_role: str, user_id: str) -> Dict[str, Any]:
        """Clean and validate LLM result"""
        
        # Remove admin ID from where clauses
        if user_role == "admin":
            for step in result.get("steps", []):
                where = step.get("where", {})
                if "id" in where and where["id"] == "admin":
                    del where["id"]
        
        # Ensure student constraints
        if user_role == "student":
            for step in result.get("steps", []):
                table = step.get("table", "")
                if table in ["students", "subjects"]:
                    where = step.get("where", {})
                    where["id"] = {"op": "=", "value": int(user_id)}
                    step["where"] = where
        
        return result

# HANDLER FUNCTIONS

async def handle_enhanced_query(
    query: str,
    user_id: str,
    user_role: str = "admin",
    session_id: str = None
) -> Dict[str, Any]:
    """Enhanced query handler with all improvements"""
    
    start_time = time.time()
    processor = EnhancedQueryProcessor()
    
    try:
        logger.info(f"🔍 Processing query: '{query}' for user {user_id} ({user_role})")
        
        # Try pattern matching first
        pattern_match = processor.intent_router.match(query, user_role)
        if pattern_match:
            pattern, captures = pattern_match
            logger.info(f"✅ Matched pattern: {pattern.intent}")
            
            # Execute pattern handler
            handler_result = await execute_pattern_handler(
                pattern, captures, query, user_id, user_role, processor.llm
            )
            
            if handler_result:
                handler_result["execution_time"] = time.time() - start_time
                return handler_result
        
        # Fall back to LLM analysis
        if not processor.llm:
            return create_error_response(query, "LLM not available", start_time)
        
        # Analyze with LLM
        analysis_result = await processor.analyze_with_llm(query, user_id, user_role)
        
        if not analysis_result:
            # Use fallback planner
            logger.info("🔄 Using fallback planner...")
            analysis_result = create_fallback_plan(query, user_role, user_id)
            
            if not analysis_result:
                return create_error_response(
                    query, 
                    "Could not understand your query. Try: 'my grades' or 'count students'", 
                    start_time
                )
        
        # Execute plan
        execution_result = await execute_plan(
            analysis_result, user_id, user_role, processor.llm
        )
        
        execution_result["execution_time"] = time.time() - start_time
        return execution_result
        
    except Exception as e:
        logger.error(f"Query processing error: {e}")
        return create_error_response(query, f"System error: {str(e)}", start_time)

async def execute_pattern_handler(
    pattern: IntentPattern,
    captures: Dict[str, str],
    query: str,
    user_id: str,
    user_role: str,
    llm: Optional[LlamaLLM] = None
) -> Optional[Dict[str, Any]]:
    """Execute a pattern handler"""
    
    session = get_session()
    
    # Build step based on pattern
    if pattern.handler == "handle_student_cgpa":
        steps = [{
            "table": "students",
            "select": ["id", "name", "overallcgpa"],
            "where": {"id": {"op": "=", "value": int(user_id)}},
            "limit": 1,
            "allow_filtering": True
        }]
        
    elif pattern.handler == "handle_student_grades":
        steps = [{
            "table": "subjects",
            "select": ["id", "subjectname", "grade", "overallpercentage"],
            "where": {"id": {"op": "=", "value": int(user_id)}},
            "limit": 100,
            "allow_filtering": True
        }]
        
        # UPDATED: Better handling for active students
        if "active" in pattern.intent or "currently_active" in pattern.intent:
            # Multiple filters for active students
            where["graduated"] = {"op": "=", "value": False}  # Only if graduated column exists
            where["status"] = {"op": "IN", "value": ["Active", "Enrolled", "Current"]}
            
        elif "graduated" in pattern.intent:
            where["graduated"] = {"op": "=", "value": True}
            where["status"] = {"op": "IN", "value": ["Graduated", "Completed"]}
            
        elif "female" in pattern.intent:
            where["gender"] = {"op": "=", "value": "Female"}
            
        elif "male" in pattern.intent:
            where["gender"] = {"op": "=", "value": "Male"}
            
        elif "country" in captures:
            where["country"] = {"op": "=", "value": captures["country"].title()}
        
        steps = [{
            "table": "students",
            "select": ["COUNT(*)"],
            "where": where,
            "allow_filtering": True
        }]
        
    elif pattern.handler == "handle_students_filter":
        where = {}
        
        if "cgpa_gt" in pattern.intent:
            where["overallcgpa"] = {"op": ">", "value": float(captures["cgpa"])}
        elif "cgpa_gte" in pattern.intent:
            where["overallcgpa"] = {"op": ">=", "value": float(captures["cgpa"])}
        elif "cgpa_lt" in pattern.intent:
            where["overallcgpa"] = {"op": "<", "value": float(captures["cgpa"])}
        elif "cgpa_between" in pattern.intent:
            where["overallcgpa"] = {"op": "BETWEEN", "value": [float(captures["cgpa_min"]), float(captures["cgpa_max"])]}
        
        steps = [{
            "table": "students",
            "select": ["id", "name", "overallcgpa", "programme"],
            "where": where,
            "limit": 100,
            "allow_filtering": True
        }]
        
    elif pattern.handler == "handle_list_students":
        steps = [{
            "table": "students",
            "select": ["id", "name", "programme", "overallcgpa", "status"],
            "where": {},
            "limit": 100,
            "allow_filtering": True
        }]
        
    elif pattern.handler == "handle_list_subjects":
        steps = [{
            "table": "subjects",
            "select": ["id", "subjectname", "grade", "examyear", "exammonth"],
            "where": {},
            "limit": 100,
            "allow_filtering": True
        }]
        
    elif pattern.handler == "handle_help":
        # Return help message without executing steps
        return create_help_response(query, user_role)
        
    else:
        return None
    
    plan = {
        "intent": pattern.intent,
        "entities": captures,
        "steps": steps,
        "query": query,
        "start_time": time.time()
    }
    
    return await execute_plan(plan, user_id, user_role, llm)

async def execute_plan(
    plan: Dict[str, Any],
    user_id: str,
    user_role: str,
    llm: Optional[LlamaLLM] = None
) -> Dict[str, Any]:
    """Execute a query plan with enhanced step runner"""
    
    session = get_session()
    steps = plan.get("steps", [])
    step_results = []
    all_metadata = []
    
    for idx, step in enumerate(steps):
        try:
            # Get ID pool from previous step if needed
            id_pool = None
            if step.get("where_in_ids_from_step") is not None:
                src_idx = step["where_in_ids_from_step"]
                if 0 <= src_idx < len(step_results):
                    id_pool = [r["id"] for r in step_results[src_idx] if "id" in r]
            
            # Execute step
            rows = run_step(session, step, id_pool)
            
            # Apply role-based filtering
            if user_role == "student":
                table = step.get("table", "")
                if table in ["students", "subjects"]:
                    # Filter columns based on permissions
                    allowed_cols = {
                        "students": ["id", "overallcgpa", "status", "graduated", "awardclassification", "programme"],
                        "subjects": ["id", "subjectname", "grade", "overallpercentage"]
                    }
                    if table in allowed_cols:
                        filtered_rows = []
                        for row in rows:
                            filtered_row = {k: v for k, v in row.items() if k in allowed_cols[table]}
                            filtered_rows.append(filtered_row)
                        rows = filtered_rows
            
            step_results.append(rows)
            logger.info(f"✅ Step {idx} ({step.get('table', 'unknown')}) -> {len(rows)} rows")
            
        except Exception as e:
            logger.error(f"❌ Step {idx} execution error: {e}")
            raise
    
    # Get final data
    data = step_results[-1] if step_results else []
    
    # Apply post-aggregation if needed
    post_agg = plan.get("post_aggregation")
    if post_agg and user_role == "admin":
        data = apply_post_aggregation(data, post_agg)
    
    # Generate response message
    try:
        if llm:
            response_prompt = get_response_prompt(
                plan.get("query", ""),
                plan.get("intent", "unknown"),
                data,
                user_role
            )
            message = await llm.generate_response(
                response_prompt,
                f"{user_role}_response_{user_id}"
            )
        else:
            message = format_response_message(plan.get("intent"), data, user_role)
    except:
        message = format_response_message(plan.get("intent"), data, user_role)
    
    return {
        "success": True,
        "message": message,
        "data": data,
        "count": len(data),
        "error": False,
        "query": plan.get("query", ""),
        "intent": plan.get("intent", "processed"),
        "entities": plan.get("entities", {}),
        "metadata": all_metadata,
        "user_id": user_id,
        "security_level": user_role
    }

def apply_post_aggregation(data: List[Dict[str, Any]], post_agg: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Apply post-processing aggregations"""
    
    agg_type = post_agg.get("type")
    field = post_agg.get("field")
    
    if agg_type == "count":
        return [{"count": len(data)}]
    
    elif agg_type == "average" and field:
        values = [float(row[field]) for row in data if row.get(field) is not None]
        if values:
            return [{"average": statistics.mean(values), "count": len(values)}]
        return [{"average": 0, "count": 0}]
    
    elif agg_type == "sum" and field:
        total = sum(float(row[field]) for row in data if row.get(field) is not None)
        return [{"sum": total}]
    
    elif agg_type == "min" and field:
        values = [float(row[field]) for row in data if row.get(field) is not None]
        if values:
            return [{"min": min(values)}]
        return [{"min": None}]
    
    elif agg_type == "max" and field:
        values = [float(row[field]) for row in data if row.get(field) is not None]
        if values:
            return [{"max": max(values)}]
        return [{"max": None}]
    
    elif agg_type == "group_by" and field:
        groups = {}
        for row in data:
            key = row.get(field)
            if key not in groups:
                groups[key] = []
            groups[key].append(row)
        
        result = []
        for key, group_rows in groups.items():
            result.append({
                field: key,
                "count": len(group_rows),
                "_rows": group_rows[:10]  # Include sample rows
            })
        return result
    
    elif agg_type == "top_n":
        n = post_agg.get("n", 10)
        if field:
            sorted_data = sorted(
                [r for r in data if r.get(field) is not None],
                key=lambda x: float(x[field]),
                reverse=True
            )
            return sorted_data[:n]
    
    return data

def create_fallback_plan(query: str, user_role: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Create a fallback plan when LLM fails"""
    
    q = query.lower().strip()
    
    # Remove punctuation for better matching
    q_clean = re.sub(r'[^\w\s]', ' ', q)
    
    # Student queries
    if user_role == "student":
        if any(phrase in q_clean for phrase in ["my cgpa", "what is my cgpa"]):
            return {
                "intent": "get_student_cgpa",
                "steps": [{
                    "table": "students",
                    "select": ["id", "name", "overallcgpa"],
                    "where": {"id": {"op": "=", "value": int(user_id)}},
                    "limit": 1,
                    "allow_filtering": True
                }]
            }
        
        elif any(phrase in q_clean for phrase in ["my grades", "my results"]):
            return {
                "intent": "get_student_grades",
                "steps": [{
                    "table": "subjects",
                    "select": ["id", "subjectname", "grade", "overallpercentage"],
                    "where": {"id": {"op": "=", "value": int(user_id)}},
                    "limit": 100,
                    "allow_filtering": True
                }]
            }
    
    # Admin queries
    elif user_role == "admin":
        if "count" in q_clean and "students" in q_clean:
            where = {}
            
            if "active" in q_clean:
                where["graduated"] = {"op": "=", "value": False}
            elif "graduated" in q_clean:
                where["graduated"] = {"op": "=", "value": True}
            
            return {
                "intent": "count_students",
                "steps": [{
                    "table": "students",
                    "select": ["COUNT(*)"],
                    "where": where,
                    "allow_filtering": True
                }]
            }
    
    return None

def format_response_message(intent: str, data: List[Dict[str, Any]], user_role: str) -> str:
    """Format a response message based on intent and data"""
    
    role_prefix = "🔒 " if user_role == "student" else "👨‍💼 "
    
    if not data:
        return f"{role_prefix}No results found for your query."
    
    # Extract count from aggregation results
    if data and "count" in data[0]:
        count = data[0]["count"]
    elif data and "system.count(*)" in data[0]:
        count = data[0]["system.count(*)"]
    else:
        count = len(data)
    
    # Format based on intent
    if "count" in intent:
        return f"{role_prefix}**Count Result**\n\n✅ Found **{count:,}** matching records."
    
    elif "cgpa" in intent and user_role == "student":
        if data and "overallcgpa" in data[0]:
            cgpa = data[0]["overallcgpa"]
            return f"{role_prefix}**Your CGPA**\n\n📊 Your Overall CGPA: **{cgpa}**"
    
    elif "grades" in intent and user_role == "student":
        return f"{role_prefix}**Your Grades**\n\n✅ Found **{len(data)}** grade records."
    
    elif "list" in intent:
        return f"{role_prefix}**List Results**\n\n✅ Showing **{len(data)}** records."
    
    return f"{role_prefix}Found **{len(data)}** results."

def create_help_response(query: str, user_role: str) -> Dict[str, Any]:
    """Create help response"""
    
    if user_role == "student":
        suggestions = [
            "What is my CGPA?",
            "Show my grades",
            "What is my graduation status?"
        ]
    else:
        suggestions = [
            "Count all students",
            "Count active students",
            "Students with CGPA > 3.0",
            "List all subjects",
            "Students with CGPA between 2.0 and 3.0"
        ]
    
    message = f"**Available Commands**\n\nHere are some things you can ask:\n\n" + \
              "\n".join(f"• {s}" for s in suggestions)
    
    return {
        "success": True,
        "message": message,
        "data": [],
        "count": 0,
        "error": False,
        "query": query,
        "intent": "help"
    }

def create_error_response(query: str, error: str, start_time: float) -> Dict[str, Any]:
    """Create error response"""
    
    return {
        "success": False,
        "message": f"❌ **Error**\n\n{error}",
        "data": [],
        "count": 0,
        "error": True,
        "query": query,
        "intent": "error",
        "execution_time": time.time() - start_time
    }

# PAGINATION SUPPORT

class PaginatedResponse:
    """Handle paginated responses"""
    
    @staticmethod
    def paginate(data: List[Dict[str, Any]], page: int = 1, page_size: int = 100) -> Dict[str, Any]:
        """Apply pagination to results"""
        
        total_count = len(data)
        total_pages = (total_count + page_size - 1) // page_size
        
        # Calculate slice
        start = (page - 1) * page_size
        end = start + page_size
        page_data = data[start:end]
        
        return {
            "data": page_data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1
            }
        }


# MAIN ENTRY POINT

# Global processor instance
_processor = None

def get_processor():
    global _processor
    if _processor is None:
        _processor = EnhancedQueryProcessor()
    return _processor

async def process_query(
    query: str,
    user_id: str,
    user_role: str = "admin",
    page: int = 1,
    page_size: int = 100
) -> Dict[str, Any]:
    """Main entry point for query processing"""
    
    # Process query
    result = await handle_enhanced_query(query, user_id, user_role)
    
    # Apply pagination if requested
    if page > 1 or page_size != 100:
        data = result.get("data", [])
        paginated = PaginatedResponse.paginate(data, page, page_size)
        result["data"] = paginated["data"]
        result["pagination"] = paginated["pagination"]
    
    return result

# Initialize on import
processor = get_processor()