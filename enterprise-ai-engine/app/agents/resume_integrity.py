import re
import logging
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime

from app.agents.constants import (
    RESUME_SECTION_GROUPS,
    TOTAL_SECTION_GROUPS,
    SUSPICIOUS_KEYWORDS,
    NON_RESUME_PATTERNS,
    UNREALISTIC_TERMS,
    CONCURRENT_EMPLOYMENT_TYPES,
    SENIOR_TITLE_SIGNALS,
)

logger = logging.getLogger(__name__)

# ==========================================================
# PRE-COMPILED SECTION PATTERNS  (replaces inline re.search loop)
# ==========================================================
# Compiled once at import time — not on every resume processed.

_SECTION_PATTERNS: List[Dict] = [
    {
        "name": group["name"],
        "patterns": [
            re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
            for term in group["terms"]
        ],
    }
    for group in RESUME_SECTION_GROUPS
]

# ==========================================================
# DATE UTILITIES
# ==========================================================

def parse_date(date_str) -> Optional[datetime]:
    if not date_str:
        return None
    date_str = str(date_str).strip()
    if date_str.lower() == "present":
        return datetime.now()
    for fmt in ("%b %Y", "%B %Y", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    m = re.search(r"\b(19|20)\d{2}\b", date_str)
    if m:
        try:
            return datetime.strptime(m.group(), "%Y")
        except ValueError:
            pass
    return None


def _months_between(d1: datetime, d2: datetime) -> int:
    return (d2.year - d1.year) * 12 + (d2.month - d1.month)


# ==========================================================
# FIELD ACCESSOR HELPERS
# ==========================================================

def _get_position(exp: dict) -> str:
    return exp.get("position") or exp.get("title") or "Unknown"


def _get_company(exp: dict) -> str:
    return exp.get("company") or "Unknown"


def _get_emp_type(exp: dict) -> str:
    return (exp.get("employment_type") or "").lower().strip()


def _get_end_date(edu: dict) -> Optional[str]:
    return edu.get("end_date") or edu.get("year")


def _get_technical_skills(skills_raw: Any) -> List[str]:
    if isinstance(skills_raw, list):
        return skills_raw
    if not isinstance(skills_raw, dict):
        return []
    if "technical" in skills_raw:
        return skills_raw["technical"] or []
    merged = []
    for v in skills_raw.values():
        if isinstance(v, list):
            merged.extend(v)
    return merged


# ==========================================================
# POSITIVE SCORING COMPONENTS
# ==========================================================

def section_presence_score(text: str) -> int:
    """
    Uses pre-compiled _SECTION_PATTERNS — ~96 regex objects compiled once
    at module load instead of on every resume call.
    """
    found = sum(
        1 for group in _SECTION_PATTERNS
        if any(p.search(text) for p in group["patterns"])
    )
    return round((found / TOTAL_SECTION_GROUPS) * 30)


def resume_density_score(text: str) -> int:
    word_count = len(text.split())
    if word_count < 80:    return 2
    if word_count < 200:   return 8
    if word_count < 400:   return 14
    if word_count < 800:   return 18
    if word_count <= 1500: return 20
    return 15


def garbage_ratio_score(text: str) -> int:
    total_chars = len(text)
    if total_chars == 0:
        return 0
    garbage       = re.findall(r"[#@!$%^&*]{2,}", text)
    garbage_count = sum(len(g) for g in garbage)
    ratio = garbage_count / total_chars
    if ratio == 0:    return 10
    if ratio < 0.01:  return 8
    if ratio < 0.05:  return 4
    return 0


def contact_info_score(text: str) -> int:
    score = 0
    if re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text):
        score += 6
    if re.search(r"\+?\d[\d\s\-().]{7,14}\d", text):
        score += 5
    if re.search(r"linkedin\.com/in/", text, re.I):
        score += 2
    if re.search(r"github\.com/", text, re.I):
        score += 2
    return min(score, 15)

def structure_score(extracted_json: Dict[str, Any]) -> int:
    if not extracted_json:
        return 0
    score   = 0
    profile = extracted_json.get("profile", {})
    if profile.get("full_name") or profile.get("name"):
        score += 5
    if _get_technical_skills(extracted_json.get("skills", {})):
        score += 5
    if extracted_json.get("education"):
        score += 5
    if extracted_json.get("experience"):
        score += 5
    if extracted_json.get("projects"):
        score += 3
    if extracted_json.get("summary"):
        score += 2
    return min(score, 25)

