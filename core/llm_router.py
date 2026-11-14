"""Dual-LLM Router for SEO Super Star.

Routes requests to Google Gemini Free API (`gemini-3.8-flash` / `gemini-3.5-flash-lite`
/ `gemini-2.5-flash`) first, and automatically fails over to Groq Free API
(`llama-3.3-70b-versatile` -> `llama-3.1-8b-instant`) if rate-limited (`HTTP 429`)
or if only one key is configured. Also supports Gemini Grounding with Google Search
(5,000 free grounded prompts/month) and a deterministic rule-based fallback when
zero LLM keys are provided.
"""

import json
import re
from typing import Any, Dict, List, Optional
from core.config import Settings, get_settings


class DualLLMRouter:
    """Self-healing LLM router across Gemini Free Tier, Groq Free Tier, and offline rules."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()

    def _clean_json_string(self, raw_text: str) -> Any:
        """Extract and parse a JSON object or array from an LLM response."""
        cleaned = raw_text.strip()
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", cleaned)
        if fence_match:
            cleaned = fence_match.group(1).strip()
        try:
            return json.loads(cleaned)
        except Exception:
            # Try finding first { ... } or [ ... ]
            obj_match = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", cleaned)
            if obj_match:
                try:
                    return json.loads(obj_match.group(1))
                except Exception:
                    pass
        return {"raw_response": raw_text}

    def complete(
        self,
        prompt: str,
        system_prompt: str = "You are SEO Super Star, a senior technical SEO, GEO, and AEO architect.",
        json_mode: bool = False,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Generate completion using Gemini Free Tier with automatic Groq Free Tier failover."""
        errors: List[str] = []

        # 1. Try Google Gemini Free Tier (`google-genai` SDK)
        if self.settings.gemini_api_key:
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self.settings.gemini_api_key)
                for model_id in self.settings.gemini_models:
                    try:
                        cfg_kwargs: Dict[str, Any] = {
                            "system_instruction": system_prompt,
                            "temperature": temperature,
                        }
                        if json_mode:
                            cfg_kwargs["response_mime_type"] = "application/json"
                        response = client.models.generate_content(
                            model=model_id,
                            contents=prompt,
                            config=types.GenerateContentConfig(**cfg_kwargs),
                        )
                        text_out = response.text or ""
                        return {
                            "status": "ok",
                            "provider": "Google Gemini Free Tier",
                            "model": model_id,
                            "content": self._clean_json_string(text_out) if json_mode else text_out,
                            "errors": errors,
                        }
                    except Exception as model_err:
                        errors.append(f"Gemini ({model_id}): {model_err}")
            except Exception as gemini_err:
                errors.append(f"Gemini SDK init: {gemini_err}")

        # 2. Fail over to Groq Free Tier (`groq` SDK)
        if self.settings.groq_api_key:
            try:
                from groq import Groq

                groq_client = Groq(api_key=self.settings.groq_api_key)
                for groq_model in [
                    self.settings.groq_primary_model,
                    self.settings.groq_fast_model,
                ]:
                    try:
                        messages = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ]
                        kwargs: Dict[str, Any] = {
                            "model": groq_model,
                            "messages": messages,
                            "temperature": temperature,
                        }
                        if json_mode:
                            kwargs["response_format"] = {"type": "json_object"}
                        chat_completion = groq_client.chat.completions.create(**kwargs)
                        text_out = chat_completion.choices[0].message.content or ""
                        return {
                            "status": "ok",
                            "provider": "Groq Free Tier",
                            "model": groq_model,
                            "content": self._clean_json_string(text_out) if json_mode else text_out,
                            "errors": errors,
                        }
                    except Exception as groq_model_err:
                        errors.append(f"Groq ({groq_model}): {groq_model_err}")
            except Exception as groq_err:
                errors.append(f"Groq SDK init: {groq_err}")

        # 3. Deterministic Offline Fallback (when zero API keys are configured)
        fallback_msg = (
            "Heuristic Mode (No Gemini or Groq API key configured). "
            "Add a free GEMINI_API_KEY or GROQ_API_KEY in the sidebar to unlock deep LLM synthesis."
        )
        return {
            "status": "heuristic_fallback",
            "provider": "Local Deterministic Engine",
            "model": "rule-based-v1",
            "content": {"notice": fallback_msg, "prompt_preview": prompt[:300]} if json_mode else fallback_msg,
            "errors": errors,
        }

    def grounded_search(self, query: str) -> Dict[str, Any]:
        """Run a live Google-grounded search via Gemini's 5,000/mo free Google Search tool."""
        if not self.settings.gemini_api_key:
            return {
                "status": "no_gemini_key",
                "query": query,
                "answer": "",
                "citations": [],
            }

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.settings.gemini_api_key)
            for model_id in self.settings.gemini_models:
                try:
                    response = client.models.generate_content(
                        model=model_id,
                        contents=(
                            f"Search Google and provide a concise, fact-checked SEO/GEO synthesis for: {query}. "
                            "Include specific brands, entities, and facts mentioned in top results."
                        ),
                        config=types.GenerateContentConfig(
                            tools=[types.Tool(google_search=types.GoogleSearch())],
                            temperature=0.1,
                        ),
                    )
                    citations: List[Dict[str, str]] = []
                    candidates = getattr(response, "candidates", []) or []
                    if candidates:
                        g_meta = getattr(candidates[0], "grounding_metadata", None)
                        chunks = getattr(g_meta, "grounding_chunks", []) if g_meta else []
                        for chunk in chunks or []:
                            web = getattr(chunk, "web", None)
                            if web and getattr(web, "uri", None):
                                citations.append(
                                    {
                                        "title": getattr(web, "title", "") or web.uri,
                                        "url": web.uri,
                                    }
                                )
                    return {
                        "status": "ok",
                        "provider": f"Gemini Grounding ({model_id})",
                        "query": query,
                        "answer": response.text or "",
                        "citations": citations,
                    }
                except Exception:
                    continue
        except Exception as exc:
            return {
                "status": "error",
                "query": query,
                "answer": "",
                "citations": [],
                "error": str(exc),
            }

        return {
            "status": "unavailable",
            "query": query,
            "answer": "",
            "citations": [],
        }
