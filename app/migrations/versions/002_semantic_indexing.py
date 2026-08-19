"""Add semantic chunks and durable indexing jobs.

Revision ID: 002
Revises: 001
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def _owner_policy(table: str) -> None:
    op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute(
        f"""CREATE POLICY {table}_owner_policy ON {table}
        USING (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)
        WITH CHECK (user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid)"""
    )


def upgrade() -> None:
    status = sa.Enum(
        "pending",
        "processing",
        "retry_wait",
        "failed",
        "completed",
        name="indexing_job_status",
    )
    op.create_table(
        "note_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "note_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_version", sa.Integer(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("embedding_model", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "note_id", "note_version", "ordinal", name="uq_chunks_note_version_ordinal"
        ),
        sa.CheckConstraint("token_count > 0", name="ck_chunks_token_count"),
    )
    op.create_index("ix_chunks_user_note", "note_chunks", ["user_id", "note_id"])
    op.create_table(
        "indexing_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "note_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("note_version", sa.Integer(), nullable=False),
        sa.Column("status", status, nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("note_id", "note_version", name="uq_jobs_note_version"),
        sa.CheckConstraint("attempt_count BETWEEN 0 AND 5", name="ck_jobs_attempt_count"),
    )
    op.create_index("ix_jobs_claim", "indexing_jobs", ["status", "available_at"])
    op.create_index("ix_jobs_user_note", "indexing_jobs", ["user_id", "note_id"])
    _owner_policy("note_chunks")
    _owner_policy("indexing_jobs")


def downgrade() -> None:
    op.drop_table("indexing_jobs")
    op.drop_table("note_chunks")
    op.execute("DROP TYPE IF EXISTS indexing_job_status")
