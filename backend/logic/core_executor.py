import time
import statistics
from typing import Dict, Any, List, Optional
from backend.database.connect_cassandra import get_session
from backend.logic.step_runner import run_step
from backend.logic.prompt_generator import get_response_prompt
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# SHARED EXECUTION LOGIC
# ============================================================================

async def execute_plan(
    plan: Dict[str, Any],
    user_id: str,
    user_role: str,
    llm = None
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
            # Return error response instead of raising
            return create_error_response(
                plan.get("query", ""),
                f"Step {idx} failed: {str(e)}",
                plan.get("start_time", time.time())
            )
    
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
    except Exception as e:
        logger.warning(f"Response generation failed: {e}")
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

def create_security_error_response(query: str, user_role: str, start_time: float) -> Dict[str, Any]:
    """Create security error response for unauthorized queries"""
    
    return {
        "success": False,
        "message": f"🔒 **Access Denied**\n\nAs a {user_role}, you can only access your own academic records. Try asking about your grades or CGPA instead.",
        "data": [],
        "count": 0,
        "error": True,
        "query": query,
        "intent": "security_error",
        "execution_time": time.time() - start_time,
        "security_level": user_role
    }

# ============================================================================
# PAGINATION SUPPORT
# ============================================================================

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