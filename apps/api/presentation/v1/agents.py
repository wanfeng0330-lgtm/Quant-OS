"""AI Agent endpoints."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
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


async def _run_agent(
    message: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """Agent loop: LLM with tools, decides what to call, iterates until done."""
    from quant_os_infra_agent.tools import tool_registry
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel
    from sqlalchemy import func as sqlfunc, case

    settings = get_app_settings()
    provider = LLMProviderFactory.create("deepseek")
    agent_model = settings.llm.deepseek_model

    # Get tool definitions from registry (single source of truth).
    # Filter to only include tools with simple parameter types (STRING/INTEGER/NUMBER/BOOLEAN)
    # compatible with all LLM function-calling APIs.
    SAFE_TOOL_NAMES = {
        "query_market_overview", "query_market_distribution", "query_indices",
        "query_limit_up", "query_limit_down", "query_consecutive_limit_up",
        "query_sector", "query_sector_ranking", "query_top_stocks",
        "query_volume_leaders", "query_dragon_tiger",
        "query_stock", "query_stock_history", "search_stocks_by_name",
    }
    all_tool_defs = tool_registry.get_tool_definitions()
    tools = [t for t in all_tool_defs if t.name in SAFE_TOOL_NAMES]

    # --- Tool execution (thin wrapper around registry) ---
    async def execute_tool(name: str, args: dict) -> str:
        try:
            result = await tool_registry.execute(name, **args)
            if result.success:
                return result.data if isinstance(result.data, str) else json.dumps(result.data, ensure_ascii=False)
            return json.dumps({"error": result.error or "Tool execution failed"}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"error": str(e)}, ensure_ascii=False)

    # --- Pre-fetch market overview for system prompt (avoids extra tool calls) ---
    market_brief = ""
    try:
        ohlcv_count = (await db.execute(select(sqlfunc.count()).select_from(OHLCVDailyModel))).scalar() or 0
        if ohlcv_count > 0:
            latest_date = (await db.execute(
                select(OHLCVDailyModel.trade_date).group_by(OHLCVDailyModel.trade_date)
                .order_by(sqlfunc.count().desc()).limit(1)
            )).scalar_one_or_none()
            if latest_date:
                stats = (await db.execute(select(
                    sqlfunc.count(),
                    sqlfunc.sum(case((OHLCVDailyModel.pct_chg > 0, 1), else_=0)),
                    sqlfunc.sum(case((OHLCVDailyModel.pct_chg < 0, 1), else_=0)),
                    sqlfunc.sum(case((OHLCVDailyModel.pct_chg >= 9.9, 1), else_=0)),
                    sqlfunc.sum(case((OHLCVDailyModel.pct_chg <= -9.9, 1), else_=0)),
                    sqlfunc.sum(OHLCVDailyModel.amount),
                ).where(OHLCVDailyModel.trade_date == latest_date))).one()
                market_brief = f"\n当前数据库概况({latest_date}): {ohlcv_count}条行情, 涨{stats[1]}/跌{stats[2]}, 涨停{stats[3]}/跌停{stats[4]}, 成交额{round(float(stats[5] or 0)/1e8)}亿"
    except Exception:
        pass

    # --- Agent loop ---
    system_prompt = (
        "你是 QuantOS AI 量化研究助手。你拥有以下工具可以查询A股市场实时数据，必须通过调用工具获取数据来回答用户问题：\n\n"
        "可用工具：\n"
        "- query_market_overview: 市场整体概况（涨跌家数、涨跌停数、成交额）\n"
        "- query_market_distribution: 涨跌幅分布统计（涨超5%、跌超5%、涨停、跌停数量）\n"
        "- query_indices: 主要指数行情（上证、深证、沪深300、创业板、科创50）\n"
        "- query_limit_up: 涨停板个股列表\n"
        "- query_limit_down: 跌停板个股列表\n"
        "- query_consecutive_limit_up(min_days=2): 连板股列表（连续涨停）\n"
        "- query_sector(sector='行业名'): 指定行业的个股行情\n"
        "- query_sector_ranking(sort_by='gainers'): 所有行业板块涨跌幅排行\n"
        "- query_top_stocks(sort_by='gainers'): 涨幅/跌幅/成交额排行\n"
        "- query_volume_leaders: 换手率/成交量排行\n"
        "- query_dragon_tiger: 龙虎榜数据\n"
        "- query_stock(ts_code='代码'): 单只股票行情\n"
        "- query_stock_history(ts_code='代码', days=20): 股票历史行情\n"
        "- search_stocks_by_name(keyword='关键词'): 按名称搜索股票\n\n"
        f"{market_brief}\n\n"
        "调用规则：\n"
        "- 你必须调用工具获取数据，不要凭空编造\n"
        "- '哪个板块涨得最猛/板块排行' → query_sector_ranking\n"
        "- 某个具体板块 → query_sector(sector='板块名')\n"
        "- 大盘/市场概况 → query_market_overview + query_indices\n"
        "- 涨停/跌停 → query_limit_up / query_limit_down\n"
        "- 连板/龙头 → query_consecutive_limit_up\n"
        "- 某只股票 → search_stocks_by_name先查代码，再query_stock\n"
        "- 市场强弱/赚钱效应 → query_market_distribution\n"
        "- 可以组合调用多个工具获取全面数据\n"
        "- 回答基于真实数据，用数据说话，简洁专业"
    )

    llm_messages = [
        Message(role=MessageRole.SYSTEM, content=system_prompt),
        Message(role=MessageRole.USER, content=message),
    ]

    max_iterations = 5
    total_tokens = 0
    import logging
    logger = logging.getLogger(__name__)

    for iteration in range(max_iterations):
        try:
            logger.info("Agent iteration %d: provider=%s, model=%s, messages=%d, tools=%d",
                        iteration, provider.provider_name, agent_model, len(llm_messages), len(tools))
            logger.info("Agent tool names: %s", [t.name for t in tools])
            response = await provider.chat(
                llm_messages,
                tools=tools,
                config=LLMConfig(model=agent_model, temperature=0.3, max_tokens=3000, tool_choice="auto"),
            )
            logger.info("Agent response: has_tool_calls=%s, tool_calls=%d, content_len=%d, finish_reason=%s",
                        response.has_tool_calls,
                        len(response.tool_calls) if response.tool_calls else 0,
                        len(response.content) if response.content else 0,
                        response.finish_reason)
        except Exception as e:
            logger.error("Agent LLM call failed: %s", e, exc_info=True)
            return {"type": "error", "message": f"LLM 调用失败: {str(e)}"}

        total_tokens += response.usage.total_tokens if response.usage else 0

        # If LLM wants to call tools
        if response.has_tool_calls and response.tool_calls:
            logger.info("Agent: executing %d tool calls", len(response.tool_calls))
            # Convert tool_calls to OpenAI format for the next message
            tc_dicts = []
            for tc in response.tool_calls:
                tc_dict = {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.arguments, ensure_ascii=False) if isinstance(tc.arguments, dict) else str(tc.arguments),
                    },
                }
                tc_dicts.append(tc_dict)

            llm_messages.append(Message(
                role=MessageRole.ASSISTANT,
                content=response.content,
                tool_calls=tc_dicts,
            ))

            # Execute each tool call and add results
            for tc in response.tool_calls:
                args = tc.arguments if isinstance(tc.arguments, dict) else {}
                logger.info("Agent: calling tool %s(%s)", tc.name, args)
                result = await execute_tool(tc.name, args)
                logger.info("Agent: tool %s returned %d chars", tc.name, len(result))
                llm_messages.append(Message(
                    role=MessageRole.TOOL,
                    content=result,
                    tool_call_id=tc.id,
                ))
            continue

        # LLM returned a final text answer (no tool calls)
        logger.info("Agent: final answer, content_len=%d", len(response.content) if response.content else 0)
        return {
            "type": "direct_answer",
            "content": response.content or "",
            "model": response.model,
            "tokens": total_tokens,
        }

    return {"type": "error", "message": "Agent 达到最大迭代次数"}


@router.post("/chat/message")
async def chat_message(
    request: ChatResearchRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """AI Agent: LLM with tools, autonomously decides what data to fetch."""
    import logging
    logger = logging.getLogger(__name__)

    message = request.message.strip()
    if not message:
        return ok({"type": "error", "message": "消息不能为空"})

    logger.info("=== Agent request: %s ===", message[:100])
    try:
        result = await _run_agent(message, db)
        logger.info("Agent result type: %s, content_len: %d", result.get("type"), len(result.get("content", "")))
        if result.get("type") not in ("direct_answer", "error"):
            result = {"type": "direct_answer", "content": str(result)}
        return ok(result)
    except Exception as e:
        logging.getLogger(__name__).error("Agent error: %s", e, exc_info=True)
        # Fallback: direct LLM answer without tools
        try:
            settings = get_app_settings()
            provider = LLMProviderFactory.create("deepseek")
            response = await provider.chat(
                [Message(role=MessageRole.SYSTEM, content="你是QuantOS AI量化研究助手。"), Message(role=MessageRole.USER, content=message)],
                config=LLMConfig(model=settings.llm.deepseek_model, temperature=0.5, max_tokens=2000),
            )
            return ok({"type": "direct_answer", "content": response.content or "无法处理请求", "model": response.model})
        except Exception:
            return ok({"type": "error", "message": f"Agent 执行失败: {str(e)}"})


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

    started_perf = time.perf_counter()

    # Use the tool-aware agent loop instead of bare LLM call
    agent_result = await _run_agent(user_input, db)

    result_type = agent_result.get("type", "error")
    assistant_content = agent_result.get("content", "") if result_type == "direct_answer" else agent_result.get("message", str(agent_result))

    response_messages = [
        {"role": "user", "content": user_input},
        {"role": "assistant", "content": assistant_content},
    ]
    run.status = "completed" if result_type == "direct_answer" else "failed"
    run.output = {
        "content": assistant_content,
        "type": result_type,
        "messages": response_messages,
    }
    run.tokens_used = agent_result.get("tokens")
    run.latency_ms = int((time.perf_counter() - started_perf) * 1000)
    run.completed_at = datetime.now(timezone.utc)
    if result_type == "error":
        run.error = agent_result.get("message", "Agent execution failed")

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
                    metadata_={"type": result_type},
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
