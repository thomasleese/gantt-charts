"""
Add account display name column

Revision ID: 2d1edbf2b13
Revises: 44aae1e9ed
Create Date: 2015-09-06 12:51:58.983331
"""

from alembic import op
import sqlalchemy as sa


revision = '2d1edbf2b13'
down_revision = '44aae1e9ed'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('account', sa.Column('display_name', sa.String,
                                       nullable=False, server_default=''))

    op.execute("""
        UPDATE account
        SET display_name = (
            SELECT email_address
            FROM account_email_address
            WHERE account_id = account.id
            LIMIT 1
        )
    """)


def downgrade():
    op.drop_column('account', 'display_name')
