from fastapi import FastAPI

try:
    from .api import router
    from .config import settings
except ImportError:
    from api import router
    from config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Automated Incident Post-Mortem & Root-Cause Synthesizer using Celery, Redis, and Multi-Provider LLMs",
    version="1.0.0"
)

app.include_router(router)

@app.get("/")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "status": "HEALTHY",
        "endpoints": {
            "webhook_pagerduty": "POST /webhooks/pagerduty",
            "trigger_incident": "POST /incidents/trigger",
            "get_postmortem": "GET /incidents/{incident_id}"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
