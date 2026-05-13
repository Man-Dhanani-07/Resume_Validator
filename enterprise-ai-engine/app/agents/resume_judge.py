import json
import re
import time
import logging
from typing import Optional, Dict, Union

from app.agents.llm_client import ask_llm

logger = logging.getLogger(__name__)


# ==========================================================
# PROMPT BUILDER
# ==========================================================

_JSON_SCHEMA = """
{
  "overall_score": 0,
  "scores": {
    "technical_fit": 0,
    "role_experience": 0,
    "impact_and_achievements": 0,
    "education_and_certifications": 0,
    "culture_and_communication": 0,
    "risk_flags": 0
  },
  "passed_minimum_requirements": true,
  "gating_fail_reasons": [],
  "top_3_strengths": [],
  "top_3_weaknesses": [],
  "recommended_role_level": "",
  "confidence": 0.00,
  "suggested_next_steps": {
    "hire_recommendation": "",
    "interview_focus_questions": [],
    "targeted_assessment": null
  },
  "evidence": [
    {"label": "", "text": ""}
  ]
}
"""

_BASE_SYSTEM = """
SYSTEM ROLE:
You are a senior enterprise hiring evaluator operating inside a structured,
audit-compliant recruitment platform.

STRICT OUTPUT REQUIREMENTS:
- Output ONLY valid JSON. No markdown. No commentary. No preamble.
- No null values except for "targeted_assessment".
- All numeric values must be numbers, not strings.
- All arrays must be valid JSON arrays.
- All booleans must be lowercase true/false.

JSON SCHEMA (STRICTLY ENFORCE):
{schema}

CRITICAL EVALUATION RULES:

1. GROUND TRUTH:
   The job description defines required skills, must-have qualifications,
   minimum years of experience, and mandatory certifications.
   If ANY must-have requirement is missing or unclear:
   - Set "passed_minimum_requirements" = false
   - Add EACH missing requirement explicitly to "gating_fail_reasons"
   - If major requirement missing → recommended_role_level = "Not a fit"

2. SCORING LOGIC (MANDATORY FORMULA):

   overall_score =
       (technical_fit               * 0.40) +
       (role_experience             * 0.25) +
       (impact_and_achievements     * 0.15) +
       (education_and_certifications* 0.05) +
       (culture_and_communication   * 0.10) -
       (risk_flags                  * 0.15)   <- max 15 point deduction

   Clamp result between 0 and 100. Round to nearest integer.
   Subscores must be integers (0-100).

3. EVIDENCE-ONLY POLICY:
   Use ONLY explicit resume content.
   Do NOT infer missing years. Do NOT assume experience.
   Do NOT fabricate achievements. If unclear -> score conservatively.

4. RISK FLAGS (0-100):
   Aggregate negative signals:
   - Employment gap >12 months without explanation
   - Date inconsistencies
   - Unverifiable elite claims
   - Contradictory titles
   - Copy-paste plagiarism indicators
   - Legal or ethics concerns

5. ROLE LEVEL CALIBRATION:
   Choose exactly one:
   "IC-1","IC-2","IC-3","Senior","Staff","Principal","Manager","Not a fit"
   Based on: scope, leadership, system ownership, years of experience, complexity.

6. CONFIDENCE SCORE (0.00-1.00, two decimal places):
   High when evidence is clear and quantified.
   Low when resume is vague, has gaps, or skills are implied.

7. INTERVIEW QUESTIONS:
   Maximum 5. Must reference resume evidence. No generic questions.
   Behavioral or technical. Test claimed expertise.

8. EVIDENCE:
   Maximum 6 entries. Each <= 28 words.
   Must quote exact resume phrase. Must justify a subscore or risk flag.

9. FAIRNESS & BIAS CONTROL:
   Ignore name, gender, ethnicity, age.
   Ignore university prestige unless job explicitly requires it.
   Evaluate only job-relevant merit.

10. STABILITY: Follow scoring formula strictly. Deterministic reasoning.
""".strip()


def _build_prompt(text: str, job_description: Optional[str] = None) -> str:
    base = _BASE_SYSTEM.replace("{schema}", _JSON_SCHEMA)

    if job_description:
        jd_block = f"""
JOB DESCRIPTION (source of all must-have requirements):
---
{job_description.strip()}
---

EVALUATION MODE: JD-MATCH
Score technical_fit and role_experience strictly against JD requirements.
Set passed_minimum_requirements = false if ANY must-have is absent.
Add each missing item to gating_fail_reasons.
""".strip()
    else:
        jd_block = """
EVALUATION MODE: STANDALONE RESUME QUALITY
No job description provided. Evaluate resume quality independently.
technical_fit = depth and breadth of skills listed.
role_experience = length and relevance of experience for stated seniority.
Set passed_minimum_requirements = true unless resume is severely incomplete.
""".strip()

    return f"{base}\n\n{jd_block}\n\nRESUME:\n{text}"


