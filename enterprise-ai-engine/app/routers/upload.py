import logging
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from typing import Optional
import tempfile
import os

from app.ingestion.pdf_parser import extract_text_from_pdf
from app.db.repository import save_resume_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/resume", tags=["Upload"])


@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    job_description: Optional[str] = Form(None),
):
    """
    Upload a resume PDF. Returns resume_id for all agent calls.
    """

    # ── 1. Validate file type ─────────────────────────────────────────────
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported."
        )

    # ── 2. Write stream to temp file (pdf_parser needs a file path) ───────
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        logger.info("upload_resume: temp file saved — %s", tmp_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {str(e)}")

    # ── 3. Extract text ───────────────────────────────────────────────────
    try:
        document_text = extract_text_from_pdf(tmp_path)

        # pdf_parser now always returns a plain str — guard just in case
        if not isinstance(document_text, str):
            document_text = str(document_text)

        # Strip leading/trailing whitespace
        document_text = document_text.strip()

        if len(document_text) < 50:
            raise HTTPException(
                status_code=422,
                detail="Could not extract readable text. "
                       "Ensure the PDF is not a blank or image-only scan."
            )

        logger.info(
            "upload_resume: extracted %d chars from '%s'",
            len(document_text), file.filename
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("upload_resume: extraction failed — %s", e)
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

    # ── 4. Save raw text to DB ────────────────────────────────────────────
    # IMPORTANT: store raw plain text — never json.dumps() here.
    # json.dumps() was in the old CLI main.py and caused the LLM to
    # receive JSON-escaped text instead of resume content → all nulls.
    try:
        resume_id = save_resume_upload(
            document_text=document_text,
            filename=file.filename,
            job_description=job_description,
        )
    except Exception as e:
        logger.error("upload_resume: DB save failed — %s", e)
        raise HTTPException(status_code=500, detail=f"Database save failed: {str(e)}")

    return {
        "resume_id":   resume_id,
        "filename":    file.filename,
        "text_length": len(document_text),
        "message":     f"Resume uploaded. Use resume_id={resume_id} to run agents.",
    }