import re
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ============================================================================
# STUDENT ROLE FALLBACK QUERIES (Self-access only)
# ============================================================================

STUDENT_FALLBACK_QUERIES = {
    # Personal CGPA queries
    "cgpa": {
        "patterns": [
            r"\bcgpa\b",
            r"\bgpa\b", 
            r"my.*cgpa",
            r"what.*my.*cgpa",
            r"cgpa.*please"
        ],
        "cql": "SELECT overallcgpa FROM students WHERE id = ? ALLOW FILTERING",
        "params_func": lambda user_id, **kwargs: [int(user_id)] if user_id.isdigit() else [user_id],
        "response_formatter": lambda rows: f"📊 Your CGPA is **{rows[0].overallcgpa:.2f}**" if rows and rows[0].overallcgpa else "CGPA not available"
    },
    
    # Personal grades/subjects
    "my_grades": {
        "patterns": [
            r"show.*my.*grades?",
            r"my.*grades?",
            r"see.*my.*results?",
            r"my.*results?",
            r"show.*grades?"
        ],
        "cql": "SELECT subjectname, grade, overallpercentage, examyear, exammonth FROM subjects WHERE id = ? ALLOW FILTERING",
        "params_func": lambda user_id, **kwargs: [int(user_id)] if user_id.isdigit() else [user_id],
        "response_formatter": lambda rows: f"📚 Found **{len(rows)}** subjects in your record"
    },
    
    # Failed subjects check
    "failed_subjects": {
        "patterns": [
            r"failed.*subjects?",
            r"subjects?.*failed",
            r"do.*i.*have.*failed",
            r"any.*failed.*subjects?",
            r"subjects?.*that.*i.*failed"
        ],
        "cql": "SELECT subjectname, grade, overallpercentage FROM subjects WHERE id = ? AND grade = 'F' ALLOW FILTERING",
        "params_func": lambda user_id, **kwargs: [int(user_id)] if user_id.isdigit() else [user_id],
        "response_formatter": lambda rows: f"❌ You have **{len(rows)}** failed subjects" if rows else "✅ You have no failed subjects"
    },
    
    # Passed subjects
    "passed_subjects": {
        "patterns": [
            r"passed.*subjects?",
            r"subjects?.*passed",
            r"subjects?.*that.*i.*passed"
        ],
        "cql": "SELECT subjectname, grade, overallpercentage FROM subjects WHERE id = ? AND grade != 'F' ALLOW FILTERING",
        "params_func": lambda user_id, **kwargs: [int(user_id)] if user_id.isdigit() else [user_id],
        "response_formatter": lambda rows: f"✅ You have passed **{len(rows)}** subjects"
    },
    
    # Graduation status
    "graduation_status": {
        "patterns": [
            r"am.*i.*graduated",
            r"graduated.*yet",
            r"graduation.*status",
            r"have.*i.*graduated"
        ],
        "cql": "SELECT graduated, status FROM students WHERE id = ? ALLOW FILTERING",
        "params_func": lambda user_id, **kwargs: [int(user_id)] if user_id.isdigit() else [user_id],
        "response_formatter": lambda rows: "🎓 **Yes, you have graduated!**" if rows and rows[0].graduated else "📚 You are still studying"
    },
    
    # Academic status
    "academic_status": {
        "patterns": [
            r"academic.*status",
            r"my.*status",
            r"current.*status"
        ],
        "cql": "SELECT status, graduated, overallcgpa FROM students WHERE id = ? ALLOW FILTERING",
        "params_func": lambda user_id, **kwargs: [int(user_id)] if user_id.isdigit() else [user_id],
        "response_formatter": lambda rows: f"📊 Status: **{rows[0].status}** | CGPA: **{rows[0].overallcgpa:.2f}**" if rows else "Status not available"
    },
    
    # Subjects by year
    "subjects_by_year": {
        "patterns": [
            r"subjects?.*from.*(\d{4})",
            r"(\d{4}).*subjects?",
            r"list.*subjects?.*(\d{4})"
        ],
        "cql": "SELECT subjectname, grade, overallpercentage, exammonth FROM subjects WHERE id = ? AND examyear = ? ALLOW FILTERING",
        "params_func": lambda user_id, match=None, **kwargs: [int(user_id) if user_id.isdigit() else user_id, int(match.group(1))] if match else [int(user_id) if user_id.isdigit() else user_id, 2023],
        "response_formatter": lambda rows, year=None: f"📚 Found **{len(rows)}** subjects from {year or 'that year'}"
    },
    
    # Full transcript
    "show_transcript": {
        "patterns": [
            r"show.*transcript",
            r"my.*transcript",
            r"full.*transcript",
            r"complete.*transcript"
        ],
        "cql": "SELECT subjectname, grade, overallpercentage, examyear, exammonth FROM subjects WHERE id = ? ORDER BY examyear, exammonth ALLOW FILTERING",
        "params_func": lambda user_id, **kwargs: [int(user_id)] if user_id.isdigit() else [user_id],
        "response_formatter": lambda rows: f"📄 **Your Complete Transcript** - {len(rows)} subjects total"
    }
}

