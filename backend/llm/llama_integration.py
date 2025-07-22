# backend/llm/llama_integration.py (Simplified for Intent-Based System)

import json
import asyncio
import aiohttp
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
import os

class LlamaLLM:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        """
        Initialize Llama LLM integration for intent classification and yes/no explanations only
        
        Args:
            base_url: Ollama server URL 
            model: Llama model to use (llama3.2, llama3.1, etc.)
        """
        self.base_url = base_url
        self.model = model

    async def generate_response(self, prompt: str, conversation_id: str = None, 
                              temperature: float = 0.1, max_tokens: int = 500) -> str:
        """
        Generate response from Llama model
        Low temperature for consistent intent classification
        """
        try:
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
            
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
                async with session.post(f"{self.base_url}/api/generate", json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        generated_text = result.get("response", "").strip()
                        return generated_text
                    else:
                        error_text = await response.text()
                        raise Exception(f"Ollama API error {response.status}: {error_text}")
                        
        except asyncio.TimeoutError:
            raise Exception("Request to Llama model timed out")
        except aiohttp.ClientError as e:
            raise Exception(f"Connection error to Llama model: {str(e)}")
        except Exception as e:
            raise Exception(f"Error generating response: {str(e)}")

    async def generate_clarification_question(self, clarification_reason: str, 
                                            available_options: List[str] = None) -> str:
        """Generate a clarification question for ambiguous queries"""
        
        prompt = f"""Generate a helpful clarification question for this reason: {clarification_reason}

Available options: {available_options if available_options else 'None provided'}

Rules:
- Be conversational and friendly
- Ask ONE clear question  
- If options are provided, list them clearly
- Keep it concise

Examples:
- "I found multiple subjects with 'programming'. Which one did you mean: PrinciplesofEntrepreneurship, PrinciplesandPracticeofManagement?"
- "Which student are you asking about? Please provide their student ID."
- "Are you looking for your CGPA or your subject grades?"

Generate the clarification question:"""
        
        try:
            response = await self.generate_response(prompt, temperature=0.3, max_tokens=100)
            return response.strip()
        except:
            # Fallback if LLM fails
            return f"I need clarification: {clarification_reason}"

    def check_health(self) -> bool:
        """Check if Ollama service is running and model is available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                return any(model.get("name", "").startswith(self.model) for model in models)
            return False
        except:
            return False

    async def pull_model(self) -> bool:
        """Pull the Llama model if not available"""
        try:
            payload = {"name": self.model}
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.base_url}/api/pull", json=payload) as response:
                    return response.status == 200
        except:
            return False

# Example usage and testing
async def test_llama_integration():
    """Test the simplified Llama integration"""
    
    llm = LlamaLLM()
    
    # Check if service is available
    if not llm.check_health():
        print("❌ Ollama service not available or model not found")
        print("Make sure Ollama is running and llama3.2 model is installed")
        return
    
    print("✅ Llama LLM service is available")
    
    # Test intent classification prompt
    test_prompt = """You are an intent classifier. Your ONLY job is to identify what the user wants to do.

USER QUERY: "Did I pass Programming Principles?"
USER ROLE: student

AVAILABLE INTENTS:
1. count_students - Count/how many students
2. get_student_cgpa - Get CGPA/GPA for student
3. get_student_grades - Get all grades/results for student  
4. get_subject_results - Get results for specific subject
5. get_student_info - Get student information/details
6. list_students - List/show students
7. yes_no_question - Questions that need yes/no answer (like "did I pass?")
8. unknown - Cannot determine

Extract raw terms mentioned (don't process them):
- Student names, IDs, subject names, programme names, countries, etc.

Respond with JSON ONLY:
{
    "intent": "one_of_the_intents_above",
    "confidence": 0.0-1.0,
    "raw_entities": ["list", "of", "raw", "terms", "mentioned"],
    "is_yes_no": true/false
}

Classify now:"""
    
    try:
        result = await llm.generate_response(test_prompt)
        print(f"LLM Response: {result}")
        
        # Try to parse JSON
        parsed = json.loads(result)
        print(f"✅ Successfully parsed JSON: {parsed}")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_llama_integration())