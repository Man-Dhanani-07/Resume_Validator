import math
import logging
from typing import Dict, Any, Optional

from app.agents.resume_integrity import resume_integrity_engine
from app.agents.resume_judge import llm_resume_verdict
import json
logger = logging.getLogger(__name__)

# ==========================================================
# FUSION WEIGHTS
# ==========================================================

STRUCTURAL_WEIGHT = 0.45
LLM_WEIGHT        = 0.55

# ==========================================================
# FRAUD SCORE NORMALIZATION
# ==========================================================

def _normalize_fraud_score(raw_penalty: int) -> int:
    """
    Converts unbounded raw penalty points → 0–100 fraud score.
    Log-scaling preserves signal above 100 raw points.

    Examples:
        0   raw → 0   fraud
        30  raw → ~32 fraud
        50  raw → ~46 fraud
        100 raw → ~64 fraud
        150 raw → ~73 fraud
        200 raw → ~79 fraud
    """
    if raw_penalty <= 0:
        return 0
    MAX_EXPECTED = 200
    normalized   = (math.log1p(raw_penalty) / math.log1p(MAX_EXPECTED)) * 100
    return min(100, round(normalized))

# ==========================================================
# RISK BAND CLASSIFIER
# ==========================================================

def _classify_risk(risk_score: int, fraud_score: int) -> str:
    # ── FIX BUG 3 (TEST_10) ──────────────────────────────────────────────
    # Original: risk_score >= 65 → HIGH → REJECT
    # Problem:  A single future end_date gives penalty=20, fraud~24,
    #           but inverse-quality math still pushed risk_score to 65+,
    #           causing REJECT instead of REVIEW for a minor anomaly.
    #
    # Fix: CRITICAL and HIGH now require BOTH elevated risk_score AND
    #      elevated fraud_score. A low fraud_score (< 40) caps at MEDIUM
    #      even if risk_score is high — meaning 1 anomaly = REVIEW not REJECT.
    if fraud_score >= 80 or risk_score >= 85:
        return "CRITICAL"
    # HIGH requires meaningful fraud signal (>=40), not just high risk_score
    if risk_score >= 65 and fraud_score >= 40:
        return "HIGH"
    # MEDIUM: either moderate risk OR any non-trivial fraud signal
    if risk_score >= 35 or fraud_score >= 15:
        return "MEDIUM"
    return "LOW"

# ==========================================================
# DECISION LOGIC
# ==========================================================

def _derive_decision(risk_level: str, final_confidence: int) -> str:
    if risk_level == "CRITICAL":
        return "REJECT"
    if risk_level == "HIGH":
        return "REJECT"
    if risk_level == "MEDIUM":
        return "REVIEW"
    # LOW risk
    if final_confidence >= 60:
        return "APPROVE"
    return "REVIEW"

# ==========================================================
# EXPLAINABILITY BUILDER
# ==========================================================

def _build_explainability(
    structural_score: int,
    llm_score: int,
    fraud_score: int,
    final_confidence: int,
    integrity_data: Dict,
    llm_score_is_fallback: bool = False,
) -> str:
    """
    Returns a JSON string stored in the explainability column.
    Now includes llm_score_is_fallback so operators know when
    the LLM failed and a default score was substituted.
    """
    penalties    = integrity_data.get("penalties", {})
    components   = integrity_data.get("components", {})
    risk_reasons = []

    kw = penalties.get("keyword_triggers", [])
    if kw:
        risk_reasons.append(f"Suspicious keywords: {', '.join(kw[:3])}")

    gaps = penalties.get("gap_details", [])
    if gaps:
        risk_reasons.append(f"Employment gaps: {'; '.join(gaps)}")

    overlaps = penalties.get("overlap_details", [])
    if overlaps:
        risk_reasons.append(f"Date overlaps: {'; '.join(overlaps)}")

    acad = penalties.get("academic_flags", [])
    if acad:
        risk_reasons.append(f"Academic anomalies: {'; '.join(acad)}")

    future = penalties.get("future_date_flags", [])
    if future:
        risk_reasons.append(f"Future dates: {'; '.join(future)}")

    dup = penalties.get("duplicate_flags", [])
    if dup:
        risk_reasons.append(f"Duplicate entries: {'; '.join(dup)}")

    tenure = penalties.get("short_tenure_flags", [])
    if tenure:
        risk_reasons.append(f"Job-hopping: {'; '.join(tenure)}")

    pct = penalties.get("percentage_flags", [])
    if pct:
        risk_reasons.append(f"Invalid percentages: {'; '.join(pct)}")

    skill = penalties.get("empty_skill_flags", [])
    if skill:
        risk_reasons.append(f"Skill gaps: {'; '.join(skill)}")

    seniority = penalties.get("seniority_flags", [])
    if seniority:
        risk_reasons.append(f"Impossible seniority: {'; '.join(seniority)}")

    if not risk_reasons:
        risk_reasons.append("No significant risk signals detected")

    explainability_dict = {
        "structural_score":       structural_score,
        "llm_score":              llm_score,
        "llm_score_is_fallback":  llm_score_is_fallback,   # NEW
        "fraud_score":            fraud_score,
        "final_confidence":       final_confidence,
        "score_components": {
            "section_score":   components.get("section_score",   0),
            "density_score":   components.get("density_score",   0),
            "garbage_score":   components.get("garbage_score",   0),
            "contact_score":   components.get("contact_score",   0),
            "structure_score": components.get("structure_score", 0),
        },
        "total_penalty": integrity_data.get("total_penalty", 0),
        "risk_reasons":  risk_reasons,
    }

    return json.dumps(explainability_dict)


