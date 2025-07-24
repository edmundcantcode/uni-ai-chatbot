# backend/logic/prompt_generator.py
from typing import Dict, Any, List
import json

# Comprehensive examples covering all major query patterns - FIXED: Removed problematic examples
EXAMPLES = [
  {
    "user_query": "Count active students",
    "plan": {
      "intent": "count_active_students",
      "steps": [
        {
          "table": "students",
          "select": ["COUNT(*)"],
          "where": { "status": { "op": "IN", "value": ["Active","Enrolled","Current"] } },
          "allow_filtering": True
        }
      ]
    }
  },
  {
    "user_query": "How many graduated students do we have?",
    "plan": {
      "intent": "count_graduated_students",
      "steps": [
        {
          "table": "students",
          "select": ["COUNT(*)"],
          "where": { "graduated": { "op": "=", "value": True } },
          "allow_filtering": True
        }
      ]
    }
  },
  {
    "user_query": "List all students",
    "plan": {
      "intent": "list_students",
      "steps": [
        {
          "table": "students",
          "select": ["id","name","programme","overallcgpa","cohort","status","graduated"],
          "where": {},
          "limit": 100,
          "allow_filtering": True
        }
      ]
    }
  },
  {
    "user_query": "Students with CGPA > 3.5",
    "plan": {
      "intent": "filter_by_cgpa",
      "steps": [
        {
          "table": "students",
          "select": ["id","name","programme","overallcgpa"],
          "where": { "overallcgpa": { "op": ">", "value": 3.5 } },
          "limit": 100,
          "allow_filtering": True
        }
      ]
    }
  },
  {
    "user_query": "Students with CGPA between 3.0 and 3.5",
    "plan": {
      "intent": "filter_by_cgpa_range",
      "steps": [
        {
          "table": "students",
          "select": ["id","name","programme","overallcgpa"],
          "where": { "overallcgpa": { "op": "BETWEEN", "value": [3.0,3.5] } },
          "limit": 100,
          "allow_filtering": True
        }
      ]
    }
  },
  {
    "user_query": "How many female students are there?",
    "plan": {
      "intent": "count_female_students",
      "steps": [
        {
          "table": "students",
          "select": ["COUNT(*)"],
          "where": { "gender": { "op": "=", "value": "Female" } },
          "allow_filtering": True
        }
      ]
    }
  },
  {
    "user_query": "Show me my grade for Data Structures",
    "plan": {
      "intent": "get_subject_grade",
      "steps": [
        {
          "table": "subjects",
          "select": ["id","subjectname","grade","overallpercentage"],
          "where": { "subjectname": { "op": "=", "value": "Data Structures" } },
          "limit": 10,
          "allow_filtering": True
        }
      ]
    }
  },
  {
    "user_query": "List subjects for student 12345",
    "plan": {
      "intent": "list_student_subjects",
      "steps": [
        {
          "table": "subjects",
          "select": ["id","subjectname","grade","overallpercentage","examyear","exammonth"],
          "where": { "id": { "op": "=", "value": 12345 } },
          "limit": 200,
          "allow_filtering": True
        }
      ]
    }
  },
  {
    "user_query": "How many students are in cohort March 2022?",
    "plan": {
      "intent": "count_cohort_students",
      "steps": [
        {
          "table": "students",
          "select": ["COUNT(*)"],
          "where": { "cohort": { "op": "=", "value": "202203" } },
          "allow_filtering": True
        }
      ]
    }
  },
  {
    "user_query": "Show active students in Computer Science",
    "plan": {
      "intent": "list_students",
      "steps": [
        {
          "table": "students",
          "select": ["id","name","programme","overallcgpa","cohort","status","graduated"],
          "where": {
            "status": { "op": "IN", "value": ["Active","Enrolled","Current"] },
            "programme": { "op": "=", "value": "Bachelor of Science (Honours) in Computer Science" }
          },
          "limit": 100,
          "allow_filtering": True
        }
      ]
    }
  }
]

