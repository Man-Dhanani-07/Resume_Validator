from typing import TypedDict, Dict, Any, List, Optional


class WorkflowState(TypedDict, total=False):

    # ── Identity ────────────────────────────────────────────────
    # Added: resume_id links every agent run back to the uploaded resume
    # in the DB. Without this, agents have no way to load the right resume.
    resume_id: int

    # ── Input ───────────────────────────────────────────────────
    document_text: str

    # Added: job_description was used in risk.py but never formally
    # part of state — making it official so any agent can access it.
    job_description: Optional[str]

    # ── Classification ──────────────────────────────────────────
    doc_type: str

    # ── Extraction & Validation ─────────────────────────────────
    processed_data: Dict[str, Any]
    validation: str
    validated_data: Dict[str, Any]

    # ── Risk Layer ───────────────────────────────────────────────
    structural_score: int
    llm_score: int
    risk_score: int
    risk_level: str
    final_confidence: int
    explainability: str        # JSON string (was List[str] — fixed to match risk.py)
    decision: str
    ai_summary: str

    # ── Per-Agent Results ────────────────────────────────────────
    # Added: each on-demand agent writes its output here.
    # Key = agent name (e.g. "gaps"), Value = result dict.
    # This way the API response is clean and the full pipeline
    # state is never mixed with individual agent results.
    agent_results: Dict[str, Any]

    # Added: tracks which agent is currently running — useful for
    # logging and for the DB to know which AgentResult row to create.
    agent_name: str