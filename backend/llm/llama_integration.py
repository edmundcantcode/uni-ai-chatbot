# Compatibility wrapper - redirects old code to new QwenClient
from backend.llm.qwen_integration import QwenClient

class LlamaLLM(QwenClient):
    def check_health(self):
        return True