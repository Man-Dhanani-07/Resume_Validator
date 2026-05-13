import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import Base, engine
from app.routers.upload import router as upload_router
from app.routers.agents import router as agents_router

# ==========================================================
# LOGGING
# ==========================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ==========================================================
# DB INIT — creates all tables on startup
# ==========================================================
# Creates: workflow_runs, resume_uploads, agent_results
# Safe to call every time — only creates tables that don't exist yet.

Base.metadata.create_all(bind=engine)
logger.info("Database tables initialized")

# ==========================================================
# FASTAPI APP
# ==========================================================

app = FastAPI(
    title="Resume Validation API",
    description=(
        "Upload a resume PDF once, then run any agent independently.\n\n"
        "**Workflow:**\n"
        "1. `POST /resume/upload` → get `resume_id`\n"
        "2. `POST /agent/{agent-name}` with `resume_id` → get result\n\n"
        "**Available Agents:**\n"
        "- `/agent/classify` — Is this document a resume?\n"
        "- `/agent/extract` — Extract all fields into structured JSON\n"
        "- `/agent/validate` — Validate schema & completeness\n"
        "- `/agent/keywords` — Suspicious keyword detection\n"
        "- `/agent/gaps` — Employment gap detection\n"
        "- `/agent/overlaps` — Overlapping job dates\n"
        "- `/agent/academics` — Impossible academic timelines\n"
        "- `/agent/percentages` — Invalid percentage flags\n"
        "- `/agent/future-dates` — Future date flags\n"
        "- `/agent/skills` — Skills presence check\n"
        "- `/agent/tenure` — Job-hopping detection\n"
        "- `/agent/duplicates` — Duplicate experience entries\n"
        "- `/agent/seniority` — Seniority vs experience mismatch\n"
        "- `/agent/integrity` — Full structural integrity engine\n"
        "- `/agent/llm-score` — LLM semantic quality scoring\n"
        "- `/agent/risk` — Full risk fusion engine\n"
        "- `/agent/full-pipeline` — Run complete LangGraph pipeline\n"
    ),
    version="2.0.0",
)

# ==========================================================
# CORS — allows frontend to call the API from any origin
# Restrict origins in production to your actual frontend URL
# ==========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================================
# ROUTERS
# ==========================================================

app.include_router(upload_router)   # POST /resume/upload
app.include_router(agents_router)   # POST /agent/* + GET /agent/results/*


# ==========================================================
# HEALTH CHECK
# ==========================================================

@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "service": "Resume Validation API v2.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}