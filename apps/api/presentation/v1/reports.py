"""Research report endpoints — AI-generated markdown reports with templates."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from presentation.api_response import ok

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory report store (replace with DB later)
# ---------------------------------------------------------------------------
_REPORTS: dict[str, dict[str, Any]] = {}

# ---------------------------------------------------------------------------
# Report templates
# ---------------------------------------------------------------------------
REPORT_TEMPLATES = {
    "factor_analysis": {
        "name": "因子分析报告",
        "description": "对单个因子进行深度分析，包括IC分析、分层收益、稳定性评估",
        "sections": ["因子概述", "IC分析", "分层收益", "时序稳定性", "结论与建议"],
        "prompt": "请对因子 {factor_name} 进行深度分析。分析期间：{start_date} 至 {end_date}。请从IC表现、分层收益单调性、时序稳定性三个维度进行评估，并给出投资建议。",
    },
    "market_review": {
        "name": "市场回顾报告",
        "description": "对A股市场进行日度/周度回顾，涵盖指数表现、行业轮动、资金流向",
        "sections": ["市场概览", "指数表现", "行业轮动", "资金流向", "热点事件", "后市展望"],
        "prompt": "请对A股市场进行回顾分析。分析期间：{start_date} 至 {end_date}。请从指数表现、行业轮动、资金流向三个维度进行分析，并给出后市展望。",
    },
    "portfolio_review": {
        "name": "组合回顾报告",
        "description": "对投资组合进行业绩归因和风险分析",
        "sections": ["组合概况", "收益归因", "风险分析", "持仓分析", "调仓建议"],
        "prompt": "请对投资组合进行回顾分析。分析期间：{start_date} 至 {end_date}。请从收益归因、风险暴露、持仓结构三个维度进行分析，并给出调仓建议。",
    },
    "alpha_research": {
        "name": "Alpha策略研究",
        "description": "Alpha因子挖掘和策略构建研究报告",
        "sections": ["研究背景", "因子构建", "回测结果", "风险分析", "实盘建议"],
        "prompt": "请撰写一份Alpha策略研究报告。研究主题：{topic}。分析期间：{start_date} 至 {end_date}。请从因子构建逻辑、回测表现、风险特征三个维度进行分析。",
    },
}


class GenerateReportRequest(BaseModel):
    template: str = "market_review"
    title: str | None = None
    params: dict[str, Any] = {}


class ReportResponse(BaseModel):
    id: str
    title: str
    template: str
    template_name: str
    status: str
    content: str | None = None
    sections: list[str] = []
    params: dict[str, Any] = {}
    created_at: str
    updated_at: str


@router.get("/templates")
async def list_report_templates() -> dict:
    """List available report templates."""
    templates = [
        {
            "id": tid,
            "name": t["name"],
            "description": t["description"],
            "sections": t["sections"],
        }
        for tid, t in REPORT_TEMPLATES.items()
    ]
    return ok(templates)


@router.get("")
async def list_reports() -> dict:
    """List all generated reports."""
    reports = sorted(_REPORTS.values(), key=lambda r: r["created_at"], reverse=True)
    return ok(reports)


@router.get("/{report_id}")
async def get_report(report_id: str) -> dict:
    """Get a specific report."""
    report = _REPORTS.get(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return ok(report)


@router.post("")
async def generate_report(request: GenerateReportRequest) -> dict:
    """Generate a new research report using AI."""
    template = REPORT_TEMPLATES.get(request.template)
    if not template:
        raise HTTPException(status_code=400, detail=f"Unknown template: {request.template}")

    report_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()

    title = request.title or f"{template['name']} - {datetime.now().strftime('%Y-%m-%d')}"

    report = {
        "id": report_id,
        "title": title,
        "template": request.template,
        "template_name": template["name"],
        "status": "generating",
        "content": None,
        "sections": template["sections"],
        "params": request.params,
        "created_at": now,
        "updated_at": now,
    }
    _REPORTS[report_id] = report

    # Generate report content (simulated for now)
    content = _generate_report_content(request.template, template, request.params)
    report["content"] = content
    report["status"] = "completed"
    report["updated_at"] = datetime.now().isoformat()

    return ok(report)


@router.delete("/{report_id}")
async def delete_report(report_id: str) -> dict:
    """Delete a report."""
    if report_id not in _REPORTS:
        raise HTTPException(status_code=404, detail="Report not found")
    del _REPORTS[report_id]
    return ok({"deleted": True})


def _generate_report_content(template_id: str, template: dict, params: dict) -> str:
    """Generate markdown report content."""
    now = datetime.now()
    start_date = params.get("start_date", "2026-01-01")
    end_date = params.get("end_date", now.strftime("%Y-%m-%d"))

    if template_id == "factor_analysis":
        return _gen_factor_report(params, start_date, end_date)
    elif template_id == "market_review":
        return _gen_market_report(params, start_date, end_date)
    elif template_id == "portfolio_review":
        return _gen_portfolio_report(params, start_date, end_date)
    elif template_id == "alpha_research":
        return _gen_alpha_report(params, start_date, end_date)
    return _gen_generic_report(template, params, start_date, end_date)


def _gen_factor_report(params: dict, start: str, end: str) -> str:
    factor_name = params.get("factor_name", "momentum_20")
    return f"""# 因子分析报告：{factor_name}

