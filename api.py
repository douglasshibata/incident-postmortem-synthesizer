import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

try:
    from .tasks import ingest_incident_logs, get_incident_report
except ImportError:
    from tasks import ingest_incident_logs, get_incident_report

router = APIRouter()

class PagerDutyWebhookPayload(BaseModel):
    event_type: str = Field(..., json_schema_extra={"example": "incident.resolved"})
    incident_id: Optional[str] = None
    title: Optional[str] = "Production Outage"
    raw_logs: Optional[List[str]] = Field(default_factory=list)

class IncidentTriggerRequest(BaseModel):
    title: str = Field(..., json_schema_extra={"example": "Database Primary Failover Latency Spike"})
    raw_logs: List[str] = Field(..., json_schema_extra={"example": ["2026-03-29 10:15:00 [ERROR] Connection timeout to master-db", "2026-03-29 10:15:02 [FATAL] 500 Internal Server Error user_id=usr_9988"]})

@router.post("/webhooks/pagerduty", status_code=202)
def handle_pagerduty_webhook(payload: Dict[str, Any], background_tasks: BackgroundTasks):
    """Webhook ingestion endpoint receiving PagerDuty incident resolved payload."""
    event_type = payload.get("event", {}).get("event_type", payload.get("event_type", "incident.resolved"))

    incident_data = payload.get("event", {}).get("data", {})
    incident_id = incident_data.get("id", payload.get("incident_id", str(uuid.uuid4())))
    title = incident_data.get("title", payload.get("title", "PagerDuty Production Incident"))

    raw_logs = payload.get("raw_logs", [
        f"2026-03-29 10:00:00 [INFO] Incident triggered: {title}",
        f"2026-03-29 10:05:00 [ERROR] 503 Service Unavailable user_id=usr_1234 ip=192.168.1.50",
        f"2026-03-29 10:08:00 [FATAL] Database connection pool exhausted for customer_email=alice@company.com",
        f"2026-03-29 10:15:00 [INFO] Incident resolved by SRE on-call"
    ])

    background_tasks.add_task(ingest_incident_logs, incident_id, title, raw_logs)

    return {
        "status": "ACCEPTED",
        "message": "PagerDuty resolved webhook received and post-mortem pipeline dispatched.",
        "incident_id": incident_id,
        "event_type": event_type
    }

@router.post("/incidents/trigger", status_code=202)
def trigger_incident_postmortem(request: IncidentTriggerRequest, background_tasks: BackgroundTasks):
    """Direct trigger endpoint for custom incident post-mortem generation."""
    incident_id = str(uuid.uuid4())
    background_tasks.add_task(ingest_incident_logs, incident_id, request.title, request.raw_logs)

    return {
        "status": "ACCEPTED",
        "message": "Incident log pipeline triggered.",
        "incident_id": incident_id,
        "title": request.title
    }

@router.get("/incidents/{incident_id}")
def fetch_incident_postmortem(incident_id: str):
    """Retrieves post-mortem processing status and report for given incident_id."""
    report = get_incident_report(incident_id)
    if report.get("status") == "NOT_FOUND":
        raise HTTPException(status_code=404, detail=f"Incident report '{incident_id}' not found or still processing.")
    return report
