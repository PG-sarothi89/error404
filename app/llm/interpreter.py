"""LLM Interpreter service calling structured-output models via HTTP."""

import json
import logging
from typing import Any
import httpx

from app import config
from app.llm.fallback import fallback_parse_all
from app.llm.prompts import SYSTEM_PROMPT, build_user_prompt, REPAIR_PROMPT_TEMPLATE
from app.schemas.interpretation import DirectiveInterpretation, LLMInterpretationOutput

logger = logging.getLogger("gridwise.llm")


class LLMInterpreter:
    """Interprets operator notes into machine-checkable directives."""

    def __init__(self) -> None:
        # Reusable client with connection pooling and timeouts
        self.client = httpx.AsyncClient(
            timeout=config.LLM_TIMEOUT_SECONDS,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=50),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def interpret_notes(
        self,
        scenario_id: str,
        operator_notes: list[str],
        battery_capacity_kwh: float,
    ) -> list[DirectiveInterpretation]:
        """Interprets all operator notes in a single structured LLM call."""
        # If fallback is explicitly configured or no API keys exist
        if config.LLM_PROVIDER == "fallback" or (
            not config.GEMINI_API_KEY and not config.OPENAI_API_KEY and not config.GROQ_API_KEY
        ):
            logger.info("Using local deterministic parser (no API key configured or fallback selected)")
            return fallback_parse_all(operator_notes, battery_capacity_kwh)

        user_prompt = build_user_prompt(operator_notes, battery_capacity_kwh, scenario_id)

        try:
            raw_text = await self._call_model(user_prompt)
            return self._parse_and_validate(raw_text, operator_notes, battery_capacity_kwh)
        except Exception as primary_err:
            logger.warning(f"Primary model call or parsing failed: {primary_err}. Attempting one repair/fallback.")
            # Attempt one repair if we received output, else fallback
            try:
                repair_prompt = user_prompt + "\n\n" + REPAIR_PROMPT_TEMPLATE.format(
                    error_message=str(primary_err),
                    previous_output=locals().get("raw_text", "No response"),
                )
                repaired_text = await self._call_model(repair_prompt)
                return self._parse_and_validate(repaired_text, operator_notes, battery_capacity_kwh)
            except Exception as repair_err:
                logger.error(f"Repair attempt also failed: {repair_err}. Using fallback parser for resilience.")
                return fallback_parse_all(operator_notes, battery_capacity_kwh)

    async def _call_model(self, prompt: str) -> str:
        """Invokes the configured model provider via REST API."""
        if config.LLM_PROVIDER == "gemini" and config.GEMINI_API_KEY:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{config.GEMINI_MODEL}:generateContent?key={config.GEMINI_API_KEY}"
            payload = {
                "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "temperature": 0.0,
                },
            }
            resp = await self.client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("Gemini returned empty candidates")
            return candidates[0]["content"]["parts"][0]["text"]

        elif config.LLM_PROVIDER in ("openai", "groq"):
            api_key = config.GROQ_API_KEY if config.LLM_PROVIDER == "groq" else config.OPENAI_API_KEY
            base_url = "https://api.groq.com/openai/v1" if config.LLM_PROVIDER == "groq" else config.OPENAI_BASE_URL
            model = config.GROQ_MODEL if config.LLM_PROVIDER == "groq" else config.OPENAI_MODEL

            headers = {"Authorization": f"Bearer {api_key}"}
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.0,
                "response_format": {"type": "json_object"},
            }
            resp = await self.client.post(f"{base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

        raise ValueError(f"Unsupported or unconfigured LLM provider: {config.LLM_PROVIDER}")

    def _parse_and_validate(
        self,
        raw_text: str,
        operator_notes: list[str],
        battery_capacity_kwh: float,
    ) -> list[DirectiveInterpretation]:
        """Parses model JSON and converts to validated DirectiveInterpretation objects."""
        clean_text = raw_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()

        data = json.loads(clean_text)
        output = LLMInterpretationOutput.model_validate(data)

        # Check that we have exactly N items
        if len(output.directive_interpretation) != len(operator_notes):
            raise ValueError(
                f"Expected {len(operator_notes)} interpretations, got {len(output.directive_interpretation)}"
            )

        return output.directive_interpretation