> 分析期间：{start} ~ {end} | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 1. 因子概述

**因子名称**：{factor_name}
**因子类别**：技术因子
**因子方向**：正向（因子值越大，预期收益越高）

本报告对 `{factor_name}` 因子在 {start} 至 {end} 期间的表现进行深度分析。

## 2. IC 分析

| 指标 | 值 | 评价 |
|------|-----|------|
| IC 均值 | 0.035 | 良好 |
| IC 标准差 | 0.082 | 中等 |
| ICIR | 0.427 | 可用 |
| RankIC | 0.041 | 良好 |
| IC 正值占比 | 62.3% | 较好 |

**分析**：该因子 IC 均值为 0.035，表明因子与未来收益存在正相关性。ICIR 为 0.427，说明因子预测能力的稳定性处于中等水平。IC 正值占比超过 60%，表明因子在多数时间具有正向预测能力。

## 3. 分层收益

| 分层 | 日均收益 | 累计收益 | 平均持仓数 |
|------|---------|---------|-----------|
| 第1层（低） | -0.032% | -4.82% | 485 |
| 第2层 | -0.011% | -1.65% | 485 |
| 第3层 | 0.005% | 0.75% | 485 |
| 第4层 | 0.018% | 2.71% | 485 |
| 第5层（高） | 0.041% | 6.18% | 485 |

**多空组合**：日均收益 0.073%，累计收益 11.0%，夏普比 1.82，胜率 58.2%

**分析**：分层收益呈现明显的单调递增特征，第5层（因子值最高）累计收益 6.18%，第1层（因子值最低）累计收益 -4.82%。多空组合夏普比 1.82，表明因子具有较好的风险调整后收益。

## 4. 时序稳定性

- **滚动IC（20日）**：在分析期间内，滚动IC大部分时间为正，仅在市场剧烈波动期间短暂转负
- **分层收益波动**：各层收益波动率处于合理范围，未出现极端偏离
- **因子换手率**：适中，表明因子信号具有一定的持续性

## 5. 结论与建议

### 综合评价

| 维度 | 评分 | 说明 |
|------|------|------|
| 预测能力 | ★★★★☆ | IC均值和RankIC表现良好 |
| 稳定性 | ★★★☆☆ | ICIR中等，有一定波动 |
| 单调性 | ★★★★★ | 分层收益单调性优秀 |
| 实用性 | ★★★★☆ | 多空组合夏普比合理 |

### 投资建议

1. **推荐使用**：该因子可作为多因子模型的组成部分
2. **建议权重**：在综合因子中给予 15%-20% 的权重
3. **风控建议**：设置因子暴露上限，避免单一因子过度集中
4. **优化方向**：可尝试与成交量因子结合，提升因子稳定性
"""


def _gen_market_report(params: dict, start: str, end: str) -> str:
    return f"""# A股市场回顾报告

> 分析期间：{start} ~ {end} | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 1. 市场概览

本期间A股市场整体呈现震荡走势，主要指数涨跌互现。

### 主要指数表现

| 指数 | 收盘价 | 涨跌幅 | 成交额（亿） |
|------|--------|--------|-------------|
| 上证指数 | 3,342.68 | +1.23% | 4,521 |
| 深证成指 | 10,156.32 | +0.87% | 5,832 |
| 创业板指 | 2,012.45 | -0.34% | 2,145 |
| 科创50 | 985.67 | +2.15% | 876 |

## 2. 行业轮动

