import json
import logging
import time
from typing import Optional, Dict, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.repository import (
    get_resume_by_id,
    save_agent_result,
    get_agent_results,
    # These two are added to repository.py (see instructions below)
    save_extracted_data,
    get_extracted_data,
)
from app.graph.workflow import workflow

from app.agents.classifier import classify_document
from app.agents.extractor import extract_document_fields
from app.agents.validator import validate_resume
from app.agents.resume_judge import llm_resume_verdict
from app.agents.risk import calculate_risk
from app.agents.resume_integrity import (
    detect_keyword_penalties,
    detect_employment_gaps,
    detect_overlapping_jobs,
    detect_impossible_academics,
    detect_invalid_percentages,
    detect_future_dates,
    detect_empty_skills,
    detect_short_tenure_pattern,
    detect_duplicate_companies,
    detect_seniority_mismatch,
    resume_integrity_engine,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/agent", tags=["Agents"])


# ==========================================================
# REQUEST MODEL
# ==========================================================

class AgentRequest(BaseModel):
    resume_id: int
    job_description: Optional[str] = None
    force_reextract: bool = False   # pass true to force a fresh LLM extraction


# ==========================================================
# HELPERS
# ==========================================================

def _load_resume(resume_id: int) -> Dict[str, Any]:
    data = get_resume_by_id(resume_id)
    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"Resume id={resume_id} not found. Please upload first."
        )
    return data


def _is_null_entry(entry: dict) -> bool:
    """True if all meaningful fields in an entry are None/empty."""
    if not isinstance(entry, dict):
        return True
    skip = {"highlights", "impact_metrics", "technologies", "impact", "links", "description"}
    meaningful = {k: v for k, v in entry.items() if k not in skip}
    return all(v is None or v == "" or v == [] for v in meaningful.values())


def _get_validated(resume_data: dict, force: bool = False) -> Optional[dict]:
    """
    EXTRACT ONCE, CACHE IN DB, REUSE FOR ALL AGENTS.

    Flow:
      1. Check DB for cached extracted data for this resume_id
      2. If found (and not force_reextract) → return cached result immediately
      3. If not found → run LLM extraction + Pydantic validation
      4. Save result to DB so every subsequent agent skips the LLM call
      5. Return validated dict

    Why this matters:
      Old approach: every agent called _extract_and_validate() independently.
      Running 16 agents = 16 LLM extraction calls on the same resume.
      New approach: 1 extraction call, 15 cache hits. 
      Speedup on "Run All": from ~400s to ~30s.
    """
    resume_id = resume_data["id"]

    # ── Step 1: Try cache ────────────────────────────────────────────────
    if not force:
        cached = get_extracted_data(resume_id)
        if cached:
            logger.info(
                "_get_validated: resume_id=%d — cache HIT, skipping LLM extraction",
                resume_id
            )
            return cached

    # ── Step 2: Cache miss — run LLM extraction ──────────────────────────
    logger.info(
        "_get_validated: resume_id=%d — cache MISS, running LLM extraction",
        resume_id
    )

    try:
        extracted_str = extract_document_fields(resume_data["document_text"])
    except Exception as e:
        logger.error("_get_validated: extraction crashed — %s", e)
        return None

    try:
        validated, error = validate_resume(extracted_str)
    except Exception as e:
        logger.error("_get_validated: validation crashed — %s", e)
        return None

    if validated is None:
        logger.warning("_get_validated: hard validation failure — %s", error)
        return None

    if error:
        logger.info("_get_validated: soft pass with warning — %s", error)

    # ── Step 3: Filter null-only placeholder entries ─────────────────────
    # LLM always returns [{company:null, position:null}] for empty sections.
    # Filter these so counts are accurate.
    for section in ("experience", "education", "projects", "certifications"):
        entries  = validated.get(section, [])
        filtered = [e for e in entries if not _is_null_entry(e)]
        if len(filtered) != len(entries):
            logger.info(
                "_get_validated: filtered %d null entries from '%s'",
                len(entries) - len(filtered), section
            )
        validated[section] = filtered

    # ── Step 4: Save to DB cache ─────────────────────────────────────────
    try:
        save_extracted_data(resume_id, validated)
        logger.info(
            "_get_validated: resume_id=%d cached — exp=%d edu=%d skills=%d proj=%d",
            resume_id,
            len(validated.get("experience", [])),
            len(validated.get("education", [])),
            len((validated.get("skills") or {}).get("technical", [])),
            len(validated.get("projects", [])),
        )
    except Exception as e:
        # Cache save failure is non-fatal — agent still works, just won't cache
        logger.warning("_get_validated: cache save failed (non-fatal) — %s", e)

    return validated


