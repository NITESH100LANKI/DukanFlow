"""create export batches and lines

Revision ID: a831e5f88421
Revises: 4e7f793b510a
Create Date: 2026-11-09 21:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a831e5f88421'
down_revision: Union[str, None] = '4e7f793b510a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create export_batches table
    op.create_table(
        'export_batches',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('batch_number', sa.String(length=50), nullable=False),
        sa.Column('export_profile', sa.String(length=50), server_default='generic', nullable=False),
        sa.Column('generated_by', sa.UUID(), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('order_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('record_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_gross', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('total_discount', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('total_benefit', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('total_net', sa.Numeric(precision=12, scale=2), server_default='0.00', nullable=False),
        sa.Column('total_fulfilment_cases', sa.Integer(), server_default='0', nullable=False),
        sa.Column('csv_filename', sa.String(length=200), nullable=False),
        sa.Column('csv_content', sa.Text(), nullable=False),
        sa.Column('file_checksum', sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(['generated_by'], ['order_desk_users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_export_batches_batch_number'), 'export_batches', ['batch_number'], unique=True)
    op.create_index(op.f('ix_export_batches_generated_by'), 'export_batches', ['generated_by'], unique=False)
    op.create_index('ix_export_batches_generated_at_desc', 'export_batches', ['generated_at'], unique=False)

    # 2. Create export_batch_lines table
    op.create_table(
        'export_batch_lines',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('batch_id', sa.UUID(), nullable=False),
        sa.Column('order_id', sa.UUID(), nullable=False),
        sa.Column('order_number_snapshot', sa.String(length=50), nullable=False),
        sa.Column('order_net_total', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['batch_id'], ['export_batches.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_export_batch_lines_batch_id'), 'export_batch_lines', ['batch_id'], unique=False)
    op.create_index(op.f('ix_export_batch_lines_order_id'), 'export_batch_lines', ['order_id'], unique=False)
    op.create_index('ix_export_batch_lines_batch_order', 'export_batch_lines', ['batch_id', 'order_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_export_batch_lines_batch_order', table_name='export_batch_lines')
    op.drop_index(op.f('ix_export_batch_lines_order_id'), table_name='export_batch_lines')
    op.drop_index(op.f('ix_export_batch_lines_batch_id'), table_name='export_batch_lines')
    op.drop_table('export_batch_lines')

    op.drop_index('ix_export_batches_generated_at_desc', table_name='export_batches')
    op.drop_index(op.f('ix_export_batches_generated_by'), table_name='export_batches')
    op.drop_index(op.f('ix_export_batches_batch_number'), table_name='export_batches')
    op.drop_table('export_batches')

