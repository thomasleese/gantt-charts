"""
Add account email preferences

Revision ID: 48f098f8da
Revises: 1a08fc421ce
Create Date: 2015-09-26 14:44:27.336093
"""

from alembic import op
import sqlalchemy as sa


revision = '48f098f8da'
down_revision = '1a08fc421ce'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('account', sa.Column('receive_summary_email', sa.Boolean,
                                       server_default='TRUE'))


def downgrade():
    op.drop_column('account', 'receive_summary_email')
