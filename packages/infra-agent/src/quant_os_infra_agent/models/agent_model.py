"""Agent and Workflow ORM models."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from quant_os_infra_market.models.base import Base, TimestampMixin, generate_uuid


class AgentModel(TimestampMixin, Base):
    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    agent_type: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    llm_provider: Mapped[str] = mapped_column(String(50), default="deepseek")
    llm_model: Mapped[str] = mapped_column(String(100), default="deepseek-chat")
    llm_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tools: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    memory_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class AgentRunModel(TimestampMixin, Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    agent_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    workflow_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    input: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    intermediate_steps: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tool_calls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ConversationModel(TimestampMixin, Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    user_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)


class MessageModel(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    agent_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system, tool
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now()
    )


class WorkflowModel(TimestampMixin, Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dag_definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class WorkflowRunModel(TimestampMixin, Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    workflow_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    node_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