# ==========================================================
# JSON REPAIR
# ==========================================================

def _repair_json(raw: str) -> str:
    """Strip markdown code fences and extract the JSON object."""
    raw   = raw.strip()
    raw   = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw   = re.sub(r"\s*```$",          "", raw, flags=re.MULTILINE)
    start = raw.find("{")
    end   = raw.rfind("}")
    if start != -1 and end != -1:
        return raw[start: end + 1]
    return raw


# ==========================================================
# SERVER-SIDE FORMULA RE-VERIFICATION
# ==========================================================

def _recompute_overall_score(scores: Dict) -> int:
    """
    Re-applies the scoring formula to catch LLM arithmetic errors.
    Mirrors the formula stated in the prompt exactly.
    """
    computed = (
        scores.get("technical_fit",                0) * 0.40 +
        scores.get("role_experience",              0) * 0.25 +
        scores.get("impact_and_achievements",      0) * 0.15 +
        scores.get("education_and_certifications", 0) * 0.05 +
        scores.get("culture_and_communication",    0) * 0.10 -
        scores.get("risk_flags",                   0) * 0.15
    )
    return max(0, min(100, round(computed)))


# ==========================================================
# RETRY WRAPPER  (exponential backoff — no hardcoded list)
# ==========================================================

MAX_RETRIES = 3
_MAX_DELAY  = 8   # seconds cap


def _call_llm_with_retry(prompt: str) -> Optional[str]:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = ask_llm(prompt)
            if response and response.strip():
                return response
            logger.warning(
                "_call_llm_with_retry: empty response on attempt %d/%d",
                attempt, MAX_RETRIES
            )
        except Exception as exc:
            logger.warning(
                "_call_llm_with_retry: failed on attempt %d/%d — %s",
                attempt, MAX_RETRIES, exc
            )

        if attempt < MAX_RETRIES:
            delay = min(_MAX_DELAY, 2 ** (attempt - 1))   # 1s, 2s, 4s, cap 8s
            logger.info("_call_llm_with_retry: retrying in %ds...", delay)
            time.sleep(delay)

    logger.error("_call_llm_with_retry: all %d attempts exhausted", MAX_RETRIES)
    return None
    
# ==========================================================
# PUBLIC API
# ==========================================================

def llm_resume_verdict(
    text: str,
    job_description: Optional[str] = None,
    return_detail: bool = False,
) -> Union[int, Dict]:
    """
    Evaluates a resume using LLM scoring.

    Args:
        text            : Raw resume text.
        job_description : Optional JD string for JD-match mode.
        return_detail   : If True, returns a dict with score + fallback flag.
                          If False (default), returns int — backward compatible.

    Returns:
        int              — overall_score 0–100 (default, backward compatible)
        dict             — {score: int, llm_score_is_fallback: bool} if return_detail=True

    Falls back to 50 on any failure. Stored in llm_score column (Integer).
    """
    prompt     = _build_prompt(text, job_description)
    raw        = _call_llm_with_retry(prompt)
    is_fallback = False

    if not raw:
        logger.error(
            "llm_resume_verdict: LLM unavailable — returning fallback score 50"
        )
        is_fallback = True
        final_score = 50

    else:
        try:
            cleaned    = _repair_json(raw)
            parsed     = json.loads(cleaned)
            base_score = parsed.get("overall_score", 50)
            scores     = parsed.get("scores", {})
            recomputed = _recompute_overall_score(scores)

            if abs(base_score - recomputed) > 5:
                logger.info(
                    "llm_resume_verdict: arithmetic mismatch reported=%d recomputed=%d "
                    "— using recomputed",
                    base_score, recomputed
                )
                base_score = recomputed

            final_score = max(0, min(100, int(base_score)))

        except Exception as exc:
            logger.error("llm_resume_verdict: JSON parse failed — %s", exc)
            is_fallback = True
            final_score = 50

    if is_fallback:
        logger.warning(
            "llm_resume_verdict: score is FALLBACK (50) — "
            "treat explainability llm_score with caution"
        )

    if return_detail:
        return {"score": final_score, "llm_score_is_fallback": is_fallback}

    return final_score