
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import relationship

from src.models.base import Base


class DoctorAssistant(Base):
    __tablename__ = "doctor_assistants"

    id = Column(Integer, primary_key=True, index=True)
    processed_file_id = Column(
        Integer, ForeignKey("processed_files.id"), nullable=False, unique=True, index=True
    )
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    response_json = Column(Text, nullable=False)
    model_name = Column(Text, nullable=False, default="gemini-2.5-flash")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    processed_file = relationship("ProcessedFile", back_populates="doctor_assistant")
    user = relationship("User", back_populates="doctor_assistants")
