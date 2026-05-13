from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from .database import Base


# ==========================================================
# TABLE 1 — WorkflowRun (unchanged)
# ==========================================================

class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id = Column(Integer, primary_key=True, index=True)

    document_text    = Column(Text,    nullable=False)
    doc_type         = Column(String,  nullable=True)
    processed_data   = Column(Text,    nullable=True)
    validated_data   = Column(Text,    nullable=True)
    validation       = Column(String,  nullable=True)
    structural_score = Column(Integer, nullable=True)
    llm_score        = Column(Integer, nullable=True)
    risk_score       = Column(Integer, nullable=True)
    risk_level       = Column(String,  nullable=True)
    final_confidence = Column(Integer, nullable=True)
    explainability   = Column(Text,    nullable=True)
    decision         = Column(String,  nullable=True)
    ai_summary       = Column(Text,    nullable=True)
    fraud_score      = Column(Integer, nullable=True)
    quality_score    = Column(Integer, nullable=True)
    total_penalty    = Column(Integer, nullable=True)
    risk_reasons     = Column(Text,    nullable=True)
    integrity_report = Column(Text,    nullable=True)
    llm_full_report  = Column(Text,    nullable=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())


# ==========================================================
# TABLE 2 — ResumeUpload
# ==========================================================
# NEW COLUMN: extracted_data
#   After first LLM extraction, the validated JSON is stored here.
#   Every subsequent agent call reads from this cache instead of
#   calling the LLM again.
#   16 agents on same resume = 1 LLM call, not 16.
# ==========================================================

class ResumeUpload(Base):
    __tablename__ = "resume_uploads"

    id              = Column(Integer, primary_key=True, index=True)
    document_text   = Column(Text,    nullable=False)
    filename        = Column(String,  nullable=True)
    job_description = Column(Text,    nullable=True)
    extracted_data  = Column(Text,    nullable=True)   # JSON cache — NEW
    uploaded_at     = Column(DateTime(timezone=True), server_default=func.now())


# ==========================================================
# TABLE 3 — AgentResult
# ==========================================================

class AgentResult(Base):
    __tablename__ = "agent_results"

    id          = Column(Integer, primary_key=True, index=True)
    resume_id   = Column(Integer, ForeignKey("resume_uploads.id"), nullable=False, index=True)
    agent_name  = Column(String,  nullable=False)
    result      = Column(Text,    nullable=True)
    status      = Column(String,  nullable=True)
    error       = Column(Text,    nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())