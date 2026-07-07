"""baseline schema as of migration 016

Revision ID: 9b9a9e6bf8f5
Revises:
Create Date: 2026-06-01 18:57:26.401730

This is an empty baseline. The schema through migrations/016 is bootstrapped by
the existing numbered SQL files (migrations/001..016) — run those once on a fresh
database, then `alembic stamp head` to mark it at this baseline. From here on,
all new schema changes go through Alembic (`alembic revision -m "..."`).
"""
from typing import Sequence, Union  # noqa: F401

from alembic import op  # noqa: F401
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = '9b9a9e6bf8f5'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op: baseline (schema already created by migrations/001..016)."""


def downgrade() -> None:
    """No-op baseline."""
