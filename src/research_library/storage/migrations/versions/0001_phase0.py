"""Create the explicit Phase 0 relational schema."""

from alembic import op

from research_library.storage.schema import metadata

revision = "0001_phase0"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind(), checkfirst=True)
