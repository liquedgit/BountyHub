"""recon_jobs.notes

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10
"""
import sqlalchemy as sa

from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('recon_jobs') as batch:
        batch.add_column(sa.Column('notes', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    with op.batch_alter_table('recon_jobs') as batch:
        batch.drop_column('notes')