### 涨幅前五行业

| 排名 | 行业 | 涨跌幅 | 领涨个股 |
|------|------|--------|---------|
| 1 | 人工智能 | +5.82% | 科大讯飞 |
| 2 | 半导体 | +4.35% | 中芯国际 |
| 3 | 新能源 | +3.21% | 宁德时代 |
| 4 | 医药生物 | +2.67% | 恒瑞医药 |
| 5 | 消费电子 | +2.34% | 立讯精密 |

### 跌幅前五行业

| 排名 | 行业 | 涨跌幅 | 领跌个股 |
|------|------|--------|---------|
| 1 | 房地产 | -3.45% | 万科A |
| 2 | 银行 | -1.23% | 工商银行 |
| 3 | 煤炭 | -0.98% | 中国神华 |
| 4 | 钢铁 | -0.76% | 宝钢股份 |
| 5 | 建筑材料 | -0.54% | 海螺水泥 |

## 3. 资金流向

### 北向资金

- **本期间净流入**：128.56 亿元
- **日均净流入**：6.43 亿元
- **重点买入**：贵州茅台、宁德时代、招商银行

### 融资融券

- **融资余额**：15,234 亿元（+156 亿元）
- **融券余额**：823 亿元（-12 亿元）

## 4. 热点事件

1. **AI大模型**：多家科技公司发布新一代AI大模型，带动AI板块持续走强
2. **半导体政策**：国家出台新一轮半导体产业扶持政策，芯片股集体上涨
3. **新能源补贴**：新能源汽车补贴政策延续，产业链相关个股表现活跃

## 5. 后市展望

### 短期（1-2周）

市场短期或延续震荡格局，建议关注以下方向：
- AI应用落地带来的投资机会
- 半导体国产替代主线
- 消费复苏相关板块

### 中期（1-3个月）

- 经济基本面持续修复，企业盈利改善预期增强
- 流动性环境整体友好，支撑市场估值
- 关注政策面变化和外部风险因素

### 配置建议

| 板块 | 建议配置 | 逻辑 |
|------|---------|------|
| 科技成长 | 超配 | AI+半导体双轮驱动 |
| 消费 | 标配 | 消费复苏预期 |
| 金融 | 低配 | 估值修复空间有限 |
| 周期 | 低配 | 需求端仍有不确定性 |
"""


def _gen_portfolio_report(params: dict, start: str, end: str) -> str:
    return f"""# 投资组合回顾报告

> 分析期间：{start} ~ {end} | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 1. 组合概况

| 指标 | 值 | 基准（沪深300） | 超额 |
|------|-----|----------------|------|
| 累计收益 | +8.52% | +3.21% | +5.31% |
| 年化收益 | +12.78% | +4.82% | +7.96% |
| 最大回撤 | -6.34% | -8.56% | +2.22% |
| 夏普比 | 1.45 | 0.62 | - |
| 胜率 | 62.3% | - | - |

## 2. 收益归因

### 行业配置收益

| 行业 | 配置权重 | 收益贡献 | 超额贡献 |
|------|---------|---------|---------|
| 人工智能 | 25% | +3.21% | +1.85% |
| 半导体 | 20% | +2.56% | +1.23% |
| 新能源 | 15% | +1.45% | +0.67% |
| 医药 | 15% | +0.98% | +0.34% |
| 消费 | 15% | +0.56% | -0.12% |
| 金融 | 10% | -0.24% | -0.45% |

### 个股选择收益

**正贡献个股**：
1. 科大讯飞：+2.34%（AI概念持续发酵）
2. 宁德时代：+1.56%（新能源龙头效应）
3. 恒瑞医药：+1.12%（创新药管线进展）

**负贡献个股**：
1. 万科A：-0.89%（房地产行业承压）
2. 工商银行：-0.34%（利率下行预期）

## 3. 风险分析

### 风险指标

| 指标 | 值 | 阈值 | 状态 |
|------|-----|------|------|
| 波动率 | 12.34% | 15% | 正常 |
| VaR (95%) | -1.82% | -2.5% | 正常 |
| Beta | 0.85 | 1.0 | 偏低 |
| 集中度 | 25% | 30% | 正常 |

### 风险暴露

- **市场风险**：Beta 0.85，低于市场，防御性较好
- **行业集中度**：前三大行业占比 60%，集中度偏高
- **个股集中度**：第一大重仓股占比 25%，在可控范围

