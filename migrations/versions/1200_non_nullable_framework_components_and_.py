"""Non-nullable framework components and enforce at least one True with a constraint

Revision ID: 1200
Revises: 1190
Create Date: 2018-05-18 14:55:37.248172

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column


# revision identifiers, used by Alembic.
revision = '1200'
down_revision = '1190'


def upgrade():
    frameworks = table('frameworks',
                       column('framework', sa.String()),
                       column('has_direct_award', sa.BOOLEAN()),
                       column('has_further_competition', sa.BOOLEAN()))

    # Need to manually insert values for these columns so that the test database gets populated corrected.
    # Live environments will be populated manually via the API before this migration goes in.
    op.execute(frameworks.update().where(frameworks.c.framework == 'g-cloud').values(
        has_direct_award=True,
        has_further_competition=False,
    ))
    op.execute(frameworks.update().where(frameworks.c.framework == 'digital-outcomes-and-specialists').values(
        has_direct_award=False,
        has_further_competition=True,
    ))

    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('frameworks', 'has_direct_award', existing_type=sa.BOOLEAN(), nullable=False)
    op.alter_column('frameworks', 'has_further_competition', existing_type=sa.BOOLEAN(), nullable=False)
    op.create_check_constraint('ck_framework_has_direct_award_or_further_competition',
                               'frameworks',
                               'has_direct_award IS true OR has_further_competition IS true')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.alter_column('frameworks', 'has_further_competition', existing_type=sa.BOOLEAN(), nullable=True)
    op.alter_column('frameworks', 'has_direct_award', existing_type=sa.BOOLEAN(), nullable=True)
    op.drop_constraint('ck_framework_has_direct_award_or_further_competition', 'frameworks', type_='check')
    # ### end Alembic commands ###
