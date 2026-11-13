from fastapi import FastAPI

from src.api.routes import (
    user,
    document,
    preprocessed,
    ocr,
    patient_assistant,
    doctor_assistant,
)
from src.models.base import Base
from src.models.database import engine
from src.models import (
    User,
    Document,
    ProcessedFile,
    OCRResult,
    PatientAssistant,
    DoctorAssistant,
)

# Creates any missing tables, including doctor_assistants, on startup.
# Existing tables/data are preserved; production deployments should use migrations.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Lab-to-Care API",
    version="0.2.0",
)

app.include_router(user.router)
app.include_router(document.router)
app.include_router(preprocessed.router)
app.include_router(ocr.router)
app.include_router(patient_assistant.router)
app.include_router(doctor_assistant.router)


@app.get("/health")
def health():
    return {"status": "ok"}
