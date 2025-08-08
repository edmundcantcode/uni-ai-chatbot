import os
import aiohttp
from typing import Optional

class QwenClient:
    def __init__(self,
                 base_url: Optional[str] = None,
                 model: Optional[str] = None):
        host = os.getenv("OLLAMA_HOST", "localhost")
        port = os.getenv("OLLAMA_PORT", "11434")
        self.base_url = base_url or f"http://{host}:{port}"
        self.model    = model    or os.getenv("QWEN_MODEL", "qwen3:8b")

    async def generate(self,
                       prompt: str,
                       max_tokens: int = 256,
                       temperature: float = 0.7,
                       stop: list[str] = None
                       ) -> str:
        payload = {
            "model":       self.model,
            "prompt":      prompt,
            "max_tokens":  max_tokens,
            "temperature": temperature,
            "stop":        stop or []
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{self.base_url}/api/completions", json=payload) as resp:
                resp.raise_for_status()
                data = await resp.json()
                # Ollama returns an array of chunks—take the last one’s “response”
                return data[-1]["response"].strip()

    async def health(self) -> bool:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.base_url}/api/tags") as resp:
                if resp.status != 200:
                    return False
                models = (await resp.json()).get("models", [])
                return any(m["name"] == self.model for m in models)