def get_response_prompt(user_query: str, intent: str = "", data: List[Dict[str, Any]] = None, user_role: str = "admin") -> str:
    """Generate LLM prompt - handles both old and new call signatures"""
    
    # NEW USAGE: Just user_query for LLM planning
    if isinstance(user_query, str) and intent == "" and data is None:
        prompt_skeleton = """You are a planner. Output ONLY valid JSON (no prose). 
Target schema:
{
  "intent": "<string>",
  "steps": [
    {
      "table": "students|subjects",
      "select": ["<col>", ...],
      "where": { "<col>": { "op": "<=|>=|=|IN|BETWEEN|...>", "value": <num|str|bool|list> } },
      "where_in_ids_from_step": <int?>,
      "limit": <int?>,
      "allow_filtering": true
    }
  ],
  "post_aggregation": { ... }?  // optional
}

CRITICAL RULES:
- Never use "*" in select; use explicit columns.
- Prefer COUNT(*) only when user clearly wants a count.
- If the user wording says "list/show/display…", return rows, not just a count.
- Use the real intent string (e.g., "list_students", "count_active_students", "get_subject_grade", etc.).
- Don't include pagination or user_id security filters; the server will inject those.
- If the query mixes subject filters (grade, examyear, subjectname) with student filters (programme, cohort, status), create two steps: first on students, then subjects, and link via `where_in_ids_from_step`.
- For IN queries, ALWAYS write the list under the key "value" (NOT "values").
- When the query contains a month + year ("March 2022", "July 2023", ...) convert it to the six-digit cohort code (YYYYMM) before putting it in "where".
- Only insert status filters when the user explicitly says "active/currently enrolled/current students". Do **not** assume it for plain "cohort" or "students" queries.
- Unless the user mentions multiple aspects, don't add *any* extra steps: "count/how many..." → **exactly one** step with "select": ["COUNT(*)"], "list/show/display..." → **exactly one** step with an explicit column list. Extra steps are allowed **only** when the user asks for *both* student-level and subject-level filters in the same question.
- Never introduce ANY column that the user did not mention.
- NEVER add programme, graduated, gender, country, or status filters unless the user explicitly mentioned those words.
- Return the most direct, minimal plan with ONLY the filters the user actually requested.

Now follow the schema exactly. Output nothing but JSON."""

        return f"""{prompt_skeleton}

REFERENCE_EXAMPLES:
```json
{json.dumps(EXAMPLES, ensure_ascii=False, indent=2)}
```

USER_QUERY: "{user_query}"
"""
    
    # LEGACY USAGE: Response formatting
    if data is None:
        data = []
    
    # FIX A: Suppress long lists with hard limit
    if len(data) > 10:
        # Extract key info for summary
        if data and isinstance(data[0], dict):
            # Try to identify what kind of data this is
            if "cohort" in data[0]:
                cohort_values = list(set(row.get("cohort", "") for row in data if row.get("cohort")))
                if len(cohort_values) == 1:
                    return f"**{len(data):,}** students found in cohort {cohort_values[0]}. (See table below.)"
            elif "programme" in data[0]:
                prog_values = list(set(row.get("programme", "") for row in data if row.get("programme")))
                if len(prog_values) == 1:
                    prog_short = prog_values[0].split("(")[0].strip() if prog_values[0] else "specified programme"
                    return f"**{len(data):,}** students found in {prog_short}. (See table below.)"
        
        # Generic fallback
        return f"**{len(data):,}** results found. (See table below.)"
    
    data_summary = ""
    if not data:
        data_summary = "No results found."
    elif len(data) <= 5:
        data_summary = f"Results ({len(data)} rows):\n{data}"
    else:
        data_summary = f"Results ({len(data)} rows):\nFirst 3 rows: {data[:3]}\n..."
    
    prompt = f"""Format a response for this query result.

Original query: {user_query}
Intent: {intent}
User role: {user_role}
{data_summary}

Provide a natural, helpful response that:
1. Directly answers the user's question
2. Highlights key information
3. Uses appropriate formatting (bold for emphasis)
4. Is concise but complete
5. If there are more than 10 rows, do NOT list them individually – give a concise summary only

For student users, be encouraging and personal.
For admin users, be professional and detailed.

Response:"""
    
    return prompt

