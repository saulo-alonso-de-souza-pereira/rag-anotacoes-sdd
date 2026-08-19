"""Grant runtime access and add an RLS-safe worker claim function.

Revision ID: 003
"""

from alembic import op

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO notes_runtime"
    )
    op.execute(
        """
        CREATE FUNCTION claim_indexing_job(claimed_at timestamptz, lease_seconds integer)
        RETURNS SETOF indexing_jobs
        LANGUAGE sql
        SECURITY DEFINER
        SET search_path = public, pg_temp
        SET row_security = off
        AS $$
          UPDATE indexing_jobs
          SET status = 'processing',
              attempt_count = attempt_count + 1,
              claimed_at = $1,
              lease_expires_at = $1 + make_interval(secs => $2)
          WHERE id = (
            SELECT id FROM indexing_jobs
            WHERE ((status IN ('pending', 'retry_wait') AND available_at <= $1)
                OR (status = 'processing' AND lease_expires_at <= $1))
            ORDER BY available_at, created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
          )
          RETURNING *
        $$
        """
    )
    op.execute("REVOKE ALL ON FUNCTION claim_indexing_job(timestamptz, integer) FROM PUBLIC")
    op.execute(
        "GRANT EXECUTE ON FUNCTION claim_indexing_job(timestamptz, integer) TO notes_runtime"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS claim_indexing_job(timestamptz, integer)")
