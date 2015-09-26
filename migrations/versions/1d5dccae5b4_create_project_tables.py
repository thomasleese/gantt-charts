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
    )

    op.create_table('project_calendar',
        sa.Column('project_id', sa.Integer, sa.ForeignKey('project.id'),
                  primary_key=True, nullable=False),
        sa.Column('start_date', sa.Date, nullable=False),
        sa.Column('works_on_monday', sa.Boolean, nullable=False),
        sa.Column('works_on_tuesday', sa.Boolean, nullable=False),
        sa.Column('works_on_wednesday', sa.Boolean, nullable=False),
        sa.Column('works_on_thursday', sa.Boolean, nullable=False),
        sa.Column('works_on_friday', sa.Boolean, nullable=False),
        sa.Column('works_on_saturday', sa.Boolean, nullable=False),
        sa.Column('works_on_sunday', sa.Boolean, nullable=False),
        sa.Column('work_starts_at', sa.Time, nullable=False),
        sa.Column('work_ends_at', sa.Time, nullable=False),
    )

    op.create_table('project_calendar_holiday',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('calendar_id', sa.Integer,
                  sa.ForeignKey('project_calendar.project_id'), nullable=False),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('start', sa.Date, nullable=False),
        sa.Column('end', sa.Date, nullable=False),
    )

    op.create_table('project_star',
        sa.Column('account_id', sa.Integer, sa.ForeignKey('account.id'),
                  primary_key=True, nullable=False),
        sa.Column('project_id', sa.Integer, sa.ForeignKey('project.id'),
                  primary_key=True, nullable=False),
    )

    op.create_table('project_member',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('account_id', sa.Integer, sa.ForeignKey('account.id'),
                  nullable=False),
        sa.Column('project_id', sa.Integer, sa.ForeignKey('project.id'),
                  nullable=False),
        sa.Column('access_level', sa.String, nullable=False),
    )

    op.create_unique_constraint('unique_project_member', 'project_member',
                                ['account_id', 'project_id'])

    op.create_table('project_resource',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('project_id', sa.Integer, sa.ForeignKey('project.id'),
                  nullable=False),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('description', sa.String, nullable=False),
        sa.Column('icon', sa.String, nullable=False),
        sa.Column('amount', sa.Integer, nullable=False),
        sa.Column('reusable', sa.Boolean, nullable=False),
    )

    op.create_table('project_entry',
        sa.Column('id', sa.Integer, primary_key=True, nullable=False),
        sa.Column('project_id', sa.Integer, sa.ForeignKey('project.id'),
                  nullable=False),
        sa.Column('name', sa.String, nullable=False),
        sa.Column('description', sa.String, nullable=False),
        sa.Column('type', sa.String, nullable=False),
        sa.Column('creation_date', sa.DateTime, nullable=False),
        sa.Column('normal_time_estimate', sa.Integer, nullable=False),
        sa.Column('pessimistic_time_estimate', sa.Integer, nullable=False),
    )

    op.create_table('project_entry_dependency',
        sa.Column('parent_id', sa.Integer, sa.ForeignKey('project_entry.id'),
                  primary_key=True, nullable=False),
        sa.Column('child_id', sa.Integer, sa.ForeignKey('project_entry.id'),
                  primary_key=True, nullable=False),
    )

    op.create_check_constraint('no_circle', 'project_entry_dependency',
                               sa.sql.column('parent_id') != sa.sql.column('child_id'))

    op.create_table('project_entry_member',
        sa.Column('entry_id', sa.Integer, sa.ForeignKey('project_entry.id'),
                  primary_key=True, nullable=False),
        sa.Column('member_id', sa.Integer, sa.ForeignKey('project_member.id'),
                  primary_key=True, nullable=False),
    )

    op.create_table('project_entry_resource',
        sa.Column('entry_id', sa.Integer, sa.ForeignKey('project_entry.id'),
                  primary_key=True, nullable=False),
        sa.Column('resource_id', sa.Integer, sa.ForeignKey('project_resource.id'),
                  primary_key=True, nullable=False),
        sa.Column('amount', sa.Integer, nullable=False),
    )


def downgrade():
    op.drop_table('project_entry_resource')
    op.drop_table('project_entry_member')
    op.drop_table('project_entry_dependency')
    op.drop_table('project_entry')

    op.drop_table('project_resource')

    op.drop_table('project_member')

    op.drop_table('project_star')

    op.drop_table('project_calendar_holiday')
    op.drop_table('project_calendar')

    op.drop_table('project')