# ============================================================================
# ADMIN ROLE FALLBACK QUERIES 
# ============================================================================

ADMIN_FALLBACK_QUERIES = {
    # Student counts
    "count_all_students": {
        "patterns": [
            r"how.*many.*students?",
            r"count.*students?",
            r"total.*students?",
            r"number.*of.*students?"
        ],
        "cql": "SELECT COUNT(*) FROM students",
        "params_func": lambda **kwargs: [],
        "response_formatter": lambda rows: f"👥 **{rows[0].count:,}** total students"
    },
    
    "count_active_students": {
        "patterns": [
            r"how.*many.*active.*students?",
            r"count.*active.*students?",
            r"currently.*active.*students?",
            r"enrolled.*students?"
        ],
        "cql": "SELECT COUNT(*) FROM students WHERE graduated = false ALLOW FILTERING",
        "params_func": lambda **kwargs: [],
        "response_formatter": lambda rows: f"👥 **{rows[0].count:,}** active students"
    },
    
    "count_graduated_students": {
        "patterns": [
            r"count.*graduated.*students?",
            r"how.*many.*graduated",
            r"graduated.*students?"
        ],
        "cql": "SELECT COUNT(*) FROM students WHERE graduated = true ALLOW FILTERING",
        "params_func": lambda **kwargs: [],
        "response_formatter": lambda rows: f"🎓 **{rows[0].count:,}** graduated students"
    },
    
    "count_female_students": {
        "patterns": [
            r"how.*many.*female.*students?",
            r"count.*female.*students?",
            r"female.*students?",
            r"women.*students?"
        ],
        "cql": "SELECT COUNT(*) FROM students WHERE gender = 'Female' ALLOW FILTERING",
        "params_func": lambda **kwargs: [],
        "response_formatter": lambda rows: f"👩‍🎓 **{rows[0].count:,}** female students"
    },
    
    "count_male_students": {
        "patterns": [
            r"how.*many.*male.*students?",
            r"count.*male.*students?",
            r"male.*students?",
            r"men.*students?"
        ],
        "cql": "SELECT COUNT(*) FROM students WHERE gender = 'Male' ALLOW FILTERING",
        "params_func": lambda **kwargs: [],
        "response_formatter": lambda rows: f"👨‍🎓 **{rows[0].count:,}** male students"
    },
    
    # Student lists
    "list_all_students": {
        "patterns": [
            r"list.*all.*students?",
            r"show.*all.*students?",
            r"all.*students?"
        ],
        "cql": "SELECT id, name, programme, overallcgpa, cohort, status FROM students LIMIT 100",
        "params_func": lambda **kwargs: [],
        "response_formatter": lambda rows: f"👥 Showing **{len(rows)}** students"
    },
    
    "list_active_students": {
        "patterns": [
            r"list.*active.*students?",
            r"show.*active.*students?",
            r"active.*students?"
        ],
        "cql": "SELECT id, name, programme, overallcgpa, cohort, status FROM students WHERE graduated = false ALLOW FILTERING LIMIT 100",
        "params_func": lambda **kwargs: [],
        "response_formatter": lambda rows: f"👥 Showing **{len(rows)}** active students"
    },
    
    # Specific student queries
    "student_cgpa": {
        "patterns": [
            r"cgpa.*for.*student.*(\d+)",
            r"student.*(\d+).*cgpa",
            r"show.*cgpa.*(\d+)"
        ],
        "cql": "SELECT id, name, overallcgpa FROM students WHERE id = ? ALLOW FILTERING",
        "params_func": lambda match=None, **kwargs: [int(match.group(1))] if match else [],
        "response_formatter": lambda rows, student_id=None: f"📊 Student {student_id}: CGPA **{rows[0].overallcgpa:.2f}**" if rows else f"Student {student_id} not found"
    },
    
    "student_grades": {
        "patterns": [
            r"grades.*for.*student.*(\d+)",
            r"student.*(\d+).*grades?",
            r"show.*grades.*(\d+)"
        ],
        "cql": "SELECT subjectname, grade, overallpercentage FROM subjects WHERE id = ? ALLOW FILTERING LIMIT 100",
        "params_func": lambda match=None, **kwargs: [int(match.group(1))] if match else [],
        "response_formatter": lambda rows, student_id=None: f"📚 Student {student_id}: **{len(rows)}** subjects found" if rows else f"No grades found for student {student_id}"
    },
    
    # Subject queries
    "list_all_subjects": {
        "patterns": [
            r"list.*all.*subjects?",
            r"show.*all.*subjects?",
            r"all.*subjects?"
        ],
        "cql": "SELECT DISTINCT subjectname FROM subjects LIMIT 200",
        "params_func": lambda **kwargs: [],
        "response_formatter": lambda rows: f"📚 Found **{len(rows)}** unique subjects"
    },
    
    # CGPA filters
    "high_cgpa_students": {
        "patterns": [
            r"students?.*cgpa.*above.*([0-9.]+)",
            r"cgpa.*greater.*than.*([0-9.]+)",
            r"cgpa.*>.*([0-9.]+)"
        ],
        "cql": "SELECT id, name, overallcgpa, programme FROM students WHERE overallcgpa > ? ALLOW FILTERING LIMIT 100",
        "params_func": lambda match=None, **kwargs: [float(match.group(1))] if match else [3.5],
        "response_formatter": lambda rows, threshold=None: f"🌟 **{len(rows)}** students with CGPA above {threshold or '3.5'}"
    },
    
    # NEW: Subjects by programme
    "subjects_by_programme": {
        "patterns": [
            r"subjects?.*for.*program(?:me)?\s+(.+)",
            r"list.*subjects?.*program(?:me)?\s+(.+)",
            r"show.*subjects?.*program(?:me)?\s+(.+)"
        ],
        "cql": "SELECT DISTINCT subjectname FROM subjects WHERE programme = ? ALLOW FILTERING",
        "params_func": lambda match=None, **kwargs: [match.group(1).strip()] if match else [],
        "response_formatter": lambda rows, programme=None: f"📚 Found **{len(rows)}** subjects for programme {programme or 'specified'}"
    },
    
    # NEW: Count students who passed a subject
    "count_passed_subject": {
        "patterns": [
            r"how many.*students?.*passed\s+(.+)",
            r"count.*students?.*passed\s+(.+)",
            r"students?.*passed\s+(.+).*count"
        ],
        "cql": "SELECT COUNT(*) FROM subjects WHERE subjectname = ? AND grade != 'F' ALLOW FILTERING",
        "params_func": lambda match=None, **kwargs: [match.group(1).strip()] if match else [],
        "response_formatter": lambda rows, subject=None: f"👥 **{rows[0].count}** students passed {subject or 'the subject'}" if rows else "No data found"
    },
    
    # NEW: Count students who failed a subject
    "count_failed_subject": {
        "patterns": [
            r"how many.*students?.*failed\s+(.+)",
            r"count.*students?.*failed\s+(.+)",
            r"students?.*failed\s+(.+).*count"
        ],
        "cql": "SELECT COUNT(*) FROM subjects WHERE subjectname = ? AND grade = 'F' ALLOW FILTERING",
        "params_func": lambda match=None, **kwargs: [match.group(1).strip()] if match else [],
        "response_formatter": lambda rows, subject=None: f"❌ **{rows[0].count}** students failed {subject or 'the subject'}" if rows else "No data found"
    },
    
    # NEW: Grade distribution for a subject
    "grade_distribution": {
        "patterns": [
            r"grade.*distribution.*for\s+(.+)",
            r"distribution.*grades?.*(.+)",
            r"grades?.*breakdown.*(.+)"
        ],
        "cql": "SELECT grade, COUNT(*) as count FROM subjects WHERE subjectname = ? GROUP BY grade ALLOW FILTERING",
        "params_func": lambda match=None, **kwargs: [match.group(1).strip()] if match else [],
        "response_formatter": lambda rows, subject=None: f"📊 **Grade Distribution for {subject or 'Subject'}**: " + 
                                                        ", ".join([f"{row.grade}: {row.count}" for row in rows]) if rows else "No grades found"
    },
    
    # NEW: Name disambiguation - find students with same name
    "student_name_lookup": {
        "patterns": [
            r"student.*name.*(.+)",
            r"find.*student.*(.+)",
            r"lookup.*student.*(.+)",
            r"show.*student.*(.+)"
        ],
        "cql": "SELECT id, name, programme, cohort, overallcgpa, status FROM students WHERE name = ? ALLOW FILTERING",
        "params_func": lambda match=None, **kwargs: [match.group(1).strip()] if match else [],
        "response_formatter": lambda rows, student_name=None: f"👥 Found **{len(rows)}** students named '{student_name}'" if len(rows) > 1 else f"👤 Found student: {rows[0].name} (ID: {rows[0].id})" if rows else f"No student found with name '{student_name}'"
    },
}

