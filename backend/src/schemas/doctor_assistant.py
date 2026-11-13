
from typing import Any
from pydantic import BaseModel, Field


class DoctorAssistantResponse(BaseModel):
    case_summary: str = ""
    key_findings: list[dict[str, Any]] = Field(default_factory=list)
    clinical_interpretation: str = ""
    differential_considerations: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    evidence_supported_pathways: list[dict[str, Any]] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    questions_for_patient: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    limitations: str = ""
