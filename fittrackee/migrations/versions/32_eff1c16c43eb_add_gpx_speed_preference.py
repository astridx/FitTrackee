"""Add user preference for gpx speed calculation

Revision ID: eff1c16c43eb
Revises: db58d195c5bf
Create Date: 2023-05-14 22:12:56.244291

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'eff1c16c43eb'
down_revision = 'db58d195c5bf'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('use_raw_gpx_speed', sa.Boolean(), nullable=True))
    op.execute("UPDATE users SET use_raw_gpx_speed = false")
    op.alter_column('users', 'use_raw_gpx_speed', nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('use_raw_gpx_speed')

    # ### end Alembic commands ###