"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-10
"""
import sqlalchemy as sa

from alembic import op

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('programs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('platform', sa.String(length=100), nullable=True),
    sa.Column('url', sa.String(length=500), nullable=True),
    sa.Column('reward_info', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('recon_assets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=True),
    sa.Column('asset_type', sa.String(length=32), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('metadata', sa.JSON(), nullable=False),
    sa.Column('ai_score', sa.Float(), nullable=True),
    sa.Column('ai_label', sa.String(length=32), nullable=True),
    sa.Column('ai_reason', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_recon_assets_asset_type'), 'recon_assets', ['asset_type'], unique=False)
    op.create_index(op.f('ix_recon_assets_job_id'), 'recon_assets', ['job_id'], unique=False)
    op.create_table('settings',
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('key')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('scope_rules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('program_id', sa.Integer(), nullable=False),
    sa.Column('action', sa.Enum('in', 'out', name='scopeaction'), nullable=False),
    sa.Column('type', sa.Enum('domain', 'wildcard', 'ip', 'url', name='scopetype'), nullable=False),
    sa.Column('value', sa.String(length=500), nullable=False),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_scope_rules_program_id'), 'scope_rules', ['program_id'], unique=False)
    op.create_table('targets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('program_id', sa.Integer(), nullable=False),
    sa.Column('value', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_targets_program_id'), 'targets', ['program_id'], unique=False)
    op.create_table('findings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('program_id', sa.Integer(), nullable=False),
    sa.Column('target_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.Enum('new', 'triaged', 'submitted', 'accepted', 'duplicate', 'rejected', 'resolved', 'paid', name='findingstatus'), nullable=False),
    sa.Column('severity', sa.Enum('info', 'low', 'medium', 'high', 'critical', name='severity'), nullable=False),
    sa.Column('payout_cents', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['target_id'], ['targets.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_findings_program_id'), 'findings', ['program_id'], unique=False)
    op.create_table('notes',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('program_id', sa.Integer(), nullable=False),
    sa.Column('finding_id', sa.Integer(), nullable=True),
    sa.Column('title', sa.String(length=300), nullable=False),
    sa.Column('body_md', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
    sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['program_id'], ['programs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notes_finding_id'), 'notes', ['finding_id'], unique=False)
    op.create_index(op.f('ix_notes_program_id'), 'notes', ['program_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notes_program_id'), table_name='notes')
    op.drop_index(op.f('ix_notes_finding_id'), table_name='notes')
    op.drop_table('notes')
    op.drop_index(op.f('ix_findings_program_id'), table_name='findings')
    op.drop_table('findings')
    op.drop_index(op.f('ix_targets_program_id'), table_name='targets')
    op.drop_table('targets')
    op.drop_index(op.f('ix_scope_rules_program_id'), table_name='scope_rules')
    op.drop_table('scope_rules')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('settings')
    op.drop_index(op.f('ix_recon_assets_job_id'), table_name='recon_assets')
    op.drop_index(op.f('ix_recon_assets_asset_type'), table_name='recon_assets')
    op.drop_table('recon_assets')
    op.drop_table('programs')
    if op.get_bind().dialect.name == "postgresql":
        for enum_name in ("findingstatus", "severity", "scopetype", "scopeaction"):
            op.execute(f"DROP TYPE IF EXISTS {enum_name}")
