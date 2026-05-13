import re
import logging
from app.agents.llm_client import ask_llm

logger = logging.getLogger(__name__)

# Maximum characters sent to LLM (~3,000 tokens for most models)
MAX_CHARS = 12_000

SCHEMA = """{
  "profile": {
    "full_name": null,
    "email": null,
    "phone": null,
    "location": {
      "city": null,
      "state": null,
      "country": null
    },
    "work_authorization": null,
    "links": {
      "linkedin": null,
      "github": null,
      "portfolio": null
    }
  },

  "summary": null,

  "experience": [
    {
      "company": null,
      "position": null,
      "employment_type": null,
      "work_mode": null,
      "location": null,
      "start_date": null,
      "end_date": null,
      "description": null,
      "highlights": [],
      "impact_metrics": []
    }
  ],

  "education": [
    {
      "institution": null,
      "degree": null,
      "degree_level": null,
      "field_of_study": null,
      "location": null,
      "start_date": null,
      "end_date": null,
      "cgpa": null,
      "percentage": null
    }
  ],

  "skills": {
    "categorized": [
      {
        "category": null,
        "items": []
      }
    ],
    "technical": [],
    "soft": [],
    "proficiency": [
      {
        "skill": null,
        "level": null,
        "years": null
      }
    ]
  },

  "languages_spoken": [],

  "projects": [
    {
      "name": null,
      "role": null,
      "description": null,
      "technologies": [],
      "impact": [],
      "links": {
        "github": null,
        "live": null,
        "demo": null
      }
    }
  ],

  "certifications": [
    {
      "name": null,
      "issuer": null,
      "date": null,
      "credential_id": null
    }
  ],

  "achievements": {
    "coding_profiles": [
      { "platform": null, "username": null, "rating": null, "rank": null }
    ],
    "awards_honors": []
  },

  "metadata": {
    "total_years_experience": 0.0,
    "confidence_score": 0.0,
    "source_file": null,
    "parsed_at": null,
    "parser_version": null
  }
}
"""


