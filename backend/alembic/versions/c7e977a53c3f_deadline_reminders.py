"""deadline reminders

Revision ID: c7e977a53c3f
Revises: 9b9a9e6bf8f5
Create Date: 2026-06-01 23:14:21.983151

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e977a53c3f'
down_revision: Union[str, Sequence[str], None] = '9b9a9e6bf8f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS deadline_reminders (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id uuid NOT NULL,
            commitment_id uuid NOT NULL REFERENCES commitments(id) ON DELETE CASCADE,
            lead_label text NOT NULL,
            due_date timestamptz NOT NULL,
            channel text NOT NULL,
            destination text,
            status text NOT NULL DEFAULT 'sent',
            error_message text,
            sent_at timestamptz,
            created_at timestamptz NOT NULL DEFAULT now(),
            UNIQUE (commitment_id, lead_label, due_date)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_deadline_reminders_user "
        "ON deadline_reminders (user_id)"
    )
    op.execute(
        "ALTER TABLE brief_delivery_preferences "
        "ADD COLUMN IF NOT EXISTS deadline_reminders_enabled boolean NOT NULL DEFAULT true"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE brief_delivery_preferences DROP COLUMN IF EXISTS deadline_reminders_enabled")
    op.execute("DROP TABLE IF EXISTS deadline_reminders")
