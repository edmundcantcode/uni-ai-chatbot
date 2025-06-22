from fastapi import APIRouter
from backend.parse_query import parse_query
from backend.intents.query_students import query_students
from backend.intents.predict_honors import predict_honors_logic
from backend.intents.weak_subjects import handle_list_weak_subjects
from backend.intents.strong_subjects import handle_list_strong_subjects
from backend.intents.failed_subjects import handle_list_failed_subjects
from backend.intents.get_subject_grades import handle_get_subject_grades
from backend.intents.get_student_profile import handle_get_student_profile

from pydantic import BaseModel

router = APIRouter()

class QueryRequest(BaseModel):
    query: str

@router.post("/chatbot")
async def chatbot_endpoint(payload: QueryRequest):
    parsed_intents = parse_query(payload.query)
    responses = []

    # 🧠 Save shared filters like ID or name
    shared_filters = {}
    for item in parsed_intents:
        shared_filters.update(item.get("filters", {}))

    for item in parsed_intents:
        intent = item.get("intent")
        filters = item.get("filters", {})

        # 🧠 Patch filters if DeepSeek missed "id" or "name"
        if "id" not in filters and "student_id" in shared_filters:
            filters["id"] = shared_filters["student_id"]
        elif "id" not in filters and "id" in shared_filters:
            filters["id"] = shared_filters["id"]
        if "name" not in filters and "name" in shared_filters:
            filters["name"] = shared_filters["name"]

        print("🧠 Detected intent:", intent)
        print("🔍 Final filters used:", filters)

        # 🔐 Ensure ID is integer for Cassandra
        if "id" in filters:
            try:
                filters["id"] = int(filters["id"])
            except (ValueError, TypeError):
                responses.append({"error": f"Invalid ID format: {filters['id']}"})
                continue

        # 🔁 Intent Routing
        if intent == "predict_honors":
            result = predict_honors_logic(filters)
        elif intent == "show_students":
            result = query_students(filters)
        elif intent == "explain_prediction":
            result = {"error": "🔧 Explanation not implemented yet."}
        elif intent == "list_weak_subjects":
            result = handle_list_weak_subjects(filters)
        elif intent == "list_strong_subjects":
            result = handle_list_strong_subjects(filters)
        elif intent == "list_failed_subjects":
            result = handle_list_failed_subjects(filters)
        elif intent == "get_subject_grades":
            result = handle_get_subject_grades(filters)
        elif intent == "get_student_profile":
            result = handle_get_student_profile(filters)

        else:
            result = {"error": f"Unknown intent: {intent}"}

        responses.append(result)

    return {"results": responses}
