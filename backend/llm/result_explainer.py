import requests

# 🧠 Explain result using LLM
def explain_result(query: str, result: dict):
    prompt = f"""
You are an assistant for a university AI chatbot.

The user asked:
"{query}"

The system responded with this result:
{result}

Your job is to explain the result in a clear, natural sentence that helps the user understand what it means.

Examples:
- If the result is a list of students, summarize what they have in common.
- If it's a prediction, explain what factors influenced it.
- If it's subject grades, describe patterns or highlights.

Keep it short but informative. Avoid repeating the raw JSON. Just explain what the data tells us.

Now, generate the explanation.
    """

    try:
        response = requests.post(
            "http://127.0.0.1:1234/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json={
                "model": "deepseek/deepseek-r1-0528-qwen3-8b",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.4,
                "max_tokens": 512,
            }
        )

        if response.ok:
            content = response.json()["choices"][0]["message"]["content"]
            return content.strip()
        else:
            return f"⚠️ LLM error: {response.status_code}"

    except Exception as e:
        return f"❌ Failed to generate explanation: {e}"
