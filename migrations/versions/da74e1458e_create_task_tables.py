"""
Create task tables.

Revision ID: da74e1458e
Revises: 1d5dccae5b4
Create Date: 2015-09-05 12:33:36.596940
"""

from alembic import op
import sqlalchemy as sa


revision = 'da74e1458e'
down_revision = '1d5dccae5b4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('task',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('project_id', sa.Integer, sa.ForeignKey('project.id'),
                  nullable=False),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('description', sa.String, nullable=False),
        sa.Column('creation_date', sa.DateTime, nullable=False),
        sa.Column('optimistic_time_estimate', sa.Integer, nullable=False),
        sa.Column('normal_time_estimate', sa.Integer, nullable=False),
        sa.Column('pessimistic_time_estimate', sa.Integer, nullable=False),
    )

    op.create_table('task_dependency',
        sa.Column('task_id', sa.Integer, sa.ForeignKey('task.id'),
                  primary_key=True, nullable=False),
        sa.Column('dependency_id', sa.Integer, sa.ForeignKey('task.id'),
                  primary_key=True, nullable=False),
    )

    # add a constraint that these task_id and dependency_id can't be the same


def downgrade():
    op.drop_table('task_dependency')
    op.drop_table('task')
