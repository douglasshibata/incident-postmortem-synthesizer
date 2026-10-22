import json
import logging
from typing import List, Dict, Any
import redis

try:
    from .config import settings
    from .llm_router import DeepInfraFilterClient, OllamaAnonymizerClient, OpenAIRCASynthesizerClient
except ImportError:
    from config import settings
    from llm_router import DeepInfraFilterClient, OllamaAnonymizerClient, OpenAIRCASynthesizerClient

logger = logging.getLogger(__name__)

# Redis client for raw log dumping & results
try:
    redis_client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception:
    redis_client = None

# Store in-memory fallback cache when Redis is unavailable
IN_MEMORY_INCIDENTS: Dict[str, Dict[str, Any]] = {}

def filter_log_batch(batch_id: int, log_lines: List[str]) -> List[str]:
    """Worker task: filters 500-line log batch using DeepInfra (Llama-3-8B)."""
    filter_client = DeepInfraFilterClient()
    return filter_client.filter_log_batch(batch_id, log_lines)

def anonymize_filtered_logs(filtered_logs: List[str]) -> List[str]:
    """Worker task: scrubs PII, user IDs, and IPs using Ollama (Local)."""
    anonymizer = OllamaAnonymizerClient()
    sanitized = []
    for line in filtered_logs:
        sanitized_line = anonymizer.anonymize_text(line)
        if sanitized_line:
            sanitized.append(sanitized_line)
    return sanitized

def synthesize_postmortem_chord(incident_id: str, incident_title: str, anonymized_chunks: List[List[str]]) -> Dict[str, Any]:
    """Chord callback task: synthesizes anonymized logs into an RCA post-mortem report using OpenAI."""
    flat_logs = []
    for chunk in anonymized_chunks:
        flat_logs.extend(chunk)

    synthesizer = OpenAIRCASynthesizerClient()
    result = synthesizer.generate_postmortem(incident_title, flat_logs)
    result["incident_id"] = incident_id

    # Store result in Redis or memory
    serialized = json.dumps(result)
    if redis_client:
        try:
            redis_client.set(f"postmortem:{incident_id}", serialized)
        except Exception as e:
            logger.warning(f"Failed to write postmortem result to Redis ({e}). Using in-memory fallback.")
            IN_MEMORY_INCIDENTS[incident_id] = result
    else:
        IN_MEMORY_INCIDENTS[incident_id] = result

    return result

def ingest_incident_logs(incident_id: str, incident_title: str, raw_logs: List[str]) -> Dict[str, Any]:
    """Ingests raw incident logs, chunks them into 500-line batches, and executes the fan-out pipeline."""
    chunk_size = settings.LOG_CHUNK_SIZE
    chunks = [raw_logs[i:i + chunk_size] for i in range(0, len(raw_logs), chunk_size)] if raw_logs else [[]]

    # Process chunks parallel/sequentially
    anonymized_chunks = []
    for idx, chunk in enumerate(chunks):
        filtered = filter_log_batch(idx, chunk)
        anonymized = anonymize_filtered_logs(filtered)
        anonymized_chunks.append(anonymized)

    final_report = synthesize_postmortem_chord(incident_id, incident_title, anonymized_chunks)
    return final_report

def get_incident_report(incident_id: str) -> Dict[str, Any]:
    """Retrieves post-mortem report by incident ID."""
    if redis_client:
        try:
            data = redis_client.get(f"postmortem:{incident_id}")
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning(f"Failed to read from Redis ({e}). Checking in-memory store.")

    if incident_id in IN_MEMORY_INCIDENTS:
        return IN_MEMORY_INCIDENTS[incident_id]

    return {"status": "NOT_FOUND", "incident_id": incident_id}
