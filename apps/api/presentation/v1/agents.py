"""AI Agent endpoints."""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_app_settings
from dependencies import get_db_session
from presentation.api_response import ok
from quant_os_infra_agent.llm.base import LLMConfig, Message, MessageRole
from quant_os_infra_agent.llm.factory import LLMProviderFactory
from quant_os_infra_agent.models import AgentModel, AgentRunModel, MessageModel, WorkflowModel, WorkflowRunModel

router = APIRouter()


DEFAULT_AGENT_NAME = "Mimo Quant Analyst"
DEFAULT_AGENT_TYPE = "quant_research"
DEFAULT_SYSTEM_PROMPT = (
    "You are a senior quantitative research assistant. Help users analyze A-share "
    "market data, factor logic, backtest results, portfolio risks, and implementation "
    "trade-offs. Be concise, empirical, and point out data or modeling caveats."
)


class AgentRunRequest(BaseModel):
    input: str | None = None
    message: str | None = None
    conversation_id: str | None = None

    @model_validator(mode="after")
    def require_prompt(self) -> "AgentRunRequest":
        if not (self.input or self.message):
            raise ValueError("Either input or message is required")
        return self


class ChatResearchRequest(BaseModel):
    message: str
    conversation_id: str | None = None


def _model_for_provider(provider: str) -> str:
    settings = get_app_settings()
    if provider == "mimo":
        return settings.llm.mimo_model
    if provider == "openai":
        return settings.llm.openai_model
    if provider == "deepseek":
        return settings.llm.deepseek_model
    return settings.llm.deepseek_model


async def _ensure_default_agent(db: AsyncSession) -> None:
    result = await db.execute(select(AgentModel).limit(1))
    if result.scalar_one_or_none():
        return

    settings = get_app_settings()
    provider = settings.llm.default_provider
    db.add(
        AgentModel(
            name=DEFAULT_AGENT_NAME,
            agent_type=DEFAULT_AGENT_TYPE,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            llm_provider=provider,
            llm_model=_model_for_provider(provider),
            llm_params={"temperature": 0.2, "max_tokens": 1200},
            tools={"enabled": ["factor", "backtest", "market"]},
            memory_config={"conversation_memory": True},
            is_active=True,
        )
    )
    await db.flush()


def _agent_to_api(agent: AgentModel) -> dict[str, Any]:
    return {
        "id": agent.id,
        "name": agent.name,
        "type": agent.agent_type,
        "agent_type": agent.agent_type,
        "description": agent.system_prompt,
        "status": "active" if agent.is_active else "inactive",
        "llm_provider": agent.llm_provider,
        "llm_model": agent.llm_model,
        "is_active": agent.is_active,
        "version": agent.version,
        "tools": agent.tools or {},
    }


