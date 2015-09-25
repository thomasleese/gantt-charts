"""
Add entry dates.

Revision ID: 1a08fc421ce
Revises: 1d5dccae5b4
Create Date: 2015-09-25 12:47:02.150214
"""

from alembic import op
import sqlalchemy as sa


revision = '1a08fc421ce'
down_revision = '1d5dccae5b4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('project_entry', sa.Column('min_start_date', sa.DateTime))
    op.add_column('project_entry', sa.Column('max_start_date', sa.DateTime))
    op.add_column('project_entry', sa.Column('min_end_date', sa.DateTime))
    op.add_column('project_entry', sa.Column('max_end_date', sa.DateTime))


def downgrade():
    with op.batch_alter_table('project_entry') as batch_op:
        batch_op.drop_column('min_start_date')
        batch_op.drop_column('max_start_date')
        batch_op.drop_column('min_end_date')
        batch_op.drop_column('max_end_date')
