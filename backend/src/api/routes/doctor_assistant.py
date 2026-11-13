
import json
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.processed_file import ProcessedFile
from src.models.ocr_result import OCRResult
from src.models.doctor_assistant import DoctorAssistant
from src.schemas.doctor_assistant import DoctorAssistantResponse
from src.LLM.doctor_assist import doctor_assistant_from_data
from src.services.doctor_assistant.retrieval import retrieve_evidence, knowledge_base_status

router = APIRouter(prefix="/api/doctor-assistant", tags=["Doctor Assistant"])


def _get_report_json(db: Session, processed_file: ProcessedFile) -> dict:
    ocr_result = (
        db.query(OCRResult)
        .filter(OCRResult.document_id == processed_file.document_id)
        .order_by(OCRResult.created_at.desc())
        .first()
    )
    if not ocr_result:
        raise HTTPException(status_code=404, detail="OCR result not found for this document.")
    json_path = Path(ocr_result.json_path)
    if not json_path.is_file():
        raise HTTPException(status_code=404, detail="Normalized laboratory JSON file not found.")
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=500, detail=f"Could not read normalized report JSON: {exc}")
    if not isinstance(data, dict):
        raise HTTPException(status_code=422, detail="Normalized report must be a JSON object.")
    return data


def _find_processed_file(db: Session, processed_file_id: int) -> ProcessedFile:
    item = db.get(ProcessedFile, processed_file_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Processed file not found.")
    return item


@router.post("/{processed_file_id}", response_model=DoctorAssistantResponse)
def generate_doctor_assistant(processed_file_id: int, db: Session = Depends(get_db)):
    """Generate (or refresh) the physician-facing interpretation for a processed page."""
    processed_file = _find_processed_file(db, processed_file_id)
    report = _get_report_json(db, processed_file)
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    try:
        result = doctor_assistant_from_data(report, model=model)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Doctor assistant generation failed: {exc}")

    record = (
        db.query(DoctorAssistant)
        .filter(DoctorAssistant.processed_file_id == processed_file.id)
        .first()
    )
    if record is None:
        record = DoctorAssistant(
            processed_file_id=processed_file.id,
            user_id=processed_file.document.user_id,
            response_json=json.dumps(result, ensure_ascii=False),
            model_name=model,
        )
        db.add(record)
    else:
        record.response_json = json.dumps(result, ensure_ascii=False)
        record.model_name = model
    db.commit()
    db.refresh(record)
    return result


@router.post("/{processed_file_id}/regenerate", response_model=DoctorAssistantResponse)
def regenerate_doctor_assistant(processed_file_id: int, db: Session = Depends(get_db)):
    """Explicit alias for regenerating the latest interpretation."""
    return generate_doctor_assistant(processed_file_id, db)


@router.get("/{processed_file_id}", response_model=DoctorAssistantResponse)
def get_doctor_assistant(processed_file_id: int, db: Session = Depends(get_db)):
    processed_file = _find_processed_file(db, processed_file_id)
    record = (
        db.query(DoctorAssistant)
        .filter(DoctorAssistant.processed_file_id == processed_file.id)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Doctor assistant result not found.")
    try:
        return json.loads(record.response_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Stored doctor assistant JSON is invalid.")


@router.get("/{processed_file_id}/evidence")
def get_doctor_assistant_evidence(processed_file_id: int, db: Session = Depends(get_db)):
    """Preview retrieved textbook passages without invoking the LLM."""
    processed_file = _find_processed_file(db, processed_file_id)
    report = _get_report_json(db, processed_file)
    from src.LLM.doctor_assist import _report_query
    evidence = retrieve_evidence(_report_query(report))
    return {"processed_file_id": processed_file_id, "knowledge_base": knowledge_base_status(),
            "evidence": evidence}
