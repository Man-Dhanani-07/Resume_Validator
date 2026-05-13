RESUME_SECTION_GROUPS = [
    {"name": "identity_header",  "terms": ["summary", "professional summary", "objective",
                                           "about me", "profile", "career objective",
                                           "personal statement", "executive summary"]},
    {"name": "experience",       "terms": ["experience", "work experience", "professional experience",
                                           "employment history", "career history", "work history",
                                           "job history", "internships", "internship experience"]},
    {"name": "education",        "terms": ["education", "academic background", "qualifications",
                                           "academic qualifications", "educational background",
                                           "degrees", "schooling"]},
    {"name": "skills",           "terms": ["skills", "technical skills", "core competencies",
                                           "expertise", "technologies", "tools", "tech stack",
                                           "programming languages", "soft skills", "key skills",
                                           "areas of expertise"]},
    {"name": "projects",         "terms": ["projects", "personal projects", "key projects",
                                           "portfolio", "academic projects", "side projects",
                                           "open source", "notable projects"]},
    {"name": "certifications",   "terms": ["certifications", "certificates", "licenses",
                                           "accreditations", "professional certifications",
                                           "credentials", "courses completed"]},
    {"name": "achievements",     "terms": ["achievements", "awards", "honors", "recognition",
                                           "accomplishments", "distinctions", "competitions",
                                           "hackathons", "scholarships", "fellowships"]},
    {"name": "contact",          "terms": ["contact", "contact information", "get in touch",
                                           "reach me", "contact details", "links"]},
    {"name": "publications",     "terms": ["publications", "research", "papers", "journals",
                                           "conference papers", "patents", "research work"]},
    {"name": "volunteer",        "terms": ["volunteer", "volunteering", "community service",
                                           "social work", "ngo work", "extracurricular"]},
    {"name": "languages",        "terms": ["languages", "language proficiency",
                                           "spoken languages", "linguistic skills"]},
    {"name": "references",       "terms": ["references", "referees", "available on request",
                                           "references available"]},
]

TOTAL_SECTION_GROUPS = len(RESUME_SECTION_GROUPS)


# ==========================================================
# FRAUD KEYWORDS
# ==========================================================

SUSPICIOUS_KEYWORDS = {

    # ── Financial Scams ────────────────────────────────────────
    "financial_scam": {
        "weight": 30,
        "terms": [
            # Original
            "lottery winner", "bitcoin investment", "crypto doubling",
            "earn money fast", "guaranteed income", "investment scheme",
            "multi-level marketing", "mlm distributor",
            # Added — common resume fraud patterns
            "forex trading expert", "binary options trader",
            "crypto arbitrage specialist", "pump and dump",
            "ponzi scheme", "pyramid scheme",
            "passive income system", "referral commission only",
            "work from home unlimited earnings",
            "earn $10000 per month", "earn $5000 weekly",
            "nft flipping expert", "defi yield farmer",
        ],
    },

    # ── Illegal / Unethical ────────────────────────────────────
    "illegal_or_unethical": {
        "weight": 40,
        "terms": [
            # Original
            "hacking services", "carding", "data breach specialist",
            "exploit system", "bypass security", "dark web",
            "unauthorized access",
            # Added — real threat actor resume patterns
            "penetration testing without authorization",
            "cracking passwords", "credential stuffing service",
            "ddos attack specialist", "ransomware development",
            "rootkit specialist", "keylogger developer",
            "phishing campaign", "spyware developer",
            "account takeover", "identity theft consultant",
            "social engineering specialist",          # context-dependent but suspicious
            "vulnerability selling", "zero-day broker",
            "black hat seo", "link farming",
            "fake review generation", "astroturfing campaigns",
            "ghost writing for academic fraud",
            "essay mill", "contract cheating",
        ],
    },

    # ── Spam / Noise Indicators ────────────────────────────────
    "spam_indicators": {
        "weight": 15,
        "terms": [
            # Original
            "click here", "telegram link", "whatsapp now",
            "dm for details", "limited offer",
            # Added — real spam patterns on fake resumes
            "contact me on telegram", "reach out on whatsapp",
            "scan qr code", "follow my instagram",
            "subscribe to my channel", "visit my website for more",
            "pay per click", "affiliate marketer",
            "drop shipping expert", "amazon fba consultant",
            "social media influencer 10m followers",
        ],
    },

    # ── Confidentiality Violations ─────────────────────────────
    "confidentiality_violation": {
        "weight": 35,
        "terms": [
            "leaked confidential data", "shared internal documents",
            "bypassed nda", "disclosed trade secrets",
            "sold proprietary code", "reverse engineered software",
            "scraped without permission", "violated terms of service",
        ],
    },
}


# ==========================================================
# NON-RESUME PATTERNS
# ==========================================================

