"""
Create project tables.

Revision ID: 1d5dccae5b4
Revises: 36190acd575
Create Date: 2015-09-05 11:52:25.493928
"""

from alembic import op
import sqlalchemy as sa


revision = '1d5dccae5b4'
down_revision = '36190acd575'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('project',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('description', sa.String, nullable=False),
        sa.Column('creation_date', sa.DateTime, nullable=False),
        sa.Column('start_date', sa.Date, nullable=False),
    )

    op.create_table('project_member',
        sa.Column('account_id', sa.Integer, sa.ForeignKey('account.id'),
                  primary_key=True, nullable=False),
        sa.Column('project_id', sa.Integer, sa.ForeignKey('project.id'),
                  primary_key=True, nullable=False),
    )


def downgrade():
    op.drop_table('project_member')
    op.drop_table('project')
