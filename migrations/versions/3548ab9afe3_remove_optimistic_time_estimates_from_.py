"""
Remove optimistic time estimates from entries

Revision ID: 3548ab9afe3
Revises: 2f29d0a8cca
Create Date: 2015-09-16 09:34:25.361727
"""

from alembic import op
import sqlalchemy as sa


revision = '3548ab9afe3'
down_revision = '2f29d0a8cca'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_column('project_entry', 'optimistic_time_estimate')


def downgrade():
    op.add_column('project_entry',
                  sa.Column('optimistic_time_estimate', sa.Integer,
                            nullable=False))
