
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.document import Document
from src.models.processed_file import ProcessedFile
from src.models.ocr_result import OCRResult

from src.ocr.engine.gemini_ocr import ocr
from src.ocr.engine.gemini_normalizer import normalize


OCR_DIR = Path("data/ocr")
OCR_DIR.mkdir(parents=True, exist_ok=True)


router = APIRouter(
    prefix="/api/ocr",
    tags=["OCR"],
)


# ---------------------------------------------------------
# POST /api/ocr/{document_id}
# ---------------------------------------------------------

@router.post("/{document_id}")
def process_ocr(
    document_id: int,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # 1. Find document
    # -----------------------------------------------------

    document = db.get(Document, document_id)

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    # -----------------------------------------------------
    # 2. Find preprocessed files
    # -----------------------------------------------------

    processed_files = (
        db.query(ProcessedFile)
        .filter(
            ProcessedFile.document_id == document_id
        )
        .order_by(
            ProcessedFile.page_number
        )
        .all()
    )

    if not processed_files:
        raise HTTPException(
            status_code=400,
            detail="Document has not been preprocessed",
        )

    # -----------------------------------------------------
    # 3. Run Gemini OCR on every page
    # -----------------------------------------------------

    page_texts = []

    for processed_file in processed_files:
        image_path = Path(processed_file.file_path)

        if not image_path.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Processed image not found: {image_path}",
            )

        ocr_output = ocr(str(image_path))

        if not isinstance(ocr_output, dict):
            raise HTTPException(
                status_code=500,
                detail="OCR engine returned invalid data.",
            )

        page_text = ocr_output.get("text")

        if not isinstance(page_text, str):
            raise HTTPException(
                status_code=500,
                detail="OCR result does not contain valid text.",
            )

        page_texts.append(
            f"--- PAGE {processed_file.page_number} ---\n"
            f"{page_text}"
        )

    combined_ocr = {
        "text": "\n\n".join(page_texts),
        "source_file": f"document_{document.id}",
    }

    normalized_result = normalize(combined_ocr)

    # -----------------------------------------------------
    # 5. Save normalized JSON file
    # -----------------------------------------------------

    ocr_document_dir = OCR_DIR / str(document.id)

    ocr_document_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    json_path = ocr_document_dir / "result.json"

    with open(
        json_path,
        "w",
        encoding="utf-8",
    ) as f:
        json.dump(
            normalized_result,
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(
        f"Saved OCR JSON at: {json_path}"
    )

    # -----------------------------------------------------
    # 6. Save JSON path in database
    # -----------------------------------------------------

    ocr_result = OCRResult(
        document_id=document.id,
        json_path=str(json_path),
    )

    db.add(ocr_result)

    # -----------------------------------------------------
    # 7. Update document status
    # -----------------------------------------------------

    document.status = "ocr_completed"

    db.commit()
    db.refresh(ocr_result)

    # -----------------------------------------------------
    # 8. Return
    # -----------------------------------------------------

    return {
        "id": ocr_result.id,
        "document_id": document.id,
        "status": document.status,
        "json_path": ocr_result.json_path,
        "created_at": ocr_result.created_at,
    }


# ---------------------------------------------------------
# GET /api/ocr/{document_id}
# ---------------------------------------------------------

@router.get("/{document_id}")
def get_ocr(
    document_id: int,
    db: Session = Depends(get_db),
):

    # -----------------------------------------------------
    # 1. Check document
    # -----------------------------------------------------

    document = db.get(
        Document,
        document_id,
    )

    if document is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    # -----------------------------------------------------
    # 2. Find OCR result
    # -----------------------------------------------------

    ocr_result = (
        db.query(OCRResult)
        .filter(
            OCRResult.document_id == document_id
        )
        .order_by(
            OCRResult.created_at.desc()
        )
        .first()
    )

    if ocr_result is None:
        raise HTTPException(
            status_code=404,
            detail="OCR result not found",
        )

    # -----------------------------------------------------
    # 3. Return result
    # -----------------------------------------------------

    return {
        "id": ocr_result.id,
        "document_id": ocr_result.document_id,
        "status": document.status,
        "json_path": ocr_result.json_path,
        "created_at": ocr_result.created_at,
    }
