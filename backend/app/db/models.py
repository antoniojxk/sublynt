from datetime import UTC, datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class FileJob(Base):
    __tablename__ = "file_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    original_name: Mapped[str] = mapped_column(String(255))
    source_format: Mapped[str] = mapped_column(String(8))
    source_path: Mapped[str] = mapped_column(String(512))
    generated_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_format: Mapped[str | None] = mapped_column(String(8), nullable=True)
    changes_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
