# fix: add relay_users table
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = depends_on = None

# REGION AI: relay_users table
def upgrade() -> None:
    op.create_table('relay_users',
        sa.Column('user_id', sa.Integer, primary_key=True),
        sa.Column('username', sa.Text),
        sa.Column('full_name', sa.Text),
        sa.Column('last_seen', sa.TIMESTAMP, server_default=sa.text('CURRENT_TIMESTAMP')),
    )


def downgrade() -> None:
    op.drop_table('relay_users')
# END REGION AI
