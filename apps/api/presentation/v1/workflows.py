"""Workflow management and execution endpoints."""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timezone
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
                # Layer 0: 并行数据获取
                {"id": "data_fetch", "name": "数据获取与清洗", "type": "task", "config": {"type": "tool", "tool": "fetch_market_data"}, "dependencies": []},
                {"id": "market_overview", "name": "市场概况采集", "type": "task", "config": {"type": "tool", "tool": "fetch_market_overview"}, "dependencies": []},
                {"id": "northbound", "name": "北向资金采集", "type": "task", "config": {"type": "tool", "tool": "fetch_northbound"}, "dependencies": []},
                {"id": "sentiment_data", "name": "情绪数据采集", "type": "task", "config": {"type": "tool", "tool": "fetch_dragon_tiger"}, "dependencies": []},
                # Layer 1: 并行分析（依赖Layer 0）
                {"id": "factor_discovery", "name": "因子探索与发现", "type": "task", "config": {"type": "llm", "prompt": "基于市场数据上下文，发现并评估有潜力的Alpha因子，给出因子公式和逻辑解释"}, "dependencies": ["data_fetch"]},
                {"id": "sector_analysis", "name": "行业轮动分析", "type": "task", "config": {"type": "llm", "prompt": "分析行业轮动和板块动量，找出当前强势行业和潜在机会"}, "dependencies": ["market_overview", "northbound"]},
                {"id": "sentiment_calc", "name": "市场情绪研判", "type": "task", "config": {"type": "llm", "prompt": "综合分析市场情绪，包括涨跌停、北向资金、龙虎榜等多维度数据，给出情绪评分和趋势判断"}, "dependencies": ["market_overview", "northbound", "sentiment_data"]},
                # Layer 2: 因子分析（依赖Layer 1）
                {"id": "factor_analysis", "name": "因子IC分析", "type": "task", "config": {"type": "tool", "tool": "analyze_ic"}, "dependencies": ["factor_discovery"]},
                # Layer 3: 综合报告（依赖所有上游）
                {"id": "report_synthesis", "name": "综合研究报告", "type": "task", "config": {"type": "llm", "prompt": "基于以上所有分析结果，生成一份完整的A股市场综合研究报告。报告格式要求：\n\n## 今日A股市场综合研究报告\n\n### 一、市场概况\n简述当前市场整体情况（基于真实股票数据）\n\n### 二、行业轮动分析\n分析哪些行业表现强势，哪些行业在走弱\n\n### 三、因子发现\n推荐有潜力的量化因子及其逻辑\n\n### 四、市场情绪研判\n当前市场情绪是偏多还是偏空，依据是什么\n\n### 五、综合结论\n用通俗易懂的语言总结今日市场状况\n\n### 六、投资建议\n给出具体可操作的建议（如关注哪些板块、注意什么风险）\n\n注意：用通俗易懂的语言，避免过多专业术语，让普通投资者也能看懂。基于真实数据分析，不要编造数据。"}, "dependencies": ["factor_analysis", "sector_analysis", "sentiment_calc"]},
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
    # Build context summary with real data (allow more context for comprehensive reports)
    context_summary = json.dumps({k: str(v)[:2000] for k, v in context.items()}, ensure_ascii=False, indent=2)
    user_msg = f"以下是真实的市场数据上下文:\n{context_summary}\n\n请执行: {system_prompt}\n\n要求：基于以上真实数据分析，给出有数据支撑的结论，不要编造数据。如果某些数据缺失，请如实说明，不要杜撰。"

    messages = [
        Message(role=MessageRole.SYSTEM, content="你是一个专业的A股量化研究AI分析师。请基于提供的真实市场数据进行分析，用数据说话，给出清晰的结论和可操作的建议。不要编造数据，只使用上下文中提供的数据。"),
        Message(role=MessageRole.USER, content=user_msg),
    ]

    log_fn(f"LLM调用: {provider_name}/{settings.llm.mimo_model}", node_id=node["id"])

    try:
        response = await provider.chat(
            messages,
            config=LLMConfig(
                model=settings.llm.mimo_model,
                temperature=0.3,
                max_tokens=5000,
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

            if tool_name in ("fetch_market_data", "fetch_market_overview"):
                from sqlalchemy import select, func as sqlfunc
                from quant_os_infra_market.models.stock_model import StockModel
                from quant_os_infra_market.models.ohlcv_model import OHLCVDailyModel

                # Get stock counts from DB
                total_result = await session.execute(select(sqlfunc.count()).select_from(StockModel))
                total = total_result.scalar() or 0

                # If no stocks, trigger sync
                if total == 0:
                    log_fn("股票列表为空，正在自动同步...", node_id=node["id"])
                    from quant_os_app_market.services.data_ingestion import DataIngestionService
                    ingestion = DataIngestionService(session, provider)
                    sync_result = await ingestion.sync_stock_list()
                    total = sync_result.get("total", 0)
                    await session.commit()

                # Fetch live market snapshot from AKShare
                live_snapshot = []
                industry_counts = {}
                market_stats = {}
                try:
                    import akshare as ak
                    import pandas as _pd
                    import asyncio as _aio

                    # Add delay to avoid rate limiting when running in parallel with other nodes
                    await _aio.sleep(3)

                    log_fn("正在获取实时行情快照...", node_id=node["id"])
                    df_spot = await provider._run_with_retry(ak.stock_zh_a_spot_em)

                    if not df_spot.empty:
                        log_fn(f"实时快照获取成功: {len(df_spot)} 只股票", node_id=node["id"])

                        # Build industry distribution
                        for col_name in ["板块", "所属行业", "行业"]:
                            if col_name in df_spot.columns:
                                ind_counts = df_spot[col_name].value_counts().head(15)
                                industry_counts = {str(k): int(v) for k, v in ind_counts.items()}
                                break

                        # Get top gainers and losers
                        if "涨跌幅" in df_spot.columns:
                            df_spot["涨跌幅"] = _pd.to_numeric(df_spot["涨跌幅"], errors="coerce")
                            df_spot["最新价"] = _pd.to_numeric(df_spot["最新价"], errors="coerce")
                            df_spot["成交额"] = _pd.to_numeric(df_spot["成交额"], errors="coerce")

                            valid = df_spot.dropna(subset=["涨跌幅"])

                            # Top 5 gainers
                            top_gain = valid.nlargest(5, "涨跌幅")
                            for _, row in top_gain.iterrows():
                                live_snapshot.append({
                                    "code": str(row.get("代码", "")),
                                    "name": str(row.get("名称", "")),
                                    "price": float(row["最新价"]) if _pd.notna(row["最新价"]) else None,
                                    "change_pct": round(float(row["涨跌幅"]), 2) if _pd.notna(row["涨跌幅"]) else None,
                                    "type": "gainer",
                                })

                            # Top 5 losers
                            top_lose = valid.nsmallest(5, "涨跌幅")
                            for _, row in top_lose.iterrows():
                                live_snapshot.append({
                                    "code": str(row.get("代码", "")),
                                    "name": str(row.get("名称", "")),
                                    "price": float(row["最新价"]) if _pd.notna(row["最新价"]) else None,
                                    "change_pct": round(float(row["涨跌幅"]), 2) if _pd.notna(row["涨跌幅"]) else None,
                                    "type": "loser",
                                })

                            # Market statistics
                            up_count = int((valid["涨跌幅"] > 0).sum())
                            down_count = int((valid["涨跌幅"] < 0).sum())
                            flat_count = int((valid["涨跌幅"] == 0).sum())
                            limit_up = int((valid["涨跌幅"] >= 9.9).sum())
                            limit_down = int((valid["涨跌幅"] <= -9.9).sum())
                            total_amount = float(df_spot["成交额"].sum()) if "成交额" in df_spot.columns else 0

                            market_stats = {
                                "total_stocks": len(df_spot),
                                "up_count": up_count,
                                "down_count": down_count,
                                "flat_count": flat_count,
                                "limit_up": limit_up,
                                "limit_down": limit_down,
                                "total_amount_billion": round(total_amount / 1e8, 2),
                                "avg_change_pct": round(float(valid["涨跌幅"].mean()), 2),
                                "median_change_pct": round(float(valid["涨跌幅"].median()), 2),
                            }

                    log_fn(f"市场统计: {market_stats.get('up_count', 0)}涨 {market_stats.get('down_count', 0)}跌 {market_stats.get('limit_up', 0)}涨停 {market_stats.get('limit_down', 0)}跌停", node_id=node["id"])

                except Exception as snap_err:
                    log_fn(f"实时快照获取失败: {snap_err}", "warning", node["id"])

                # Also get OHLCV count from DB
                ohlcv_result = await session.execute(select(sqlfunc.count()).select_from(OHLCVDailyModel))
                ohlcv_count = ohlcv_result.scalar() or 0

                # Get latest OHLCV data from DB for additional context
                latest_prices = []
                if ohlcv_count > 0:
                    from sqlalchemy import desc
                    latest_bars = await session.execute(
                        select(OHLCVDailyModel).order_by(desc(OHLCVDailyModel.trade_date)).limit(5)
                    )
                    for bar in latest_bars.scalars():
                        latest_prices.append({
                            "ts_code": bar.ts_code,
                            "date": str(bar.trade_date),
                            "close": float(bar.close),
                            "volume": float(bar.volume),
                        })

                # Get sample stocks
                stocks = await ds.list_stocks(page=1, size=5)
                sample = stocks.get("items", [])[:5]

                # Build industry list from snapshot or DB
                industries = []
                if industry_counts:
                    industries = [{"name": k, "count": v} for k, v in industry_counts.items()]
                else:
                    # Fallback: query DB
                    from sqlalchemy import desc as sql_desc
                    industry_result = await session.execute(
                        select(StockModel.industry, sqlfunc.count().label("cnt"))
                        .where(StockModel.industry.isnot(None))
                        .group_by(StockModel.industry)
                        .order_by(sqlfunc.count().desc())
                        .limit(10)
                    )
                    industries = [{"name": r[0], "count": r[1]} for r in industry_result.all()]

                output = {
                    "stocks_count": total,
                    "ohlcv_records": ohlcv_count,
                    "data_source": "akshare",
                    "last_update": datetime.now().isoformat(),
                    "market_stats": market_stats,
                    "top_movers": live_snapshot,
                    "sample_stocks": [{"name": s.get("name"), "code": s.get("ts_code")} for s in sample],
                    "latest_prices": latest_prices,
                    "top_industries": industries,
                }

            elif tool_name == "fetch_northbound":
                import asyncio as _aio
                from sqlalchemy import select, func as sqlfunc
                from quant_os_infra_market.models.northbound_model import NorthboundFlowModel

                # Delay to avoid rate limiting with parallel nodes
                await _aio.sleep(5)

                result = await session.execute(select(sqlfunc.count()).select_from(NorthboundFlowModel))
                count = result.scalar() or 0

                # Try to sync if empty
                if count == 0:
                    log_fn("北向资金数据为空，正在自动同步...", node_id=node["id"])
                    try:
                        from quant_os_app_market.services.data_ingestion import DataIngestionService
                        ingestion = DataIngestionService(session, provider)
                        sync_result = await ingestion.sync_northbound_flow()
                        await session.commit()
                        # Re-check count
                        result = await session.execute(select(sqlfunc.count()).select_from(NorthboundFlowModel))
                        count = result.scalar() or 0
                    except Exception as sync_err:
                        log_fn(f"北向资金同步失败: {sync_err}", "warning", node["id"])

                if count > 0:
                    latest = await session.execute(
                        select(NorthboundFlowModel).order_by(NorthboundFlowModel.trade_date.desc()).limit(10)
                    )
                    flows = [{"date": str(r.trade_date), "net_flow": float(r.net_amount or 0)} for r in latest.scalars()]
                    output = {"records": count, "recent_flows": flows}
                else:
                    output = {"records": 0, "message": "北向资金数据同步失败，可能是AKShare API变更，请检查日志"}

            elif tool_name == "fetch_dragon_tiger":
                import asyncio as _aio
                from sqlalchemy import select, func as sqlfunc
                from quant_os_infra_market.models.dragon_tiger_model import DragonTigerModel

                # Delay to avoid rate limiting with parallel nodes
                await _aio.sleep(10)

                result = await session.execute(select(sqlfunc.count()).select_from(DragonTigerModel))
                count = result.scalar() or 0

                # Try to sync if empty
                if count == 0:
                    log_fn("龙虎榜数据为空，正在自动同步...", node_id=node["id"])
                    try:
                        from quant_os_app_market.services.data_ingestion import DataIngestionService
                        ingestion = DataIngestionService(session, provider)
                        sync_result = await ingestion.sync_dragon_tiger()
                        await session.commit()
                        result = await session.execute(select(sqlfunc.count()).select_from(DragonTigerModel))
                        count = result.scalar() or 0
                    except Exception as sync_err:
                        log_fn(f"龙虎榜同步失败: {sync_err}", "warning", node["id"])

                if count > 0:
                    latest = await session.execute(
                        select(DragonTigerModel).order_by(DragonTigerModel.trade_date.desc()).limit(10)
                    )
                    entries = [{"name": getattr(r, "name", None) or r.ts_code, "reason": r.reason, "date": str(r.trade_date)} for r in latest.scalars()]
                    output = {"records": count, "recent_entries": entries}
                else:
                    output = {"records": 0, "message": "龙虎榜数据同步失败，可能是AKShare API变更，请检查日志"}

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
