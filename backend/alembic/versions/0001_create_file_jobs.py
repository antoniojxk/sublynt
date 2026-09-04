"""Create file jobs table."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "file_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("source_format", sa.String(8), nullable=False),
        sa.Column("source_path", sa.String(512), nullable=False),
        sa.Column("generated_path", sa.String(512), nullable=True),
        sa.Column("output_format", sa.String(8), nullable=True),
        sa.Column("changes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("file_jobs")
