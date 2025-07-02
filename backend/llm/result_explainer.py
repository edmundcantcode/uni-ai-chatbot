import requests
from backend.llm.connect_llm import LLAMA3_API_URL

def verify_output_against_query(query: str, result: list) -> str:
    prompt = f"""
You are verifying the consistency between a user's question and a database result.

User query: "{query}"
Database result: {result}

Is the result logically answering the user's query? Reply with one sentence only.
    """.strip()

    try:
        response = requests.post(LLAMA3_API_URL, json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}]
        })
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Verification failed: {e}"