# ==========================================================
# FRAUD / ANOMALY DETECTORS
# ==========================================================

def detect_keyword_penalties(text: str) -> Tuple[int, List[str]]:
    text_lower    = text.lower()
    total_penalty = 0
    triggers      = []

    for category, data in SUSPICIOUS_KEYWORDS.items():
        for term in data["terms"]:
            if term in text_lower:
                total_penalty += data["weight"]
                triggers.append(f"{category}: '{term}'")

    for category, data in NON_RESUME_PATTERNS.items():
        for term in data["terms"]:
            if term in text_lower:
                total_penalty += data["weight"]
                triggers.append(f"wrong_doc_type/{category}: '{term}'")

    for term in UNREALISTIC_TERMS["terms"]:
        if term in text_lower:
            total_penalty += UNREALISTIC_TERMS["weight"]
            triggers.append(f"unrealistic_claim: '{term}'")

    return total_penalty, triggers


def detect_employment_gaps(extracted_json: dict) -> Tuple[int, List[str]]:
    experiences = extracted_json.get("experience", [])
    educations  = extracted_json.get("education", [])

    edu_ranges = []
    for edu in educations:
        s = parse_date(edu.get("start_date"))
        e = parse_date(_get_end_date(edu))
        if s and e:
            edu_ranges.append((s, e))

    parsed = []
    for exp in experiences:
        start   = parse_date(exp.get("start_date"))
        end_raw = (exp.get("end_date") or "").strip().lower()

        # ── FIX BUG 2 (TEST_06) part A ───────────────────────────────────
        # Original code: if end is None (current/present job) → skip entry.
        # That meant Job1(end=null) and Job2 would never be compared,
        # so a gap BEFORE a "present" job was invisible.
        # Fix: treat null/present end_date as today so the entry is included.
        if end_raw in ("present", "current", "now", "") or not end_raw:
            end = datetime.now()
        else:
            end = parse_date(exp.get("end_date"))

        if start and end:
            parsed.append((start, end, _get_company(exp)))

    parsed.sort(key=lambda x: x[0])
    gap_penalty = 0
    details     = []

    for i in range(1, len(parsed)):
        prev_end   = parsed[i - 1][1]
        curr_start = parsed[i][0]
        gap_months = _months_between(prev_end, curr_start)

        # ── FIX BUG 2 (TEST_06) part B ───────────────────────────────────
        # Original threshold was > 12 months.
        # Changed to >= 6 months so a 33-month gap is always caught.
        if gap_months >= 6:
            in_education = any(
                edu_s <= prev_end and edu_e >= curr_start
                for edu_s, edu_e in edu_ranges
            )
            if not in_education:
                gap_penalty += 10
                details.append(
                    f"{gap_months}mo unexplained gap: "
                    f"'{parsed[i-1][2]}' → '{parsed[i][2]}'"
                )

    return gap_penalty, details


def detect_overlapping_jobs(extracted_json: dict) -> Tuple[int, List[str]]:
    experiences = extracted_json.get("experience", [])
    parsed      = []

    for exp in experiences:
        start    = parse_date(exp.get("start_date"))
        end      = parse_date(exp.get("end_date"))
        emp_type = _get_emp_type(exp)
        if start and end:
            parsed.append((start, end, emp_type,
                           _get_company(exp), _get_position(exp)))

    parsed.sort(key=lambda x: x[0])
    overlap_penalty = 0
    details         = []

    for i in range(1, len(parsed)):
        prev_end   = parsed[i - 1][1]
        curr_start = parsed[i][0]
        curr_type  = parsed[i][2]
        prev_type  = parsed[i - 1][2]

        if curr_start < prev_end:
            overlap_months = _months_between(curr_start, prev_end)
            if overlap_months <= 2:
                continue
            if (curr_type in CONCURRENT_EMPLOYMENT_TYPES or
                    prev_type in CONCURRENT_EMPLOYMENT_TYPES):
                continue
            overlap_penalty += 15
            details.append(
                f"Overlap ({overlap_months}mo): "
                f"'{parsed[i-1][3]}/{parsed[i-1][4]}' "
                f"and '{parsed[i][3]}/{parsed[i][4]}'"
            )
    return overlap_penalty, details