def get_analysis_prompt(query: str, user_id: str, user_role: str) -> str:
    header = f"""You are an AI assistant analyzing database queries for a university system.
Current user: {user_id} (Role: {user_role})
Query: {query}
"""

    body = """
Available tables:
1. students: id, name, programme, overallcgpa, status, graduated, awardclassification, gender, country
2. subjects: id, subjectname, grade, overallpercentage, examyear, exammonth

IMPORTANT OPERATOR SCHEMA:
Use the enhanced WHERE clause format with operators:

{
  "where": {
    "column_name": {"op": "OPERATOR", "value": VALUE}
  }
}

Supported operators:
- "=": Equality (default)
- ">", ">=", "<", "<=": Numeric comparisons
- "!=": Not equal
- "IN": Match any value in list
- "BETWEEN": Range (requires 2-element list)
- "CONTAINS": Substring search (Python filtered)
- "LIKE": Pattern matching with % wildcards (Python filtered)

Examples:
- CGPA > 3.0: {"overallcgpa": {"op": ">", "value": 3.0}}
- Programme in CS or IT: {"programme": {"op": "IN", "value": ["Computer Science", "Information Technology"]}}
- CGPA between 2.0 and 3.5: {"overallcgpa": {"op": "BETWEEN", "value": [2.0, 3.5]}}
- Subject containing "Math": {"subjectname": {"op": "CONTAINS", "value": "Math"}}

SECURITY RULES:
"""
    if user_role == "student":
        security = f"""
- You can ONLY access data for student ID {user_id}
- Always add "id": {{"op": "=", "value": {user_id}}} to WHERE clause for students/subjects tables
- Cannot perform COUNT(*) or other aggregations
- Cannot access other students' data
"""
    else:
        security = """
- Admins can access all data
- Can perform aggregations and complex queries
- Do NOT include "id": "admin" in WHERE clauses
"""

    footer = """
Return a JSON object with:
{
  "intent": "description of what the query wants",
  "entities": {extracted entities from query},
  "steps": [
    {
      "table": "table_name",
      "select": ["column1", "column2"],  // or ["COUNT(*)"] for counts
      "where": {
        "column": {"op": "operator", "value": value}
      },
      "limit": 100,  // optional
      "allow_filtering": true,
      "where_in_ids_from_step": null  // or step index to use IDs from
    }
  ],
  "post_aggregation": {  // optional, for admin only
    "type": "average|sum|count|group_by|top_n",
    "field": "column_name",
    "n": 10  // for top_n
  },
  "response_message": "Natural language description"
}

IMPORTANT:
- Return ONLY valid JSON, no explanations
- Use the operator schema for ALL WHERE conditions
- Never use "id": "admin" in WHERE clauses
- For students, always filter by their ID
- NEVER add filters for columns the user did not explicitly mention
"""
    return header + body + security + footer

def get_validation_prompt(json_str: str, errors: List[str]) -> str:
    """Generate prompt for JSON correction"""
    
    prompt = f"""Your previous JSON response had validation errors:

Errors:
{chr(10).join(f"- {e}" for e in errors)}

Original JSON:
{json_str}

Please provide a CORRECTED JSON response that fixes these errors.
Remember to use the operator schema for WHERE clauses.
Return ONLY the corrected JSON, no explanations.

Corrected JSON:"""
    
    return prompt

def get_synonym_prompt(query: str) -> str:
    """Generate prompt for query synonym expansion"""
    
    prompt = f"""Expand this query with synonyms and related terms.

Query: {query}

Common synonyms in academic context:
- active = enrolled = current = not graduated
- graduated = completed = finished
- cgpa = gpa = grade point average
- programme = program = course = major
- marks = grades = scores
- failed = unsuccessful = did not pass

Return a JSON object with:
{
  "original": "{query}",
  "expanded_terms": ["term1", "term2", ...],
  "normalized_query": "query with synonyms replaced"
}

JSON:"""
    
    return prompt

# Legacy alias
def generate_prompt(user_query: str) -> str:
    """Legacy prompt generation - redirects to new system"""
    return get_response_prompt(user_query)