# ==========================================================
# MAIN FUNCTION
# ==========================================================

def calculate_risk(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Input state keys used:
        validated_data   → Dict (from validator)
        document_text    → str  (raw resume text)
        job_description  → str  (optional — enables JD-aware LLM scoring)

    Output state keys written to WorkflowRun columns:
        structural_score → Integer
        llm_score        → Integer
        risk_score       → Integer
        risk_level       → String  (LOW / MEDIUM / HIGH / CRITICAL)
        final_confidence → Integer (0-100, quality-based)
        explainability   → Text    (JSON string)
        decision         → String  (APPROVE / REVIEW / REJECT)
    """

    # ── Guard: validation failed ──────────────────────────────────────────
    if not state.get("validated_data"):
        logger.error("calculate_risk: no validated_data in state — CRITICAL reject")
        explainability = json.dumps({
            "structural_score":      0,
            "llm_score":             0,
            "llm_score_is_fallback": False,
            "fraud_score":           100,
            "final_confidence":      0,
            "risk_reasons":          ["Schema validation failed — resume could not be parsed"],
        })
        return {
            **state,
            "structural_score": 0,
            "llm_score":        0,
            "risk_score":       95,
            "risk_level":       "CRITICAL",
            "final_confidence": 0,
            "explainability":   explainability,
            "decision":         "REJECT",
        }

    text:            str           = state.get("document_text", "")
    extracted:       Dict          = state["validated_data"]
    job_description: Optional[str] = state.get("job_description")

    # ── 1. Structural Integrity Engine ────────────────────────────────────
    try:
        integrity_data   = resume_integrity_engine(text, extracted)
        structural_score = integrity_data["integrity_score"]
        penalties_total  = integrity_data["total_penalty"]
    except Exception as exc:
        logger.error("calculate_risk: integrity engine failed — %s", exc)
        integrity_data   = {}
        structural_score = 50
        penalties_total  = 0

    # ── 2. LLM Score  ─────────────────────────────────────────────────────
    llm_score_is_fallback = False
    try:
        verdict = llm_resume_verdict(text, job_description, return_detail=True)
        if isinstance(verdict, dict):
            llm_score             = int(verdict["score"])
            llm_score_is_fallback = verdict.get("llm_score_is_fallback", False)
        else:
            llm_score = int(verdict)
    except Exception as exc:
        logger.error("calculate_risk: LLM judge failed — %s", exc)
        llm_score             = 50
        llm_score_is_fallback = True

    if llm_score_is_fallback:
        logger.warning(
            "calculate_risk: llm_score=%d is a FALLBACK — "
            "LLM was unavailable, risk accuracy may be reduced", llm_score
        )

    # ── 3. Quality Score ──────────────────────────────────────────────────
    quality_score = round(
        structural_score * STRUCTURAL_WEIGHT +
        llm_score        * LLM_WEIGHT
    )
    quality_score    = max(0, min(100, quality_score))
    final_confidence = quality_score

    # ── 4. Fraud Score ────────────────────────────────────────────────────
    fraud_score = _normalize_fraud_score(penalties_total)
    if penalties_total >= 100:
        fraud_score = max(fraud_score, 80)

    # ── 5. Final Risk Score ───────────────────────────────────────────────
    inverse_quality = 100 - final_confidence
    risk_score = max(
        fraud_score,
        round(inverse_quality * 0.6 + fraud_score * 0.4)
    )
    risk_score = max(0, min(100, risk_score))

    # ── 6. Risk Level & Decision ──────────────────────────────────────────
    risk_level = _classify_risk(risk_score, fraud_score)
    decision   = _derive_decision(risk_level, final_confidence)

    logger.info(
        "calculate_risk: structural=%d llm=%d(fallback=%s) fraud=%d "
        "risk_score=%d risk_level=%s decision=%s",
        structural_score, llm_score, llm_score_is_fallback,
        fraud_score, risk_score, risk_level, decision
    )

    # ── 7. Explainability ─────────────────────────────────────────────────
    explainability = _build_explainability(
        structural_score, llm_score, fraud_score,
        final_confidence, integrity_data,
        llm_score_is_fallback=llm_score_is_fallback,
    )

    return {
        **state,
        "structural_score": structural_score,
        "llm_score":        llm_score,
        "risk_score":       risk_score,
        "risk_level":       risk_level,
        "final_confidence": final_confidence,
        "explainability":   explainability,
        "decision":         decision,
    }