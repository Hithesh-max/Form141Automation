"""add form141 models and preview fields

Revision ID: 2e4d5c6b7a89
Revises: 1d1a36fef7a4
Create Date: 2026-09-15 09:38:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e4d5c6b7a89'
down_revision: Union[str, Sequence[str], None] = '1d1a36fef7a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add preview fields and logical_filing_id to jobs table
    op.add_column('jobs', sa.Column('logical_filing_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_jobs_logical_filing_id'), 'jobs', ['logical_filing_id'], unique=False)
    op.add_column('jobs', sa.Column('preview_metadata', sa.JSON(), nullable=True))
    op.add_column('jobs', sa.Column('preview_reached_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('jobs', sa.Column('preview_screenshot_path', sa.String(), nullable=True))

    # 2. Create form141_imports table
    op.create_table(
        'form141_imports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=True),
        sa.Column('total_customers', sa.Integer(), server_default='0', nullable=True),
        sa.Column('status', sa.String(), server_default='IMPORTED', nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_form141_imports_id'), 'form141_imports', ['id'], unique=False)

    # 3. Create form141_logical_filings table
    op.create_table(
        'form141_logical_filings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('import_id', sa.Integer(), nullable=True),
        sa.Column('logical_filing_id', sa.String(), nullable=True),
        sa.Column('customer_label', sa.String(), nullable=True),
        sa.Column('column_index', sa.Integer(), server_default='1', nullable=True),
        sa.Column('deductor_pan', sa.String(), nullable=True),
        sa.Column('deductee_pan', sa.String(), nullable=True),
        sa.Column('amount', sa.Float(), server_default='0.0', nullable=True),
        sa.Column('tds_amount', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), server_default='READY', nullable=True),
        sa.Column('current_step', sa.String(), server_default='READY', nullable=True),
        sa.Column('validation_errors', sa.JSON(), nullable=True),
        sa.Column('validation_warnings', sa.JSON(), nullable=True),
        sa.Column('field_values', sa.JSON(), nullable=True),
        sa.Column('field_metadata', sa.JSON(), nullable=True),
        sa.Column('job_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['import_id'], ['form141_imports.id'], ),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_form141_logical_filings_id'), 'form141_logical_filings', ['id'], unique=False)
    op.create_index(op.f('ix_form141_logical_filings_logical_filing_id'), 'form141_logical_filings', ['logical_filing_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_form141_logical_filings_logical_filing_id'), table_name='form141_logical_filings')
    op.drop_index(op.f('ix_form141_logical_filings_id'), table_name='form141_logical_filings')
    op.drop_table('form141_logical_filings')

    op.drop_index(op.f('ix_form141_imports_id'), table_name='form141_imports')
    op.drop_table('form141_imports')

    op.drop_column('jobs', 'preview_screenshot_path')
    op.drop_column('jobs', 'preview_reached_at')
    op.drop_column('jobs', 'preview_metadata')
    op.drop_index(op.f('ix_jobs_logical_filing_id'), table_name='jobs')
    op.drop_column('jobs', 'logical_filing_id')