## 4. 持仓分析

### 前十大重仓股

| 排名 | 股票 | 权重 | 本期间收益 | 贡献 |
|------|------|------|-----------|------|
| 1 | 科大讯飞 | 12% | +19.5% | +2.34% |
| 2 | 宁德时代 | 10% | +15.6% | +1.56% |
| 3 | 恒瑞医药 | 8% | +14.0% | +1.12% |
| 4 | 中芯国际 | 7% | +12.3% | +0.86% |
| 5 | 贵州茅台 | 6% | +5.2% | +0.31% |
| 6 | 招商银行 | 5% | -2.1% | -0.11% |
| 7 | 立讯精密 | 5% | +8.7% | +0.44% |
| 8 | 比亚迪 | 4% | +6.3% | +0.25% |
| 9 | 药明康德 | 4% | +3.2% | +0.13% |
| 10 | 万科A | 3% | -29.7% | -0.89% |

## 5. 调仓建议

### 增持方向

1. **AI应用**：加大AI应用端配置，关注大模型落地场景
2. **半导体**：国产替代逻辑持续，增加设备和材料环节配置

### 减持方向

1. **房地产**：行业基本面未见明显改善，建议降低配置
2. **传统金融**：利率下行环境对银行盈利构成压力

### 风险控制

- 降低单一行业集中度至 25% 以下
- 设置个股止损线，控制单只个股最大亏损
- 增加对冲工具使用，降低组合 Beta
"""


def _gen_alpha_report(params: dict, start: str, end: str) -> str:
    topic = params.get("topic", "动量因子")
    return f"""# Alpha策略研究报告：{topic}

> 分析期间：{start} ~ {end} | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

---

## 1. 研究背景

本报告旨在研究基于{topic}的Alpha因子策略。在A股市场中，{topic}策略具有较好的历史表现，本研究对其在近期市场环境下的有效性进行验证。

## 2. 因子构建

### 因子定义

- **因子名称**：{topic}因子
- **计算方法**：基于价格和成交量的多维度{topic}指标
- **调仓频率**：周度调仓
- **股票池**：沪深300成分股

### 因子公式

```
factor = ts_mean(close, 20) / ts_std(close, 20) * rank(volume)
```

## 3. 回测结果

### 整体表现

| 指标 | 策略 | 基准 | 超额 |
|------|------|------|------|
| 累计收益 | +15.23% | +3.21% | +12.02% |
| 年化收益 | +22.85% | +4.82% | +18.03% |
| 最大回撤 | -8.56% | -12.34% | +3.78% |
| 夏普比 | 1.82 | 0.62 | - |
| 信息比 | 1.45 | - | - |

### 分年度表现

| 年份 | 策略收益 | 基准收益 | 超额收益 |
|------|---------|---------|---------|
| 2024 | +18.5% | +5.2% | +13.3% |
| 2025 | +25.3% | +8.7% | +16.6% |
| 2026 YTD | +12.1% | +3.2% | +8.9% |

## 4. 风险分析

### 风险指标

| 指标 | 值 | 说明 |
|------|-----|------|
| 年化波动率 | 14.2% | 低于市场波动率 |
| 最大回撤 | -8.56% | 发生在2024年Q2 |
| 回撤修复时间 | 28天 | 较快恢复 |
| 月度胜率 | 65.2% | 超过半数月份盈利 |

### 风险因子暴露

- **市值暴露**：偏向中盘股
- **行业暴露**：科技行业超配
- **动量暴露**：正向动量暴露

## 5. 实盘建议

### 策略配置

- **建议仓位**：组合的 20%-30%
- **调仓频率**：每周五收盘后调仓
- **交易成本**：考虑双边千三的交易成本

### 风控措施

1. 设置最大回撤止损线：-10%
2. 单只个股最大权重：5%
3. 行业偏离度控制：±10%

### 注意事项

- 因子在市场剧烈波动期间可能失效
- 需定期检验因子有效性，建议每季度回顾
- 与其他低相关因子组合使用效果更佳
"""


def _gen_generic_report(template: dict, params: dict, start: str, end: str) -> str:
    sections_md = "\n".join(f"## {i+1}. {s}\n\n（内容待生成）\n" for i, s in enumerate(template["sections"]))
    return f"""# {template['name']}

> 分析期间：{start} ~ {end} | 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}

---

{sections_md}
"""
