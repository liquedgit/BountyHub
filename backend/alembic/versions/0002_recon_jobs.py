"""recon jobs table and recon_assets.source

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10
"""
import sqlalchemy as sa

from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('recon_jobs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('program_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('current_stage', sa.String(length=32), nullable=True),
    sa.Column('targets', sa.JSON(), nullable=False),
    sa.Column('rejected_targets', sa.JSON(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recon_jobs_program_id'), 'recon_jobs', ['program_id'], unique=False)
    op.create_index(op.f('ix_recon_jobs_status'), 'recon_jobs', ['status'], unique=False)
    with op.batch_alter_table('recon_assets') as batch:
        batch.add_column(sa.Column('source', sa.String(length=64), nullable=True))
        batch.create_foreign_key('fk_recon_assets_job_id', 'recon_jobs', ['job_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('recon_assets') as batch:
        batch.drop_constraint('fk_recon_assets_job_id', type_='foreignkey')
        batch.drop_column('source')
    op.drop_index(op.f('ix_recon_jobs_status'), table_name='recon_jobs')
    op.drop_index(op.f('ix_recon_jobs_program_id'), table_name='recon_jobs')
    op.drop_table('recon_jobs')
