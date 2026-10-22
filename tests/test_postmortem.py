import pytest
from fastapi.testclient import TestClient

try:
    from ..main import app
    from ..llm_router import DeepInfraFilterClient, OllamaAnonymizerClient, OpenAIRCASynthesizerClient
    from ..tasks import filter_log_batch, anonymize_filtered_logs, synthesize_postmortem_chord, ingest_incident_logs, get_incident_report
except ImportError:
    from main import app
    from llm_router import DeepInfraFilterClient, OllamaAnonymizerClient, OpenAIRCASynthesizerClient
    from tasks import filter_log_batch, anonymize_filtered_logs, synthesize_postmortem_chord, ingest_incident_logs, get_incident_report

client = TestClient(app)

def test_deepinfra_filter_fallback():
    filter_client = DeepInfraFilterClient()
    logs = [
        "2026-03-29 10:00:00 [DEBUG] Health check OK",
        "2026-03-29 10:01:00 [ERROR] Connection refused to database",
        "2026-03-29 10:02:00 [INFO] User logged in",
        "2026-03-29 10:03:00 [FATAL] 503 Gateway Timeout"
    ]
    filtered = filter_client.filter_log_batch(0, logs)
    assert len(filtered) == 2
    assert "ERROR" in filtered[0]
    assert "FATAL" in filtered[1]

def test_ollama_anonymizer_fallback():
    anonymizer = OllamaAnonymizerClient()
    raw_text = "User user_id=usr_9988 with ip=192.168.1.100 and email=admin@company.com failed"
    anonymized = anonymizer.anonymize_text(raw_text)
    assert "[IP_REDACTED]" in anonymized
    assert "[PII_REDACTED]" in anonymized
    assert "[USER_ID_REDACTED]" in anonymized

def test_openai_rca_synthesizer():
    synthesizer = OpenAIRCASynthesizerClient()
    report = synthesizer.generate_postmortem("Database Outage", ["2026-03-29 [ERROR] Connection timeout"])
    assert report["status"] == "COMPLETED"
    assert "Database Outage" in report["report_markdown"]
    assert "Root Cause Analysis" in report["report_markdown"]

def test_full_pipeline_ingestion():
    raw_logs = [
        "2026-03-29 10:00:00 [DEBUG] Polling queue...",
        "2026-03-29 10:05:00 [ERROR] HTTP 500 internal error user_id=usr_1234 ip=10.0.0.1",
        "2026-03-29 10:06:00 [FATAL] Stackoverflow in worker thread"
    ]
    result = ingest_incident_logs("inc_test_123", "Payment Gateway Timeout", raw_logs)
    assert result["status"] == "COMPLETED"
    assert result["incident_id"] == "inc_test_123"

    retrieved = get_incident_report("inc_test_123")
    assert retrieved["status"] == "COMPLETED"

def test_pagerduty_webhook_endpoint():
    payload = {
        "event_type": "incident.resolved",
        "incident_id": "pd_inc_999",
        "title": "API Gateway Latency Spike",
        "raw_logs": [
            "2026-03-29 11:00:00 [ERROR] 504 Gateway Timeout ip=172.16.0.1"
        ]
    }
    response = client.post("/webhooks/pagerduty", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "ACCEPTED"
    assert data["incident_id"] == "pd_inc_999"

def test_incident_trigger_and_get_report():
    trigger_payload = {
        "title": "Redis Cluster Memory Outage",
        "raw_logs": [
            "2026-03-29 12:00:00 [FATAL] OOMKilled process redis-server user_id=usr_555"
        ]
    }
    response = client.post("/incidents/trigger", json=trigger_payload)
    assert response.status_code == 202
    incident_id = response.json()["incident_id"]

    # Fetch report
    report_res = client.get(f"/incidents/{incident_id}")
    assert report_res.status_code == 200
    report_data = report_res.json()
    assert report_data["status"] == "COMPLETED"
    assert "Redis Cluster Memory Outage" in report_data["report_markdown"]
