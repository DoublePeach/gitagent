# 统一在此导入所有模型，供 Alembic env.py 和其他需要完整 metadata 的地方使用
from app.db.models.release_plan import ReleaseItem, ReleasePlan  # noqa: F401
