"""
Antigravity Token 计费价格计算引擎
严格对齐官方及 Sub2API 计费规则：
- Gemini 3.1 Pro: <=200k (输入 $2.00, 输出 $12.00, 缓存 $0.20) / >200k (输入 $4.00, 输出 $18.00, 缓存 $0.40)
- Gemini 3.8 / 3.7 / 3.6 Flash: 输入 $0.75, 输出 $3.75, 缓存读取 $0.075
- Gemini 3.5 Flash-Lite: 输入 $0.30, 输出 $2.50, 缓存读取 $0.03
- Gemini 3.1 Flash-Lite: 输入 $0.25, 输出 $1.50, 缓存读取 $0.025
- Gemini 2.5 Flash-Lite: 输入 $0.10, 输出 $0.40, 缓存读取 $0.01
- Claude Opus 4.6 (Thinking): 输入 $5.00, 输出 $25.00, 缓存读取 $0.50 (对齐 Sub2API model_pricing.json)
- 默认/兜底: 输入 $0.75, 输出 $3.75, 缓存读取 $0.075
单位均基于每 1,000,000 (1M) Tokens。
"""

from typing import Any, Dict, Tuple

TOKENS_PER_MILLION = 1_000_000.0


def get_model_rates(model_name: str, context_tokens: int = 0) -> Tuple[float, float, float]:
    """
    根据模型名称和上下文长度返回 (input_rate, output_rate, cache_read_rate)，单位为 USD/1M tokens
    严格对齐 Google 官方价卡与 Sub2API 配置。
    """
    name = (model_name or "").lower().strip()

    # 1. 高阶旗舰: Gemini 3.1 Pro / Pro 系列 (截图 1 第一行)
    if "pro" in name and "claude" not in name:
        if context_tokens > 200_000:
            return 4.00, 18.00, 0.40
        return 2.00, 12.00, 0.20

    # 2. 经典过渡: Gemini 2.5 Flash-Lite (截图 1 第五行)
    if "2.5-flash-lite" in name or ("2.5" in name and "lite" in name):
        return 0.10, 0.40, 0.01

    # 3. 超轻量级: Gemini 3.1 Flash-Lite (截图 1 第四行)
    if "3.1-flash-lite" in name:
        return 0.25, 1.50, 0.025

    # 4. 轻量高速: Gemini 3.5 Flash-Lite (截图 1 第三行)
    if "3.5-flash-lite" in name:
        return 0.30, 2.50, 0.03

    # 5. Claude Opus 4.6 系列 (对齐 Sub2API 官方 model_pricing.json)
    if "claude" in name or "opus" in name:
        return 5.00, 25.00, 0.50

    # 6. 主力模型: Gemini 3.8 / 3.7 / 3.6 Flash 系列 (截图 1 第二行)
    # 覆盖 gemini-3.8-flash, gemini-3.8-flash-control, gemini-3.8-flash-tiered, gemini-3.8-flash-n 等
    if "flash" in name or "gemini" in name:
        return 0.75, 3.75, 0.075

    # 默认兜底按 Gemini 3.8 Flash 费率计算
    return 0.75, 3.75, 0.075


def calculate_record_cost(record: Dict[str, Any], rate_multiplier: float = 1.0) -> Dict[str, float]:
    """
    计算单条请求调用的各维度费用（美元 USD），严格对齐 Sub2API 标准语义：
    - standard_cost (标准费用): 官方标准目录价 (包含未缓存输入 + 输出 + 缓存读取价)
    - actual_cost (实际消费): standard_cost * rate_multiplier (默认 1.0 倍率)
    - account_cost (账号成本): standard_cost
    - savings (缓存节约): 相较于无缓存纯输入全价节省的金额
    """
    model_name = record.get("model_name") or record.get("model_id") or ""
    inp = float(record.get("input_tokens") or 0)
    cac = float(record.get("cached_tokens") or 0)
    out = float(record.get("output_tokens") or 0)
    context_total = int(inp + cac)

    inp_rate, out_rate, cac_rate = get_model_rates(model_name, context_total)

    input_cost = (inp / TOKENS_PER_MILLION) * inp_rate
    cache_cost = (cac / TOKENS_PER_MILLION) * cac_rate
    output_cost = (out / TOKENS_PER_MILLION) * out_rate

    # 标准消费（Sub2API 官方基准价）
    standard_cost = input_cost + cache_cost + output_cost
    # 实际消费（用户倍率折算）
    actual_cost = standard_cost * rate_multiplier
    # 账号成本（上游进货成本）
    account_cost = standard_cost

    # Prompt Caching 节约金额
    hypothetical_full_cost = ((inp + cac) / TOKENS_PER_MILLION) * inp_rate + output_cost
    savings = max(0.0, hypothetical_full_cost - standard_cost)

    return {
        "actual_cost": round(actual_cost, 6),
        "standard_cost": round(standard_cost, 6),
        "account_cost": round(account_cost, 6),
        "savings": round(savings, 6),
        "input_cost": round(input_cost, 6),
        "cache_cost": round(cache_cost, 6),
        "output_cost": round(output_cost, 6),
        "inp_rate": inp_rate,
        "out_rate": out_rate,
        "cac_rate": cac_rate,
    }


def format_usd(val: float, precision: int = 4) -> str:
    """格式化美元金额展示"""
    if val is None or val == 0:
        return "$0.0000"
    if precision == 4:
        return f"${val:.4f}"
    return f"${val:.6f}"
