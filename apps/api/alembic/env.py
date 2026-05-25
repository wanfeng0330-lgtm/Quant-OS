"""Alembic environment configuration."""

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Import all models so Alembic can detect them
from quant_os_infra_market.models import Base as MarketBase
from quant_os_infra_factor.models import FactorModel, FactorValueModel, FactorAnalysisResultModel
from quant_os_infra_strategy.models import StrategyModel, BacktestRunModel
from quant_os_infra_agent.models import (
    AgentModel, AgentRunModel, ConversationModel, MessageModel,
    WorkflowModel, WorkflowRunModel,
)

config = context.config

# Override sqlalchemy.url from DATABASE_URL env var (for production / Railway)
db_url = os.environ.get("DATABASE_URL")
if db_url:
    if "asyncpg" in db_url:
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    elif "aiosqlite" in db_url:
        db_url = db_url.replace("sqlite+aiosqlite://", "sqlite://")
    config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Use the MarketBase metadata which includes all models via shared Base
target_metadata = MarketBase.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