NON_RESUME_PATTERNS = {

    # ── Cooking / Recipe ───────────────────────────────────────
    "cooking_recipe": {
        "weight": 25,
        "terms": [
            # Original
            "tablespoon", "teaspoon", "preheat oven",
            "bake at", "cups flour", "stir until", "simmer for",
            # Added
            "chopped onions", "medium heat", "add salt to taste",
            "refrigerate overnight", "serves 4", "preparation time",
            "cooking time", "ingredients:", "toss until coated",
        ],
    },

    # ── Legal Documents ────────────────────────────────────────
    "legal_document": {
        "weight": 20,
        "terms": [
            # Original
            "whereas the party", "indemnification clause",
            "terms and conditions apply",
            # Added
            "hereinafter referred to as", "notwithstanding the foregoing",
            "in witness whereof", "pursuant to section",
            "the undersigned party", "binding arbitration",
            "force majeure", "severability clause",
        ],
    },

    # ── Medical / Clinical ─────────────────────────────────────
    "medical_document": {
        "weight": 20,
        "terms": [
            "patient diagnosis", "prescribed medication",
            "dosage instructions", "clinical trial results",
            "blood pressure reading", "medical history",
            "informed consent form",
        ],
    },

    # ── Academic Assignments ───────────────────────────────────
    "academic_assignment": {
        "weight": 15,
        "terms": [
            "submitted by student", "roll number",
            "assignment submitted to", "marks obtained",
            "professor:", "course code", "semester exam",
            "answer all questions", "total marks",
        ],
    },

    # ── News / Articles ────────────────────────────────────────
    "news_article": {
        "weight": 10,
        "terms": [
            "published by reuters", "according to bbc",
            "reported by the times", "press release",
            "breaking news", "staff correspondent",
            "published on:", "last updated:",
        ],
    },
}


# ==========================================================
# UNREALISTIC / IMPOSSIBLE CLAIMS
# ==========================================================

UNREALISTIC_TERMS = {
    "weight": 20,
    "terms": [
        # Original
        "invented artificial general intelligence",
        "solved the halting problem",
        "iq 190", "iq of 190",
        "nobel prize winner",
        "solved p vs np",
        "created the internet",
        "turing award at age",
        "fully autonomous agi system",
        "world's first fully autonomous",

        # ── IQ / Intelligence Claims ───────────────────────────
        "iq 180", "iq of 180", "iq 200", "iq of 200",
        "iq 170", "mensa certified genius",
        "highest iq in", "genius level iq",

        # ── Scale Inflation ────────────────────────────────────
        "managed 10000 employees",
        "managed 50000 employees",
        "billion users daily",
        "generated $100 billion",
        "handled 1 trillion requests",
        "99.9999% uptime across all systems",
        "zero bugs in entire career",

        # ── Tech Impossibilities ───────────────────────────────
        "built quantum computer from scratch",
        "achieved 100% accuracy on all ml models",
        "trained model on entire internet",
        "cracked 256-bit encryption",
        "solved np-complete in polynomial time",
        "built artificial superintelligence",
        "created sentient ai",

        # ── Award Fabrications ─────────────────────────────────
        "youngest billionaire",
        "youngest ceo in history",
        "world record holder in programming",
        "guinness world record for coding",
        "best developer in the world",
        "number one developer globally",

        # ── Degree / Credential Fabrications ──────────────────
        "phd from mit at age 15",
        "graduated age 12",
        "triple phd",
        "degree from hogwarts",           # joke/fake university
        "certified by god",               # absurd credential
        "self-awarded certification",
        "diploma from unaccredited",
    ],
}


# ==========================================================
# SENIORITY TITLES (for seniority mismatch detection)
# ==========================================================

SENIOR_TITLE_SIGNALS = {
    # C-Suite — 15+ years typically expected
    "c_suite": {
        "min_years_experience": 12,
        "titles": [
            "chief executive officer", "ceo",
            "chief technology officer", "cto",
            "chief operating officer", "coo",
            "chief financial officer", "cfo",
            "chief product officer", "cpo",
            "chief data officer", "cdo",
            "chief information officer", "cio",
        ],
    },
    # VP / Director — 8+ years typically expected
    "vp_director": {
        "min_years_experience": 7,
        "titles": [
            "vice president", "vp of engineering", "vp engineering",
            "vp product", "vp of product",
            "director of engineering", "director of technology",
            "director of product", "engineering director",
            "managing director",
        ],
    },
    # Senior / Lead / Principal — 3+ years typically expected
    "senior_lead": {
        "min_years_experience": 3,
        "titles": [
            "senior engineer", "senior developer", "senior software engineer",
            "senior data scientist", "senior analyst", "senior architect",
            "lead engineer", "lead developer", "lead data scientist",
            "principal engineer", "principal architect",
            "staff engineer", "staff software engineer",
            "head of engineering", "head of product", "head of",
            "engineering manager", "technical lead", "tech lead",
        ],
    },
    # Manager — 2+ years typically expected
    "manager": {
        "min_years_experience": 2,
        "titles": [
            "manager", "project manager", "product manager",
            "program manager", "delivery manager",
            "scrum master",
        ],
    },
}

# Flat set for quick prefix matching (used in detect_seniority_mismatch)
SENIOR_TITLE_FLAT = {
    title
    for group in SENIOR_TITLE_SIGNALS.values()
    for title in group["titles"]
}


# ==========================================================
# EMPLOYMENT TYPE ALIASES (concurrent role detection)
# ==========================================================

CONCURRENT_EMPLOYMENT_TYPES = {
    "part-time", "part time", "parttime",
    "contract", "contractor",
    "freelance", "freelancer",
    "consulting", "consultant",
    "self-employed", "self employed",
    "volunteer", "volunteering",
    "internship", "intern",
    "temporary", "temp",
    "casual", "gig",
}


# ==========================================================
# SCORE COMPONENT CAPS (for hbar rendering in dashboard)
# ==========================================================

SCORE_COMPONENT_CAPS = {
    "section_score":   30,
    "density_score":   20,
    "garbage_score":   10,
    "contact_score":   15,
    "structure_score": 25,
}