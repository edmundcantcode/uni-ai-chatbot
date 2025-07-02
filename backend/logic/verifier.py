from backend.llm.result_explainer import verify_output_against_query

def attach_llm_verification(user_query: str, result: list, processed_query: str, cql: str):
    explanation = verify_output_against_query(user_query, result)

    return {
        "query": user_query,
        "processed_query": processed_query,
        "cql": cql,
        "result": result,
        "verification": explanation
    }
