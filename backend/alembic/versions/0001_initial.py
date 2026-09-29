"""initial schema"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("email", sa.String(320), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", sa.String(8), nullable=False), sa.Column("name", sa.String(120), nullable=False), sa.Column("organisation", sa.String(160)), sa.Column("active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("email"))
    op.create_index("ix_users_email", "users", ["email"], unique=True); op.create_index("ix_users_role", "users", ["role"])
    op.create_table("episodes", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("episode_id", sa.String(64), nullable=False), sa.Column("robot_id", sa.String(64), nullable=False), sa.Column("task_name", sa.String(160), nullable=False), sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False), sa.Column("duration_seconds", sa.Integer(), nullable=False), sa.Column("operator_name", sa.String(120), nullable=False), sa.Column("quality", sa.String(6), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("episode_id"))
    for name, cols in [("ix_episodes_episode_id", ["episode_id"]), ("ix_episodes_robot_id", ["robot_id"]), ("ix_episodes_task_name", ["task_name"]), ("ix_episodes_recorded_at", ["recorded_at"]), ("ix_episodes_quality", ["quality"]), ("ix_episode_analytics", ["recorded_at", "robot_id", "quality"])]: op.create_index(name, "episodes", cols, unique=name == "ix_episodes_episode_id")
    op.create_table("dataset_requests", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("client_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("task_name", sa.String(160), nullable=False), sa.Column("episodes_requested", sa.Integer(), nullable=False), sa.Column("deadline", sa.Date(), nullable=False), sa.Column("notes", sa.Text()), sa.Column("status", sa.String(11), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    for col in ("client_id", "task_name", "status", "created_at"): op.create_index(f"ix_dataset_requests_{col}", "dataset_requests", [col])
    op.create_table("assignments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("request_id", sa.Integer(), sa.ForeignKey("dataset_requests.id", ondelete="CASCADE"), nullable=False), sa.Column("episode_id", sa.Integer(), sa.ForeignKey("episodes.id", ondelete="RESTRICT"), nullable=False), sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("episode_id"), sa.UniqueConstraint("request_id", "episode_id")); op.create_index("ix_assignments_request_id", "assignments", ["request_id"])
    op.create_table("status_history", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("request_id", sa.Integer(), sa.ForeignKey("dataset_requests.id", ondelete="CASCADE"), nullable=False), sa.Column("from_status", sa.String(11)), sa.Column("to_status", sa.String(11), nullable=False), sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False))
    for col in ("request_id", "to_status", "changed_by", "changed_at"): op.create_index(f"ix_status_history_{col}", "status_history", [col])


def downgrade():
    op.drop_table("status_history"); op.drop_table("assignments"); op.drop_table("dataset_requests"); op.drop_table("episodes"); op.drop_table("users")

