"""Workflow management and execution endpoints."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dependencies import get_db_session
from presentation.api_response import ok
from quant_os_infra_agent.models.agent_model import WorkflowModel, WorkflowRunModel

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory workflow run state (for streaming). Production: Redis.
# ---------------------------------------------------------------------------
_active_runs: dict[str, dict[str, Any]] = {}
_run_event_queues: dict[str, list[asyncio.Queue]] = {}


def _broadcast(run_id: str, event: dict[str, Any]) -> None:
    """Push event to all SSE listeners for a run."""
    for q in _run_event_queues.get(run_id, []):
        q.put_nowait(event)


# ---------------------------------------------------------------------------
# Predefined research workflow templates
# ---------------------------------------------------------------------------

RESEARCH_WORKFLOW_TEMPLATES: dict[str, dict[str, Any]] = {
    "alpha_research": {
        "name": "Alpha 因子研究",
        "description": "从数据获取到因子分析的完整 Alpha 研究流程",
        "dag": {
            "nodes": [
                {"id": "data_fetch", "name": "数据获取", "type": "task", "config": {"type": "tool", "tool": "fetch_market_data"}, "dependencies": []},
                {"id": "factor_gen", "name": "因子生成", "type": "task", "config": {"type": "llm", "prompt": "生成候选Alpha因子"}, "dependencies": ["data_fetch"]},
                {"id": "factor_calc", "name": "因子计算", "type": "task", "config": {"type": "tool", "tool": "compute_factor"}, "dependencies": ["factor_gen"]},
                {"id": "ic_analysis", "name": "IC分析", "type": "task", "config": {"type": "tool", "tool": "analyze_ic"}, "dependencies": ["factor_calc"]},
                {"id": "ic_check", "name": "IC阈值检查", "type": "condition", "config": {"type": "threshold", "value": "ic_mean", "operator": ">", "threshold": 0.03, "true_branch": "backtest", "false_branch": "reject"}, "dependencies": ["ic_analysis"]},
                {"id": "backtest", "name": "因子回测", "type": "task", "config": {"type": "tool", "tool": "run_backtest"}, "dependencies": ["ic_check"]},
                {"id": "risk_analysis", "name": "风险分析", "type": "task", "config": {"type": "tool", "tool": "analyze_risk"}, "dependencies": ["backtest"]},
                {"id": "report", "name": "研究报告", "type": "task", "config": {"type": "llm", "prompt": "生成研究报告"}, "dependencies": ["risk_analysis"]},
                {"id": "reject", "name": "因子不达标", "type": "task", "config": {"type": "function", "function": "log_rejection"}, "dependencies": ["ic_check"]},
            ],
        },
    },
    "portfolio_optimization": {
        "name": "组合优化研究",
        "description": "多因子组合优化与风险控制",
        "dag": {
            "nodes": [
                {"id": "factor_pool", "name": "因子池筛选", "type": "task", "config": {"type": "tool", "tool": "list_factors"}, "dependencies": []},
                {"id": "factor_corr", "name": "因子相关性分析", "type": "task", "config": {"type": "tool", "tool": "analyze_correlation"}, "dependencies": ["factor_pool"]},
                {"id": "combine", "name": "因子合成", "type": "task", "config": {"type": "tool", "tool": "combine_factors"}, "dependencies": ["factor_corr"]},
                {"id": "portfolio", "name": "组合构建", "type": "task", "config": {"type": "tool", "tool": "optimize_portfolio"}, "dependencies": ["combine"]},
                {"id": "backtest", "name": "组合回测", "type": "task", "config": {"type": "tool", "tool": "run_backtest"}, "dependencies": ["portfolio"]},
                {"id": "report", "name": "组合报告", "type": "task", "config": {"type": "llm", "prompt": "生成组合报告"}, "dependencies": ["backtest"]},
            ],
        },
    },
    "sentiment_analysis": {
        "name": "市场情绪研究",
        "description": "A股市场情绪综合分析",
        "dag": {
            "nodes": [
                {"id": "market_data", "name": "市场数据", "type": "task", "config": {"type": "tool", "tool": "fetch_market_overview"}, "dependencies": []},
                {"id": "northbound", "name": "北向资金", "type": "task", "config": {"type": "tool", "tool": "fetch_northbound"}, "dependencies": []},
                {"id": "dragon_tiger", "name": "龙虎榜", "type": "task", "config": {"type": "tool", "tool": "fetch_dragon_tiger"}, "dependencies": []},
                {"id": "sentiment", "name": "情绪计算", "type": "task", "config": {"type": "llm", "prompt": "综合分析市场情绪"}, "dependencies": ["market_data", "northbound", "dragon_tiger"]},
                {"id": "report", "name": "情绪报告", "type": "task", "config": {"type": "llm", "prompt": "生成情绪报告"}, "dependencies": ["sentiment"]},
            ],
        },
    },
    "full_research": {
        "name": "全量研究分析",
        "description": "数据获取、因子探索、市场分析、情绪分析、报告生成的完整研究链路",
        "dag": {
            "nodes": [
                # Layer 0: 单一数据同步节点（顺序执行所有AKShare调用，避免并行冲突）
                {"id": "data_sync", "name": "全量数据同步", "type": "task", "config": {"type": "tool", "tool": "sync_all_market_data"}, "dependencies": []},
                # Layer 1: 并行分析（依赖数据同步完成）
                {"id": "factor_discovery", "name": "因子探索与发现", "type": "task", "config": {"type": "llm", "prompt": "基于数据上下文中的market_overview、top_gainers、top_losers、top_volume等真实数据，发现并评估有潜力的Alpha因子。给出2-3个具体因子公式（如动量因子、量价因子），解释其经济逻辑和适用场景。"}, "dependencies": ["data_sync"]},
                {"id": "sector_analysis", "name": "行业轮动分析", "type": "task", "config": {"type": "llm", "prompt": "基于数据上下文中的limit_up_industries（涨停板块分布）、limit_up_pool（涨停股详情）、top_gainers/top_losers（涨跌幅排行）、dragon_tiger_entries（龙虎榜）数据，分析行业轮动趋势。指出当前强势行业和弱势行业，分析资金集中方向。"}, "dependencies": ["data_sync"]},
                {"id": "sentiment_calc", "name": "市场情绪研判", "type": "task", "config": {"type": "llm", "prompt": "基于数据上下文中的market_overview（涨跌家数、涨跌停数、成交额）、market_indices（主要指数涨跌幅）、limit_up_pool（涨停股及原因）、dragon_tiger_entries（龙虎榜）数据，综合分析市场情绪。给出情绪评分(0-100)、情绪偏多/偏空判断、以及情绪变化趋势。"}, "dependencies": ["data_sync"]},
                # Layer 2: 综合报告（依赖所有分析完成）
                {"id": "report_synthesis", "name": "综合研究报告", "type": "task", "config": {"type": "llm", "prompt": "基于以上三个分析结果（因子探索、行业轮动、市场情绪），生成一份完整的A股市场综合研究报告。报告格式要求：\n\n## 今日A股市场综合研究报告\n\n### 一、市场概况\n引用market_indices（主要指数涨跌幅）、涨跌家数、涨跌停数、总成交额等数据\n\n### 二、涨停分析\n引用limit_up_pool数据，分析涨停原因、连板情况、板块效应\n\n### 三、行业轮动分析\n指出强势行业和弱势行业，引用行业统计数据\n\n### 四、因子发现\n推荐2-3个有潜力的量化因子及其逻辑\n\n### 五、市场情绪研判\n给出情绪评分(0-100)和偏多/偏空判断\n\n### 六、综合结论与投资建议\n用通俗易懂的语言总结并给出建议\n\n注意：用通俗易懂的语言，必须引用真实数据，不要编造。"}, "dependencies": ["factor_discovery", "sector_analysis", "sentiment_calc"]},
            ],
        },
    },
}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class WorkflowCreateRequest(BaseModel):
    name: str
    description: str = ""
    dag: dict[str, Any] = Field(default_factory=dict)
    template: str | None = None


class WorkflowRunRequest(BaseModel):
    input: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _workflow_to_api(wf: WorkflowModel) -> dict[str, Any]:
    return {
        "id": wf.id,
        "name": wf.name,
        "description": wf.description,
        "dag": wf.dag_definition,
        "is_active": wf.is_active,
        "created_at": wf.created_at.isoformat() if wf.created_at else None,
    }


def _run_to_api(run: WorkflowRunModel) -> dict[str, Any]:
    return {
        "id": run.id,
        "workflow_id": run.workflow_id,
        "status": run.status,
        "state": run.state or {},
        "node_results": run.node_results or {},
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
@router.get("/")
async def list_workflows(
    is_active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    query = select(WorkflowModel)
    if is_active is not None:
        query = query.where(WorkflowModel.is_active == is_active)
    result = await db.execute(query.order_by(WorkflowModel.created_at.desc()))
    return ok([_workflow_to_api(wf) for wf in result.scalars().all()])


@router.get("/templates")
async def list_workflow_templates() -> dict[str, Any]:
    templates = []
    for key, tpl in RESEARCH_WORKFLOW_TEMPLATES.items():
        templates.append({
            "id": key,
            "name": tpl["name"],
            "description": tpl["description"],
            "node_count": len(tpl["dag"]["nodes"]),
        })
    return ok(templates)


@router.post("")
@router.post("/")
async def create_workflow(
    request: WorkflowCreateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    dag = request.dag
    if request.template and request.template in RESEARCH_WORKFLOW_TEMPLATES:
        dag = RESEARCH_WORKFLOW_TEMPLATES[request.template]["dag"]
        if not request.name:
            request.name = RESEARCH_WORKFLOW_TEMPLATES[request.template]["name"]

    if not dag or not dag.get("nodes"):
        raise HTTPException(status_code=400, detail="dag with nodes is required (or provide template)")

    wf = WorkflowModel(
        name=request.name,
        description=request.description,
        dag_definition=dag,
        is_active=True,
    )
    db.add(wf)
    await db.flush()
    return ok(_workflow_to_api(wf))


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await db.execute(select(WorkflowModel).where(WorkflowModel.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")
    return ok(_workflow_to_api(wf))


@router.post("/{workflow_id}/run")
async def run_workflow(
    workflow_id: str,
    request: WorkflowRunRequest,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Execute a workflow and return run ID. Use SSE /workflows/runs/{run_id}/stream for real-time updates."""
    result = await db.execute(select(WorkflowModel).where(WorkflowModel.id == workflow_id))
    wf = result.scalar_one_or_none()
    if not wf:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id} not found")

    run = WorkflowRunModel(
        workflow_id=workflow_id,
        status="running",
        state={"input": request.input, "current_node": None, "logs": []},
        node_results={},
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()

    # Start async execution
    asyncio.create_task(_execute_workflow_async(run.id, wf.dag_definition, request.input))

    return ok({
        "run_id": run.id,
        "workflow_id": workflow_id,
        "status": "running",
    })


@router.get("/runs/{run_id}")
async def get_workflow_run(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await db.execute(select(WorkflowRunModel).where(WorkflowRunModel.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Workflow run {run_id} not found")
    return ok(_run_to_api(run))


@router.get("/{workflow_id}/runs")
async def list_workflow_runs(
    workflow_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await db.execute(
        select(WorkflowRunModel)
        .where(WorkflowRunModel.workflow_id == workflow_id)
        .order_by(WorkflowRunModel.created_at.desc())
        .limit(limit)
    )
    return ok([_run_to_api(run) for run in result.scalars().all()])


@router.post("/runs/{run_id}/cancel")
async def cancel_workflow_run(
    run_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    result = await db.execute(select(WorkflowRunModel).where(WorkflowRunModel.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail=f"Workflow run {run_id} not found")
    if run.status != "running":
        raise HTTPException(status_code=400, detail="Run is not running")
    run.status = "cancelled"
    run.completed_at = datetime.now(timezone.utc)
    await db.flush()
    _broadcast(run_id, {"type": "status", "status": "cancelled"})
    return ok({"status": "cancelled"})


# ---------------------------------------------------------------------------
# Async workflow execution (simulated DAG with real LLM calls)
# ---------------------------------------------------------------------------

async def _execute_workflow_async(
    run_id: str,
    dag: dict[str, Any],
    input_data: dict[str, Any],
) -> None:
    """Execute workflow nodes in topological order with SSE broadcasting."""
    from dependencies import get_session_factory

    nodes = dag.get("nodes", [])
    node_map: dict[str, dict] = {n["id"]: n for n in nodes}

    # Build adjacency
    in_degree: dict[str, int] = {n["id"]: 0 for n in nodes}
    children: dict[str, list[str]] = {n["id"]: [] for n in nodes}
    for n in nodes:
        for dep in n.get("dependencies", []):
            children[dep].append(n["id"])
            in_degree[n["id"]] += 1

    # Topological execution
    queue = [nid for nid, deg in in_degree.items() if deg == 0]
    completed: set[str] = set()
    context: dict[str, Any] = dict(input_data)
    node_results: dict[str, Any] = {}
    logs: list[dict] = []

    _run_event_queues.setdefault(run_id, [])

    def _log(msg: str, level: str = "info", node_id: str | None = None) -> None:
        entry = {"time": datetime.now(timezone.utc).isoformat(), "message": msg, "level": level, "node_id": node_id}
        logs.append(entry)
        _broadcast(run_id, {"type": "log", **entry})

    _log(f"工作流开始执行 (run_id={run_id})")

    while queue:
        # Execute all nodes at current level in parallel
        level_nodes = list(queue)
        queue = []

        tasks = [_execute_node(run_id, node_map[nid], context, _log) for nid in level_nodes]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for nid, result in zip(level_nodes, results):
            if isinstance(result, Exception):
                node_results[nid] = {"status": "failed", "error": str(result)}
                _log(f"节点 {node_map[nid]['name']} 执行失败: {result}", "error", nid)
                _broadcast(run_id, {"type": "node_result", "node_id": nid, "status": "failed", "error": str(result)})
                # Mark run as failed
                await _finalize_run(run_id, "failed", node_results, logs, str(result))
                return
            else:
                node_results[nid] = result
                context[f"node_{nid}_output"] = result.get("output")
                _broadcast(run_id, {"type": "node_result", "node_id": nid, **result})

                # Check condition branching
                node_def = node_map[nid]
                if node_def["type"] == "condition" and result.get("output"):
                    cond = result["output"]
                    if isinstance(cond, dict) and "condition_result" in cond:
                        branch = "true_branch" if cond["condition_result"] else "false_branch"
                        skip_branch = "false_branch" if cond["condition_result"] else "true_branch"
                        skip_node = node_def.get("config", {}).get(skip_branch)
                        if skip_node and skip_node in node_map:
                            node_results[skip_node] = {"status": "skipped", "output": None}
                            completed.add(skip_node)
                            _broadcast(run_id, {"type": "node_result", "node_id": skip_node, "status": "skipped"})

                completed.add(nid)

            # Unblock dependents
            for child_id in children[nid]:
                in_degree[child_id] -= 1
                if in_degree[child_id] == 0 and child_id not in completed:
                    queue.append(child_id)

    _log("工作流执行完成")
    await _finalize_run(run_id, "completed", node_results, logs, None)


async def _execute_node(
    run_id: str,
    node: dict[str, Any],
    context: dict[str, Any],
    log_fn: Any,
) -> dict[str, Any]:
    """Execute a single workflow node."""
    node_id = node["id"]
    node_name = node["name"]
    node_type = node["type"]
    config = node.get("config", {})

    _broadcast(run_id, {"type": "node_start", "node_id": node_id, "name": node_name})
    log_fn(f"开始执行: {node_name}", node_id=node_id)
    started = time.perf_counter()

    if node_type == "start":
        result = {"status": "completed", "output": context.get("input", {}), "duration_ms": 0}
    elif node_type == "end":
        result = {"status": "completed", "output": context, "duration_ms": 0}
    elif node_type == "task":
        task_type = config.get("type", "function")
        if task_type == "llm":
            result = await _execute_llm_node(node, config, context, log_fn)
        elif task_type == "tool":
            result = await _execute_tool_node(node, config, context, log_fn)
        elif task_type == "function":
            result = await _execute_function_node(node, config, context, log_fn)
        else:
            result = {"status": "completed", "output": f"[{node_name}] executed", "duration_ms": 0}
    elif node_type == "condition":
        result = await _execute_condition_node(node, config, context, log_fn)
    else:
        result = {"status": "completed", "output": None, "duration_ms": 0}

    result["duration_ms"] = int((time.perf_counter() - started) * 1000)
    log_fn(f"完成: {node_name} ({result['duration_ms']}ms)", node_id=node_id)
    _broadcast(run_id, {"type": "node_complete", "node_id": node_id, "name": node_name, **result})
    return result


async def _execute_llm_node(
    node: dict[str, Any],
    config: dict[str, Any],
    context: dict[str, Any],
    log_fn: Any,
) -> dict[str, Any]:
    """Execute an LLM-powered node."""
    from config import get_app_settings
    from quant_os_infra_agent.llm.base import LLMConfig, Message, MessageRole
    from quant_os_infra_agent.llm.factory import LLMProviderFactory

    settings = get_app_settings()
    provider_name = settings.llm.default_provider
    provider = LLMProviderFactory.create(provider_name)

    system_prompt = config.get("prompt", "你是一个量化研究助手。")
    # Build context summary with real data (allow sufficient context for analysis)
    context_summary = json.dumps({k: v for k, v in context.items() if k not in ("input", "user_message")}, ensure_ascii=False, indent=2)
    # Truncate only if extremely large (80K chars max)
    if len(context_summary) > 80000:
        context_summary = context_summary[:80000] + "\n...(数据截断)"

    # Include user's specific question so LLM focuses on what they asked
    user_question = context.get("user_message", "")
    question_line = f"\n\n【用户具体问题】{user_question}\n请重点围绕用户的问题进行分析，不要泛泛而谈。" if user_question else ""

    user_msg = f"以下是真实的市场数据上下文（来自数据库）:\n{context_summary}\n\n请执行: {system_prompt}{question_line}\n\n要求：基于以上真实数据分析，给出有数据支撑的结论，不要编造数据。如果某些数据缺失，请如实说明，不要杜撰。"

    messages = [
        Message(role=MessageRole.SYSTEM, content="你是一个专业的A股量化研究AI分析师。请基于提供的真实市场数据进行分析，用数据说话，给出清晰的结论和可操作的建议。不要编造数据，只使用上下文中提供的数据。"),
        Message(role=MessageRole.USER, content=user_msg),
    ]

    log_fn(f"LLM调用: {provider_name}/{settings.llm.mimo_model}", node_id=node["id"])

    try:
        # Use fewer tokens for analysis nodes, more for report synthesis
        is_report = "report" in node["id"]
        max_tokens = 5000 if is_report else 3000
        response = await provider.chat(
            messages,
            config=LLMConfig(
                model=settings.llm.mimo_model,
                temperature=0.3,
                max_tokens=max_tokens,
            ),
        )
        tokens = response.usage.total_tokens if response.usage else 0
        log_fn(f"LLM响应: {tokens} tokens", node_id=node["id"])
        return {
            "status": "completed",
            "output": response.content,
            "model": response.model,
            "provider": provider_name,
            "tokens": tokens,
        }
    except Exception as e:
        log_fn(f"LLM调用失败: {e}", "error", node["id"])
        return {"status": "failed", "error": str(e)}


async def _execute_tool_node(
    node: dict[str, Any],
    config: dict[str, Any],
    context: dict[str, Any],
    log_fn: Any,
) -> dict[str, Any]:
    """Execute a tool-powered node with real data from database."""
    tool_name = config.get("tool", "unknown")
    log_fn(f"工具调用: {tool_name}", node_id=node["id"])

    # Resolve parameters from context
    params = {}
    for k, v in config.get("parameters", {}).items():
        if isinstance(v, str) and v.startswith("$"):
            params[k] = context.get(v[1:])
        else:
            params[k] = v

    try:
        from dependencies import get_session_factory
        from quant_os_infra_market.data_service import DataService
        from quant_os_infra_market.providers import ProviderFactory

        factory = get_session_factory()
        async with factory() as session:
            provider = ProviderFactory.get("akshare")
            ds = DataService(session, provider)

            if tool_name == "sync_all_market_data":
                # Read all data from database (pre-synced by scheduled sync job)
                from sqlalchemy import select, func as sqlfunc, desc as sql_desc, case, and_
                from quant_os_infra_market.models.stock_model import StockModel
                from quant_os_infra_market.models.northbound_model import NorthboundFlowModel
                from quant_os_infra_market.models.dragon_tiger_model import DragonTigerModel
                from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

                result_data = {}

                # Stock count
                total = (await session.execute(select(sqlfunc.count()).select_from(StockModel))).scalar() or 0
                result_data["stocks_count"] = total
                log_fn(f"数据库: {total} 只股票", node_id=node["id"])

                # --- Market Indices (parallel fetch) ---
                try:
                    import akshare as ak
                    loop = asyncio.get_event_loop()
                    indices = {
                        "上证指数": "sh000001",
                        "深证成指": "sz399001",
                        "沪深300": "sh000300",
                        "创业板指": "sz399006",
                        "科创50": "sh000688",
                    }
                    start_date = (datetime.now().date() - timedelta(days=10)).strftime("%Y%m%d")

                    async def _fetch_index(name: str, symbol: str):
                        try:
                            df = await loop.run_in_executor(None, lambda s=symbol: ak.stock_zh_index_daily_em(symbol=s, start_date=start_date))
                            if not df.empty:
                                latest = df.iloc[-1]
                                prev = df.iloc[-2] if len(df) > 1 else latest
                                pct = round((float(latest["close"]) - float(prev["close"])) / float(prev["close"]) * 100, 2) if float(prev["close"]) > 0 else 0
                                return name, {
                                    "close": round(float(latest["close"]), 2),
                                    "pct_chg": pct,
                                    "volume_billion": round(float(latest["volume"]) / 1e8, 2),
                                    "amount_billion": round(float(latest["amount"]) / 1e8, 2),
                                    "date": str(latest["date"]),
                                }
                        except Exception:
                            pass
                        return name, None

                    index_results = await asyncio.gather(*[_fetch_index(n, s) for n, s in indices.items()])
                    index_data = {name: data for name, data in index_results if data}
                    if index_data:
                        result_data["market_indices"] = index_data
                        log_fn(f"指数数据: {len(index_data)} 个指数", node_id=node["id"])
                except Exception as e:
                    log_fn(f"指数数据获取失败: {e}", "warning", node_id=node["id"])

                # --- Limit Up/Down Pool ---
                try:
                    import akshare as ak
                    loop = asyncio.get_event_loop()
                    zt_df = await loop.run_in_executor(None, lambda: ak.stock_zt_pool_em(date=datetime.now().strftime("%Y%m%d")))
                    if not zt_df.empty:
                        zt_records = []
                        for _, row in zt_df.head(20).iterrows():
                            cols = list(zt_df.columns)
                            zt_records.append({
                                "name": str(row.iloc[2]) if len(cols) > 2 else "",
                                "code": str(row.iloc[1]) if len(cols) > 1 else "",
                                "pct_chg": round(float(row.iloc[3]), 2) if len(cols) > 3 else 0,
                                "price": float(row.iloc[4]) if len(cols) > 4 else 0,
                                "amount_billion": round(float(row.iloc[5]) / 1e8, 2) if len(cols) > 5 else 0,
                                "turnover": round(float(row.iloc[8]), 2) if len(cols) > 8 else 0,
                                "seal_money_billion": round(float(row.iloc[9]) / 1e8, 2) if len(cols) > 9 else 0,
                                "first_seal_time": str(row.iloc[10]) if len(cols) > 10 else "",
                                "last_seal_time": str(row.iloc[11]) if len(cols) > 11 else "",
                                "explosion_count": int(row.iloc[12]) if len(cols) > 12 else 0,
                                "limit_stats": str(row.iloc[13]) if len(cols) > 13 else "",
                                "consecutive": int(row.iloc[14]) if len(cols) > 14 else 1,
                                "industry": str(row.iloc[15]) if len(cols) > 15 else "",
                            })
                        result_data["limit_up_pool"] = zt_records
                        # Count by industry
                        from collections import Counter
                        ind_counts = Counter(r["industry"] for r in zt_records if r["industry"])
                        result_data["limit_up_industries"] = [{"name": k, "count": v} for k, v in ind_counts.most_common(10)]
                        log_fn(f"涨停池: {len(zt_records)} 只", node_id=node["id"])
                except Exception as e:
                    log_fn(f"涨停池获取失败: {e}", "warning", node_id=node["id"])

                # --- OHLCV Market Statistics ---
                ohlcv_count = (await session.execute(select(sqlfunc.count()).select_from(OHLCVDailyModel))).scalar() or 0
                if ohlcv_count > 0:
                    # Get the date with the most records (not just the latest)
                    latest_date = (await session.execute(
                        select(OHLCVDailyModel.trade_date)
                        .group_by(OHLCVDailyModel.trade_date)
                        .order_by(sqlfunc.count().desc())
                        .limit(1)
                    )).scalar_one_or_none()

                    if latest_date:
                        # Market-wide stats for latest date
                        stats_row = (await session.execute(
                            select(
                                sqlfunc.count().label("total"),
                                sqlfunc.sum(case((OHLCVDailyModel.pct_chg > 0, 1), else_=0)).label("up_count"),
                                sqlfunc.sum(case((OHLCVDailyModel.pct_chg < 0, 1), else_=0)).label("down_count"),
                                sqlfunc.sum(case((OHLCVDailyModel.pct_chg == 0, 1), else_=0)).label("flat_count"),
                                sqlfunc.sum(case((OHLCVDailyModel.pct_chg >= 9.9, 1), else_=0)).label("limit_up"),
                                sqlfunc.sum(case((OHLCVDailyModel.pct_chg <= -9.9, 1), else_=0)).label("limit_down"),
                                sqlfunc.sum(OHLCVDailyModel.volume).label("total_volume"),
                                sqlfunc.sum(OHLCVDailyModel.amount).label("total_amount"),
                                sqlfunc.avg(OHLCVDailyModel.pct_chg).label("avg_pct_chg"),
                                sqlfunc.max(OHLCVDailyModel.pct_chg).label("max_pct_chg"),
                                sqlfunc.min(OHLCVDailyModel.pct_chg).label("min_pct_chg"),
                            ).where(OHLCVDailyModel.trade_date == latest_date)
                        )).one()

                        result_data["market_overview"] = {
                            "trade_date": str(latest_date),
                            "total_stocks": int(stats_row.total or 0),
                            "up_count": int(stats_row.up_count or 0),
                            "down_count": int(stats_row.down_count or 0),
                            "flat_count": int(stats_row.flat_count or 0),
                            "limit_up_count": int(stats_row.limit_up or 0),
                            "limit_down_count": int(stats_row.limit_down or 0),
                            "total_volume_billion": round(float(stats_row.total_volume or 0) / 1e8, 2),
                            "total_amount_billion": round(float(stats_row.total_amount or 0) / 1e8, 2),
                            "avg_pct_chg": round(float(stats_row.avg_pct_chg or 0), 2),
                            "max_pct_chg": round(float(stats_row.max_pct_chg or 0), 2),
                            "min_pct_chg": round(float(stats_row.min_pct_chg or 0), 2),
                        }
                        log_fn(f"市场概况: {stats_row.total}只股票, 涨{stats_row.up_count}/跌{stats_row.down_count}, 涨停{stats_row.limit_up}/跌停{stats_row.limit_down}", node_id=node["id"])

                        # Top gainers (top 15)
                        top_gainers = await session.execute(
                            select(OHLCVDailyModel.ts_code, OHLCVDailyModel.close, OHLCVDailyModel.pct_chg, OHLCVDailyModel.volume, OHLCVDailyModel.amount)
                            .where(OHLCVDailyModel.trade_date == latest_date)
                            .order_by(sql_desc(OHLCVDailyModel.pct_chg))
                            .limit(15)
                        )
                        result_data["top_gainers"] = [
                            {"ts_code": r[0], "close": float(r[1]), "pct_chg": float(r[2]), "volume": float(r[3]), "amount": float(r[4] or 0)}
                            for r in top_gainers.all()
                        ]

                        # Top losers (top 15)
                        top_losers = await session.execute(
                            select(OHLCVDailyModel.ts_code, OHLCVDailyModel.close, OHLCVDailyModel.pct_chg, OHLCVDailyModel.volume, OHLCVDailyModel.amount)
                            .where(OHLCVDailyModel.trade_date == latest_date)
                            .order_by(OHLCVDailyModel.pct_chg)
                            .limit(15)
                        )
                        result_data["top_losers"] = [
                            {"ts_code": r[0], "close": float(r[1]), "pct_chg": float(r[2]), "volume": float(r[3]), "amount": float(r[4] or 0)}
                            for r in top_losers.all()
                        ]

                        # Top volume (top 15)
                        top_vol = await session.execute(
                            select(OHLCVDailyModel.ts_code, OHLCVDailyModel.close, OHLCVDailyModel.pct_chg, OHLCVDailyModel.volume, OHLCVDailyModel.amount)
                            .where(OHLCVDailyModel.trade_date == latest_date)
                            .order_by(sql_desc(OHLCVDailyModel.volume))
                            .limit(15)
                        )
                        result_data["top_volume"] = [
                            {"ts_code": r[0], "close": float(r[1]), "pct_chg": float(r[2]), "volume": float(r[3]), "amount": float(r[4] or 0)}
                            for r in top_vol.all()
                        ]
                else:
                    result_data["market_overview"] = {"error": "无行情数据，请先执行数据同步"}
                    log_fn("OHLCV: 无数据", "warning", node_id=node["id"])

                # --- Dragon Tiger ---
                dt_count = (await session.execute(select(sqlfunc.count()).select_from(DragonTigerModel))).scalar() or 0
                if dt_count > 0:
                    latest_dt = await session.execute(
                        select(DragonTigerModel)
                        .order_by(DragonTigerModel.trade_date.desc())
                        .limit(20)
                    )
                    result_data["dragon_tiger_entries"] = [
                        {
                            "name": getattr(r, "name", None) or r.ts_code,
                            "ts_code": r.ts_code,
                            "reason": r.reason,
                            "buy_amount": float(r.buy_amount or 0),
                            "sell_amount": float(r.sell_amount or 0),
                            "net_amount": float(r.net_amount or 0),
                            "date": str(r.trade_date),
                        }
                        for r in latest_dt.scalars()
                    ]
                    log_fn(f"龙虎榜: {dt_count} 条记录", node_id=node["id"])
                else:
                    result_data["dragon_tiger_entries"] = []
                    log_fn("龙虎榜: 无数据", "warning", node_id=node["id"])

                result_data["data_source"] = "database"
                result_data["last_update"] = datetime.now().isoformat()

                output = result_data

            elif tool_name in ("fetch_market_data", "fetch_market_overview"):
                # Read from pre-synced database
                from sqlalchemy import select, func as sqlfunc, desc as sql_desc
                from quant_os_infra_market.models.stock_model import StockModel
                from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

                total = (await session.execute(select(sqlfunc.count()).select_from(StockModel))).scalar() or 0
                ohlcv_count = (await session.execute(select(sqlfunc.count()).select_from(OHLCVDailyModel))).scalar() or 0

                latest_prices = []
                if ohlcv_count > 0:
                    latest_bars = await session.execute(
                        select(OHLCVDailyModel).order_by(sql_desc(OHLCVDailyModel.trade_date)).limit(5)
                    )
                    for bar in latest_bars.scalars():
                        latest_prices.append({
                            "ts_code": bar.ts_code, "date": str(bar.trade_date),
                            "close": float(bar.close), "volume": float(bar.volume),
                        })

                industry_result = await session.execute(
                    select(StockModel.industry, sqlfunc.count().label("cnt"))
                    .where(StockModel.industry.isnot(None))
                    .group_by(StockModel.industry).order_by(sqlfunc.count().desc()).limit(10)
                )
                industries = [{"name": r[0], "count": r[1]} for r in industry_result.all()]

                output = {
                    "stocks_count": total, "ohlcv_records": ohlcv_count,
                    "data_source": "database", "last_update": datetime.now().isoformat(),
                    "latest_prices": latest_prices, "top_industries": industries,
                }

            elif tool_name == "fetch_northbound":
                from sqlalchemy import select, func as sqlfunc
                from quant_os_infra_market.models.northbound_model import NorthboundFlowModel
                count = (await session.execute(select(sqlfunc.count()).select_from(NorthboundFlowModel))).scalar() or 0
                if count > 0:
                    latest = await session.execute(
                        select(NorthboundFlowModel).order_by(NorthboundFlowModel.trade_date.desc()).limit(10)
                    )
                    flows = [{"date": str(r.trade_date), "net_flow_billion": round(float(r.net_amount or 0) / 1e8, 2)} for r in latest.scalars()]
                    output = {"records": count, "recent_flows": flows}
                else:
                    output = {"records": 0, "message": "北向资金数据为空，请先通过数据同步功能获取"}

            elif tool_name == "fetch_dragon_tiger":
                from sqlalchemy import select, func as sqlfunc
                from quant_os_infra_market.models.dragon_tiger_model import DragonTigerModel
                count = (await session.execute(select(sqlfunc.count()).select_from(DragonTigerModel))).scalar() or 0
                if count > 0:
                    latest = await session.execute(
                        select(DragonTigerModel).order_by(DragonTigerModel.trade_date.desc()).limit(10)
                    )
                    entries = [{"name": getattr(r, "name", None) or r.ts_code, "reason": r.reason, "date": str(r.trade_date)} for r in latest.scalars()]
                    output = {"records": count, "recent_entries": entries}
                else:
                    output = {"records": 0, "message": "龙虎榜数据为空，请先通过数据同步功能获取"}

            elif tool_name == "compute_factor":
                output = {"status": "pending", "message": "因子计算需要完整的OHLCV历史数据，请先同步数据"}
            elif tool_name == "analyze_ic":
                output = {"status": "pending", "message": "IC分析需要因子值和收益率数据，请先完成因子计算"}
            elif tool_name == "run_backtest":
                output = {"status": "pending", "message": "回测需要因子信号和历史行情数据，请先完成因子分析"}
            elif tool_name == "analyze_risk":
                output = {"status": "pending", "message": "风险分析需要回测结果，请先完成回测"}
            elif tool_name == "list_factors":
                output = {"status": "pending", "message": "因子列表需要因子库支持"}
            elif tool_name == "analyze_correlation":
                output = {"status": "pending", "message": "相关性分析需要多个因子数据"}
            elif tool_name == "combine_factors":
                output = {"status": "pending", "message": "因子合成需要因子IC数据"}
            elif tool_name == "optimize_portfolio":
                output = {"status": "pending", "message": "组合优化需要因子权重和约束条件"}
            else:
                output = {"tool": tool_name, "status": "executed", "params": params}

            await session.commit()

        return {"status": "completed", "output": output, "tool": tool_name}
    except Exception as e:
        log_fn(f"工具执行失败: {e}", "error", node["id"])
        return {"status": "failed", "error": str(e), "tool": tool_name}


async def _execute_function_node(
    node: dict[str, Any],
    config: dict[str, Any],
    context: dict[str, Any],
    log_fn: Any,
) -> dict[str, Any]:
    """Execute a function node."""
    func_path = config.get("function", "")
    log_fn(f"函数调用: {func_path}", node_id=node["id"])
    return {"status": "completed", "output": f"Function {func_path} executed", "function": func_path}


async def _execute_condition_node(
    node: dict[str, Any],
    config: dict[str, Any],
    context: dict[str, Any],
    log_fn: Any,
) -> dict[str, Any]:
    """Execute a condition node."""
    condition_type = config.get("type", "expression")

    if condition_type == "threshold":
        value_key = config.get("value", "")
        threshold = config.get("threshold", 0)
        operator = config.get("operator", ">")
        value = context.get(value_key, 0)

        ops = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}
        result = ops.get(operator, lambda a, b: False)(float(value), float(threshold))

        log_fn(f"条件判断: {value_key}={value} {operator} {threshold} → {result}", node_id=node["id"])
        return {
            "status": "completed",
            "output": {"condition_result": result, "value": value, "threshold": threshold, "operator": operator},
        }
    elif condition_type == "expression":
        expression = config.get("expression", "True")
        try:
            eval_ctx = {"context": context, "result": None}
            exec(f"result = {expression}", eval_ctx)
            result = bool(eval_ctx["result"])
        except Exception:
            result = False
        return {"status": "completed", "output": {"condition_result": result}}
    else:
        return {"status": "completed", "output": {"condition_result": True}}


async def _finalize_run(
    run_id: str,
    status: str,
    node_results: dict[str, Any],
    logs: list[dict],
    error: str | None,
) -> None:
    """Persist final run state to database."""
    from dependencies import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(select(WorkflowRunModel).where(WorkflowRunModel.id == run_id))
        run = result.scalar_one_or_none()
        if run:
            run.status = status
            run.node_results = node_results
            run.state = {"logs": logs, "error": error}
            run.completed_at = datetime.now(timezone.utc)
            await session.commit()

    _broadcast(run_id, {"type": "status", "status": status, "error": error})

    # Broadcast final report content when workflow completes
    if status == "completed":
        report_output = None
        for nid, result in node_results.items():
            if "report" in nid:
                output_data = result.get("output", {})
                if isinstance(output_data, str):
                    report_output = output_data
                elif isinstance(output_data, dict):
                    report_output = output_data.get("output") or output_data.get("content") or str(output_data)
        if report_output:
            _broadcast(run_id, {"type": "report", "content": report_output})
