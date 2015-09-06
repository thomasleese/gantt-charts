"""
Add project description column

Revision ID: 44aae1e9ed
Revises: 41ba25d85cb
Create Date: 2015-09-06 11:09:15.245947
"""

from alembic import op
import sqlalchemy as sa


revision = '44aae1e9ed'
down_revision = '41ba25d85cb'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('project', sa.Column('description', sa.String,
                                       nullable=False, server_default=''))


def downgrade():
    op.drop_column('project', 'description')
