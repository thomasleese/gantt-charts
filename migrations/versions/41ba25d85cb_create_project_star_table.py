"""
Create project star table

Revision ID: 41ba25d85cb
Revises: da74e1458e
Create Date: 2015-09-05 20:49:33.404937
"""

from alembic import op
import sqlalchemy as sa


revision = '41ba25d85cb'
down_revision = 'da74e1458e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('project_star',
        sa.Column('account_id', sa.Integer, sa.ForeignKey('account.id'),
                  primary_key=True, nullable=False),
        sa.Column('project_id', sa.Integer, sa.ForeignKey('project.id'),
                  primary_key=True, nullable=False),
    )


def downgrade():
    op.drop_table('project_star')