def _run_agent(resume_id: int, agent_name: str, agent_fn):
    start = time.time()
    try:
        result      = agent_fn()
        duration_ms = int((time.time() - start) * 1000)
        save_agent_result(
            resume_id=resume_id,
            agent_name=agent_name,
            result=result,
            status="success",
            duration_ms=duration_ms,
        )
        return {
            "resume_id":   resume_id,
            "agent":       agent_name,
            "status":      "success",
            "duration_ms": duration_ms,
            "result":      result,
        }
    except HTTPException:
        raise
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        logger.error("_run_agent: %s crashed — %s", agent_name, e, exc_info=True)
        save_agent_result(
            resume_id=resume_id,
            agent_name=agent_name,
            result=None,
            status="error",
            error=str(e),
            duration_ms=duration_ms,
        )
        raise HTTPException(
            status_code=500,
            detail=f"{agent_name} failed: {str(e)}"
        )


def _risk_label(penalty: int, low: int = 10, high: int = 30) -> str:
    return "HIGH" if penalty >= high else "MEDIUM" if penalty >= low else "LOW"


# ==========================================================
# AGENT 1 — CLASSIFY
# Does not need extraction — works on raw text
# ==========================================================

@router.post("/classify")
def agent_classify(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        doc_type = classify_document(resume_data["document_text"])
        return {"doc_type": doc_type, "is_resume": doc_type == "resume"}

    return _run_agent(req.resume_id, "classify", run)

# ==========================================================
# AGENT 2 — EXTRACT
# Triggers the extraction + caches result.
# All subsequent agents will use the cache.
# ==========================================================

@router.post("/extract")
def agent_extract(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        # force=True if user explicitly wants fresh extraction
        validated = _get_validated(resume_data, force=req.force_reextract)

        if not validated:
            return {"error": "Extraction failed — LLM could not parse resume."}

        # Return both full data + summary counts for UI
        exp    = validated.get("experience", [])
        edu    = validated.get("education", [])
        proj   = validated.get("projects", [])
        skills = validated.get("skills", {})
        tech   = skills.get("technical", []) if isinstance(skills, dict) else []
        meta   = validated.get("metadata", {})
        conf   = meta.get("confidence_score", 0) if isinstance(meta, dict) else 0

        return {
            "extracted_data":   validated,
            "experience_count": len(exp),
            "education_count":  len(edu),
            "skills_count":     len(tech),
            "projects_count":   len(proj),
            "confidence_score": conf,
            "cached":           not req.force_reextract,
        }

    return _run_agent(req.resume_id, "extract", run)


# ==========================================================
# AGENT 3 — VALIDATE
# Uses cached extraction — no extra LLM call
# ==========================================================

@router.post("/validate")
def agent_validate(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)

        if not validated:
            return {"status": "failed", "error": "Extraction failed."}

        meta = validated.get("_validation_meta", {})
        return {
            "status":                "passed",
            "completeness_score":    meta.get("completeness_score"),
            "field_presence":        meta.get("field_presence"),
            "consistency_warnings":  meta.get("consistency_warnings", []),
            "extraction_confidence": meta.get("extraction_confidence"),
        }

    return _run_agent(req.resume_id, "validate", run)


# ==========================================================
# AGENT 4 — KEYWORDS
# Raw text agent — no extraction, no cache needed
# ==========================================================

@router.post("/keywords")
def agent_keywords(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        penalty, triggers = detect_keyword_penalties(resume_data["document_text"])
        return {
            "penalty":       penalty,
            "trigger_count": len(triggers),
            "triggers":      triggers,
            "risk_signal":   _risk_label(penalty, low=15, high=40),
        }

    return _run_agent(req.resume_id, "keywords", run)


# ==========================================================
# AGENT 5 — EMPLOYMENT GAPS
# Uses cached extraction
# ==========================================================

@router.post("/gaps")
def agent_gaps(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)
        if not validated:
            return {"error": "Extraction failed.", "penalty": 0, "gap_count": 0,
                    "gap_details": [], "experience_count": 0, "risk_signal": "LOW"}

        exp_count = len(validated.get("experience", []))
        if exp_count == 0:
            return {"penalty": 0, "gap_count": 0, "gap_details": [],
                    "experience_count": 0, "risk_signal": "LOW",
                    "note": "No work experience found — fresher/student resume."}

        penalty, details = detect_employment_gaps(validated)
        return {"penalty": penalty, "gap_count": len(details), "gap_details": details,
                "experience_count": exp_count, "risk_signal": _risk_label(penalty, 10, 30)}

    return _run_agent(req.resume_id, "gaps", run)


# ==========================================================
# AGENT 6 — OVERLAPPING JOBS
# ==========================================================

@router.post("/overlaps")
def agent_overlaps(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)
        if not validated:
            return {"error": "Extraction failed.", "penalty": 0, "overlap_count": 0,
                    "overlap_details": [], "experience_count": 0, "risk_signal": "LOW"}

        exp_count = len(validated.get("experience", []))
        penalty, details = detect_overlapping_jobs(validated)
        return {"penalty": penalty, "overlap_count": len(details), "overlap_details": details,
                "experience_count": exp_count, "risk_signal": _risk_label(penalty, 10, 30)}

    return _run_agent(req.resume_id, "overlaps", run)

# ==========================================================
# AGENT 7 — IMPOSSIBLE ACADEMICS
# ==========================================================

@router.post("/academics")
def agent_academics(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)
        if not validated:
            return {"error": "Extraction failed.", "penalty": 0, "flag_count": 0,
                    "academic_flags": [], "education_count": 0, "risk_signal": "LOW"}

        edu_count = len(validated.get("education", []))
        penalty, details = detect_impossible_academics(validated)
        return {"penalty": penalty, "flag_count": len(details), "academic_flags": details,
                "education_count": edu_count, "risk_signal": _risk_label(penalty, 10, 30)}

    return _run_agent(req.resume_id, "academics", run)

# ==========================================================
# AGENT 8 — INVALID PERCENTAGES
# ==========================================================

@router.post("/percentages")
def agent_percentages(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)
        if not validated:
            return {"error": "Extraction failed.", "penalty": 0, "flag_count": 0,
                    "percentage_flags": [], "education_count": 0, "risk_signal": "LOW"}

        edu_count = len(validated.get("education", []))
        penalty, details = detect_invalid_percentages(validated)
        return {"penalty": penalty, "flag_count": len(details), "percentage_flags": details,
                "education_count": edu_count, "risk_signal": _risk_label(penalty, 10, 30)}

    return _run_agent(req.resume_id, "percentages", run)

# ==========================================================
# AGENT 8 — FUTURE DATES
# ==========================================================

@router.post("/future-dates")
def agent_future_dates(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)
        if not validated:
            return {"error": "Extraction failed.", "penalty": 0, "flag_count": 0,
                    "future_date_flags": [], "risk_signal": "LOW"}

        penalty, details = detect_future_dates(validated)
        return {"penalty": penalty, "flag_count": len(details),
                "future_date_flags": details, "risk_signal": _risk_label(penalty, 10, 20)}

    return _run_agent(req.resume_id, "future-dates", run)


# ==========================================================
# AGENT 9 — SKILLS CHECK
# ==========================================================

@router.post("/skills")
def agent_skills(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)
        if not validated:
            return {"error": "Extraction failed.", "penalty": 0, "flag_count": 0,
                    "skill_flags": [], "technical_skills_count": 0,
                    "technical_skills": [], "risk_signal": "LOW"}

        skills_raw = validated.get("skills", {})
        technical  = skills_raw.get("technical", []) if isinstance(skills_raw, dict) else []
        penalty, details = detect_empty_skills(validated)
        return {"penalty": penalty, "flag_count": len(details), "skill_flags": details,
                "technical_skills_count": len(technical), "technical_skills": technical,
                "risk_signal": _risk_label(penalty, 8, 15)}

    return _run_agent(req.resume_id, "skills", run)


# ==========================================================
# AGENT 10 — SHORT TENURE
# ==========================================================

@router.post("/tenure")
def agent_tenure(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)
        if not validated:
            return {"error": "Extraction failed.", "penalty": 0, "flag_count": 0,
                    "short_tenure_details": [], "experience_count": 0, "risk_signal": "LOW"}

        exp_count = len(validated.get("experience", []))
        penalty, details = detect_short_tenure_pattern(validated)
        return {"penalty": penalty, "flag_count": len(details),
                "short_tenure_details": details, "experience_count": exp_count,
                "risk_signal": _risk_label(penalty, 5, 10)}

    return _run_agent(req.resume_id, "tenure", run)


# ==========================================================
# AGENT 11 — DUPLICATES
# ==========================================================

@router.post("/duplicates")
def agent_duplicates(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)
        if not validated:
            return {"error": "Extraction failed.", "penalty": 0, "duplicate_count": 0,
                    "duplicate_details": [], "risk_signal": "LOW"}

        penalty, details = detect_duplicate_companies(validated)
        return {"penalty": penalty, "duplicate_count": len(details),
                "duplicate_details": details, "risk_signal": _risk_label(penalty, 10, 20)}

    return _run_agent(req.resume_id, "duplicates", run)


# ==========================================================
# AGENT 12 — SENIORITY MISMATCH
# ==========================================================

@router.post("/seniority")
def agent_seniority(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)
        if not validated:
            return {"error": "Extraction failed.", "penalty": 0, "mismatch_count": 0,
                    "seniority_details": [], "experience_count": 0, "risk_signal": "LOW"}

        exp_count = len(validated.get("experience", []))
        edu_count = len(validated.get("education", []))
        penalty, details = detect_seniority_mismatch(validated)
        return {"penalty": penalty, "mismatch_count": len(details),
                "seniority_details": details, "experience_count": exp_count,
                "education_count": edu_count, "risk_signal": _risk_label(penalty, 10, 25)}

    return _run_agent(req.resume_id, "seniority", run)


# ==========================================================
# AGENT 13 — INTEGRITY ENGINE
# ==========================================================

@router.post("/integrity")
def agent_integrity(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)
        if not validated:
            return {"error": "Extraction failed.", "integrity_score": 0,
                    "risk_level": "UNKNOWN", "total_penalty": 0}

        return resume_integrity_engine(resume_data["document_text"], validated)

    return _run_agent(req.resume_id, "integrity", run)


# ==========================================================
# AGENT 14 — LLM SCORE
# Raw text agent — no extraction needed
# ==========================================================

@router.post("/llm-score")
def agent_llm_score(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)
    jd = req.job_description or resume_data.get("job_description")

    def run():
        verdict = llm_resume_verdict(
            text=resume_data["document_text"],
            job_description=jd,
            return_detail=True,
        )
        if isinstance(verdict, dict):
            score       = verdict.get("score", 50)
            is_fallback = verdict.get("llm_score_is_fallback", False)
        else:
            score       = int(verdict) if verdict else 50
            is_fallback = False

        return {"llm_score": score, "is_fallback": is_fallback,
                "job_description_used": bool(jd),
                "note": "Fallback score — LLM unavailable" if is_fallback else None}

    return _run_agent(req.resume_id, "llm-score", run)


# ==========================================================
# AGENT 15 — RISK ENGINE
# Uses cached extraction
# ==========================================================

@router.post("/risk")
def agent_risk(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)
    jd = req.job_description or resume_data.get("job_description")

    def run():
        validated = _get_validated(resume_data, force=req.force_reextract)
        state = {
            "document_text":   resume_data["document_text"],
            "validated_data":  validated,
            "job_description": jd,
        }
        result = calculate_risk(state)
        expl = result.get("explainability")
        if isinstance(expl, str):
            try:
                expl = json.loads(expl)
            except Exception:
                pass
        return {"structural_score": result.get("structural_score"),
                "llm_score":        result.get("llm_score"),
                "risk_score":       result.get("risk_score"),
                "risk_level":       result.get("risk_level"),
                "final_confidence": result.get("final_confidence"),
                "decision":         result.get("decision"),
                "explainability":   expl}

    return _run_agent(req.resume_id, "risk", run)


# ==========================================================
# AGENT 16 — FULL PIPELINE (restored + fixed)
# ==========================================================

@router.post("/full-pipeline")
def agent_full_pipeline(req: AgentRequest):
    resume_data = _load_resume(req.resume_id)
    jd = req.job_description or resume_data.get("job_description")

    def run():
        result = workflow.invoke({
            "document_text":   resume_data["document_text"],
            "job_description": jd,
        })
        expl = result.get("explainability")
        if isinstance(expl, str):
            try:
                expl = json.loads(expl)
            except Exception:
                pass
        return {"doc_type":         result.get("doc_type"),
                "validation":       result.get("validation"),
                "structural_score": result.get("structural_score"),
                "llm_score":        result.get("llm_score"),
                "risk_score":       result.get("risk_score"),
                "risk_level":       result.get("risk_level"),
                "final_confidence": result.get("final_confidence"),
                "decision":         result.get("decision"),
                "explainability":   expl}

    return _run_agent(req.resume_id, "full-pipeline", run)


# ==========================================================
# GET — all past results
# ==========================================================

@router.get("/results/{resume_id}")
def get_results(resume_id: int):
    results = get_agent_results(resume_id)
    return {"resume_id": resume_id, "total_agents_run": len(results), "results": results}