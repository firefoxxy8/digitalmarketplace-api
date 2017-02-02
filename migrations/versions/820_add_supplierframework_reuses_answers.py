"""Add SupplierFramework.reuses_answers_from_framework_id column and constraints

Revision ID: 820
Revises: 810
Create Date: 2017-01-27 10:47:44.565269

"""

# revision identifiers, used by Alembic.
revision = '820'
down_revision = '810'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

def upgrade():
    op.add_column('supplier_frameworks', sa.Column('reuses_answers_from_framework_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_supplier_frameworks_reuses_answers_from_framework_id_framework",
        'supplier_frameworks',
        'frameworks',
        ['reuses_answers_from_framework_id'],
        ['id'],
    )
    op.create_foreign_key(
        "fk_supplier_frameworks_supplier_id_reuses_answers_from_framework_id_supplier_framework",
        'supplier_frameworks',
        'supplier_frameworks',
        ['supplier_id', 'reuses_answers_from_framework_id'],
        ['supplier_id', 'framework_id'],
    )


def downgrade():
    op.drop_constraint(
        "fk_supplier_frameworks_reuses_answers_from_framework_id_framework",
        'supplier_frameworks',
        type_='foreignkey',
    )
    op.drop_constraint(
        "fk_supplier_frameworks_supplier_id_reuses_answers_from_framework_id_supplier_framework",
        'supplier_frameworks',
        type_='foreignkey',
    )
    op.drop_column('supplier_frameworks', 'reuses_answers_from_framework_id')
