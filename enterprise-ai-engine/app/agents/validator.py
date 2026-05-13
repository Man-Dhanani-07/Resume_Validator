import json
import re
import logging
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional, Dict, Tuple, Any, Union
from datetime import datetime

logger = logging.getLogger(__name__)


# ==========================================================
# SUB-MODELS
# ==========================================================

class Location(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

class Links(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None

class Profile(BaseModel):
    # Accepts both "full_name" and "name" (alias)
    full_name: Optional[str] = Field(default=None, alias="full_name")
    headline: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[Location] = None
    work_authorization: Optional[str] = None
    links: Optional[Links] = None

    model_config = {"populate_by_name": True}

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v):
        if v is None:
            return v
        if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", v):
            logger.warning("validate_email_format: invalid email wiped — %r", v)
            return None
        return v


class Experience(BaseModel):
    company: Optional[str] = None
    # Accepts both "position" and "title" (alias)
    position: Optional[str] = Field(default=None, alias="position")
    employment_type: Optional[str] = None
    work_mode: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    description: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)
    impact_metrics: List[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def check_date_ordering(self):
        start = _parse_date_safe(self.start_date)
        end   = _parse_date_safe(self.end_date)
        if start and end and start > end:
            logger.warning(
                "check_date_ordering: start > end at %r / %r",
                self.company, self.position
            )
            self.highlights = ["[FLAG:start_after_end_date]"] + self.highlights
        return self


class Education(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    degree_level: Optional[str] = None
    field_of_study: Optional[str] = None
    location: Optional[str] = None
    start_date: Optional[str] = None
    # Accepts both "end_date" and "year" (alias)
    end_date: Optional[str] = Field(default=None, alias="end_date")
    cgpa: Optional[Union[str, float, int]] = None
    percentage: Optional[Union[str, float, int]] = None

    model_config = {"populate_by_name": True}

    @field_validator("cgpa")
    @classmethod
    def validate_cgpa(cls, v):
        if v is None:
            return v
        raw = str(v).strip()
        try:
            parts = raw.split("/")
            value = float(parts[0])
            scale = float(parts[1]) if len(parts) > 1 else 10.0
            # ── FIX BUG 1 (TEST_05) ──────────────────────────────────────
            # If value > 10 AND no explicit scale given, the LLM almost
            # certainly put a percentage (e.g. 72) into the cgpa field.
            # Tag it so the model_validator below can move it to percentage.
            if value > 10 and len(parts) == 1:
                logger.warning(
                    "validate_cgpa: value %s > 10 with no scale — "
                    "likely a percentage misplaced in cgpa field", raw
                )
                return f"[LIKELY_PERCENTAGE:{raw}]"
            if value < 0 or value > scale:
                logger.warning("validate_cgpa: out-of-range value %r", raw)
                return f"[INVALID:{raw}]"
        except (ValueError, IndexError):
            pass
        return raw

    @model_validator(mode="after")
    def fix_cgpa_percentage_confusion(self):
        """
        FIX BUG 1 (TEST_05):
        When the LLM writes a percentage value (e.g. 72) into the cgpa
        field, validate_cgpa tags it as [LIKELY_PERCENTAGE:72].
        This validator moves it to the percentage field so:
          - cgpa becomes None  (no false INVALID_CGPA flag)
          - percentage gets 72 (correct field, valid range 0-100)
        """
        if self.cgpa and str(self.cgpa).startswith("[LIKELY_PERCENTAGE:"):
            raw_val = str(self.cgpa)[len("[LIKELY_PERCENTAGE:"):-1]
            logger.info(
                "fix_cgpa_percentage_confusion: moving %r from cgpa → percentage",
                raw_val
            )
            # Only move if percentage is not already populated
            if self.percentage is None:
                self.percentage = raw_val
            self.cgpa = None
        return self

    @field_validator("percentage")
    @classmethod
    def validate_percentage(cls, v):
        if v is None:
            return v
        raw = str(v).strip()
        raw_clean = raw.replace("%", "")
        raw_clean = re.sub(r"\s*/\s*100", "", raw_clean, flags=re.IGNORECASE)
        raw_clean = re.sub(r"\s+out\s+of\s+100", "", raw_clean, flags=re.IGNORECASE)
        raw_clean = raw_clean.strip()
        try:
            value = float(raw_clean)
            if value < 0 or value > 100:
                logger.warning("validate_percentage: out-of-range value %r", raw)
                return f"[INVALID:{raw}]"
            return raw_clean
        except ValueError:
            logger.warning("validate_percentage: non-numeric value %r", raw)
            return f"[NON_NUMERIC:{raw}]"


class SkillCategory(BaseModel):
    category: Optional[str] = None
    items: List[str] = Field(default_factory=list)


class SkillProficiency(BaseModel):
    skill: Optional[str] = None
    level: Optional[str] = None
    years: Optional[float] = None

class Skills(BaseModel):
    categorized: List[SkillCategory] = Field(default_factory=list)
    technical: List[str] = Field(default_factory=list)
    soft: List[str] = Field(default_factory=list)
    proficiency: List[SkillProficiency] = Field(default_factory=list)

class ProjectLinks(BaseModel):
    github: Optional[str] = None
    live: Optional[str] = None
    demo: Optional[str] = None

class Project(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    impact: List[str] = Field(default_factory=list)
    links: Optional[ProjectLinks] = None

class Certification(BaseModel):
    name: Optional[str] = None
    issuer: Optional[str] = None
    date: Optional[str] = None
    credential_id: Optional[str] = None

class CodingProfile(BaseModel):
    platform: Optional[str] = None
    username: Optional[str] = None
    rating: Optional[Union[str, float, int]] = None
    rank: Optional[str] = None

    @field_validator("rating", mode="before")
    @classmethod
    def coerce_rating_to_str(cls, v):
        if v is None:
            return v
        return str(v)


class Achievements(BaseModel):
    coding_profiles: List[CodingProfile] = Field(default_factory=list)
    awards_honors: List[str] = Field(default_factory=list)


class Metadata(BaseModel):
    total_years_experience: float = 0.0
    confidence_score: float = 0.0
    source_file: Optional[str] = None
    parsed_at: Optional[str] = None
    parser_version: Optional[str] = None


class Resume(BaseModel):
    profile: Profile
    summary: Optional[str] = None
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    skills: Skills
    languages_spoken: List[str] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    certifications: List[Certification] = Field(default_factory=list)
    achievements: Optional[Achievements] = None
    metadata: Metadata


# ==========================================================
# DATE UTILITY
# ==========================================================

def _parse_date_safe(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    s = date_str.strip()
    if s.lower() == "present":
        return datetime.now()
    for fmt in ("%b %Y", "%B %Y", "%Y-%m", "%Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    m = re.search(r"\b(19|20)\d{2}\b", s)
    if m:
        try:
            return datetime.strptime(m.group(), "%Y")
        except ValueError:
            pass
    return None


# ==========================================================
# NORMALIZER — maps real-world JSON shapes → Resume schema
# ==========================================================

def _normalize_resume_data(data: dict) -> dict:
    """
    Transforms real-world LLM-extracted JSON into the Resume schema shape.
    Handles all known field name variations without modifying Pydantic models.
    """
    data = dict(data)

    # ── profile ──
    profile = dict(data.get("profile", {}))

    if "name" in profile and "full_name" not in profile:
        logger.debug("_normalize: profile.name → full_name")
        profile["full_name"] = profile.pop("name")

    links = dict(profile.get("links") or {})
    for link_key in ("linkedin", "github", "portfolio"):
        if link_key in profile and link_key not in links:
            logger.debug("_normalize: profile.%s → profile.links.%s", link_key, link_key)
            links[link_key] = profile.pop(link_key)
    if links:
        profile["links"] = links

    data["profile"] = profile

    # ── experience ──
    normalized_exp = []
    for exp in data.get("experience", []):
        exp = dict(exp)
        if "title" in exp and "position" not in exp:
            logger.debug("_normalize: experience.title → position")
            exp["position"] = exp.pop("title")
        if "responsibilities" in exp and not exp.get("highlights"):
            exp["highlights"] = exp.pop("responsibilities")
        normalized_exp.append(exp)
    data["experience"] = normalized_exp

    # ── education ──
    normalized_edu = []
    for edu in data.get("education", []):
        edu = dict(edu)
        if "year" in edu and "end_date" not in edu:
            logger.debug("_normalize: education.year → end_date")
            edu["end_date"] = edu.pop("year")
        normalized_edu.append(edu)
    data["education"] = normalized_edu

    # ── skills ──
    skills_raw = data.get("skills", {})
    if isinstance(skills_raw, dict):
        if "technical" not in skills_raw and "categorized" not in skills_raw:
            logger.debug("_normalize: skills flat dict → categorized + technical")
            all_technical = []
            categorized = []
            for cat_name, items in skills_raw.items():
                if isinstance(items, list):
                    all_technical.extend(items)
                    categorized.append({"category": cat_name, "items": items})
            data["skills"] = {
                "technical":   all_technical,
                "categorized": categorized,
                "soft":        [],
                "proficiency": [],
            }
        elif "technical" not in skills_raw:
            all_technical = []
            for cat in skills_raw.get("categorized", []):
                all_technical.extend(cat.get("items", []))
            skills_raw["technical"] = all_technical
            data["skills"] = skills_raw

    # ── achievements ──
    achievements_raw = data.get("achievements")

    if isinstance(achievements_raw, list):
        awards = []
        coding_profiles = []
        for item in achievements_raw:
            if isinstance(item, str):
                awards.append(item)
            elif isinstance(item, dict):
                if item.get("platform") or item.get("rating") or item.get("rank"):
                    rating_raw = item.get("rating")
                    coding_profiles.append({
                        "platform": item.get("platform"),
                        "username": item.get("username") or item.get("handle"),
                        "rating":   str(rating_raw) if rating_raw is not None else None,
                        "rank":     item.get("rank"),
                    })
                else:
                    text = (
                        item.get("name") or item.get("title") or
                        item.get("description") or item.get("award") or
                        item.get("achievement")
                    )
                    if text:
                        awards.append(str(text))
                    else:
                        fallback = " | ".join(
                            str(v) for v in item.values()
                            if v and isinstance(v, (str, int, float))
                        )
                        if fallback:
                            awards.append(fallback)
        data["achievements"] = {
            "coding_profiles": coding_profiles,
            "awards_honors":   awards,
        }

    elif isinstance(achievements_raw, dict):
        awards_raw = achievements_raw.get("awards_honors", [])
        cleaned = []
        for item in awards_raw:
            if isinstance(item, str):
                cleaned.append(item)
            elif isinstance(item, dict):
                text = (
                    item.get("name") or item.get("title") or
                    item.get("description") or item.get("award")
                )
                if text:
                    cleaned.append(str(text))
        achievements_raw["awards_honors"] = cleaned
        data["achievements"] = achievements_raw

    # ── certifications ──
    normalized_certs = []
    for cert in data.get("certifications", []):
        if isinstance(cert, str):
            normalized_certs.append({"name": cert, "issuer": None, "date": None, "credential_id": None})
        elif isinstance(cert, dict):
            normalized_certs.append({
                "name":          cert.get("name") or cert.get("title") or cert.get("certification"),
                "issuer":        cert.get("issuer") or cert.get("provider") or cert.get("organization"),
                "date":          cert.get("date") or cert.get("issued_date") or cert.get("year"),
                "credential_id": cert.get("credential_id") or cert.get("id") or cert.get("link"),
            })
    data["certifications"] = normalized_certs

    # ── projects ──
    normalized_projects = []
    for proj in data.get("projects", []):
        if isinstance(proj, dict):
            proj = dict(proj)
            links_raw = proj.get("links")
            if isinstance(links_raw, str):
                url = links_raw
                if "github.com" in url.lower():
                    proj["links"] = {"github": url, "live": None, "demo": None}
                else:
                    proj["links"] = {"github": None, "live": url, "demo": None}
            elif not links_raw:
                for url_key in ("project_link", "url", "link", "github_url"):
                    url_val = proj.get(url_key)
                    if url_val and isinstance(url_val, str):
                        if "github.com" in url_val.lower():
                            proj["links"] = {"github": url_val, "live": None, "demo": None}
                        else:
                            proj["links"] = {"github": None, "live": url_val, "demo": None}
                        break
            normalized_projects.append(proj)
    data["projects"] = normalized_projects

    # ── metadata ──
    if "metadata" not in data:
        data["metadata"] = {
            "total_years_experience": 0.0,
            "confidence_score":       0.75,
            "source_file":            None,
            "parsed_at":              None,
            "parser_version":         None,
        }
    elif data["metadata"].get("confidence_score", 0) == 0:
        data["metadata"]["confidence_score"] = 0.75

    return data


# ==========================================================
# COMPLETENESS SCORER
# ==========================================================

COMPLETENESS_WEIGHTS = {
    "has_name":             10,
    "has_email":             8,
    "has_phone":             5,
    "has_experience":       20,
    "has_education":        15,
    "has_technical_skills": 15,
    "has_projects":         10,
    "has_summary":           5,
    "has_certifications":    5,
    "has_location":          4,
    "has_links":             3,
}


def compute_completeness_score(resume: Resume) -> Tuple[int, Dict[str, bool]]:
    checks = {
        "has_name":             bool(resume.profile.full_name),
        "has_email":            bool(resume.profile.email),
        "has_phone":            bool(resume.profile.phone),
        "has_experience":       len(resume.experience) > 0,
        "has_education":        len(resume.education) > 0,
        "has_technical_skills": len(resume.skills.technical) > 0,
        "has_projects":         len(resume.projects) > 0,
        "has_summary":          bool(resume.summary),
        "has_certifications":   len(resume.certifications) > 0,
        "has_location":         resume.profile.location is not None,
        "has_links":            resume.profile.links is not None,
    }
    total  = sum(COMPLETENESS_WEIGHTS.values())
    earned = sum(COMPLETENESS_WEIGHTS[k] for k, v in checks.items() if v)
    score  = round((earned / total) * 100)
    logger.debug("compute_completeness_score: %d/100", score)
    return score, checks


# ==========================================================
# CONSISTENCY CHECKS
# ==========================================================

def run_consistency_checks(resume: Resume) -> List[str]:
    warnings: List[str] = []
    now = datetime.now()

    for exp in resume.experience:
        start = _parse_date_safe(exp.start_date)
        end   = _parse_date_safe(exp.end_date)
        if start and start > now:
            warnings.append(f"Future start_date: {exp.company} / {exp.position}")
        if end and end > now and (exp.end_date or "").lower() != "present":
            warnings.append(f"Non-present future end_date: {exp.company} / {exp.position}")

    for edu in resume.education:
        start = _parse_date_safe(edu.start_date)
        end   = _parse_date_safe(edu.end_date)
        if start and end and end < start:
            warnings.append(f"Education end before start: {edu.institution}")
        if edu.cgpa and str(edu.cgpa).startswith("[INVALID"):
            warnings.append(f"Invalid CGPA: {edu.cgpa} at {edu.institution}")
        if edu.percentage and str(edu.percentage).startswith("[INVALID"):
            warnings.append(f"Invalid percentage: {edu.percentage}")

    short = 0
    for exp in resume.experience:
        if (exp.employment_type or "").lower() in {
            "part-time", "contract", "freelance", "consulting", "self-employed"
        }:
            continue
        s = _parse_date_safe(exp.start_date)
        e = _parse_date_safe(exp.end_date)
        if s and e:
            months = (e.year - s.year) * 12 + (e.month - s.month)
            if 0 < months < 6:
                short += 1
    if short >= 3:
        warnings.append(f"Job-hopping signal: {short} full-time roles under 6 months")

    if warnings:
        logger.info("run_consistency_checks: %d warning(s) found", len(warnings))

    return warnings


# ==========================================================
# THRESHOLDS
# ==========================================================

CONFIDENCE_THRESHOLD   = 0.40
COMPLETENESS_THRESHOLD = 30


# ==========================================================
# MAIN validate_resume
# ==========================================================

def validate_resume(json_text: str):
    """
    Returns:
        (validated_dict, None)      — success
        (validated_dict, warning)   — soft-pass with warnings
        (None, error_string)        — hard failure
    """
    # Stage 1: JSON parse
    try:
        data = json.loads(json_text) if isinstance(json_text, str) else json_text
    except json.JSONDecodeError as e:
        logger.error("validate_resume: JSON parse failed — %s", e)
        return None, f"Invalid JSON format: {str(e)}"

    # Stage 2: Normalize
    try:
        data = _normalize_resume_data(data)
    except Exception as e:
        logger.error("validate_resume: normalization failed — %s", e)
        return None, f"Normalization error: {str(e)}"

    # Stage 3: Pydantic schema validation
    try:
        validated = Resume(**data)
    except Exception as e:
        logger.error("validate_resume: schema validation failed — %s", e)
        return None, f"Schema validation error: {str(e)}"

    # Stage 4: Confidence check
    confidence = validated.metadata.confidence_score
    if confidence < CONFIDENCE_THRESHOLD:
        logger.warning(
            "validate_resume: low confidence %.2f < %.2f threshold",
            confidence, CONFIDENCE_THRESHOLD
        )
        return None, (
            f"Low confidence extraction: {confidence:.2f} "
            f"(threshold: {CONFIDENCE_THRESHOLD})."
        )

    # Stage 5: Completeness check
    completeness_score, field_presence = compute_completeness_score(validated)
    if completeness_score < COMPLETENESS_THRESHOLD:
        missing = [k for k, v in field_presence.items() if not v]
        logger.warning(
            "validate_resume: completeness %d < %d threshold, missing: %s",
            completeness_score, COMPLETENESS_THRESHOLD, missing
        )
        return None, (
            f"Resume too incomplete: completeness={completeness_score}/100. "
            f"Missing: {missing}"
        )


    # Stage 6: Consistency checks
    consistency_warnings = run_consistency_checks(validated)

    result = validated.model_dump()
    result["_validation_meta"] = {
        "completeness_score":    completeness_score,
        "field_presence":        field_presence,
        "consistency_warnings":  consistency_warnings,
        "extraction_confidence": confidence,
    }

    warning_message = None
    if consistency_warnings:
        warning_message = (
            f"Validation passed with {len(consistency_warnings)} warning(s): "
            + "; ".join(consistency_warnings[:3])
        )

    logger.info(
        "validate_resume: PASSED — completeness=%d, confidence=%.2f, warnings=%d",
        completeness_score, confidence, len(consistency_warnings)
    )
    return result, warning_message
    