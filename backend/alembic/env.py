from alembic import context

from app.jobs import models as job_models  # noqa: F401  (jobs sit above the modules)
from app.modules import models  # noqa: F401  (registers every table on Base.metadata)
from app.core.database import Base, engine

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
