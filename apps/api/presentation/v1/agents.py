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


async def _run_agent(
    message: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """Agent loop: LLM with tools, decides what to call, iterates until done."""
    from quant_os_infra_agent.llm.base import ToolDefinition, ToolCall
    from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel
    from quant_os_infra_market.models.stock_model import StockModel
    from quant_os_infra_market.models.dragon_tiger_model import DragonTigerModel
    from sqlalchemy import func as sqlfunc, desc as sql_desc, case

    settings = get_app_settings()
    provider = LLMProviderFactory.create(settings.llm.default_provider)

    # --- Tool definitions ---
    tools = [
        ToolDefinition(
            name="query_market_overview",
            description="查询A股市场整体概况：涨跌家数、涨跌停数、成交额、平均涨跌幅等",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
        ToolDefinition(
            name="query_indices",
            description="查询主要市场指数（上证指数、深证成指、沪深300、创业板指、科创50）的最新行情",
            parameters={"type": "object", "properties": {}, "required": []},
        ),
        ToolDefinition(
            name="query_limit_up",
            description="查询今日涨停板个股列表，含涨停原因、连板数、所属行业",
            parameters={"type": "object", "properties": {"limit": {"type": "integer", "description": "返回条数，默认20"}}, "required": []},
        ),
        ToolDefinition(
            name="query_sector",
            description="查询指定板块/行业的个股行情。可按行业名称筛选，返回该行业股票的涨跌幅、成交额等",
            parameters={"type": "object", "properties": {
                "sector": {"type": "string", "description": "行业名称，如'通信'、'电子'、'银行'、'医药'等"},
                "limit": {"type": "integer", "description": "返回条数，默认20"},
            }, "required": ["sector"]},
        ),
        ToolDefinition(
            name="query_top_stocks",
            description="查询涨幅榜、跌幅榜或成交额排行",
            parameters={"type": "object", "properties": {
                "sort_by": {"type": "string", "enum": ["gainers", "losers", "volume"], "description": "排序方式：gainers=涨幅榜, losers=跌幅榜, volume=成交额榜"},
                "limit": {"type": "integer", "description": "返回条数，默认15"},
            }, "required": ["sort_by"]},
        ),
        ToolDefinition(
            name="query_dragon_tiger",
            description="查询龙虎榜数据，含买卖金额、净额、上榜原因",
            parameters={"type": "object", "properties": {"limit": {"type": "integer", "description": "返回条数，默认20"}}, "required": []},
        ),
        ToolDefinition(
            name="query_stock",
            description="查询单只股票的最新行情数据",
            parameters={"type": "object", "properties": {
                "ts_code": {"type": "string", "description": "股票代码，如'000001.SZ'、'600519.SH'"},
            }, "required": ["ts_code"]},
        ),
    ]

    # --- Tool execution ---
    async def execute_tool(name: str, args: dict) -> str:
        import json as _json
        try:
            if name == "query_market_overview":
                ohlcv_count = (await db.execute(select(sqlfunc.count()).select_from(OHLCVDailyModel))).scalar() or 0
                if ohlcv_count == 0:
                    return _json.dumps({"error": "无行情数据"}, ensure_ascii=False)
                latest_date = (await db.execute(
                    select(OHLCVDailyModel.trade_date).group_by(OHLCVDailyModel.trade_date)
                    .order_by(sqlfunc.count().desc()).limit(1)
                )).scalar_one_or_none()
                stats = (await db.execute(select(
                    sqlfunc.count(),
                    sqlfunc.sum(case((OHLCVDailyModel.pct_chg > 0, 1), else_=0)),
                    sqlfunc.sum(case((OHLCVDailyModel.pct_chg < 0, 1), else_=0)),
                    sqlfunc.sum(case((OHLCVDailyModel.pct_chg >= 9.9, 1), else_=0)),
                    sqlfunc.sum(case((OHLCVDailyModel.pct_chg <= -9.9, 1), else_=0)),
                    sqlfunc.sum(OHLCVDailyModel.amount),
                    sqlfunc.avg(OHLCVDailyModel.pct_chg),
                ).where(OHLCVDailyModel.trade_date == latest_date))).one()
                return _json.dumps({
                    "date": str(latest_date), "total": int(stats[0]),
                    "up": int(stats[1] or 0), "down": int(stats[2] or 0),
                    "limit_up": int(stats[3] or 0), "limit_down": int(stats[4] or 0),
                    "amount_billion": round(float(stats[5] or 0) / 1e8, 2),
                    "avg_pct_chg": round(float(stats[6] or 0), 2),
                }, ensure_ascii=False)

            elif name == "query_indices":
                import akshare as ak
                loop = asyncio.get_event_loop()
                indices = {"上证指数": "sh000001", "深证成指": "sz399001", "沪深300": "sh000300", "创业板指": "sz399006", "科创50": "sh000688"}
                from datetime import timedelta
                sd = (datetime.now().date() - timedelta(days=10)).strftime("%Y%m%d")
                result = {}
                for n, s in indices.items():
                    try:
                        df = await loop.run_in_executor(None, lambda s=s: ak.stock_zh_index_daily_em(symbol=s, start_date=sd))
                        if not df.empty:
                            latest = df.iloc[-1]
                            prev = df.iloc[-2] if len(df) > 1 else latest
                            pct = round((float(latest["close"]) - float(prev["close"])) / float(prev["close"]) * 100, 2) if float(prev["close"]) > 0 else 0
                            result[n] = {"close": round(float(latest["close"]), 2), "pct_chg": pct}
                    except Exception:
                        pass
                return _json.dumps(result, ensure_ascii=False)

            elif name == "query_limit_up":
                import akshare as ak
                loop = asyncio.get_event_loop()
                zt_df = await loop.run_in_executor(None, lambda: ak.stock_zt_pool_em(date=datetime.now().strftime("%Y%m%d")))
                if zt_df.empty:
                    return _json.dumps({"error": "今日无涨停数据"}, ensure_ascii=False)
                limit = args.get("limit", 20)
                records = []
                for _, row in zt_df.head(limit).iterrows():
                    cols = list(zt_df.columns)
                    records.append({
                        "name": str(row.iloc[2]) if len(cols) > 2 else "",
                        "code": str(row.iloc[1]) if len(cols) > 1 else "",
                        "pct_chg": round(float(row.iloc[3]), 2) if len(cols) > 3 else 0,
                        "consecutive": int(row.iloc[14]) if len(cols) > 14 else 1,
                        "industry": str(row.iloc[15]) if len(cols) > 15 else "",
                    })
                return _json.dumps(records, ensure_ascii=False)

            elif name == "query_sector":
                sector = args.get("sector", "")
                limit = args.get("limit", 20)
                ohlcv_count = (await db.execute(select(sqlfunc.count()).select_from(OHLCVDailyModel))).scalar() or 0
                if ohlcv_count == 0:
                    return _json.dumps({"error": "无行情数据"}, ensure_ascii=False)
                latest_date = (await db.execute(
                    select(OHLCVDailyModel.trade_date).group_by(OHLCVDailyModel.trade_date)
                    .order_by(sqlfunc.count().desc()).limit(1)
                )).scalar_one_or_none()
                # Join with StockModel to filter by industry
                rows = (await db.execute(
                    select(StockModel.name, StockModel.ts_code, OHLCVDailyModel.close, OHLCVDailyModel.pct_chg, OHLCVDailyModel.amount, OHLCVDailyModel.volume)
                    .join(OHLCVDailyModel, StockModel.ts_code == OHLCVDailyModel.ts_code)
                    .where(OHLCVDailyModel.trade_date == latest_date)
                    .where(StockModel.industry.ilike(f"%{sector}%"))
                    .order_by(sql_desc(OHLCVDailyModel.pct_chg))
                    .limit(limit)
                )).all()
                if not rows:
                    return _json.dumps({"error": f"未找到'{sector}'相关板块数据", "hint": "请检查行业名称，如通信、电子、银行、医药等"}, ensure_ascii=False)
                return _json.dumps({
                    "sector": sector, "date": str(latest_date), "count": len(rows),
                    "stocks": [{"name": r[0], "ts_code": r[1], "close": float(r[2]), "pct_chg": float(r[3]), "amount_billion": round(float(r[4] or 0) / 1e8, 2)} for r in rows],
                }, ensure_ascii=False)

            elif name == "query_top_stocks":
                sort_by = args.get("sort_by", "gainers")
                limit = args.get("limit", 15)
                latest_date = (await db.execute(
                    select(OHLCVDailyModel.trade_date).group_by(OHLCVDailyModel.trade_date)
                    .order_by(sqlfunc.count().desc()).limit(1)
                )).scalar_one_or_none()
                if not latest_date:
                    return _json.dumps({"error": "无行情数据"}, ensure_ascii=False)
                q = select(StockModel.name, OHLCVDailyModel.ts_code, OHLCVDailyModel.close, OHLCVDailyModel.pct_chg, OHLCVDailyModel.amount).join(OHLCVDailyModel, StockModel.ts_code == OHLCVDailyModel.ts_code).where(OHLCVDailyModel.trade_date == latest_date)
                if sort_by == "gainers":
                    q = q.order_by(sql_desc(OHLCVDailyModel.pct_chg))
                elif sort_by == "losers":
                    q = q.order_by(OHLCVDailyModel.pct_chg)
                else:
                    q = q.order_by(sql_desc(OHLCVDailyModel.amount))
                rows = (await db.execute(q.limit(limit))).all()
                return _json.dumps([{"name": r[0], "ts_code": r[1], "close": float(r[2]), "pct_chg": float(r[3]), "amount_billion": round(float(r[4] or 0) / 1e8, 2)} for r in rows], ensure_ascii=False)

            elif name == "query_dragon_tiger":
                limit = args.get("limit", 20)
                rows = (await db.execute(
                    select(DragonTigerModel).order_by(DragonTigerModel.trade_date.desc()).limit(limit)
                )).scalars().all()
                return _json.dumps([{"name": getattr(r, "name", None) or r.ts_code, "ts_code": r.ts_code, "reason": r.reason, "buy_amount": float(r.buy_amount or 0), "sell_amount": float(r.sell_amount or 0), "net_amount": float(r.net_amount or 0), "date": str(r.trade_date)} for r in rows], ensure_ascii=False)

            elif name == "query_stock":
                ts_code = args.get("ts_code", "")
                stock = (await db.execute(select(StockModel).where(StockModel.ts_code == ts_code))).scalar_one_or_none()
                if not stock:
                    return _json.dumps({"error": f"股票{ts_code}不存在"}, ensure_ascii=False)
                latest = (await db.execute(select(OHLCVDailyModel).where(OHLCVDailyModel.ts_code == ts_code).order_by(OHLCVDailyModel.trade_date.desc()).limit(1))).scalar_one_or_none()
                if not latest:
                    return _json.dumps({"name": stock.name, "ts_code": ts_code, "error": "无行情数据"}, ensure_ascii=False)
                return _json.dumps({"name": stock.name, "ts_code": ts_code, "industry": stock.industry, "close": float(latest.close), "pct_chg": float(latest.pct_chg), "volume": float(latest.volume), "amount": float(latest.amount or 0), "date": str(latest.trade_date)}, ensure_ascii=False)

            else:
                return _json.dumps({"error": f"未知工具: {name}"}, ensure_ascii=False)
        except Exception as e:
            return _json.dumps({"error": str(e)}, ensure_ascii=False)

    # --- Agent loop ---
    system_prompt = (
        "你是 QuantOS AI 量化研究助手。你拥有工具可以查询A股市场实时数据。\n"
        "根据用户的问题，自主决定调用哪些工具获取数据，然后基于真实数据给出专业分析。\n"
        "规则：\n"
        "- 需要数据时主动调用工具，不要猜测或编造数据\n"
        "- 可以多次调用不同工具来获取全面信息\n"
        "- 回答要基于工具返回的真实数据，用数据说话\n"
        "- 回答简洁专业，同时通俗易懂"
    )

    llm_messages = [
        Message(role=MessageRole.SYSTEM, content=system_prompt),
        Message(role=MessageRole.USER, content=message),
    ]

    max_iterations = 5
    total_tokens = 0

    for _ in range(max_iterations):
        try:
            response = await provider.chat(
                llm_messages,
                tools=tools,
                config=LLMConfig(model=settings.llm.mimo_model, temperature=0.3, max_tokens=3000),
            )
        except Exception as e:
            return {"type": "error", "message": f"LLM 调用失败: {str(e)}"}

        total_tokens += response.usage.total_tokens if response.usage else 0

        # If LLM wants to call tools
        if response.has_tool_calls and response.tool_calls:
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
                content=response.content or "",
                tool_calls=tc_dicts,
            ))

            # Execute each tool call and add results
            for tc in response.tool_calls:
                args = tc.arguments if isinstance(tc.arguments, dict) else {}
                result = await execute_tool(tc.name, args)
                llm_messages.append(Message(
                    role=MessageRole.TOOL,
                    content=result,
                    tool_call_id=tc.id,
                ))
            continue

        # LLM returned a final text answer
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
    message = request.message.strip()
    if not message:
        return ok({"type": "error", "message": "消息不能为空"})

    try:
        result = await _run_agent(message, db)
        if result.get("type") not in ("direct_answer", "error"):
            result = {"type": "direct_answer", "content": str(result)}
        return ok(result)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("Agent error: %s", e, exc_info=True)
        # Fallback: direct LLM answer without tools
        try:
            settings = get_app_settings()
            provider = LLMProviderFactory.create(settings.llm.default_provider)
            response = await provider.chat(
                [Message(role=MessageRole.SYSTEM, content="你是QuantOS AI量化研究助手。"), Message(role=MessageRole.USER, content=message)],
                config=LLMConfig(model=settings.llm.mimo_model, temperature=0.5, max_tokens=2000),
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