def _run_to_api(run: AgentRunModel, messages: list[dict[str, str]] | None = None) -> dict[str, Any]:
    output = run.output or {}
    return {
        "id": run.id,
        "agent_id": run.agent_id,
        "conversation_id": run.conversation_id,
        "status": run.status,
        "input": run.input or {},
        "output": output,
        "messages": messages or output.get("messages", []),
        "tokens_used": run.tokens_used,
        "latency_ms": run.latency_ms,
        "cost_usd": float(run.cost_usd) if run.cost_usd is not None else None,
        "error": run.error,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


@router.post("/chat/research")
async def chat_research(
    request: ChatResearchRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Accept a user message, auto-create and run a full_research workflow, return run_id."""
    from presentation.v1.workflows import RESEARCH_WORKFLOW_TEMPLATES, _execute_workflow_async

    await _ensure_default_agent(db)

    # Get default agent
    result = await db.execute(select(AgentModel).where(AgentModel.is_active == True).limit(1))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="No active agent found")

    # Create workflow from full_research template
    template = RESEARCH_WORKFLOW_TEMPLATES["full_research"]
    workflow_id = str(uuid.uuid4())
    workflow = WorkflowModel(
        id=workflow_id,
        name=template["name"],
        description=template["description"],
        dag_definition=template["dag"],
        is_active=True,
    )
    db.add(workflow)

    # Create workflow run
    run_id = str(uuid.uuid4())
    run = WorkflowRunModel(
        id=run_id,
        workflow_id=workflow_id,
        status="running",
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)

    # Create agent run for tracking
    agent_run = AgentRunModel(
        agent_id=agent.id,
        conversation_id=request.conversation_id,
        status="running",
        input={"query": request.message},
        started_at=datetime.now(timezone.utc),
    )
    db.add(agent_run)
    await db.flush()

    # Launch workflow execution in background
    dag = template["dag"]
    initial_context = {"user_message": request.message}
    asyncio.create_task(_execute_workflow_async(run_id, dag, initial_context))

    return ok({
        "run_id": run_id,
        "workflow_id": workflow_id,
        "agent_run_id": agent_run.id,
        "status": "running",
        "conversation_id": request.conversation_id,
    })


async def _detect_intent(message: str) -> str:
    """LLM-based intent detection with clear guidance."""
    settings = get_app_settings()
    provider = LLMProviderFactory.create(settings.llm.default_provider)
    classify_messages = [
        Message(
            role=MessageRole.SYSTEM,
            content=(
                "你是意图分类器。判断用户是想「获取市场数据做研究」还是「普通对话」。\n\n"
                "research：用户明确要求获取、查看、分析实时A股市场数据。例如：\n"
                "- 今日市场/大盘/行情怎么样\n"
                "- 分析一下今天的市场\n"
                "- 涨停板/跌停板有哪些\n"
                "- 板块轮动/行业分析\n"
                "- 市场情绪研判\n"
                "- 帮我研究一下XX\n"
                "- 生成研究报告\n\n"
                "chat：用户在聊天、问概念、问操作方法、闲聊。例如：\n"
                "- 你好/谢谢\n"
                "- 什么是量化/因子/IC\n"
                "- 怎么使用这个系统\n"
                "- 帮我解释一下XX概念\n"
                "- 你觉得XX怎么样（观点类问题）\n\n"
                "只回复一个词：research 或 chat"
            ),
        ),
        Message(role=MessageRole.USER, content=message),
    ]
    try:
        resp = await provider.chat(
            classify_messages,
            config=LLMConfig(model=settings.llm.mimo_model, temperature=0, max_tokens=10),
        )
        result = (resp.content or "").strip().lower()
        return "research" if "research" in result else "chat"
    except Exception:
        return "chat"


@router.post("/chat/message")
async def chat_message(
    request: ChatResearchRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Smart chat: LLM decides whether to run research or answer directly."""
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel
    from sqlalchemy import func as sqlfunc

    message = request.message.strip()
    if not message:
        return ok({"type": "error", "message": "消息不能为空"})

    # Let LLM decide: research workflow or direct chat
    intent = await _detect_intent(message)
    if intent == "research":
        return await chat_research(request, db)

    # Direct LLM answer with market context
    settings = get_app_settings()
    provider = LLMProviderFactory.create(settings.llm.default_provider)

    # Get brief market context
    ohlcv_count = (await db.execute(select(sqlfunc.count()).select_from(OHLCVDailyModel))).scalar() or 0
    latest_date = None
    market_brief = ""
    if ohlcv_count > 0:
        from sqlalchemy import case
        latest_date = (await db.execute(
            select(OHLCVDailyModel.trade_date)
            .group_by(OHLCVDailyModel.trade_date)
            .order_by(sqlfunc.count().desc())
            .limit(1)
        )).scalar_one_or_none()

        if latest_date:
            stats = (await db.execute(
                select(
                    sqlfunc.count(),
                    sqlfunc.sum(case((OHLCVDailyModel.pct_chg > 0, 1), else_=0)),
                    sqlfunc.sum(case((OHLCVDailyModel.pct_chg < 0, 1), else_=0)),
                    sqlfunc.sum(OHLCVDailyModel.amount),
                ).where(OHLCVDailyModel.trade_date == latest_date)
            )).one()
            market_brief = f"当前数据库: {ohlcv_count}条行情({latest_date}), 涨{stats[1]}/跌{stats[2]}, 成交额{round(float(stats[3] or 0)/1e8)}亿"

    system_prompt = f"""你是 QuantOS AI 量化研究助手。你是没有工具调用能力，只能基于数据库信息进行回答。

你的职责：
1. 回答关于A股市场、量化投资、金融知识的问题
2. 解释量化概念、因子、策略
3. 根据下方提供的市场数据摘要回答具体问题

{market_brief}

重要规则：
- 你不能调用任何工具、API或外部数据源。不要生成tool_call、function_call或任何代码块。
- 直接用文字回答用户问题，基于你已有的知识和上方提供的数据。
- 如果用户需要实时市场分析、板块行情、涨跌停分析等需要完整数据的研究，请直接告诉用户："这个需求需要运行完整研究分析，请输入'分析今日市场'等指令来触发。"
- 回答要简洁专业，但同时要易懂。"""

    llm_messages = [
        Message(role=MessageRole.SYSTEM, content=system_prompt),
        Message(role=MessageRole.USER, content=message),
    ]

    try:
        response = await provider.chat(
            llm_messages,
            config=LLMConfig(model=settings.llm.mimo_model, temperature=0.5, max_tokens=2000),
        )
        return ok({
            "type": "direct_answer",
            "content": response.content,
            "model": response.model,
            "tokens": response.usage.total_tokens if response.usage else 0,
        })
    except Exception as e:
        return ok({"type": "error", "message": f"LLM 调用失败: {str(e)}"})


@router.get("")
@router.get("/")
async def list_agents(
    agent_type: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_default_agent(db)

    query = select(AgentModel)
    if agent_type:
        query = query.where(AgentModel.agent_type == agent_type)
    if is_active is not None:
        query = query.where(AgentModel.is_active == is_active)

    result = await db.execute(query.order_by(AgentModel.name))
    agents = result.scalars().all()
    return ok([_agent_to_api(agent) for agent in agents])


@router.get("/{agent_id}")
async def get_agent(
    agent_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    await _ensure_default_agent(db)
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return ok(_agent_to_api(agent))


@router.post("/{agent_id}/runs")
async def start_agent_run(
    agent_id: str,
    request: AgentRunRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await db.execute(select(AgentModel).where(AgentModel.id == agent_id))
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    if not agent.is_active:
        raise HTTPException(status_code=400, detail=f"Agent {agent_id} is inactive")

    user_input = request.input or request.message or ""
    started_at = datetime.now(timezone.utc)
    run = AgentRunModel(
        agent_id=agent_id,
        conversation_id=request.conversation_id,
        status="running",
        input={"query": user_input},
        started_at=started_at,
    )
    db.add(run)
    await db.flush()

    llm_params = agent.llm_params or {}
    provider = LLMProviderFactory.create(agent.llm_provider)
    messages = [
        Message(role=MessageRole.SYSTEM, content=agent.system_prompt),
        Message(role=MessageRole.USER, content=user_input),
    ]
    started_perf = time.perf_counter()

    try:
        response = await provider.chat(
            messages,
            config=LLMConfig(
                model=agent.llm_model or provider.default_model,
                temperature=float(llm_params.get("temperature", 0.2)),
                max_tokens=int(llm_params.get("max_tokens", 1200)),
            ),
        )
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        run.latency_ms = int((time.perf_counter() - started_perf) * 1000)
        run.completed_at = datetime.now(timezone.utc)
        await db.flush()
        raise HTTPException(status_code=502, detail=f"LLM provider call failed: {exc}") from exc

    assistant_content = response.content or ""
    response_messages = [
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": assistant_content},
    ]
    usage = response.usage
    run.status = "completed"
    run.output = {
        "content": assistant_content,
        "model": response.model or agent.llm_model,
        "provider": provider.provider_name,
        "messages": response_messages,
    }
    run.tokens_used = usage.total_tokens if usage else None
    run.cost_usd = Decimal(str(usage.cost_estimate)) if usage else None
    run.latency_ms = int((time.perf_counter() - started_perf) * 1000)
    run.completed_at = datetime.now(timezone.utc)

    if request.conversation_id:
        db.add_all(
            [
                MessageModel(
                    conversation_id=request.conversation_id,
                    agent_run_id=run.id,
                    role="user",
                    content=user_input,
                ),
                MessageModel(
                    conversation_id=request.conversation_id,
                    agent_run_id=run.id,
                    role="assistant",
                    content=assistant_content,
                    metadata_={"model": response.model or agent.llm_model},
                ),
            ]
        )

    await db.flush()
    return ok(_run_to_api(run, response_messages))


@router.get("/{agent_id}/runs")
async def list_agent_runs(
    agent_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await db.execute(
        select(AgentRunModel)
        .where(AgentRunModel.agent_id == agent_id)
        .order_by(AgentRunModel.created_at.desc())
        .limit(limit)
    )
    return ok([_run_to_api(run) for run in result.scalars().all()])


@router.get("/runs/{run_id}")
async def get_agent_run(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await db.execute(select(AgentRunModel).where(AgentRunModel.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Agent run {run_id} not found")
    return ok(_run_to_api(run))
