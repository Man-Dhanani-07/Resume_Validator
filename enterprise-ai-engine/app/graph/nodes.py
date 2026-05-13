import logging
from app.agents.classifier import classify_document
from app.agents.validator import validate_resume
from app.agents.extractor import extract_document_fields
from app.agents.risk import calculate_risk

logger = logging.getLogger(__name__)


# ==========================================================
# NODE 1 — CLASSIFY
# ==========================================================

def classify_node(state: dict) -> dict:
    """
    Classifies the document type.
    If the document is NOT a resume, immediately short-circuits
    the pipeline with a REJECT decision — no point running
    extraction or scoring on an invoice or contract.
    """
    logger.info("classify_node: starting classification")

    doc_type = classify_document(state["document_text"])
    logger.info("classify_node: doc_type=%r", doc_type)

    if doc_type != "resume":
        logger.warning(
            "classify_node: document is %r, not a resume — short-circuit REJECT",
            doc_type
        )
        return {
            **state,
            "doc_type":         doc_type,
            "validation":       "failed",
            "validated_data":   None,
            "structural_score": 0,
            "llm_score":        0,
            "risk_score":       100,
            "risk_level":       "CRITICAL",
            "final_confidence": 0,
            "decision":         "REJECT",
            "explainability":   None,
        }

    return {**state, "doc_type": doc_type}
      


      
# ==========================================================
# NODE 2 — EXTRACT
# ==========================================================

def process_node(state: dict) -> dict:
    """
    Extracts all resume fields from raw text into structured JSON.
    Skips extraction if the pipeline already short-circuited in classify_node.
    """
    # Skip if already rejected by classify_node
    if state.get("decision") == "REJECT":
        logger.info("process_node: skipping — pipeline already rejected")
        return state

    logger.info("process_node: extracting document fields")
    extracted = extract_document_fields(state["document_text"])
    logger.info("process_node: extraction complete")

    return {**state, "processed_data": extracted}


# ==========================================================
# NODE 3 — VALIDATE
# ==========================================================

def validation_node(state: dict) -> dict:
    """
    Validates extracted JSON against the Resume schema.
    Checks completeness, field formats, and logical consistency.
    Skips if pipeline already short-circuited.
    """
    # Skip if already rejected by classify_node
    if state.get("decision") == "REJECT":
        logger.info("validation_node: skipping — pipeline already rejected")
        return state

    logger.info("validation_node: starting schema validation")

    validated_data, error = validate_resume(state["processed_data"])

    if error:
        logger.warning("validation_node: validation failed — %s", error)
        validation_status = "failed"
    else:
        logger.info("validation_node: schema validation passed")
        validation_status = "passed"

    return {
        **state,
        "validation":     validation_status,
        "validated_data": validated_data,
    }


# ==========================================================
# NODE 4 — RISK
# ==========================================================

def risk_node(state: dict) -> dict:
    """
    Runs the full risk fusion engine:
      - Rule-based structural integrity (resume_integrity.py)
      - LLM semantic scoring (resume_judge.py)
      - Fraud score normalization + risk band classification
      - Sets: structural_score, llm_score, risk_score,
              risk_level, final_confidence, explainability, decision
    Skips if pipeline already short-circuited.
    """
    if state.get("decision") == "REJECT":
        logger.info("risk_node: skipping — pipeline already rejected")
        return state

    logger.info("risk_node: starting risk calculation")
    updated_state = calculate_risk(state)
    logger.info(
        "risk_node: complete — risk_level=%s decision=%s risk_score=%s",
        updated_state.get("risk_level"),
        updated_state.get("decision"),
        updated_state.get("risk_score"),
    )
    return updated_state


# ==========================================================
# NODE 5 — DECISION
# ==========================================================

def decision_node(state: dict) -> dict:
    """
    Final decision gate.

    risk.py already computes:
      - risk_level : LOW / MEDIUM / HIGH / CRITICAL
      - decision   : APPROVE / REVIEW / REJECT

    This node's job is to:
      1. Override decision to REJECT if validation failed
         (risk_node may not have run or may have returned APPROVE
         on a partially-parsed resume that failed schema validation)
      2. Trust risk.py's decision in all other cases
      3. Log the final decision for the audit trail

    Label contract (matches DB column and main.py report):
      APPROVE  — low risk, sufficient confidence
      REVIEW   — medium risk or low confidence
      REJECT   — high/critical risk or validation failure
    """
    logger.info("decision_node: finalizing decision")

    # ── Hard override: validation failure always → REJECT ─────────────────
    if state.get("validation") != "passed":
        logger.warning(
            "decision_node: validation=%r — overriding to REJECT",
            state.get("validation")
        )
        return {**state, "decision": "REJECT"}

    decision   = state.get("decision",    "REVIEW")   # fallback: REVIEW
    risk_level = state.get("risk_level",  "UNKNOWN")
    risk_score = state.get("risk_score",  "N/A")
    llm_score  = state.get("llm_score",   "N/A")

    logger.info(
        "decision_node: FINAL — decision=%s risk_level=%s "
        "risk_score=%s llm_score=%s",
        decision, risk_level, risk_score, llm_score
    )

    return {**state, "decision": decision}