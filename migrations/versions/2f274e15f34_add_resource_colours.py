"""
Add resource colours

Revision ID: 2f274e15f34
Revises: 48f098f8da
Create Date: 2015-10-01 13:24:36.225464
"""

from alembic import op
import sqlalchemy as sa


revision = '2f274e15f34'
down_revision = '48f098f8da'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('project_resource',
                  sa.Column('colour', sa.String, nullable=False,
                            server_default='#000000'))


def downgrade():
    op.drop_column('project_resource', 'colour')
