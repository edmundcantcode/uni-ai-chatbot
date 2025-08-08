import json
import logging
import os
import re
from typing import Dict, Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


class IntentClassifier:
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        host = os.getenv("OLLAMA_HOST", "localhost")
        port = os.getenv("OLLAMA_PORT", "11434")
        self.base_url = base_url or f"http://{host}:{port}"
        self.model = model or os.getenv("QWEN_MODEL", "qwen3:8b")
        self.timeout = aiohttp.ClientTimeout(total=30)

    # -------------------- helpers --------------------

    def _strip_think_and_extract_json(self, text: str) -> str:
        """Remove <think>…</think>, pull JSON from ```json fences if present, else the first {...} blob."""
        if not text:
            return "{}"
        # Strip any <think> blocks
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()

        # Pull from ```json fences if they exist
        if "```json" in text:
            try:
                return text.split("```json", 1)[1].split("```", 1)[0].strip()
            except Exception:
                pass

        # Otherwise, take the first {...} blob
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            return text[first:last + 1].strip()

        return text.strip()

    async def _call_qwen(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.1,
        json_mode: bool = False,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
                "top_p": 0.9,
                "top_k": 40,
            },
        }
        if json_mode:
            payload["format"] = "json"
            payload["prompt"] = (
                prompt
                + "\n\nReturn ONLY valid minified JSON. No prose, no markdown, no <think>."
            )

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            url = f"{self.base_url}/api/generate"
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    raise Exception(f"API error: {resp.status}")
                data = await resp.json()
                return data.get("response", "").strip()

    def _keyword_fallback(self, query: str) -> Optional[Dict[str, Any]]:
        """Super lightweight fallback if the LLM totally biffs it."""
        q = (query or "").lower()
        if any(w in q for w in ["active", "currently enrolled", "current students"]):
            return {"intent": "get_active_students", "confidence": 0.55, "entities": {}}
        if any(w in q for w in ["completed", "complete", "finished", "finish"]):
            return {"intent": "get_completed_students", "confidence": 0.55, "entities": {}}
        if "withdraw" in q or "withdrawn" in q:
            return {"intent": "get_withdrawn_students", "confidence": 0.55, "entities": {}}
        if "transfer out" in q or "transferred out" in q:
            return {"intent": "get_transferred_out_students", "confidence": 0.55, "entities": {}}
        return None

    def _heuristic_entities(self, query: str) -> Dict[str, Any]:
        """Heuristically pull out cohort like '202301' or 'March 2022' and a subject-ish phrase."""
        q = query or ""
        out: Dict[str, Any] = {}

        # Cohort forms:
        #   - 6 digit: 202301, 201803
        #   - 4 digit year: 2023 (keep as-is; your normalizer will expand year-only)
        #   - 'March 2022' / 'mar 2022' etc.
        m6 = re.search(r"\b(20\d{2}(0[1-9]|1[0-2]))\b", q)
        if m6:
            out["cohort"] = m6.group(1)
        else:
            myear = re.search(r"\b(20\d{2})\b", q)
            if myear:
                out["cohort"] = myear.group(1)
            else:
                months = (
                    "jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|"
                    "sep|sept|september|oct|october|nov|november|dec|december"
                )
                mmonth = re.search(rf"\b({months})\s+(20\d{{2}})\b", q, flags=re.I)
                if mmonth:
                    out["cohort"] = f"{mmonth.group(1)} {mmonth.group(2)}"

        # Subject name: grab words after 'fail/failed' or after 'in/for' up to punctuation
        subj = None
        mfail = re.search(r"\bfail(?:ed)?\s+([A-Za-z][\w\s&\-/]+)", q, flags=re.I)
        if mfail:
            subj = mfail.group(1)
        else:
            # fallback: after 'in ' or 'for '
            mpre = re.search(r"\b(?:in|for)\s+([A-Za-z][\w\s&\-/]+)", q, flags=re.I)
            if mpre:
                subj = mpre.group(1)

        if subj:
            subj = subj.strip().rstrip("?.!,")
            # keep it short-ish
            subj = re.sub(r"\s{2,}", " ", subj)
            out["subject_name"] = subj

        return out

    # -------------------- public API --------------------

    async def classify_query_type(self, query: str) -> str:
        from backend.constants.intent_config import get_query_type_prompt

        try:
            prompt = get_query_type_prompt(query)
            raw = await self._call_qwen(prompt, max_tokens=16, temperature=0.0)
            cleaned = re.sub(r"<think>.*?</think>", "", raw, flags=re.S).strip().lower()
            m = re.search(r"\b(count|list)\b", cleaned)
            if m:
                return m.group(1)
            logger.warning(f"Invalid query type: {cleaned}, defaulting to 'list'")
        except Exception as e:
            logger.warning(f"classify_query_type failed: {e}; defaulting to 'list'")
        return "list"

    async def classify_intent(self, query: str) -> Dict[str, Any]:
        from backend.constants.intent_config import get_intent_classification_prompt, BASE_INTENTS

        prompt = get_intent_classification_prompt(query)
        raw = await self._call_qwen(prompt, max_tokens=256, temperature=0.1, json_mode=True)

        try:
            cleaned = self._strip_think_and_extract_json(raw)
            result = json.loads(cleaned)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON: {raw}")
            fb = self._keyword_fallback(query)
            return fb or {"intent": None, "confidence": 0.0, "entities": {}}

        # Validate + fallback to keyword if intent not known
        if result.get("intent") not in BASE_INTENTS:
            fb = self._keyword_fallback(query)
            return fb or {"intent": None, "confidence": 0.0, "entities": {}}

        # Ensure entities is a dict
        entities = result.get("entities") or {}
        if not isinstance(entities, dict):
            entities = {}

        # Heuristic backfill for cohort / subject_name if the LLM omitted them
        heur = self._heuristic_entities(query)
        for k, v in heur.items():
            entities.setdefault(k, v)

        result["entities"] = entities
        return result