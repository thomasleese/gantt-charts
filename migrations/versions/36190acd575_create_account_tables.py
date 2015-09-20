"""
Create account tables.

Revision ID: 36190acd575
Revises:
Create Date: 2015-09-05 11:10:45.283275
"""

from datetime import datetime

from alembic import op
import sqlalchemy as sa


revision = '36190acd575'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('account',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('display_name', sa.String, nullable=False),
        sa.Column('password_hashed', sa.String, nullable=False),
        sa.Column('creation_date', sa.DateTime, nullable=False),
        sa.Column('reset_password_key', sa.String),
        sa.Column('reset_password_key_expiration_date', sa.DateTime),
        sa.Column('last_reset_password_email_date', sa.DateTime),
    )

    op.create_table('account_email_address',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('account_id', sa.Integer, sa.ForeignKey('account.id'),
                  nullable=False),
        sa.Column('email_address', sa.String, unique=True,
                  nullable=False),
        sa.Column('primary', sa.Boolean, nullable=False),
        sa.Column('verified', sa.Boolean, nullable=False),
        sa.Column('verify_key', sa.String, nullable=False),
        sa.Column('last_verification_email_date', sa.DateTime),
    )


def downgrade():
    op.drop_table('account_email_address')
    op.drop_table('account')
