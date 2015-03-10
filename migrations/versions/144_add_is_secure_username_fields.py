"""Added is_secure / username fields for IMAP/SMTP servers

Revision ID: 296a86ec5e41
Revises: 1d7a72222b7c
Create Date: 2015-03-10 04:15:32.896222

"""

# revision identifiers, used by Alembic.
revision = '296a86ec5e41'
down_revision = '1d7a72222b7c'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

def upgrade():
    op.add_column('genericaccount', sa.Column('imap_username', sa.String(length=255), nullable=True))
    op.add_column('genericaccount', sa.Column('smtp_username', sa.String(length=255), nullable=True))
    op.add_column('imapaccount', sa.Column('_imap_server_is_secure', sa.Boolean(), server_default='1', nullable=False))
    op.add_column('imapaccount', sa.Column('_smtp_server_is_secure', sa.Boolean(), server_default='1', nullable=False))


def downgrade():
    op.drop_column('imapaccount', '_smtp_server_is_secure')
    op.drop_column('imapaccount', '_imap_server_is_secure')
    op.drop_column('genericaccount', 'smtp_username')
    op.drop_column('genericaccount', 'imap_username')
