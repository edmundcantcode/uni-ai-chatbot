# backend/logic/prompt_generator.py
from typing import Dict, Any, List

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
"""
    return header + body + security + footer


def get_response_prompt(query: str, intent: str, data: List[Dict[str, Any]], user_role: str) -> str:
    """Generate response formatting prompt"""
    
    # Prepare data summary
    data_summary = ""
    if not data:
        data_summary = "No results found."
    elif len(data) <= 5:
        data_summary = f"Results ({len(data)} rows):\n{data}"
    else:
        data_summary = f"Results ({len(data)} rows):\nFirst 3 rows: {data[:3]}\n..."
    
    prompt = f"""Format a response for this query result.

Original query: {query}
Intent: {intent}
User role: {user_role}
{data_summary}

Provide a natural, helpful response that:
1. Directly answers the user's question
2. Highlights key information
3. Uses appropriate formatting (bold for emphasis)
4. Is concise but complete

For student users, be encouraging and personal.
For admin users, be professional and detailed.

Response:"""
    
    return prompt

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