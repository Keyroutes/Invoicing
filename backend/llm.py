import os
import json
import logging
import httpx

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "llama-3.3-70b-versatile"


def llm_chat(messages, temperature=0.3, max_tokens=1024):
    if not GROQ_API_KEY:
        return None
    try:
        resp = httpx.post(
            f"{GROQ_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
            timeout=30,
        )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        logger.error("Groq API error %d: %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.error("Groq call failed: %s", e)
    return None


def llm_json(messages, temperature=0.2):
    text = llm_chat(messages, temperature=temperature, max_tokens=2048)
    if not text:
        return None
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except json.JSONDecodeError:
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            logger.error("Failed to parse LLM JSON: %s", text[:200])
            return None
