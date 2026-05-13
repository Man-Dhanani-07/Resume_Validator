import json
import logging
from typing import Optional, Dict, Any, List

from .database import SessionLocal
from .models import WorkflowRun, ResumeUpload, AgentResult

logger = logging.getLogger(__name__)


# ==========================================================
# HELPERS
# ==========================================================

def _safe_json(value, default=None):
    """Safely serialize value to JSON string for Text columns."""
    if value is None:
        return json.dumps(default) if default is not None else None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except (TypeError, ValueError):
        return str(value)


def _extract_from_explainability(explainability_raw):
    """Pull fraud_score, total_penalty, risk_reasons from explainability JSON."""
    if not explainability_raw:
        return {}
    try:
        data = (
            json.loads(explainability_raw)
            if isinstance(explainability_raw, str)
            else explainability_raw
        )
        return {
            "fraud_score":   data.get("fraud_score"),
            "total_penalty": data.get("total_penalty"),
            "risk_reasons":  json.dumps(data.get("risk_reasons", [])),
        }
    except Exception:
        return {}


# ==========================================================
# WorkflowRun — unchanged
# ==========================================================

def save_workflow(state: dict):
    db = SessionLocal()
    try:
        expl_raw    = state.get("explainability")
        expl_extras = _extract_from_explainability(expl_raw)

        run = WorkflowRun(
            document_text    = state.get("document_text"),
            doc_type         = state.get("doc_type"),
            processed_data   = _safe_json(state.get("processed_data", {})),
            validated_data   = _safe_json(state.get("validated_data", {})),
            validation       = state.get("validation"),
            structural_score = state.get("structural_score"),
            llm_score        = state.get("llm_score"),
            risk_score       = state.get("risk_score"),
            risk_level       = state.get("risk_level"),
            final_confidence = state.get("final_confidence"),
            explainability   = _safe_json(expl_raw),
            decision         = state.get("decision"),
            ai_summary       = state.get("ai_summary"),
            fraud_score      = state.get("fraud_score")   or expl_extras.get("fraud_score"),
            quality_score    = state.get("quality_score"),
            total_penalty    = state.get("total_penalty") or expl_extras.get("total_penalty"),
            risk_reasons     = _safe_json(
                state.get("risk_reasons") or expl_extras.get("risk_reasons")
            ),
            integrity_report = _safe_json(state.get("integrity_report")),
            llm_full_report  = _safe_json(state.get("llm_full_report")),
        )
        db.add(run)
        db.commit()

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


# ==========================================================
# ResumeUpload CRUD
# ==========================================================

def save_resume_upload(
    document_text:   str,
    filename:        Optional[str] = None,
    job_description: Optional[str] = None,
) -> int:
    """
    Save uploaded PDF text to DB. Returns new resume_id.
    Called by: POST /resume/upload
    """
    db = SessionLocal()
    try:
        upload = ResumeUpload(
            document_text   = document_text,
            filename        = filename,
            job_description = job_description,
        )
        db.add(upload)
        db.commit()
        db.refresh(upload)
        logger.info("save_resume_upload: saved resume_id=%d (%s)", upload.id, filename)
        return upload.id
    except Exception as e:
        db.rollback()
        logger.error("save_resume_upload: failed — %s", e)
        raise e
    finally:
        db.close()


def get_resume_by_id(resume_id: int) -> Optional[Dict[str, Any]]:
    """
    Load resume row from DB. Returns dict with all fields, or None.
    Includes 'id' field so agents can use it as cache key.
    Called by: every agent endpoint.
    """
    db = SessionLocal()
    try:
        row = db.query(ResumeUpload).filter(ResumeUpload.id == resume_id).first()
        if not row:
            logger.warning("get_resume_by_id: resume_id=%d not found", resume_id)
            return None
        return {
            "id":              row.id,           # agents use this as cache key
            "resume_id":       row.id,
            "document_text":   row.document_text,
            "job_description": row.job_description,
            "filename":        row.filename,
        }
    finally:
        db.close()


# ==========================================================
# Extracted Data Cache
# ==========================================================
# These two functions power the "extract once, reuse everywhere"
# pattern in agents.py (_get_validated).
#
# Flow:
#   1. First agent call → get_extracted_data() returns None (miss)
#   2. agents.py runs LLM extraction → save_extracted_data() stores result
#   3. All subsequent agents → get_extracted_data() returns cached dict (hit)
#   Result: 16 agents = 1 LLM call instead of 16.
# ==========================================================

def save_extracted_data(resume_id: int, validated: dict) -> None:
    """
    Cache the fully validated resume JSON against resume_id.
    Stored in extracted_data column of resume_uploads table.
    """
    db = SessionLocal()
    try:
        row = db.query(ResumeUpload).filter(ResumeUpload.id == resume_id).first()
        if row:
            row.extracted_data = json.dumps(validated)
            db.commit()
            logger.info("save_extracted_data: cached for resume_id=%d", resume_id)
        else:
            logger.warning("save_extracted_data: resume_id=%d not found", resume_id)
    except Exception as e:
        db.rollback()
        logger.error("save_extracted_data: failed — %s", e)
        raise e
    finally:
        db.close()


def get_extracted_data(resume_id: int) -> Optional[dict]:
    """
    Return cached extracted data for resume_id, or None on cache miss.
    None = not yet extracted → caller must run LLM extraction.
    dict = previously extracted → skip LLM, use this directly.
    """
    db = SessionLocal()
    try:
        row = db.query(ResumeUpload).filter(ResumeUpload.id == resume_id).first()
        if row and row.extracted_data:
            logger.info("get_extracted_data: cache HIT for resume_id=%d", resume_id)
            return json.loads(row.extracted_data)
        logger.info("get_extracted_data: cache MISS for resume_id=%d", resume_id)
        return None
    except Exception as e:
        logger.error("get_extracted_data: failed — %s", e)
        return None
    finally:
        db.close()


# ==========================================================
# AgentResult CRUD
# ==========================================================

def save_agent_result(
    resume_id:   int,
    agent_name:  str,
    result:      Optional[Dict[str, Any]],
    status:      str = "success",
    error:       Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> int:
    """
    Save a single agent's output to agent_results table.
    Returns new AgentResult row ID.
    Called by: _run_agent() wrapper in agents.py after every agent run.
    """
    db = SessionLocal()
    try:
        row = AgentResult(
            resume_id   = resume_id,
            agent_name  = agent_name,
            result      = _safe_json(result),
            status      = status,
            error       = error,
            duration_ms = duration_ms,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        logger.info(
            "save_agent_result: agent=%s resume_id=%d status=%s duration=%dms",
            agent_name, resume_id, status, duration_ms or 0
        )
        return row.id
    except Exception as e:
        db.rollback()
        logger.error("save_agent_result: failed — %s", e)
        raise e
    finally:
        db.close()


def get_agent_results(resume_id: int) -> List[dict]:
    """
    Return all agent results for a resume, newest first.
    Called by: GET /agent/results/{resume_id}
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(AgentResult)
            .filter(AgentResult.resume_id == resume_id)
            .order_by(AgentResult.created_at.desc())
            .all()
        )
        return [
            {
                "id":          r.id,
                "agent_name":  r.agent_name,
                "result":      json.loads(r.result) if r.result else None,
                "status":      r.status,
                "error":       r.error,
                "duration_ms": r.duration_ms,
                "created_at":  str(r.created_at),
            }
            for r in rows
        ]
    finally:
        db.close()     

        