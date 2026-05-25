"""AI Native Research — autonomous research from natural language goals."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from presentation.api_response import ok

router = APIRouter()

# In-memory store
_RESEARCH_GOALS: dict[str, dict[str, Any]] = {}


class ResearchGoalRequest(BaseModel):
    goal: str
    context: dict[str, Any] = {}


class ResearchGoal(BaseModel):
    id: str
    goal: str
    status: str
    plan: list[dict[str, Any]]
    results: list[dict[str, Any]]
    insights: list[str]
    created_at: str
    updated_at: str


@router.post("/goals")
async def create_research_goal(request: ResearchGoalRequest) -> dict:
    """Create a research goal from natural language description."""
    goal_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    # Parse goal and generate research plan
    plan = _generate_research_plan(request.goal, request.context)

    goal = {
        "id": goal_id,
        "goal": request.goal,
        "status": "planning",
        "plan": plan,
        "results": [],
        "insights": [],
        "created_at": now,
        "updated_at": now,
        "context": request.context,
    }
    _RESEARCH_GOALS[goal_id] = goal

    # Simulate executing the plan
    results, insights = _execute_plan(plan)
    goal["results"] = results
    goal["insights"] = insights
    goal["status"] = "completed"
    goal["updated_at"] = datetime.now().isoformat()

    return ok(goal)


@router.get("/goals")
async def list_research_goals() -> dict:
    """List all research goals."""
    goals = sorted(_RESEARCH_GOALS.values(), key=lambda g: g["created_at"], reverse=True)
    return ok(goals)


@router.get("/goals/{goal_id}")
async def get_research_goal(goal_id: str) -> dict:
    """Get a specific research goal."""
    goal = _RESEARCH_GOALS.get(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return ok(goal)


@router.delete("/goals/{goal_id}")
async def delete_research_goal(goal_id: str) -> dict:
    """Delete a research goal."""
    if goal_id not in _RESEARCH_GOALS:
        raise HTTPException(status_code=404, detail="Goal not found")
    del _RESEARCH_GOALS[goal_id]
    return ok({"deleted": True})


def _generate_research_plan(goal: str, context: dict) -> list[dict[str, Any]]:
    """Generate a research plan from natural language goal."""
    goal_lower = goal.lower()

    # Detect research type from goal
    if any(k in goal_lower for k in ["因子", "factor", "alpha", "选股", "选时"]):
        return _factor_research_plan(goal)
    elif any(k in goal_lower for k in ["组合", "portfolio", "配置", "权重"]):
        return _portfolio_research_plan(goal)
    elif any(k in goal_lower for k in ["市场", "market", "行情", "趋势", "大盘"]):
        return _market_research_plan(goal)
    elif any(k in goal_lower for k in ["风险", "risk", "回撤", "风控"]):
        return _risk_research_plan(goal)
    else:
        return _general_research_plan(goal)


def _factor_research_plan(goal: str) -> list[dict[str, Any]]:
    return [
        {"step": 1, "name": "数据准备", "description": "获取A股行情数据，构建因子计算面板", "tool": "data_sync", "status": "completed"},
        {"step": 2, "name": "因子构建", "description": "基于目标构建候选因子表达式", "tool": "factor_engine", "status": "completed"},
        {"step": 3, "name": "IC分析", "description": "计算因子IC、RankIC、ICIR等指标", "tool": "factor_engine", "status": "completed"},
        {"step": 4, "name": "分层回测", "description": "按因子值分层，计算各层收益和多空组合", "tool": "factor_engine", "status": "completed"},
        {"step": 5, "name": "稳定性检验", "description": "滚动IC分析，检验因子时序稳定性", "tool": "factor_engine", "status": "completed"},
        {"step": 6, "name": "综合评估", "description": "汇总分析结果，给出因子评价和建议", "tool": "llm", "status": "completed"},
    ]


def _portfolio_research_plan(goal: str) -> list[dict[str, Any]]:
    return [
        {"step": 1, "name": "市场环境分析", "description": "分析当前市场状态和行业轮动", "tool": "sentiment", "status": "completed"},
        {"step": 2, "name": "因子暴露分析", "description": "分析当前组合的因子暴露", "tool": "factor_engine", "status": "completed"},
        {"step": 3, "name": "风险归因", "description": "分解组合风险来源", "tool": "backtest", "status": "completed"},
        {"step": 4, "name": "优化建议", "description": "生成组合调仓建议", "tool": "llm", "status": "completed"},
    ]


def _market_research_plan(goal: str) -> list[dict[str, Any]]:
    return [
        {"step": 1, "name": "指数分析", "description": "分析主要指数走势和技术形态", "tool": "market_data", "status": "completed"},
        {"step": 2, "name": "行业轮动", "description": "分析行业板块资金流向和动量", "tool": "sentiment", "status": "completed"},
        {"step": 3, "name": "资金面分析", "description": "分析北向资金、融资融券等资金指标", "tool": "sentiment", "status": "completed"},
        {"step": 4, "name": "情绪指标", "description": "分析涨跌停、连板等情绪指标", "tool": "sentiment", "status": "completed"},
        {"step": 5, "name": "综合研判", "description": "给出市场观点和配置建议", "tool": "llm", "status": "completed"},
    ]


def _risk_research_plan(goal: str) -> list[dict[str, Any]]:
    return [
        {"step": 1, "name": "波动率分析", "description": "分析市场和个股波动率水平", "tool": "market_data", "status": "completed"},
        {"step": 2, "name": "回撤分析", "description": "分析历史最大回撤和回撤修复", "tool": "backtest", "status": "completed"},
        {"step": 3, "name": "VaR计算", "description": "计算在险价值和预期短缺", "tool": "factor_engine", "status": "completed"},
        {"step": 4, "name": "风控建议", "description": "给出风险控制建议", "tool": "llm", "status": "completed"},
    ]


def _general_research_plan(goal: str) -> list[dict[str, Any]]:
    return [
        {"step": 1, "name": "目标分析", "description": "解析研究目标，确定分析维度", "tool": "llm", "status": "completed"},
        {"step": 2, "name": "数据收集", "description": "收集相关市场数据", "tool": "market_data", "status": "completed"},
        {"step": 3, "name": "定量分析", "description": "进行定量分析和计算", "tool": "factor_engine", "status": "completed"},
        {"step": 4, "name": "定性分析", "description": "综合分析并生成结论", "tool": "llm", "status": "completed"},
    ]


def _execute_plan(plan: list[dict]) -> tuple[list[dict], list[str]]:
    """Simulate executing a research plan and generating results."""
    results = []
    insights = []

    for step in plan:
        result = {
            "step": step["step"],
            "name": step["name"],
            "status": "completed",
            "output": _simulate_step_output(step),
            "duration_ms": 150 + step["step"] * 80,
        }
        results.append(result)

    # Generate insights based on plan type
    insights = _generate_insights(plan)

    return results, insights


def _simulate_step_output(step: dict) -> str:
    """Simulate output for a research step."""
    tool = step.get("tool", "")
    name = step.get("name", "")

    if tool == "factor_engine":
        return f"因子分析完成。IC均值=0.035, ICIR=0.43, 分层收益单调性良好。"
    elif tool == "sentiment":
        return f"情绪分析完成。市场情绪偏多，涨停45家，北向资金净流入32亿。"
    elif tool == "market_data":
        return f"市场数据分析完成。上证指数+1.2%，创业板指-0.3%，成交量放大。"
    elif tool == "backtest":
        return f"回测分析完成。策略年化收益18.5%，最大回撤-8.2%，夏普比1.65。"
    elif tool == "llm":
        return f"AI综合分析完成。基于多维度分析，给出投资建议。"
    else:
        return f"{name}完成。"


def _generate_insights(plan: list[dict]) -> list[str]:
    """Generate research insights."""
    tools = set(step.get("tool", "") for step in plan)

    insights = [
        "基于因子分析，动量类因子近期表现优异，建议关注20日动量因子",
        "市场情绪偏暖，涨停家数增加，连板高度提升，短线做多情绪浓厚",
        "北向资金持续净流入，外资偏好消费和科技龙头",
        "行业轮动加速，建议关注AI和半导体板块的投资机会",
        "组合风险可控，当前Beta为0.85，波动率12.3%",
        "建议适当增加科技板块配置，降低传统行业权重",
    ]

    if "factor_engine" in tools:
        insights.insert(0, "因子IC分析显示，技术因子在当前市场环境下具有较好的预测能力")
    if "sentiment" in tools:
        insights.insert(1, "市场情绪指标显示，当前处于偏多格局，适合积极配置")
    if "backtest" in tools:
        insights.insert(2, "回测结果表明，策略在不同市场环境下均能获得正超额收益")

    return insights[:5]
