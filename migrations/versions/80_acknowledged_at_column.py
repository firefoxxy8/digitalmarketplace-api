"""empty message

Revision ID: 3a0090458cd3
Revises: 60_acknowledged_not_null
Create Date: 2015-06-17 12:55:16.630026

"""

# revision identifiers, used by Alembic.
revision = '80_acknowledged_at_column'
down_revision = '60_add_acknowledged_column'

from alembic import op
import sqlalchemy as sa


def upgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.add_column('audit_events', sa.Column('acknowledged_at', sa.DateTime(), nullable=True))
    ### end Alembic commands ###


def downgrade():
    ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('audit_events', 'acknowledged_at')
    ### end Alembic commands ###
