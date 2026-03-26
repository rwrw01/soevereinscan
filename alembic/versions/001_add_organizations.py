"""Add organizations table and link to scans

Revision ID: 001_add_organizations
Revises:
Create Date: 2026-03-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001_add_organizations"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("website", sa.String(2048), nullable=False),
        sa.Column("provincie", sa.String(100), nullable=True),
        sa.Column("cbs_code", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_organizations_category", "organizations", ["category"])
    op.create_index("ix_organizations_website", "organizations", ["website"], unique=True)

    op.add_column("scans", sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_scans_organization_id", "scans", "organizations", ["organization_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_scans_organization_id", "scans", type_="foreignkey")
    op.drop_column("scans", "organization_id")
    op.drop_index("ix_organizations_website", "organizations")
    op.drop_index("ix_organizations_category", "organizations")
    op.drop_table("organizations")
