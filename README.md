# 🚨 Automated Incident Post-Mortem & Root-Cause Synthesizer

Production outages require rapid root-cause analysis (RCA), timeline reconstruction, and preventative action items.
This distributed system orchestrates an asynchronous Celery and Redis log extraction pipeline with multi-provider LLM routing:

1. **FastAPI Webhook Gateway:** Ingests PagerDuty "Resolved" webhooks or direct log submission requests.
2. **Redis Log Storage & Fan-Out Chord:** Splitting high-volume raw logs into 500-line batches.
3. **Multi-Provider LLM Routing Tier:**
   - **DeepInfra (Meta-Llama-3-8B):** Parallel high-throughput batch filtering, discarding ~95% routine logs to isolate error traces.
   - **Ollama (Local Mistral):** Scans and anonymizes customer PII, internal user IDs, and internal IP addresses before cloud processing.
   - **OpenAI (GPT-4o):** Synthesizes the clean error timeline into an incident post-mortem with RCA, timeline graph, and action items.

---

## 🛠️ Architecture Overview

```text
[PagerDuty Webhook / API]
           │
           ▼
 [FastAPI Gateway] ──► [Redis Buffer]
                               │
                               ▼
                   [Celery Pipeline Orchestrator]
                               │
              ┌────────────────┴────────────────┐
              ▼                                 ▼
   [DeepInfra Filter Workers]      [Ollama Anonymizer Worker]
   (Meta-Llama-3-8B 500-line)       (Local Zero-Trust PII Redaction)
              │                                 │
              └────────────────┬────────────────┘
                               ▼
                  [OpenAI GPT-4o Synthesizer]
                               │
                               ▼
                  [Incident Post-Mortem Report]
```

---

## 🚀 Quickstart & Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run pytest test suite
PYTHONPATH=. pytest tests/test_postmortem.py
```
