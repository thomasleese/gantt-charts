"""
Add reset password fields to account

Revision ID: 2f29d0a8cca
Revises: 1eb09ae4883
Create Date: 2015-09-14 09:54:50.832210
"""

from alembic import op
import sqlalchemy as sa


revision = '2f29d0a8cca'
down_revision = '1eb09ae4883'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('account', sa.Column('reset_password_key', sa.String))
    op.add_column('account',
                  sa.Column('reset_password_key_expiration_date', sa.DateTime))
    op.add_column('account',
                  sa.Column('last_reset_password_email_date', sa.DateTime))


def downgrade():
    op.drop_column('account', 'reset_password_key')
    op.drop_column('account', 'reset_password_key_creation_date')
    op.drop_column('account', 'last_reset_password_email_date')