def detect_impossible_academics(extracted_json: dict) -> Tuple[int, List[str]]:
    penalty = 0
    details = []

    for edu in extracted_json.get("education", []):
        cgpa = edu.get("cgpa")
        if not cgpa:
            continue
        raw = str(cgpa)
        if raw.startswith("[INVALID"):
            penalty += 25
            details.append(f"Invalid CGPA: {raw} at {edu.get('institution','?')}")
            continue
        try:
            parts = raw.split("/")
            value = float(parts[0])
            scale = float(parts[1]) if len(parts) > 1 else 10.0
            if value > scale:
                penalty += 25
                details.append(
                    f"CGPA {value} exceeds scale {scale} "
                    f"at {edu.get('institution','?')}"
                )
        except (ValueError, IndexError):
            pass

    return penalty, details


def _parse_percentage_value(raw: str) -> Optional[float]:
    s = str(raw).strip()
    s = s.replace("%", "")
    s = re.sub(r"\s*/\s*100", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+out\s+of\s+100", "", s, flags=re.IGNORECASE)
    s = s.strip()
    try:
        return float(s)
    except ValueError:
        return None


def detect_invalid_percentages(extracted_json: dict) -> Tuple[int, List[str]]:
    penalty = 0
    details = []

    for edu in extracted_json.get("education", []):
        pct = edu.get("percentage")
        if not pct:
            continue
        raw = str(pct)
        if raw.startswith("[INVALID"):
            penalty += 20
            details.append(f"Invalid percentage: {raw} in {edu.get('degree','?')}")
        elif raw.startswith("[NON_NUMERIC"):
            penalty += 10
            details.append(f"Non-numeric percentage: {raw}")
        else:
            value = _parse_percentage_value(raw)
            if value is None:
                penalty += 10
                details.append(f"Non-numeric percentage: {pct}")
            elif value < 0 or value > 100:
                penalty += 20
                details.append(
                    f"Out-of-range percentage {pct} in {edu.get('degree','?')}"
                )
    return penalty, details


def detect_future_dates(extracted_json: dict) -> Tuple[int, List[str]]:
    now     = datetime.now()
    penalty = 0
    details = []

    for exp in extracted_json.get("experience", []):
        end_raw = (exp.get("end_date") or "").lower()
        if end_raw == "present":
            continue
        end = parse_date(exp.get("end_date"))
        if end and end > now:
            penalty += 20
            details.append(
                f"Future end_date '{exp.get('end_date')}' "
                f"at {_get_company(exp)}"
            )

    return penalty, details

def detect_empty_skills(extracted_json: dict) -> Tuple[int, List[str]]:
    technical = _get_technical_skills(extracted_json.get("skills", {}))
    if not technical:
        return 15, ["No technical skills detected"]
    if len(technical) < 3:
        return 8, [f"Very few technical skills: {len(technical)} listed"]
    return 0, []


def detect_short_tenure_pattern(extracted_json: dict) -> Tuple[int, List[str]]:
    experiences   = extracted_json.get("experience", [])
    short_count   = 0
    short_details = []

    for exp in experiences:
        if _get_emp_type(exp) in CONCURRENT_EMPLOYMENT_TYPES:
            continue
        start = parse_date(exp.get("start_date"))
        end   = parse_date(exp.get("end_date"))
        if start and end:
            months = _months_between(start, end)
            if 0 < months < 6:
                short_count += 1
                short_details.append(f"{_get_company(exp)} ({months}mo)")

    if short_count >= 3:
        return 10, [f"Job-hopper signal: {', '.join(short_details)}"]
    return 0, []


def detect_duplicate_companies(extracted_json: dict) -> Tuple[int, List[str]]:
    experiences = extracted_json.get("experience", [])
    seen        = {}
    penalty     = 0
    details     = []

    for exp in experiences:
        key = (
            _get_company(exp).lower().strip(),
            _get_position(exp).lower().strip(),
        )
        if key[0] or key[1]:
            if key in seen:
                penalty += 20
                details.append(
                    f"Duplicate entry: '{_get_company(exp)}' / '{_get_position(exp)}'"
                )
            else:
                seen[key] = True

    return penalty, details


def detect_seniority_mismatch(extracted_json: dict) -> Tuple[int, List[str]]:
    """
    Tiered matching with min_years_experience thresholds.

    Tier          Min Exp   Examples
    ──────────── ──────── ────────────────────────────────
    c_suite       12 yr    CEO, CTO, COO, CFO
    vp_director    7 yr    VP Engineering, Director
    senior_lead    3 yr    Senior Engineer, Lead, Staff, Principal
    manager        2 yr    Project Manager, Product Manager

    Fires when years_experience_at_role_start < min_years_for_tier.
    Penalty: 25 pts per violation.
    """
    penalty = 0
    details = []

    earliest_grad = None
    for edu in extracted_json.get("education", []):
        end = parse_date(_get_end_date(edu))
        if end:
            if earliest_grad is None or end < earliest_grad:
                earliest_grad = end

    if not earliest_grad:
        return 0, []

    for exp in extracted_json.get("experience", []):
        title = _get_position(exp).lower()
        start = parse_date(exp.get("start_date"))
        if not start:
            continue

        matched_tier      = None
        min_yrs_required  = 0
        for tier, data in SENIOR_TITLE_SIGNALS.items():
            if any(t in title for t in data["titles"]):
                matched_tier     = tier
                min_yrs_required = data["min_years_experience"]
                break

        if not matched_tier:
            continue

        years_exp = _months_between(earliest_grad, start) / 12

        if years_exp < min_yrs_required:
            penalty += 25
            details.append(
                f"Seniority mismatch ({matched_tier}): "
                f"'{_get_position(exp)}' at '{_get_company(exp)}' "
                f"— needs {min_yrs_required}yr exp, "
                f"had {max(0, round(years_exp, 1))}yr "
                f"(grad {earliest_grad.year}, started {start.year})"
            )

    return penalty, details


# ==========================================================
# RISK CLASSIFIER
# ==========================================================

def classify_risk_level(score: int) -> str:
    if score >= 80: return "LOW"
    if score >= 60: return "MEDIUM"
    if score >= 40: return "HIGH"
    return "CRITICAL"


# ==========================================================
# MAIN ENGINE
# ==========================================================

def resume_integrity_engine(
    text: str,
    extracted_json: Dict[str, Any]
) -> Dict[str, Any]:

    sec_score  = section_presence_score(text)
    den_score  = resume_density_score(text)
    garb_score = garbage_ratio_score(text)
    cont_score = contact_info_score(text)
    str_score  = structure_score(extracted_json)

    base_score = max(0, min(100,
        sec_score + den_score + garb_score + cont_score + str_score
    ))

    keyword_penalty,        keyword_triggers     = detect_keyword_penalties(text)
    gap_penalty,            gap_details          = detect_employment_gaps(extracted_json)
    overlap_penalty,        overlap_details      = detect_overlapping_jobs(extracted_json)
    academic_penalty,       academic_details     = detect_impossible_academics(extracted_json)
    future_penalty,         future_details       = detect_future_dates(extracted_json)
    percentage_penalty,     percentage_details   = detect_invalid_percentages(extracted_json)
    empty_skills_penalty,   empty_skills_details = detect_empty_skills(extracted_json)
    tenure_penalty,         tenure_details       = detect_short_tenure_pattern(extracted_json)
    dup_penalty,            dup_details          = detect_duplicate_companies(extracted_json)
    seniority_penalty,      seniority_details    = detect_seniority_mismatch(extracted_json)

    total_penalty = (
        keyword_penalty      +
        gap_penalty          +
        overlap_penalty      +
        academic_penalty     +
        future_penalty       +
        percentage_penalty   +
        empty_skills_penalty +
        tenure_penalty       +
        dup_penalty          +
        seniority_penalty
    )

    final_score = max(0, min(100, base_score - total_penalty))

    logger.info(
        "resume_integrity_engine: base=%d penalty=%d final=%d risk=%s",
        base_score, total_penalty, final_score, classify_risk_level(final_score)
    )

    return {
        "integrity_score": final_score,
        "risk_level":      classify_risk_level(final_score),
        "total_penalty":   total_penalty,
        "components": {
            "section_score":   sec_score,
            "density_score":   den_score,
            "garbage_score":   garb_score,
            "contact_score":   cont_score,
            "structure_score": str_score,
        },
        "penalties": {
            "keyword_triggers":   keyword_triggers,
            "gap_details":        gap_details,
            "overlap_details":    overlap_details,
            "academic_flags":     academic_details,
            "future_date_flags":  future_details,
            "percentage_flags":   percentage_details,
            "empty_skill_flags":  empty_skills_details,
            "short_tenure_flags": tenure_details,
            "duplicate_flags":    dup_details,
            "seniority_flags":    seniority_details,
        },
    }   