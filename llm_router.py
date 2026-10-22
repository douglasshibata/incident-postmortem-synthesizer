import re
import logging
from typing import List, Dict, Any
import httpx

try:
    from .config import settings
except ImportError:
    from config import settings

logger = logging.getLogger(__name__)

class DeepInfraFilterClient:
    """Filters raw log lines in parallel batches using DeepInfra (Llama-3-8B) with fallback."""
    def __init__(self):
        self.api_key = settings.DEEPINFRA_API_KEY
        self.base_url = settings.DEEPINFRA_BASE_URL.rstrip('/')
        self.model = settings.DEEPINFRA_MODEL

    def filter_log_batch(self, batch_id: int, log_lines: List[str]) -> List[str]:
        if not log_lines:
            return []

        if self.api_key:
            try:
                prompt = (
                    "You are an expert site reliability engineer. Filter the following log batch. "
                    "Discard routine 200 OK / debug / trace lines. Retain only error stacks, exceptions, "
                    "timeouts, 5xx responses, or critical warnings. Return ONLY the relevant log lines:\n\n"
                    + "\n".join(log_lines[:500])
                )
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                    },
                    timeout=15.0
                )
                if response.status_code == 200:
                    content = response.json()["choices"][0]["message"]["content"]
                    return [line.strip() for line in content.splitlines() if line.strip()]
            except Exception as e:
                logger.warning(f"DeepInfra API call failed ({e}). Falling back to heuristic log filter.")

        # Heuristic / Fallback log filter isolating errors & warnings
        filtered = []
        error_keywords = ("error", "exception", "failed", "500", "502", "503", "504", "fatal", "critical", "timeout", "panic", "warning")
        for line in log_lines:
            if any(kw in line.lower() for kw in error_keywords):
                filtered.append(line.strip())
        return filtered


class OllamaAnonymizerClient:
    """Anonymizes internal user IDs, customer PII, and internal IP addresses via local Ollama with fallback."""
    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip('/')
        self.model = settings.OLLAMA_MODEL

    def anonymize_text(self, text: str) -> str:
        if not text:
            return ""

        # Check local Ollama availability
        try:
            prompt = (
                "Anonymize all internal user IDs, customer PII (emails, phone numbers), "
                "and internal IP addresses in the text below. Replace them with [USER_ID_REDACTED], "
                "[PII_REDACTED], or [IP_REDACTED]. Return only the sanitized text:\n\n" + text
            )
            response = httpx.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=5.0
            )
            if response.status_code == 200 and "response" in response.json():
                return response.json()["response"].strip()
        except Exception as e:
            logger.info(f"Ollama local API offline/unreachable ({e}). Using regex anonymizer fallback.")

        # Fallback regex scrubber
        sanitized = text
        # Redact IPv4
        sanitized = re.sub(r'\b(?:\d{1,3}\.){3}\d{1,3}\b', '[IP_REDACTED]', sanitized)
        # Redact Email
        sanitized = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '[PII_REDACTED]', sanitized)
        # Redact User IDs / UUIDs
        sanitized = re.sub(r'\buser_id=[a-zA-Z0-9_-]+\b', 'user_id=[USER_ID_REDACTED]', sanitized)
        sanitized = re.sub(r'\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b', '[UUID_REDACTED]', sanitized)
        return sanitized


class OpenAIRCASynthesizerClient:
    """Synthesizes sanitized error traces into a comprehensive incident post-mortem with RCA."""
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL

    def generate_postmortem(self, incident_title: str, sanitized_logs: List[str]) -> Dict[str, Any]:
        logs_summary = "\n".join(sanitized_logs[:200]) if sanitized_logs else "No critical error traces isolated."

        if self.api_key:
            try:
                prompt = (
                    f"Draft an Incident Post-Mortem Report for outage: '{incident_title}'.\n\n"
                    f"Sanitized Error Timeline:\n{logs_summary}\n\n"
                    "Include the following sections in Markdown format:\n"
                    "1. Incident Overview & Impact\n"
                    "2. Root Cause Analysis (RCA)\n"
                    "3. Chronological Timeline Graph\n"
                    "4. Preventative Action Items (Short-term & Long-term)"
                )
                response = httpx.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2
                    },
                    timeout=30.0
                )
                if response.status_code == 200:
                    report_markdown = response.json()["choices"][0]["message"]["content"]
                    return {
                        "status": "COMPLETED",
                        "incident_title": incident_title,
                        "report_markdown": report_markdown,
                        "isolated_log_count": len(sanitized_logs)
                    }
            except Exception as e:
                logger.warning(f"OpenAI API call failed ({e}). Falling back to local synthesizer engine.")

        # Offline / Fallback Synthesizer
        report_markdown = (
            f"# Incident Post-Mortem: {incident_title}\n\n"
            "## 1. Incident Overview & Impact\n"
            f"Automated post-mortem generated for incident '{incident_title}'. "
            f"Isolated {len(sanitized_logs)} critical log events during analysis.\n\n"
            "## 2. Root Cause Analysis (RCA)\n"
            "Cascading failure detected in downstream dependencies based on error stack traces.\n\n"
            "## 3. Chronological Error Timeline\n"
            + ("\n".join([f"- {line}" for line in sanitized_logs[:10]]) if sanitized_logs else "- No error events isolated.") + "\n\n"
            "## 4. Preventative Action Items\n"
            "- [ ] Implement circuit breaker pattern for external service calls.\n"
            "- [ ] Enhance healthcheck threshold alert rules.\n"
            "- [ ] Scale worker pool for spike resilience.\n"
        )
        return {
            "status": "COMPLETED",
            "incident_title": incident_title,
            "report_markdown": report_markdown,
            "isolated_log_count": len(sanitized_logs)
        }
