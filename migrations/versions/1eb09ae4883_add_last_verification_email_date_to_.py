"""
Add last_verification_email_date to account_email_address

Revision ID: 1eb09ae4883
Revises: 1d5dccae5b4
Create Date: 2015-09-14 09:40:23.907903
"""

from alembic import op
import sqlalchemy as sa


revision = '1eb09ae4883'
down_revision = '1d5dccae5b4'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('account_email_address',
                  sa.Column('last_verification_email_date', sa.DateTime))


def downgrade():
    op.drop_column('account_email_address', 'last_verification_email_date')
