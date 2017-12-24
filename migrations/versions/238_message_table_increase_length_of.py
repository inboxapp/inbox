"""message table - increase length of snippet and subject

Revision ID: 369c7cfff3a6
Revises: 780b1dabd51
Create Date: 2017-11-28 20:35:01.406759

"""

# revision identifiers, used by Alembic.
revision = '369c7cfff3a6'
down_revision = '780b1dabd51'

from alembic import op
from sqlalchemy.sql import text


def upgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE message"
                      " MODIFY subject VARCHAR(2047) DEFAULT NULL"))
    conn.execute(text("ALTER TABLE message"
                      " MODIFY snippet VARCHAR(2047) NOT NULL"))
    conn.execute(text("ALTER TABLE thread"
                      " MODIFY subject VARCHAR(2047) DEFAULT NULL"))
    conn.execute(text("ALTER TABLE thread"
                      " MODIFY _cleaned_subject VARCHAR(2047) DEFAULT NULL"))
    conn.execute(text("ALTER TABLE thread"
                      " MODIFY snippet VARCHAR(2047) DEFAULT NULL"))


def downgrade():
    conn = op.get_bind()
    conn.execute(text("ALTER TABLE message"
                      " MODIFY subject VARCHAR(255) DEFAULT NULL"))
    conn.execute(text("ALTER TABLE message"
                      " MODIFY snippet VARCHAR(191) NOT NULL"))
    conn.execute(text("ALTER TABLE thread"
                      " MODIFY subject VARCHAR(255) DEFAULT NULL"))
    conn.execute(text("ALTER TABLE thread"
                      " MODIFY _cleaned_subject VARCHAR(255) DEFAULT NULL"))
    conn.execute(text("ALTER TABLE thread"
                      " MODIFY snippet VARCHAR(191) DEFAULT NULL"))
