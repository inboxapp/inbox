"""MAD-460 - table Message - add column 'encrypted'

Revision ID: 731019fd024
Revises: 369c7cfff3a6
Create Date: 2017-12-10 15:50:12.286623

"""

# revision identifiers, used by Alembic.
revision = '731019fd024'
down_revision = '369c7cfff3a6'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE message"
                      " ADD column encrypted tinyint(1) DEFAULT 0"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE message"
                      " DROP column encrypted"))