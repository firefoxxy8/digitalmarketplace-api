"""Add 'obfuscated' flag to User and ContactInformation models

Revision ID: 1140
Revises: 1130
Create Date: 2018-05-01 09:47:36.085886

"""
from alembic import op
import sqlalchemy as sa


revision = '1140'
down_revision = '1130'


def upgrade():
    op.add_column('users', sa.Column('obfuscated', sa.Boolean(), nullable=False,  server_default=sa.false()))
    op.add_column(
        'contact_information',
        sa.Column('obfuscated', sa.Boolean(), nullable=False, server_default=sa.false())
    )


def downgrade():
    op.drop_column('contact_information', 'obfuscated')
    op.drop_column('users', 'obfuscated')

