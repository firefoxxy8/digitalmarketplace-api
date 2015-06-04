"""Add audit events

Revision ID: 30_add_audit_events
Revises: 20_adding_json_index_to_services
Create Date: 2015-06-05 11:30:26.425563

"""

# revision identifiers, used by Alembic.
revision = '30_add_audit_events'
down_revision = '40_add_draft_services'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.create_table('audit_events',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('user', sa.String(), nullable=True),
    sa.Column('data', postgresql.JSON(), nullable=True),
    sa.Column('object_type', sa.String(), nullable=True),
    sa.Column('object_id', sa.BigInteger(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('audit_events')
    ### end Alembic commands ###