# ============================================================================
# FALLBACK QUERY MATCHER
# ============================================================================

class FallbackQueryMatcher:
    """Matches user queries to predefined fallback CQL queries"""
    
    def __init__(self):
        self.student_queries = STUDENT_FALLBACK_QUERIES
        self.admin_queries = ADMIN_FALLBACK_QUERIES
    
    def find_fallback_query(self, query: str, user_role: str) -> Optional[Dict[str, Any]]:
        """Find a matching fallback query for the user's input"""
        
        query_lower = query.lower().strip()
        queries = self.student_queries if user_role == "student" else self.admin_queries
        
        for query_name, query_def in queries.items():
            for pattern in query_def["patterns"]:
                match = re.search(pattern, query_lower, re.IGNORECASE)
                if match:
                    logger.info(f"🎯 Matched fallback query: {query_name} for role: {user_role}")
                    return {
                        "name": query_name,
                        "definition": query_def,
                        "match": match,
                        "query": query
                    }
        
        return None
    
    async def execute_fallback_query(
        self, 
        session, 
        matched_query: Dict[str, Any], 
        user_id: str, 
        user_role: str
    ) -> Dict[str, Any]:
        """Execute a matched fallback query"""
        
        query_def = matched_query["definition"]
        match = matched_query["match"]
        
        try:
            # Build parameters
            params = query_def["params_func"](
                user_id=user_id, 
                user_role=user_role,
                match=match
            )
            
            # Execute CQL
            logger.info(f"Executing fallback CQL: {query_def['cql']} with params: {params}")
            result = session.execute(query_def["cql"], params)
            rows = list(result)
            
            # Format response - handle different formatter signatures
            try:
                # Try calling with just rows first (simplest case)
                message = query_def["response_formatter"](rows)
            except TypeError:
                # If that fails, try with additional kwargs
                formatter_kwargs = {
                    "user_id": user_id,
                    "user_role": user_role
                }
                
                # Add extracted values from regex match for formatter
                if match and hasattr(match, 'groups'):
                    for i, group in enumerate(match.groups(), 1):
                        if group and group.isdigit():
                            if len(group) == 4:
                                formatter_kwargs["year"] = int(group)
                            elif len(group) > 4:
                                formatter_kwargs["student_id"] = int(group)
                            else:
                                formatter_kwargs["threshold"] = float(group)
                        elif group:
                            formatter_kwargs["programme"] = group
                            formatter_kwargs["subject"] = group
                            formatter_kwargs["cohort"] = group
                
                try:
                    message = query_def["response_formatter"](rows, **formatter_kwargs)
                except TypeError as e:
                    # Fallback to basic message
                    logger.warning(f"Formatter error: {e}, using basic message")
                    message = f"Found {len(rows)} results"
            
            # Convert rows to list of dicts for consistent response format
            data = []
            for row in rows:
                row_dict = {}
                for column in row._fields if hasattr(row, '_fields') else dir(row):
                    if not column.startswith('_'):
                        try:
                            row_dict[column] = getattr(row, column)
                        except:
                            pass
                data.append(row_dict)
            
            return {
                "success": True,
                "message": message,
                "data": data,
                "count": len(data),
                "intent": f"fallback_{matched_query['name']}",
                "processor_used": "fallback_cql",
                "fallback_query": query_def["cql"]
            }
            
        except Exception as e:
            logger.error(f"Fallback query execution failed: {e}")
            return {
                "success": False,
                "message": f"Could not execute fallback query: {str(e)}",
                "data": [],
                "count": 0,
                "error": True,
                "fallback_query": query_def["cql"]
            }

# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================

def get_fallback_matcher():
    """Get the global fallback query matcher"""
    return FallbackQueryMatcher()

def should_try_fallback(result: Dict[str, Any]) -> bool:
    """Determine if we should try fallback queries"""
    return (
        not result.get("success", False) or
        result.get("error", False) or
        result.get("count", 0) == 0 or
        len(result.get("data", [])) == 0
    )

async def try_fallback_query(
    session,
    query: str, 
    user_id: str, 
    user_role: str
) -> Optional[Dict[str, Any]]:
    """Try to execute a fallback query if semantic processing failed"""
    
    # TODO: Add name disambiguation later - for now just use regular fallback patterns
    
    matcher = get_fallback_matcher()
    matched = matcher.find_fallback_query(query, user_role)
    
    if matched:
        logger.info(f"🔄 Attempting fallback query for: '{query}'")
        return await matcher.execute_fallback_query(session, matched, user_id, user_role)
    
    return None