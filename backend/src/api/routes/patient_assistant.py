
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.processed_file import ProcessedFile
from src.models.ocr_result import OCRResult
from src.models.patient_assistant import PatientAssistant
from src.schemas.patient_assistant import PatientAssistantResponse

from src.LLM.patient_assist import patient_assistant


router = APIRouter(
    prefix="/api/patient-assistant",
    tags=["Patient Assistant"],
)


@router.post(
    "/{processed_file_id}",
    response_model=PatientAssistantResponse,
)
def generate_patient_assistant(
    processed_file_id: int,
    db: Session = Depends(get_db),
):

    # --------------------------------------------------------
    # 1. Find processed file
    # --------------------------------------------------------

    processed_file = (
        db.query(ProcessedFile)
        .filter(
            ProcessedFile.id == processed_file_id
        )
        .first()
    )

    if not processed_file:
        raise HTTPException(
            status_code=404,
            detail="Processed file not found",
        )

    # --------------------------------------------------------
    # 2. Find OCR result for this document
    # --------------------------------------------------------

    ocr_result = (
        db.query(OCRResult)
        .filter(
            OCRResult.document_id
            == processed_file.document_id
        )
        .order_by(
            OCRResult.created_at.desc()
        )
        .first()
    )

    if not ocr_result:
        raise HTTPException(
            status_code=404,
            detail="OCR result not found",
        )

    # --------------------------------------------------------
    # 3. Get JSON path
    # --------------------------------------------------------

    json_path = Path(
        ocr_result.json_path
    )

    if not json_path.exists():
        raise HTTPException(
            status_code=404,
            detail="OCR JSON file not found",
        )

    print(
        f"Using OCR JSON file at: {json_path}"
    )

    # --------------------------------------------------------
    # 4. Run Patient Assistant
    # --------------------------------------------------------

    try:

        assistant_result = patient_assistant(
            str(json_path)
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=f"Patient assistant failed: {str(exc)}",
        )

    # --------------------------------------------------------
    # 5. Save Patient Assistant result
    # --------------------------------------------------------

    assistant_record = PatientAssistant(
        processed_file_id=processed_file.id,
        user_id=processed_file.document.user_id,
        response_json=json.dumps(
            assistant_result,
            ensure_ascii=False,
        ),
    )

    db.add(assistant_record)
    db.commit()
    db.refresh(assistant_record)

    # --------------------------------------------------------
    # 6. Return response
    # --------------------------------------------------------

    return assistant_result




@router.get(
    "/{processed_file_id}",
    response_model=PatientAssistantResponse,
)
def get_patient_assistant(
    processed_file_id: int,
    db: Session = Depends(get_db),
):

    # 1. Find processed file
    processed_file = (
        db.query(ProcessedFile)
        .filter(
            ProcessedFile.id == processed_file_id
        )
        .first()
    )

    if not processed_file:
        raise HTTPException(
            status_code=404,
            detail="Processed file not found",
        )

    # 2. Find Patient Assistant response
    assistant_record = (
        db.query(PatientAssistant)
        .filter(
            PatientAssistant.processed_file_id
            == processed_file.id
        )
        .first()
    )

    if not assistant_record:
        raise HTTPException(
            status_code=404,
            detail="Patient assistant result not found",
        )

    # 3. Convert stored JSON string to Python object
    try:
        assistant_result = json.loads(
            assistant_record.response_json
        )

    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Invalid patient assistant JSON",
        )

    # 4. Return the LLM response
    return assistant_result