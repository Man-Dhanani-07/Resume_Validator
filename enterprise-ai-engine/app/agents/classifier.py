import re
import logging
from app.agents.llm_client import ask_llm

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# KEYWORD FALLBACK
# If the LLM misclassifies a resume as something else, these
# keywords act as a safety net.
# Logic: 4+ hits from this list = almost certainly a resume.
# ─────────────────────────────────────────────────────────────
_RESUME_SIGNALS = [
    # Section headers
    "work experience", "professional experience", "employment history",
    "internship", "projects", "certifications", "achievements",
    "technical skills", "core competencies", "areas of expertise",
    # Education signals
    "education", "bachelor", "master", "b.tech", "m.tech", "b.e", "m.e",
    "b.sc", "m.sc", "mba", "pgdm", "cgpa", "gpa", "percentage",
    # Personal profile signals
    "objective", "career objective", "professional summary", "profile",
    "date of birth", "languages known", "hobbies",
    # Online profiles
    "linkedin", "github.com", "leetcode", "hackerrank",
    "codeforces", "codechef", "portfolio",
    # Common resume words
    "references", "curriculum vitae", "resume", "biodata",
]


def _looks_like_resume(text: str) -> bool:
    """
    Returns True if the text contains 4+ strong resume signals.
    Used to override LLM misclassification.
    """
    lower = text.lower()
    hits = sum(1 for signal in _RESUME_SIGNALS if signal in lower)
    logger.debug("_looks_like_resume: %d signal hits", hits)
    return hits >= 4


def _smart_truncate(text: str, max_chars: int = 4000) -> str:
    """
    Takes text from START + END of document.
    This captures name/contact (usually at top) AND education/skills
    (often at bottom) — both critical for resume classification.
    Avoids the bug where text[:3000] cuts before any resume sections appear.
    """
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n[...middle truncated...]\n\n" + text[-half:]


def classify_document(text: str) -> str:

    # ── Keyword pre-check ────────────────────────────────────────────────
    # If text already screams "resume" before even calling LLM, return fast.
    if _looks_like_resume(text):
        logger.info("classify_document: keyword pre-check → resume (skipping LLM)")
        return "resume"

    # ── Smart truncation — capture both top and bottom of document ────────
    truncated = _smart_truncate(text, max_chars=4000)

    prompt = f"""You are an expert document classification engine used in enterprise data pipelines.
Your output is consumed directly by a machine parser — any deviation from the rules will break the pipeline.

════════════════════════════════════════
OUTPUT CONTRACT  (MUST follow exactly)
════════════════════════════════════════
✦ Return ONE word only
✦ Lowercase only
✦ No punctuation, no spaces, no newlines
✦ No preamble, no explanation
✦ Must be exactly one of the 16 labels below

════════════════════════════════════════
ALLOWED LABELS
════════════════════════════════════════
resume    → A person's professional profile / CV / biodata / job application.
            Contains ANY of: name + contact info, education, skills, work experience,
            projects, certifications, career objective.
            IMPORTANT: Student/fresher resumes with ONLY education + skills (no job
            experience) are STILL a resume — not a report.
            IMPORTANT: If a document describes a single person's background → resume.

invoice   → Payment request; line items, amount due, invoice number
receipt   → Payment confirmation; transaction ID, amount paid
contract  → Legal agreement; clauses, obligations, signatures
report    → Research/analysis document; findings, data, recommendations.
            A report is about a TOPIC, not about a PERSON.
bank      → Bank statement; account number, debit/credit transactions
identity  → Govt ID; passport, national ID, driver's license, DOB
medical   → Healthcare; prescription, lab result, diagnosis
legal     → Court/regulatory; affidavit, court order, subpoena
shipping  → Logistics; bill of lading, waybill, packing list
tax       → Tax filing; W-2, 1099, VAT/GST return
form      → Data-collection; application form, survey, questionnaire
email     → Digital message; From/To/Subject/Date headers
letter    → Formal correspondence; Dear..., Sincerely...
statement → Account activity summary; credit card, utility bill
unknown   → ONLY if genuinely cannot match any label above

════════════════════════════════════════
TIE-BREAKER RULES
════════════════════════════════════════
• report  vs resume  → Does it describe a PERSON (name, skills, education)?
                        YES → resume.  NO (describes a topic) → report.
• invoice vs receipt → requested payment = invoice; confirmed payment = receipt
• bank vs statement  → bank-issued = bank; any account summary = statement
• legal vs contract  → agreement between parties = contract; court action = legal

════════════════════════════════════════
DOCUMENT
════════════════════════════════════════
{truncated}
════════════════════════════════════════

Label:"""

    allowed = {
        "invoice", "receipt", "contract", "report", "bank",
        "identity", "medical", "legal", "shipping", "tax",
        "resume", "form", "email", "letter", "statement", "unknown"
    }

    try:
        result = ask_llm(prompt)
        label  = result.strip().lower().strip(".,!?;: \n")

        if label not in allowed:
            logger.warning(
                "classify_document: unexpected LLM label %r — trying keyword fallback",
                label
            )
            # Unknown label from LLM — fall through to keyword fallback below
            label = "unknown"

        # ── Keyword fallback ─────────────────────────────────────────────
        # If LLM returned something other than "resume" but the full text
        # looks like a resume → override.
        # This catches cases where the LLM sees a student/fresher resume
        # (no work experience) and calls it "report" or "form".
        if label != "resume" and _looks_like_resume(text):
            logger.info(
                "classify_document: overriding LLM label %r → resume "
                "(keyword fallback: 4+ resume signals found)", label
            )
            return "resume"

        logger.info("classify_document: final label = %r", label)
        return label

    except RuntimeError as exc:
        logger.error("classify_document: LLM unavailable — %s", exc)
        # LLM failed entirely — keyword fallback is the only option
        if _looks_like_resume(text):
            logger.info("classify_document: LLM failed, keyword fallback → resume")
            return "resume"
        return "unknown"