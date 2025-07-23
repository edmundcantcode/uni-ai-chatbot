import os
import aiohttp
import asyncio
import requests
from typing import Dict, List, Optional, Any  # make sure Optional is imported

class LlamaLLM:
    def __init__(self,
                 base_url: Optional[str] = None,
                 model: Optional[str] = None):
        # Read what docker-compose is already exporting
        host = os.getenv("OLLAMA_HOST", "ollama")
        port = os.getenv("OLLAMA_PORT", "11434")
        self.base_url = base_url or f"http://{host}:{port}"
        self.model = model or os.getenv("LLAMA_MODEL", "llama3.2")

    async def generate_response(self, prompt: str, conversation_id: str = None,
                                temperature: float = 0.1, max_tokens: int = 500) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_k": 10,
                "top_p": 0.8
            }
        }
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload) as resp:
                    if resp.status != 200:
                        raise Exception(f"Ollama API error {resp.status}: {await resp.text()}")
                    data = await resp.json()
                    return data.get("response", "").strip()
        except asyncio.TimeoutError:
            raise Exception("Request to Llama model timed out")
        except aiohttp.ClientError as e:
            raise Exception(f"Connection error to Llama model: {e}")

    def check_health(self) -> bool:
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if r.status_code == 200:
                return any(m.get("name", "").startswith(self.model) for m in r.json().get("models", []))
            return False
        except Exception:
            return False