def extract_document_fields(text: str) -> str:

    # ── Guard: truncate oversized documents ──────────────────────────────────
    if len(text) > MAX_CHARS:
        logger.warning(
            "extract_document_fields: Resume text truncated from %d to %d chars",
            len(text), MAX_CHARS
        )
        text = text[:MAX_CHARS]

    prompt = f"""You are an Enterprise Resume Intelligence Engine deployed inside an automated recruitment pipeline.
Your JSON output is ingested directly by downstream systems — structural or factual errors will cause pipeline failures.

════════════════════════════════════════════════════════════
OUTPUT CONTRACT  (zero tolerance — never violate)
════════════════════════════════════════════════════════════
✦ Return ONLY a single, valid JSON object
✦ No markdown fences (no ```json), no comments, no trailing commas
✦ No preamble, no explanation, no text outside the JSON
✦ Do NOT invent, infer, or hallucinate any data — if it is not in the resume, use null or []
✦ Preserve the candidate's exact wording; do not paraphrase
✦ Missing scalar fields → null
✦ Missing array fields  → []
✦ confidence_score: float 0.0–1.0 reflecting overall extraction certainty

════════════════════════════════════════════════════════════
FIELD-LEVEL EXTRACTION RULES
════════════════════════════════════════════════════════════

── PROFILE ──────────────────────────────────────────────
• full_name     : Full name exactly as written; no titles (Mr./Dr.)
• email         : Lowercase, trim whitespace
• phone         : Include country code if present; preserve original formatting
• location      : Parse city / state / country separately; never concatenate
• work_authorization : Only extract if explicitly stated (e.g. "US Citizen", "H1-B", "Open to work")
• links         : Extract LinkedIn, GitHub, Portfolio URLs verbatim; null if absent

── SUMMARY ──────────────────────────────────────────────
• Copy the professional summary / objective section verbatim
• If absent → null

── EXPERIENCE ───────────────────────────────────────────
• Extract EVERY job entry — do not skip any
• position        : Exact job title as written
• employment_type : Full-time / Part-time / Contract / Internship / Freelance — infer only if obvious from context; else null
• work_mode       : Remote / On-site / Hybrid — infer only if stated; else null
• start_date / end_date : Normalize to YYYY-MM; if "Present" or "Current" → end_date = null
• highlights      : Every bullet point under this role — do NOT summarize, do NOT drop any
• impact_metrics  : Pull out any quantified achievements (%, $, numbers) from highlights as separate strings

── EDUCATION ────────────────────────────────────────────
# In your LLM extraction prompt, add:
- If the score has a '%' symbol → store in 'percentage' field (valid: 0-100)
- If the score is a decimal like 8.5 or X/10 → store in 'cgpa' field (valid: 0-10)
- NEVER put a percentage value into the cgpa field
• Extract EVERY education entry
• degree_level    : High School / Associate / Bachelor / Master / PhD / Diploma / Certificate
• If only ONE date is visible → treat as end_date; start_date = null (never guess enrollment year)
• cgpa            : Numeric value only (e.g. 3.8); strip "/4.0" scale suffix
• percentage      : Numeric value only (e.g. 87.5); strip "%" symbol

── SKILLS ───────────────────────────────────────────────
• categorized : Reproduce EVERY skill category header from the resume exactly; list ALL items under each
• technical   : Flat list of ALL technical skills across all categories (deduplicated)
• soft        : Flat list of ALL soft skills (Communication, Leadership, etc.)
• proficiency : Populate only if skill level or years are explicitly stated (Beginner/Intermediate/Expert or "3 years"); else []
• Do NOT merge categories, do NOT drop items, do NOT rename categories

── PROJECTS ─────────────────────────────────────────────
• Extract EVERY project listed
• technologies : All tools/languages/frameworks listed for the project as an array
• impact       : Any measurable outcomes or results stated for the project
• links        : github / live / demo URLs — null if not present

── CERTIFICATIONS ───────────────────────────────────────
• Extract EVERY certification / course / license
• date          : Normalize to YYYY-MM if possible; else preserve as written
• credential_id : Extract if present; else null

── ACHIEVEMENTS ─────────────────────────────────────────
• coding_profiles : LeetCode, Codeforces, HackerRank, CodeChef, etc. — extract username, rating, rank if stated
• awards_honors   : Every award, honour, scholarship, recognition listed

── METADATA ─────────────────────────────────────────────
• total_years_experience : Sum of all non-overlapping work experience durations; round to 1 decimal
• confidence_score       : Your honest estimate (0.0–1.0) of extraction completeness and accuracy
• source_file            : null (caller will populate)
• parsed_at              : null (caller will populate)
• parser_version         : "2.0"

════════════════════════════════════════════════════════════
DISAMBIGUATION RULES  (for common edge cases)
════════════════════════════════════════════════════════════
• Overlapping date ranges in experience → include all; do not merge
• Same company, multiple roles → create a SEPARATE experience entry per role
• Skills listed inline in experience bullets → do NOT add to skills section unless also listed in a skills section
• Projects listed inside a job role → extract under "projects" AND reference in that experience's highlights
• Certifications with no issuer → issuer = null, do not guess
• GPA on 10-point scale → store raw value in cgpa; do not convert
• Percentage and CGPA both present → populate both fields

════════════════════════════════════════════════════════════
SCHEMA  (follow exactly — no extra keys, no missing keys)
════════════════════════════════════════════════════════════
{SCHEMA}

════════════════════════════════════════════════════════════
RESUME TEXT
════════════════════════════════════════════════════════════
{text}
════════════════════════════════════════════════════════════

JSON output:"""

    try:
        raw_result = ask_llm(prompt)
    except RuntimeError as exc:
        logger.error("extract_document_fields: LLM unavailable — %s", exc)
        return SCHEMA

    # ── 1. Strip accidental markdown fences ──────────────────────────────────
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_result.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    # ── 2. Extract the outermost JSON object ─────────────────────────────────
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        candidate = match.group(0)

        # ── 3. Repair common LLM JSON mistakes ───────────────────────────────
        # Remove trailing commas before } or ]
        candidate = re.sub(r",\s*([}\]])", r"\1", candidate)
        # Replace Python-style None/True/False with JSON equivalents
        candidate = re.sub(r"\bNone\b",  "null",  candidate)
        candidate = re.sub(r"\bTrue\b",  "true",  candidate)
        candidate = re.sub(r"\bFalse\b", "false", candidate)

        logger.info("extract_document_fields: extraction successful")
        return candidate

    # ── 4. Fallback — return the clean schema so the pipeline never breaks ───
    logger.warning("extract_document_fields: no JSON found in LLM response — returning empty schema")
    return SCHEMA