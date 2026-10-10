"""
多维度 Token 统计聚合与精美报告生成器
- 支持 Windows 与 WSL2 跨环境数据整合（完全跨机型自适应，无硬编码）
- 支持顶层工具类型切换（Antigravity IDE vs Antigravity CLI vs 全部）
- 支持自定义主题（默认暖黄护眼风格，可选极客暗黑风格）
- 支持 GitHub 风格年度贡献热力图（含年份切换与 Hover 浮层）
- 支持每日走势图（日期范围与模型下拉多选联动、紧凑高度约70%、实时求和统计卡片栏）
- 支持执行完成后自动在系统默认浏览器中打开 HTML 报表
"""

import csv
from datetime import datetime, timedelta
import http.server
import json
import os
import re
import socketserver
import sys
import threading
import time
import urllib.parse
import webbrowser
from collections import defaultdict
from typing import Any, Dict, List, Optional, Union

# 确保在 Windows 控制台下的 UTF-8 打印兼容
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from pricing import calculate_record_cost, format_usd, get_model_rates
from token_analyzer import collect_all_data, discover_all_data_dirs, scan_all_conversation_dbs


def format_num(n: Union[int, float]) -> str:
    """格式化大数字，添加千分位逗号"""
    if isinstance(n, float):
        return f"{n:,.2f}"
    return f"{n:,}"


def format_tokens_m(n: Union[int, float], show_raw: bool = False) -> str:
    """
    格式化 Token 数量为以 M (百万) 为核心单位的易读字符串
    - 保证足够精度：根据大小自适应保留 2~4 位小数
    - 例如: 123.45 M, 0.05 M, 0.002 M
    """
    if n is None:
        return "0.00 M"
    m = float(n) / 1_000_000.0
    if abs(m) == 0:
        s = "0.00 M"
    elif abs(m) >= 100:
        s = f"{m:,.2f} M"
    elif abs(m) >= 1:
        s = f"{m:.2f} M"
    elif abs(m) >= 0.01:
        s = f"{m:.3f} M"
    elif abs(m) >= 0.0001:
        s = f"{m:.4f} M"
    else:
        s = f"{m:.6f} M"
    if show_raw:
        return f"{s} ({format_num(n)})"
    return s


def human_tokens(n: int) -> str:
    """人性化大数字展示，统一优先使用 M (百万) 为主单位"""
    return f"{format_tokens_m(n)} Tokens"


def generate_multi_dimensional_stats(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """生成单套记录的多维度统计数据结构（含严格官方对齐计费与 Sub2 每次请求详情）"""
    total_calls = len(records)
    total_input = 0
    total_cached = 0
    total_output = 0
    total_thinking = 0
    total_response = 0
    total_tokens = 0
    total_latency = 0.0
    valid_latency_count = 0

    total_actual_cost = 0.0
    total_standard_cost = 0.0
    total_savings = 0.0

    timestamps = [r["timestamp"] for r in records if r.get("timestamp")]
    min_time = min(timestamps) if timestamps else None
    max_time = max(timestamps) if timestamps else None

    # 1. 模型维度
    model_stats = defaultdict(
        lambda: {
            "model_name": "",
            "model_id": "",
            "calls": 0,
            "input_tokens": 0,
            "cached_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "response_tokens": 0,
            "total_tokens": 0,
            "actual_cost": 0.0,
            "account_cost": 0.0,
            "standard_cost": 0.0,
            "savings": 0.0,
            "total_latency": 0.0,
            "latency_count": 0,
        }
    )

    # 2. 会话维度
    conv_stats = defaultdict(
        lambda: {
            "conv_id": "",
            "db_file": "",
            "env": "windows",
            "client_type": "Antigravity IDE",
            "calls": 0,
            "input_tokens": 0,
            "cached_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "total_tokens": 0,
            "actual_cost": 0.0,
            "models": defaultdict(int),
            "first_time": None,
            "last_time": None,
        }
    )

    # 3. 环境维度 (Windows 本地 vs WSL2:Ubuntu 等)
    env_stats = defaultdict(
        lambda: {
            "env": "",
            "calls": 0,
            "conversations": set(),
            "input_tokens": 0,
            "cached_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "response_tokens": 0,
            "total_tokens": 0,
            "actual_cost": 0.0,
            "account_cost": 0.0,
            "standard_cost": 0.0,
            "savings": 0.0,
        }
    )

    # 4. 工具客户端维度 (Antigravity IDE vs Antigravity CLI)
    client_stats = defaultdict(
        lambda: {
            "client_type": "",
            "calls": 0,
            "conversations": set(),
            "input_tokens": 0,
            "cached_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "response_tokens": 0,
            "total_tokens": 0,
            "actual_cost": 0.0,
            "account_cost": 0.0,
            "standard_cost": 0.0,
            "savings": 0.0,
        }
    )

    # 5. 时间维度 (按日、按月、按日+模型细分统计)
    daily_stats = defaultdict(
        lambda: {
            "date": "",
            "calls": 0,
            "input_tokens": 0,
            "cached_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "response_tokens": 0,
            "total_tokens": 0,
            "actual_cost": 0.0,
            "standard_cost": 0.0,
            "savings": 0.0,
        }
    )

    daily_by_model = defaultdict(
        lambda: defaultdict(
            lambda: {
                "calls": 0,
                "input_tokens": 0,
                "cached_tokens": 0,
                "output_tokens": 0,
                "thinking_tokens": 0,
                "response_tokens": 0,
                "total_tokens": 0,
                "actual_cost": 0.0,
            }
        )
    )

    monthly_stats = defaultdict(
        lambda: {
            "month": "",
            "calls": 0,
            "input_tokens": 0,
            "cached_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "total_tokens": 0,
            "actual_cost": 0.0,
            "standard_cost": 0.0,
        }
    )

    # Sub2 风格小时级精准数据结构 (精确到 60 分钟)
    hourly_stats = defaultdict(
        lambda: {
            "hour": "",
            "date": "",
            "hour_num": 0,
            "calls": 0,
            "input_tokens": 0,
            "cached_tokens": 0,
            "output_tokens": 0,
            "thinking_tokens": 0,
            "response_tokens": 0,
            "total_tokens": 0,
            "actual_cost": 0.0,
            "standard_cost": 0.0,
            "models": defaultdict(int),
        }
    )

    hourly_by_model = defaultdict(
        lambda: defaultdict(
            lambda: {
                "calls": 0,
                "input_tokens": 0,
                "cached_tokens": 0,
                "output_tokens": 0,
                "thinking_tokens": 0,
                "response_tokens": 0,
                "total_tokens": 0,
                "actual_cost": 0.0,
            }
        )
    )

    # 6. Prompt Breakdown 细分统计
    prompt_breakdown_stats = {
        "count_with_breakdown": 0,
        "total_system_prompt": 0,
        "total_tools": 0,
        "total_chat_messages": 0,
    }

    for r in records:
        inp = r.get("input_tokens", 0)
        cac = r.get("cached_tokens", 0)
        out = r.get("output_tokens", 0)
        thk = r.get("thinking_tokens", 0)
        rsp = r.get("response_tokens", 0)
        tok = r.get("total_tokens", 0)
        lat = r.get("latency_sec", 0.0) or 0.0
        ts = r.get("timestamp")
        env_val = r.get("env", "windows")
        client_val = r.get("client_type", "Antigravity IDE")

        total_input += inp
        total_cached += cac
        total_output += out
        total_thinking += thk
        total_response += rsp
        total_tokens += tok
        if lat > 0:
            total_latency += lat
            valid_latency_count += 1

        # 计费核算
        cost_info = calculate_record_cost(r)
        r["cost_info"] = cost_info
        r_actual_cost = cost_info["actual_cost"]
        r_account_cost = cost_info.get("account_cost", cost_info["standard_cost"])
        r_standard_cost = cost_info["standard_cost"]
        r_savings = cost_info["savings"]

        total_actual_cost += r_actual_cost
        total_standard_cost += r_standard_cost
        total_savings += r_savings

        # 环境聚合
        e_dict = env_stats[env_val]
        e_dict["env"] = env_val
        e_dict["calls"] += 1
        e_dict["conversations"].add(r.get("conv_id", ""))
        e_dict["input_tokens"] += inp
        e_dict["cached_tokens"] += cac
        e_dict["output_tokens"] += out
        e_dict["thinking_tokens"] += thk
        e_dict["response_tokens"] += rsp
        e_dict["total_tokens"] += tok
        e_dict["actual_cost"] += r_actual_cost
        e_dict["account_cost"] += r_account_cost
        e_dict["standard_cost"] += r_standard_cost
        e_dict["savings"] += r_savings

        # 工具客户端聚合
        cl_dict = client_stats[client_val]
        cl_dict["client_type"] = client_val
        cl_dict["calls"] += 1
        cl_dict["conversations"].add(r.get("conv_id", ""))
        cl_dict["input_tokens"] += inp
        cl_dict["cached_tokens"] += cac
        cl_dict["output_tokens"] += out
        cl_dict["thinking_tokens"] += thk
        cl_dict["response_tokens"] += rsp
        cl_dict["total_tokens"] += tok
        cl_dict["actual_cost"] += r_actual_cost
        cl_dict["account_cost"] += r_account_cost
        cl_dict["standard_cost"] += r_standard_cost
        cl_dict["savings"] += r_savings

        # 模型聚合
        m_key = r.get("model_name", "Unknown")
        m_dict = model_stats[m_key]
        m_dict["model_name"] = m_key
        m_dict["model_id"] = r.get("model_id", "")
        m_dict["calls"] += 1
        m_dict["input_tokens"] += inp
        m_dict["cached_tokens"] += cac
        m_dict["output_tokens"] += out
        m_dict["thinking_tokens"] += thk
        m_dict["response_tokens"] += rsp
        m_dict["total_tokens"] += tok
        m_dict["actual_cost"] += r_actual_cost
        m_dict["account_cost"] += r_account_cost
        m_dict["standard_cost"] += r_standard_cost
        m_dict["savings"] += r_savings
        if lat > 0:
            m_dict["total_latency"] += lat
            m_dict["latency_count"] += 1

        # 会话聚合
        c_key = r.get("conv_id", "")
        c_dict = conv_stats[c_key]
        c_dict["conv_id"] = c_key
        c_dict["db_file"] = r.get("db_file", "")
        c_dict["env"] = env_val
        c_dict["client_type"] = client_val
        c_dict["calls"] += 1
        c_dict["input_tokens"] += inp
        c_dict["cached_tokens"] += cac
        c_dict["output_tokens"] += out
        c_dict["thinking_tokens"] += thk
        c_dict["total_tokens"] += tok
        c_dict["actual_cost"] += r_actual_cost
        c_dict["models"][m_key] += 1
        if ts:
            if not c_dict["first_time"] or ts < c_dict["first_time"]:
                c_dict["first_time"] = ts
            if not c_dict["last_time"] or ts > c_dict["last_time"]:
                c_dict["last_time"] = ts

        # 时间维度聚合
        if ts:
            dt = datetime.fromtimestamp(ts)
            day_str = dt.strftime("%Y-%m-%d")
            month_str = dt.strftime("%Y-%m")
            hour_str = dt.strftime("%Y-%m-%d %H:00")
            h_int = dt.hour

            d_dict = daily_stats[day_str]
            d_dict["date"] = day_str
            d_dict["calls"] += 1
            d_dict["input_tokens"] += inp
            d_dict["cached_tokens"] += cac
            d_dict["output_tokens"] += out
            d_dict["thinking_tokens"] += thk
            d_dict["response_tokens"] += rsp
            d_dict["total_tokens"] += tok
            d_dict["actual_cost"] += r_actual_cost
            d_dict["standard_cost"] += r_standard_cost
            d_dict["savings"] += r_savings

            dm_dict = daily_by_model[day_str][m_key]
            dm_dict["calls"] += 1
            dm_dict["input_tokens"] += inp
            dm_dict["cached_tokens"] += cac
            dm_dict["output_tokens"] += out
            dm_dict["thinking_tokens"] += thk
            dm_dict["response_tokens"] += rsp
            dm_dict["total_tokens"] += tok
            dm_dict["actual_cost"] += r_actual_cost

            # 小时维度
            h_dict = hourly_stats[hour_str]
            h_dict["hour"] = hour_str
            h_dict["date"] = day_str
            h_dict["hour_num"] = h_int
            h_dict["calls"] += 1
            h_dict["input_tokens"] += inp
            h_dict["cached_tokens"] += cac
            h_dict["output_tokens"] += out
            h_dict["thinking_tokens"] += thk
            h_dict["response_tokens"] += rsp
            h_dict["total_tokens"] += tok
            h_dict["actual_cost"] += r_actual_cost
            h_dict["standard_cost"] += r_standard_cost
            h_dict["models"][m_key] += tok

            hm_dict = hourly_by_model[hour_str][m_key]
            hm_dict["calls"] += 1
            hm_dict["input_tokens"] += inp
            hm_dict["cached_tokens"] += cac
            hm_dict["output_tokens"] += out
            hm_dict["thinking_tokens"] += thk
            hm_dict["response_tokens"] += rsp
            hm_dict["total_tokens"] += tok
            hm_dict["actual_cost"] += r_actual_cost

            mo_dict = monthly_stats[month_str]
            mo_dict["month"] = month_str
            mo_dict["calls"] += 1
            mo_dict["input_tokens"] += inp
            mo_dict["cached_tokens"] += cac
            mo_dict["output_tokens"] += out
            mo_dict["thinking_tokens"] += thk
            mo_dict["total_tokens"] += tok
            mo_dict["actual_cost"] += r_actual_cost
            mo_dict["standard_cost"] += r_standard_cost

        # Prompt Breakdown
        pb = r.get("prompt_breakdown")
        if pb and (pb.get("system_prompt_tokens") or pb.get("tools_tokens") or pb.get("chat_messages_tokens")):
            prompt_breakdown_stats["count_with_breakdown"] += 1
            prompt_breakdown_stats["total_system_prompt"] += pb.get("system_prompt_tokens", 0)
            prompt_breakdown_stats["total_tools"] += pb.get("tools_tokens", 0)
            prompt_breakdown_stats["total_chat_messages"] += pb.get("chat_messages_tokens", 0)

    total_full_prompt = total_input + total_cached
    cache_hit_rate = (total_cached / total_full_prompt * 100) if total_full_prompt > 0 else 0.0
    avg_latency = (total_latency / valid_latency_count) if valid_latency_count > 0 else 0.0

    # 格式化环境统计
    env_list = []
    for k, v in env_stats.items():
        v_copy = dict(v)
        v_copy["conv_count"] = len(v["conversations"])
        del v_copy["conversations"]
        v_copy["actual_cost"] = round(v_copy["actual_cost"], 4)
        v_copy["account_cost"] = round(v_copy.get("account_cost", v_copy["actual_cost"]), 4)
        v_copy["standard_cost"] = round(v_copy.get("standard_cost", v_copy["actual_cost"]), 4)
        v_copy["savings"] = round(v_copy.get("savings", 0.0), 4)
        env_list.append(v_copy)
    env_list.sort(key=lambda x: x["total_tokens"], reverse=True)

    # 格式化工具客户端统计
    client_list = []
    for k, v in client_stats.items():
        v_copy = dict(v)
        v_copy["conv_count"] = len(v["conversations"])
        del v_copy["conversations"]
        v_copy["actual_cost"] = round(v_copy["actual_cost"], 4)
        v_copy["account_cost"] = round(v_copy.get("account_cost", v_copy["actual_cost"]), 4)
        v_copy["standard_cost"] = round(v_copy["standard_cost"], 4)
        v_copy["savings"] = round(v_copy["savings"], 4)
        client_list.append(v_copy)
    client_list.sort(key=lambda x: x["total_tokens"], reverse=True)

    # 格式化 daily_by_model 结构
    formatted_daily_model = {}
    for day, m_map in sorted(daily_by_model.items()):
        formatted_daily_model[day] = dict(m_map)

    # 格式化 hourly_stats 与 hourly_by_model (Sub2 风格)
    formatted_hourly = []
    for h_key, h_info in sorted(hourly_stats.items()):
        item = dict(h_info)
        item["models"] = dict(item["models"])
        item["actual_cost"] = round(item["actual_cost"], 4)
        item["standard_cost"] = round(item["standard_cost"], 4)
        formatted_hourly.append(item)

    formatted_hourly_model = {}
    for h_key, m_map in sorted(hourly_by_model.items()):
        formatted_hourly_model[h_key] = dict(m_map)

    # 计算今日、昨日、当前小时与峰值小时统计
    now_dt = datetime.now()
    today_str = now_dt.strftime("%Y-%m-%d")
    yesterday_str = (now_dt.date() - timedelta(days=1)).strftime("%Y-%m-%d")
    cur_hour_str = now_dt.strftime("%Y-%m-%d %H:00")

    today_tokens = sum(h["total_tokens"] for h in formatted_hourly if h["date"] == today_str)
    today_calls = sum(h["calls"] for h in formatted_hourly if h["date"] == today_str)
    today_cost = sum(h.get("actual_cost", 0.0) for h in formatted_hourly if h["date"] == today_str)
    yesterday_tokens = sum(h["total_tokens"] for h in formatted_hourly if h["date"] == yesterday_str)
    yesterday_cost = sum(h.get("actual_cost", 0.0) for h in formatted_hourly if h["date"] == yesterday_str)
    cur_hour_tokens = hourly_stats[cur_hour_str]["total_tokens"] if cur_hour_str in hourly_stats else 0
    cur_hour_calls = hourly_stats[cur_hour_str]["calls"] if cur_hour_str in hourly_stats else 0
    cur_hour_cost = hourly_stats[cur_hour_str]["actual_cost"] if cur_hour_str in hourly_stats else 0.0

    peak_hour_item = max(formatted_hourly, key=lambda x: x["total_tokens"]) if formatted_hourly else None
    peak_hour_str = peak_hour_item["hour"] if peak_hour_item else "N/A"
    peak_hour_tokens = peak_hour_item["total_tokens"] if peak_hour_item else 0

    # 提取最近 300 条调用明细 (按时间倒序排列，供静态离线前端直读)
    recent_records = []
    sorted_recs = sorted(records, key=lambda x: x.get("timestamp") or 0, reverse=True)
    for r in sorted_recs[:300]:
        ts_val = r.get("timestamp")
        dt_str = datetime.fromtimestamp(ts_val).strftime("%Y-%m-%d %H:%M:%S") if ts_val else "--"
        c_info = r.get("cost_info") or calculate_record_cost(r)
        inp = r.get("input_tokens", 0)
        cac = r.get("cached_tokens", 0)
        out = r.get("output_tokens", 0)
        thk = r.get("thinking_tokens", 0)
        rsp = r.get("response_tokens", 0)
        full_inp = inp + cac
        c_rate = round(cac / full_inp * 100, 1) if full_inp > 0 else 0.0
        lat = r.get("latency_sec") or 0.0

        recent_records.append({
            "conv_id": r.get("conv_id", "--"),
            "step_idx": r.get("step_idx", 0),
            "time": dt_str,
            "client": r.get("client_type", "Antigravity IDE"),
            "model": r.get("model_name", "Unknown"),
            "model_id": r.get("model_id", ""),
            "latency": f"{lat:.2f}s" if lat > 0 else "--",
            "latency_sec": lat,
            "input_tokens": inp,
            "cached_tokens": cac,
            "output_tokens": out,
            "thinking_tokens": thk,
            "response_tokens": rsp,
            "total_tokens": r.get("total_tokens", inp + cac + out),
            "actual_cost": c_info["actual_cost"],
            "account_cost": c_info.get("account_cost", c_info["actual_cost"]),
            "standard_cost": c_info["standard_cost"],
            "savings": c_info["savings"],
            "cost_str": format_usd(c_info["actual_cost"], 4),
            "savings_str": format_usd(c_info["savings"], 4),
            "cache_rate": c_rate,
            "status": 200,
            "inp_rate": c_info.get("inp_rate", 0.75),
            "out_rate": c_info.get("out_rate", 3.75),
            "cac_rate": c_info.get("cac_rate", 0.075),
        })

    # 模型列表按消耗排序并格式化金额
    model_list = []
    for k, v in model_stats.items():
        v_copy = dict(v)
        v_copy["actual_cost"] = round(v_copy["actual_cost"], 4)
        v_copy["account_cost"] = round(v_copy.get("account_cost", v_copy["actual_cost"]), 4)
        v_copy["standard_cost"] = round(v_copy["standard_cost"], 4)
        v_copy["savings"] = round(v_copy["savings"], 4)
        model_list.append(v_copy)
    model_list.sort(key=lambda x: x["total_tokens"], reverse=True)

    # 日期列表按日期升序
    daily_list = []
    for k, v in sorted(daily_stats.items()):
        v_copy = dict(v)
        v_copy["actual_cost"] = round(v_copy["actual_cost"], 4)
        v_copy["standard_cost"] = round(v_copy["standard_cost"], 4)
        v_copy["savings"] = round(v_copy["savings"], 4)
        daily_list.append(v_copy)

    # 会话列表
    conv_list = []
    for k, v in conv_stats.items():
        v_copy = dict(v)
        v_copy["models"] = dict(v_copy["models"])
        v_copy["actual_cost"] = round(v_copy["actual_cost"], 4)
        conv_list.append(v_copy)
    conv_list.sort(key=lambda x: x["total_tokens"], reverse=True)

    # 月度列表
    monthly_list = []
    for k, v in sorted(monthly_stats.items()):
        v_copy = dict(v)
        v_copy["actual_cost"] = round(v_copy["actual_cost"], 4)
        v_copy["standard_cost"] = round(v_copy["standard_cost"], 4)
        monthly_list.append(v_copy)

    return {
        "overview": {
            "total_calls": total_calls,
            "total_conversations": len(conv_stats),
            "min_time": datetime.fromtimestamp(min_time).strftime("%Y-%m-%d %H:%M:%S") if min_time else "N/A",
            "max_time": datetime.fromtimestamp(max_time).strftime("%Y-%m-%d %H:%M:%S") if max_time else "N/A",
            "total_input_uncached": total_input,
            "total_cached_read": total_cached,
            "total_full_input": total_full_prompt,
            "cache_hit_rate": cache_hit_rate,
            "total_output": total_output,
            "total_thinking": total_thinking,
            "total_response": total_response,
            "total_tokens": total_tokens,
            "total_tokens_m": round(total_tokens / 1_000_000, 2),
            "total_cost": round(total_actual_cost, 4),
            "actual_cost": round(total_actual_cost, 4),
            "account_cost": round(total_standard_cost, 4),
            "standard_cost": round(total_standard_cost, 4),
            "savings": round(total_savings, 4),
            "total_cost_str": format_usd(total_actual_cost, 4),
            "actual_cost_str": format_usd(total_actual_cost, 4),
            "account_cost_str": format_usd(total_standard_cost, 4),
            "standard_cost_str": format_usd(total_standard_cost, 4),
            "savings_str": format_usd(total_savings, 4),
            "today_tokens": today_tokens,
            "today_calls": today_calls,
            "today_cost": round(today_cost, 4),
            "yesterday_tokens": yesterday_tokens,
            "yesterday_cost": round(yesterday_cost, 4),
            "cur_hour_tokens": cur_hour_tokens,
            "cur_hour_calls": cur_hour_calls,
            "cur_hour_cost": round(cur_hour_cost, 4),
            "peak_hour": peak_hour_str,
            "peak_hour_tokens": peak_hour_tokens,
            "avg_latency": avg_latency,
        },
        "models": model_list,
        "conversations": conv_list,
        "environments": env_list,
        "clients": client_list,
        "daily": daily_list,
        "daily_by_model": formatted_daily_model,
        "hourly": formatted_hourly,
        "hourly_by_model": formatted_hourly_model,
        "monthly": monthly_list,
        "prompt_breakdown": prompt_breakdown_stats,
        "recent_records": recent_records,
    }


def render_markdown_report(
    stats: Dict[str, Any],
    scanned_targets: Optional[List[Dict[str, str]]] = None
) -> str:
    """渲染生成结构化 Markdown 报告 (统一采用 M 为主要统计单位)"""
    ov = stats["overview"]
    pb = stats["prompt_breakdown"]
    envs = stats.get("environments", [])
    clients = stats.get("clients", [])

    md = []
    md.append("# Antigravity Token 多维度使用统计分析报告\n")
    md.append(f"> **统计生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    md.append(f"> **数据统计区间**：`{ov['min_time']}` 至 `{ov['max_time']}`  ")
    md.append(f"> **核心统计单位**：`M Tokens` (百万，1 M = 1,000,000 Tokens)  ")

    # 扫描范围展示
    if scanned_targets:
        md.append("> **数据库扫描覆盖范围**：")
        for st in scanned_targets:
            md.append(f"> - `[{st['env']}]` `{st['path']}`")
        md.append("")
    else:
        md.append("> **数据库扫描范围**：Windows 本地与 WSL2 跨环境全部会话数据库\n")

    md.append("## 一、 总体宏观消耗概览 (Overall Overview)\n")
    md.append("| 指标项 | 统计数值 (M) | 精确 Token 数 | 说明 |")
    md.append("| :--- | :---: | :---: | :--- |")
    md.append(
        f"| **总会话数量 (Conversations)** | `{format_num(ov['total_conversations'])}` 个 | - | 包含有效对话记录的数据库 |"
    )
    md.append(f"| **总模型调用次数 (Total Calls)** | `{format_num(ov['total_calls'])}` 次 | - | LLM 生成响应总轮次 |")
    md.append(
        f"| **累计消耗总 Token (Total Tokens)** | **`{format_tokens_m(ov['total_tokens'])}`** | `{format_num(ov['total_tokens'])}` | 未缓存输入 + 缓存读取 + 输出 |"
    )
    md.append(
        f"| **未缓存输入 Token (Uncached Input)** | `{format_tokens_m(ov['total_input_uncached'])}` | `{format_num(ov['total_input_uncached'])}` | 需全额计算的 Prompt Token |"
    )
    md.append(
        f"| **缓存读取 Token (Cache Read)** | `{format_tokens_m(ov['total_cached_read'])}` | `{format_num(ov['total_cached_read'])}` | 命中的上下文缓存 Token（大幅提速省成本） |"
    )
    md.append(
        f"| **总提示词输入量 (Full Prompt)** | `{format_tokens_m(ov['total_full_input'])}` | `{format_num(ov['total_full_input'])}` | 逻辑总输入量（未缓存+缓存） |"
    )
    md.append(f"| **上下文缓存命中率 (Cache Hit Rate)** | **`{ov['cache_hit_rate']:.2f}%`** | - | 缓存占总输入提示词比例 |")
    md.append(f"| **总生成输出 Token (Total Output)** | `{format_tokens_m(ov['total_output'])}` | `{format_num(ov['total_output'])}` | 模型生成的总 Token |")
    md.append(
        f"| ↳ **思维链思考 Token (Thinking)** | `{format_tokens_m(ov['total_thinking'])}` | `{format_num(ov['total_thinking'])}` | 推理思考消耗的 Token 数量 |"
    )
    md.append(
        f"| ↳ **最终文本输出 Token (Response)** | `{format_tokens_m(ov['total_response'])}` | `{format_num(ov['total_response'])}` | 实际呈现给用户的正文 Token |"
    )
    md.append(f"| **平均单次响应耗时 (Avg Latency)** | `{ov['avg_latency']:.2f} 秒` | - | 模型接口往返平均耗时 |")
    md.append("\n---\n")

    # 客户端工具分布统计
    if clients:
        md.append("## 二、 工具类型分布统计 (Tool/Client Breakdown)\n")
        md.append("| 工具类型 (Client Type) | 独立会话数 | 模型调用次数 | 未缓存输入 (M) | 缓存命中输入 (M) | 模型输出 (M) | 消耗总 Token (M) | 占比 |")
        md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for cl in clients:
            pct = (cl["total_tokens"] / ov["total_tokens"] * 100) if ov["total_tokens"] > 0 else 0.0
            md.append(
                f"| **`{cl['client_type']}`** | {format_num(cl['conv_count'])} 个 | {format_num(cl['calls'])} 次 | "
                f"{format_tokens_m(cl['input_tokens'])} | {format_tokens_m(cl['cached_tokens'])} | "
                f"{format_tokens_m(cl['output_tokens'])} | **{format_tokens_m(cl['total_tokens'])}** | `{pct:.2f}%` |"
            )
        md.append("\n---\n")

    # 运行环境分布统计
    if envs:
        md.append("## 三、 运行环境分布统计 (Environment Distribution)\n")
        md.append("| 运行环境 (Environment) | 独立会话数 | 模型调用次数 | 未缓存输入 (M) | 缓存命中输入 (M) | 模型输出 (M) | 消耗总 Token (M) | 占比 |")
        md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
        for e in envs:
            pct = (e["total_tokens"] / ov["total_tokens"] * 100) if ov["total_tokens"] > 0 else 0.0
            md.append(
                f"| **`{e['env']}`** | {format_num(e['conv_count'])} 个 | {format_num(e['calls'])} 次 | "
                f"{format_tokens_m(e['input_tokens'])} | {format_tokens_m(e['cached_tokens'])} | "
                f"{format_tokens_m(e['output_tokens'])} | **{format_tokens_m(e['total_tokens'])}** | `{pct:.2f}%` |"
            )
        md.append("\n---\n")

    md.append("## 四、 模型维度统计 (Token Usage by Model)\n")
    md.append(
        "| 模型名称 (Model Name) | 调用次数 | 未缓存输入 (M) | 缓存命中输入 (M) | 输出 (M) (思考/正文) | 总消耗 (M) | 缓存命中率 | 平均耗时 |"
    )
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    for m in stats["models"]:
        full_inp = m["input_tokens"] + m["cached_tokens"]
        c_rate = (m["cached_tokens"] / full_inp * 100) if full_inp > 0 else 0.0
        avg_lat = (m["total_latency"] / m["latency_count"]) if m["latency_count"] > 0 else 0.0
        out_detail = f"{format_tokens_m(m['output_tokens'])}<br><small>({format_tokens_m(m['thinking_tokens'])} 思考 / {format_tokens_m(m['response_tokens'])} 正文)</small>"
        md.append(
            f"| **{m['model_name']}**<br>`{m['model_id']}` "
            f"| {format_num(m['calls'])} "
            f"| {format_tokens_m(m['input_tokens'])} "
            f"| {format_tokens_m(m['cached_tokens'])} "
            f"| {out_detail} "
            f"| **{format_tokens_m(m['total_tokens'])}** "
            f"| {c_rate:.1f}% "
            f"| {avg_lat:.2f}s |"
        )
    md.append("\n---\n")

    md.append("## 五、 时间维度与精准小时级用量统计 (Time Trends & Sub2 Hourly Analytics)\n")

    # Sub2 风格小时级明细 (最近 24 个活跃小时)
    hourly_list = stats.get("hourly", [])
    if hourly_list:
        md.append("### 1. 小时级精准用量明细 (Sub2 风格 · 最近活跃时段)\n")
        md.append("| 时间段 | 调用轮次 | 未缓存输入 (M) | 缓存命中 (M) | 生成输出 (M) | 总消耗 (M) | 缓存命中率 | 主要模型 |")
        md.append("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |")
        recent_hours = hourly_list[-24:]
        for h in reversed(recent_hours):
            h_full = h["input_tokens"] + h["cached_tokens"]
            h_crate = (h["cached_tokens"] / h_full * 100) if h_full > 0 else 0.0
            top_m = max(h["models"].items(), key=lambda x: x[1])[0] if h["models"] else "Unknown"
            md.append(
                f"| `{h['hour']}` "
                f"| {format_num(h['calls'])} "
                f"| {format_tokens_m(h['input_tokens'])} "
                f"| {format_tokens_m(h['cached_tokens'])} "
                f"| {format_tokens_m(h['output_tokens'])} "
                f"| **{format_tokens_m(h['total_tokens'])}** "
                f"| {h_crate:.1f}% "
                f"| {top_m} |"
            )
        md.append("\n")

    md.append("### 2. 最近 30 天每日消耗走势 (Recent 30 Days Daily Trend)\n")
    md.append("| 日期 | 调用次数 | 未缓存输入 (M) | 缓存命中输入 (M) | 输出 Token (M) | 当日总 Token (M) |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
    recent_daily = stats["daily"][-30:]
    for d in recent_daily:
        md.append(
            f"| {d['date']} "
            f"| {format_num(d['calls'])} "
            f"| {format_tokens_m(d['input_tokens'])} "
            f"| {format_tokens_m(d['cached_tokens'])} "
            f"| {format_tokens_m(d['output_tokens'])} "
            f"| **{format_tokens_m(d['total_tokens'])}** |"
        )
    md.append("\n")

    md.append("### 3. 月度消耗统计 (Monthly Trend)\n")
    md.append("| 月份 | 调用次数 | 未缓存输入 (M) | 缓存命中读取 (M) | 生成输出 (M) (思考) | 月度消耗总 Token (M) |")
    md.append("| :--- | :---: | :---: | :---: | :---: | :---: |")
    for mo in stats["monthly"]:
        md.append(
            f"| **{mo['month']}** "
            f"| {format_num(mo['calls'])} "
            f"| {format_tokens_m(mo['input_tokens'])} "
            f"| {format_tokens_m(mo['cached_tokens'])} "
            f"| {format_tokens_m(mo['output_tokens'])} ({format_tokens_m(mo['thinking_tokens'])}) "
            f"| **{format_tokens_m(mo['total_tokens'])}** |"
        )
    md.append("\n---\n")

    md.append("## 六、 会话维度深度分析 (Top 20 Most Consumed Conversations)\n")
    md.append("| 排名 | 会话 ID | 工具类型 | 运行环境 | 交互轮次 | 主要使用模型 | 起止时间 | 缓存命中率 | 会话消耗总 Token (M) |")
    md.append("| :---: | :--- | :---: | :---: | :---: | :--- | :--- | :---: | :---: |")
    for rank, c in enumerate(stats["conversations"][:20], 1):
        top_model = max(c["models"].items(), key=lambda x: x[1])[0] if c["models"] else "Unknown"
        start_str = datetime.fromtimestamp(c["first_time"]).strftime("%m-%d %H:%M") if c["first_time"] else "N/A"
        end_str = datetime.fromtimestamp(c["last_time"]).strftime("%m-%d %H:%M") if c["last_time"] else "N/A"
        full_inp = c["input_tokens"] + c["cached_tokens"]
        c_rate = (c["cached_tokens"] / full_inp * 100) if full_inp > 0 else 0.0
        env_badge = f"`{c.get('env', 'windows')}`"
        client_badge = f"`{c.get('client_type', 'IDE')}`"
        md.append(
            f"| {rank} "
            f"| `{c['conv_id'][:16]}...` "
            f"| {client_badge} "
            f"| {env_badge} "
            f"| {format_num(c['calls'])} 轮 "
            f"| {top_model} "
            f"| {start_str} ~ {end_str} "
            f"| {c_rate:.1f}% "
            f"| **{format_tokens_m(c['total_tokens'])}** |"
        )
    md.append("\n---\n")

    md.append("## 七、 Token 组成结构与 Prompt 细分剖析 (Token Composition & Breakdown)\n")
    if pb["count_with_breakdown"] > 0:
        tot_breakdown = pb["total_system_prompt"] + pb["total_tools"] + pb["total_chat_messages"]
        sp_pct = (pb["total_system_prompt"] / tot_breakdown * 100) if tot_breakdown > 0 else 0
        tl_pct = (pb["total_tools"] / tot_breakdown * 100) if tot_breakdown > 0 else 0
        cm_pct = (pb["total_chat_messages"] / tot_breakdown * 100) if tot_breakdown > 0 else 0
        md.append(f"> 基于包含详细细分指标的 `{format_num(pb['count_with_breakdown'])}` 次请求采样统计：\n")
        md.append("| Prompt 组成模块 | 累计 Token 消耗 (M) | 精确 Token 数 | 占比 | 作用与特点 |")
        md.append("| :--- | :---: | :---: | :---: | :--- |")
        md.append(
            f"| **系统预设 (System Prompt)** | `{format_tokens_m(pb['total_system_prompt'])}` | `{format_num(pb['total_system_prompt'])}` | **{sp_pct:.1f}%** | 包含 Agent 身份、代码规范、上下文规则 |"
        )
        md.append(
            f"| **工具定义 (Tools / MCPs)** | `{format_tokens_m(pb['total_tools'])}` | `{format_num(pb['total_tools'])}` | **{tl_pct:.1f}%** | 各种内置文件、终端工具及 MCP 工具的 JSON Schema |"
        )
        md.append(
            f"| **对话历史 (Chat Messages)** | `{format_tokens_m(pb['total_chat_messages'])}` | `{format_num(pb['total_chat_messages'])}` | **{cm_pct:.1f}%** | 用户问题、模型中间思考过程与工具调用历史记录 |"
        )
        md.append("\n")

    md.append("### Token 宏观结构占比\n")
    inp_pct = (ov["total_input_uncached"] / ov["total_tokens"] * 100) if ov["total_tokens"] > 0 else 0
    cac_pct = (ov["total_cached_read"] / ov["total_tokens"] * 100) if ov["total_tokens"] > 0 else 0
    out_pct = (ov["total_output"] / ov["total_tokens"] * 100) if ov["total_tokens"] > 0 else 0
    thk_pct = (ov["total_thinking"] / ov["total_output"] * 100) if ov["total_output"] > 0 else 0

    md.append(f"- **未缓存直接输入 (Uncached Input)**：占总 Token 的 **{inp_pct:.1f}%** ({format_tokens_m(ov['total_input_uncached'])})")
    md.append(f"- **上下文缓存命中 (Cache Read)**：占总 Token 的 **{cac_pct:.1f}%** ({format_tokens_m(ov['total_cached_read'])})")
    md.append(f"- **模型生成输出 (Model Output)**：占总 Token 的 **{out_pct:.1f}%** ({format_tokens_m(ov['total_output'])})")
    md.append(f"  - 在所有输出中，**思维链深度思考 (Thinking Tokens)** 占比达 **{thk_pct:.1f}%** ({format_tokens_m(ov['total_thinking'])})")
    return "\n".join(md)


def render_html_dashboard(
    stats_by_client: Dict[str, Any],
    scanned_targets: Optional[List[Dict[str, str]]] = None,
    server_port: int = 8765
) -> str:
    """生成具备实时监控与 Sub2 风格小时级精准用量分析的交互式 HTML 仪表盘"""
    stats_json_str = json.dumps(stats_by_client, ensure_ascii=False)
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # 优先使用优化稿前端: Antigravity Token 仪表盘（优化稿）.html
    candidates = [
        os.path.join(base_dir, "Antigravity Token 仪表盘（优化稿）.html"),
        os.path.join(base_dir, "Antigravity_Token_Dashboard.html"),
    ]
    template_content = None
    for cand in candidates:
        if cand and os.path.exists(cand):
            try:
                with open(cand, "r", encoding="utf-8") as f:
                    template_content = f.read()
                if "const STATS_BY_CLIENT" in template_content:
                    break
            except Exception:
                continue

    if not template_content:
        return f"<!DOCTYPE html><html><body><script>const STATS_BY_CLIENT = {stats_json_str};</script><h1>Antigravity Token Dashboard</h1></body></html>"

    # 动态注入最新全量统计数据源
    pattern = r"const\s+STATS_BY_CLIENT\s*=\s*\{.*?\};"
    replacement = f"const STATS_BY_CLIENT = {stats_json_str};"
    rendered, count = re.subn(pattern, replacement, template_content, count=1)
    if count == 0:
        pattern_multi = r"const\s+STATS_BY_CLIENT\s*=\s*\{[\s\S]*?\n\s*\};"
        rendered = re.sub(pattern_multi, replacement, template_content, count=1)

    # 动态适配当前实际服务端端口 (供 file:/// 本地协议访问时连接)
    if server_port and server_port != 8765:
        rendered = re.sub(
            r"'http://127\.0\.0\.1:8765'",
            f"'http://127.0.0.1:{server_port}'",
            rendered
        )

    return rendered


class ReusableThreadingTCPServer(socketserver.ThreadingTCPServer):
    """支持端口快速复用与守护线程的 TCPServer"""
    allow_reuse_address = True
    daemon_threads = True


class TokenDashboardHTTPHandler(http.server.SimpleHTTPRequestHandler):
    """支持 CORS、静态资源、/api/stats、/api/status 与 /api/refresh 的实时 HTTP 处理器"""
    def __init__(self, *args, live_server=None, **kwargs):
        self.live_server = live_server
        super().__init__(*args, **kwargs)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/", "/Antigravity_Token_Dashboard.html", "/Antigravity Token 仪表盘（优化稿）.html", urllib.parse.quote("/Antigravity Token 仪表盘（优化稿）.html")):
            dashboard_file = os.path.join(self.live_server.work_dir, "Antigravity Token 仪表盘（优化稿）.html")
            if not os.path.exists(dashboard_file):
                dashboard_file = os.path.join(self.live_server.work_dir, "Antigravity_Token_Dashboard.html")
            if os.path.exists(dashboard_file):
                with open(dashboard_file, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(content)))
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                try:
                    self.wfile.write(content)
                except (ConnectionResetError, BrokenPipeError):
                    pass
                return

        if path == "/api/stats":
            data = self.live_server.get_stats_json()
            encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except (ConnectionResetError, BrokenPipeError):
                pass
            return

        if path in ("/api/refresh", "/api/stats/refresh"):
            query = urllib.parse.parse_qs(parsed.query)
            force = query.get("force", ["0"])[0] in ("1", "true", "yes")
            data = self.live_server.trigger_refresh(force=force)
            encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except (ConnectionResetError, BrokenPipeError):
                pass
            return

        if path in ("/api/status", "/api/health"):
            status_data = {
                "status": "online",
                "port": getattr(self.live_server, "actual_port", self.live_server.port),
                "last_updated": self.live_server.last_update_time,
                "total_records": len(getattr(self.live_server, "all_records", []) or []),
                "total_calls": len(getattr(self.live_server, "all_records", []) or []),
            }
            encoded = json.dumps(status_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except (ConnectionResetError, BrokenPipeError):
                pass
            return

        if path == "/api/records":
            qs = urllib.parse.parse_qs(parsed.query)
            try:
                page = max(1, int(qs.get("page", ["1"])[0]))
            except ValueError:
                page = 1
            try:
                page_size = max(1, min(200, int(qs.get("page_size", qs.get("pageSize", ["20"]))[0])))
            except ValueError:
                page_size = 20

            search = qs.get("search", [""])[0].strip().lower()
            model_filter = qs.get("model", [""])[0].strip()
            client_filter = qs.get("client", [""])[0].strip()
            env_filter = qs.get("env", [""])[0].strip()
            start_date = qs.get("start_date", [""])[0].strip()
            end_date = qs.get("end_date", [""])[0].strip()
            sort_by = qs.get("sort_by", ["time"])[0].strip()
            order = qs.get("order", ["desc"])[0].strip()

            all_recs = getattr(self.live_server, "all_records", []) or []
            filtered = []
            for r in all_recs:
                if client_filter and client_filter != "ALL" and r.get("client_type") != client_filter:
                    continue
                if env_filter and env_filter != "ALL" and r.get("env") != env_filter:
                    continue
                if model_filter and model_filter != "ALL":
                    m_name = (r.get("model_name") or "").lower()
                    m_id = (r.get("model_id") or "").lower()
                    m_fil = model_filter.lower()
                    if m_fil not in m_name and m_fil not in m_id:
                        continue
                if search:
                    txt = f"{r.get('conv_id', '')} {r.get('model_name', '')} {r.get('model_id', '')} {r.get('client_type', '')}".lower()
                    if search not in txt:
                        continue
                ts_val = r.get("timestamp")
                if ts_val:
                    r_day = datetime.fromtimestamp(ts_val).strftime("%Y-%m-%d")
                    if start_date and r_day < start_date:
                        continue
                    if end_date and r_day > end_date:
                        continue
                filtered.append(r)

            # 排序
            reverse = (order.lower() != "asc")
            if sort_by in ("tokens", "total_tokens"):
                filtered.sort(key=lambda x: x.get("total_tokens") or 0, reverse=reverse)
            elif sort_by in ("latency", "latency_sec"):
                filtered.sort(key=lambda x: x.get("latency_sec") or 0.0, reverse=reverse)
            elif sort_by in ("cost", "actual_cost"):
                filtered.sort(key=lambda x: calculate_record_cost(x)["actual_cost"], reverse=reverse)
            else:
                filtered.sort(key=lambda x: x.get("timestamp") or 0, reverse=reverse)

            total = len(filtered)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paged = filtered[start_idx:end_idx]

            out_records = []
            for r in paged:
                c_info = r.get("cost_info") or calculate_record_cost(r)
                inp = r.get("input_tokens", 0)
                cac = r.get("cached_tokens", 0)
                out = r.get("output_tokens", 0)
                thk = r.get("thinking_tokens", 0)
                rsp = r.get("response_tokens", 0)
                full_inp = inp + cac
                c_rate = round(cac / full_inp * 100, 1) if full_inp > 0 else 0.0
                lat = r.get("latency_sec") or 0.0
                ts_val = r.get("timestamp")
                dt_str = datetime.fromtimestamp(ts_val).strftime("%Y-%m-%d %H:%M:%S") if ts_val else "--"
                out_records.append({
                    "conv_id": r.get("conv_id", "--"),
                    "step_idx": r.get("step_idx", 0),
                    "time": dt_str,
                    "client": r.get("client_type", "Antigravity IDE"),
                    "env": r.get("env", "Windows"),
                    "model": r.get("model_name", "Unknown"),
                    "model_id": r.get("model_id", ""),
                    "latency": f"{lat:.2f}s" if lat > 0 else "--",
                    "latency_sec": lat,
                    "input_tokens": inp,
                    "cached_tokens": cac,
                    "output_tokens": out,
                    "thinking_tokens": thk,
                    "response_tokens": rsp,
                    "total_tokens": r.get("total_tokens", inp + cac + out),
                    "actual_cost": c_info["actual_cost"],
                    "account_cost": c_info.get("account_cost", c_info["actual_cost"]),
                    "standard_cost": c_info["standard_cost"],
                    "savings": c_info["savings"],
                    "cost_str": format_usd(c_info["actual_cost"], 4),
                    "savings_str": format_usd(c_info["savings"], 4),
                    "cache_rate": c_rate,
                    "status": 200,
                    "inp_rate": c_info.get("inp_rate", 0.75),
                    "out_rate": c_info.get("out_rate", 3.75),
                    "cac_rate": c_info.get("cac_rate", 0.075),
                })

            resp = {
                "code": 200,
                "total": total,
                "page": page,
                "page_size": page_size,
                "records": out_records
            }
            encoded = json.dumps(resp, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except (ConnectionResetError, BrokenPipeError):
                pass
            return

        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/api/refresh", "/api/stats/refresh"):
            query = urllib.parse.parse_qs(parsed.query)
            force = query.get("force", ["0"])[0] in ("1", "true", "yes")
            data = self.live_server.trigger_refresh(force=force)
            encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except (ConnectionResetError, BrokenPipeError):
                pass
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        # 静默常规访问日志，避免控制台刷屏
        pass


class TokenLiveServer:
    """轻量级实时 HTTP 服务与后台文件监听器"""
    def __init__(self, port: int = 8765, host: str = "127.0.0.1", work_dir: str = "."):
        self.port = port
        self.actual_port = port
        self.host = host
        self.work_dir = os.path.abspath(work_dir)
        self.running = False
        self.stats_lock = threading.Lock()
        self.latest_stats = {}
        self.all_records = []
        self.last_update_time = 0
        self.server = None

    def get_stats_json(self):
        with self.stats_lock:
            return self.latest_stats

    def trigger_refresh(self, force=False):
        self.scan_and_update(force=force)
        return self.get_stats_json()

    def scan_and_update(self, force=False):
        records = collect_all_data(use_cache=not force)
        if not records:
            return
        self.all_records = records
        overall_stats = generate_multi_dimensional_stats(records)
        stats_by_client = {"ALL": overall_stats}
        client_types = set(r.get("client_type", "Antigravity IDE") for r in records)
        for c_name in client_types:
            sub_records = [r for r in records if r.get("client_type") == c_name]
            stats_by_client[c_name] = generate_multi_dimensional_stats(sub_records)

        with self.stats_lock:
            self.latest_stats = stats_by_client
            self.last_update_time = time.time()

        # 原子写入磁盘（临时文件 + os.replace，规避并发文件锁与读取半写入冲突）
        try:
            html_content = render_html_dashboard(stats_by_client, server_port=self.actual_port)
            for fname in ["Antigravity Token 仪表盘（优化稿）.html", "Antigravity_Token_Dashboard.html"]:
                target_html = os.path.join(self.work_dir, fname)
                tmp_html = f"{target_html}.tmp"
                with open(tmp_html, "w", encoding="utf-8") as f:
                    f.write(html_content)
                os.replace(tmp_html, target_html)

            json_path = os.path.join(self.work_dir, "token_stats_summary.json")
            tmp_json = f"{json_path}.tmp"
            with open(tmp_json, "w", encoding="utf-8") as f:
                json.dump(stats_by_client, f, ensure_ascii=False, indent=2)
            os.replace(tmp_json, json_path)
        except Exception:
            pass

    def watcher_loop(self):
        last_check_mtimes = {}
        last_db_scan_time = 0
        cached_dbs = []
        while self.running:
            time.sleep(2.0)
            try:
                now_t = time.time()
                # 每 10 秒刷新一次全局数据库探测列表，平时仅轮询已知会话文件与 WAL 缓冲状态，大幅降低磁盘 I/O 开销
                if now_t - last_db_scan_time > 10.0 or not cached_dbs:
                    cached_dbs = scan_all_conversation_dbs()
                    last_db_scan_time = now_t

                current_mtimes = {}
                changed = False
                for item in cached_dbs:
                    p = item["path"]
                    try:
                        st = os.stat(p)
                        m1, s1 = st.st_mtime, st.st_size
                    except Exception:
                        m1, s1 = 0, 0

                    wal_p = f"{p}-wal"
                    try:
                        st_w = os.stat(wal_p)
                        m2, s2 = st_w.st_mtime, st_w.st_size
                    except Exception:
                        m2, s2 = 0, 0

                    current_mtimes[p] = (m1, s1, m2, s2)

                if last_check_mtimes and current_mtimes != last_check_mtimes:
                    changed = True
                last_check_mtimes = current_mtimes

                if changed:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] ⚡ 检测到 Antigravity 会话更新 (含 WAL 写入)，正在聚合最新 Token...")
                    self.scan_and_update(force=False)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] [OK] 最新 Token 统计已自动同步至前端仪表盘！")
            except Exception:
                pass

    def start(self, initial_stats, all_records: Optional[List[Dict[str, Any]]] = None, open_browser: bool = True):
        self.latest_stats = initial_stats
        self.all_records = all_records or []
        self.last_update_time = time.time()
        self.running = True

        actual_port = self.port
        for p in range(self.port, self.port + 10):
            try:
                handler = lambda *args, **kwargs: TokenDashboardHTTPHandler(
                    *args, live_server=self, directory=self.work_dir, **kwargs
                )
                self.server = ReusableThreadingTCPServer((self.host, p), handler)
                actual_port = p
                self.actual_port = p
                break
            except OSError:
                continue

        if not self.server:
            print(f"[错误] 无法绑定端口 {self.port}~{self.port+10}")
            return

        server_url = f"http://{self.host}:{actual_port}"
        print("\n" + "=" * 68)
        print(f"🟢 [实时监控已启动] 本地监控服务运行于: {server_url}")
        print("   - 秒级自动监控本地 Antigravity 会话变动与 Token 消耗 (支持 WAL 实时捕捉)")
        print("   - 前端仪表盘已开启实时自动同步与 Sub2 风格小时级精准用量分析")
        print("   - 统计单位: M Tokens (百万)")
        print("   - 按 Ctrl+C 可停止监控服务")
        print("=" * 68 + "\n")

        watcher_thread = threading.Thread(target=self.watcher_loop, daemon=True)
        watcher_thread.start()

        if open_browser:
            try:
                webbrowser.open(server_url)
                print(f"[OK] 已在默认浏览器中打开实时监控仪表盘: {server_url}")
            except Exception:
                pass

        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\n正在停止 Token 实时监控服务...")
        finally:
            self.running = False
            self.server.shutdown()
            self.server.server_close()
            print("[OK] 服务已安全停止。")


def export_all(
    base_dirs: Optional[Union[str, List[Union[str, Dict[str, str]]]]] = None,
    output_dir: Optional[str] = None,
    use_cache: bool = True,
    start_server: bool = True,
    port: int = 8765,
    open_browser: bool = True
):
    """主执行函数：自动收集聚合数据并导出完整报告，默认开启实时后台监控服务"""
    if output_dir is None:
        output_dir = os.path.dirname(os.path.abspath(__file__))

    scanned_targets = discover_all_data_dirs() if base_dirs is None else None

    records = collect_all_data(base_dirs, use_cache=use_cache)
    if not records:
        print("未找到任何 Token 记录！")
        return

    # 全量总览统计
    overall_stats = generate_multi_dimensional_stats(records)

    # 按工具类型分拆聚合统计 (供前端顶层切换联动)
    stats_by_client = {
        "ALL": overall_stats
    }
    client_types = set(r.get("client_type", "Antigravity IDE") for r in records)
    for c_name in client_types:
        sub_records = [r for r in records if r.get("client_type") == c_name]
        stats_by_client[c_name] = generate_multi_dimensional_stats(sub_records)

    # 1. 导出 Markdown 报告
    report_md_path = os.path.join(output_dir, "Antigravity_Token_Report.md")
    md_content = render_markdown_report(overall_stats, scanned_targets)
    with open(report_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[OK] 统计报告已保存至: {os.path.abspath(report_md_path)}")

    # 1.2 导出 HTML 仪表盘
    dashboard_html_path = os.path.join(output_dir, "Antigravity Token 仪表盘（优化稿）.html")
    html_content = render_html_dashboard(stats_by_client, scanned_targets, server_port=port)
    for fname in ["Antigravity Token 仪表盘（优化稿）.html", "Antigravity_Token_Dashboard.html"]:
        target_html = os.path.join(output_dir, fname)
        with open(target_html, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[OK] 可视化仪表盘已保存至: {os.path.abspath(target_html)}")

    # 2. 导出全量 JSON 数据
    json_path = os.path.join(output_dir, "token_stats_summary.json")
    for s_item in stats_by_client.values():
        for c in s_item.get("conversations", []):
            if isinstance(c.get("models"), defaultdict):
                c["models"] = dict(c["models"])

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(stats_by_client, f, ensure_ascii=False, indent=2)
    print(f"[OK] 结构化统计数据已保存至: {os.path.abspath(json_path)}")

    # 3. 导出精简明细 CSV 文件
    csv_path = os.path.join(output_dir, "token_records_detailed.csv")
    csv_fields = [
        "conv_id",
        "client_type",
        "env",
        "step_idx",
        "timestamp",
        "model_name",
        "model_id",
        "input_tokens",
        "cached_tokens",
        "output_tokens",
        "thinking_tokens",
        "response_tokens",
        "total_tokens",
        "latency_sec",
        "request_id",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            writer.writerow(r)
    print(f"[OK] 明细 CSV 数据已保存至: {os.path.abspath(csv_path)}")

    # 4. 打印终端控制台摘要 (全以 M 为核心单位)
    ov = overall_stats["overview"]
    envs = overall_stats.get("environments", [])
    clients = overall_stats.get("clients", [])
    print("\n" + "=" * 68)
    print("           ANTIGRAVITY TOKEN 跨环境与多工具统计总览")
    print("=" * 68)
    print(f"核心统计单位       : M Tokens (百万)")
    print(f"有效数据库会话总数 : {ov['total_conversations']}")
    print(f"LLM 响应总调用次数 : {format_num(ov['total_calls'])}")
    print(f"消耗总 Token 数量   : {format_tokens_m(ov['total_tokens'])} Tokens ({format_num(ov['total_tokens'])})")
    print(f"  ├─ 未缓存输入   : {format_tokens_m(ov['total_input_uncached'])} Tokens ({format_num(ov['total_input_uncached'])})")
    print(f"  ├─ 缓存读取输入 : {format_tokens_m(ov['total_cached_read'])} Tokens ({format_num(ov['total_cached_read'])}, 缓存率: {ov['cache_hit_rate']:.1f}%)")
    print(
        f"  └─ 模型生成输出 : {format_tokens_m(ov['total_output'])} Tokens (思考: {format_tokens_m(ov['total_thinking'])}, 正文: {format_tokens_m(ov['total_response'])})"
    )
    print(f"平均单次响应耗时   : {ov['avg_latency']:.2f} 秒")
    print("-" * 68)
    print("Sub2 今日与峰值用量分析 (Hourly Overview):")
    print(f"  ├─ 今日累计用量 : {format_tokens_m(ov.get('today_tokens', 0))} Tokens ({format_num(ov.get('today_calls', 0))} 次调用)")
    print(f"  └─ 历史峰值小时 : {format_tokens_m(ov.get('peak_hour_tokens', 0))} Tokens (时段: {ov.get('peak_hour', 'N/A')})")
    print("-" * 68)
    print("工具类型分布 (Client Breakdown):")
    for cl in clients:
        pct = (cl["total_tokens"] / ov["total_tokens"] * 100) if ov["total_tokens"] > 0 else 0.0
        print(
            f" - {cl['client_type']:<18} : {format_tokens_m(cl['total_tokens']):>12} Tokens ({pct:>5.1f}%) | {cl['conv_count']:>3} 会话 | {cl['calls']:>5} 次调用"
        )
    print("-" * 68)
    print("跨运行环境分布 (Environment Distribution):")
    for e in envs:
        pct = (e["total_tokens"] / ov["total_tokens"] * 100) if ov["total_tokens"] > 0 else 0.0
        print(
            f" - {e['env']:<18} : {format_tokens_m(e['total_tokens']):>12} Tokens ({pct:>5.1f}%) | {e['conv_count']:>3} 会话 | {e['calls']:>5} 次调用"
        )
    print("-" * 68)
    print("各模型消耗分布 (Top Models):")
    for m in overall_stats["models"][:8]:
        print(
            f" - {m['model_name']:<30} : {format_tokens_m(m['total_tokens']):>12} Tokens ({m['calls']:>4} 次调用, 平均耗时 {m['total_latency'] / max(1, m['latency_count']):.2f}s)"
        )
    print("=" * 68 + "\n")

    # 5. 启动实时监控服务或静态打开
    if start_server:
        live_srv = TokenLiveServer(port=port, work_dir=output_dir)
        live_srv.start(stats_by_client, all_records=records, open_browser=open_browser)
    elif open_browser:
        dashboard_abs_path = os.path.abspath(dashboard_html_path)
        try:
            if os.name == "nt":
                os.startfile(dashboard_abs_path)
            else:
                webbrowser.open(f"file:///{dashboard_abs_path.replace(os.sep, '/')}")
            print(f"[OK] 已在系统默认浏览器中打开静态仪表盘: {dashboard_abs_path}")
        except Exception:
            pass


if __name__ == "__main__":
    force_refresh = any(arg in sys.argv for arg in ["--no-cache", "--force-refresh", "-f"])
    once_mode = any(arg in sys.argv for arg in ["--once", "--export-only", "--no-server", "-1"])
    no_browser = any(arg in sys.argv for arg in ["--no-browser", "-n"])
    port = 8765
    for arg in sys.argv:
        if arg.startswith("--port="):
            try:
                port = int(arg.split("=")[1])
            except ValueError:
                pass
        elif arg == "--port" and sys.argv.index(arg) + 1 < len(sys.argv):
            try:
                port = int(sys.argv[sys.argv.index(arg) + 1])
            except ValueError:
                pass

    if force_refresh:
        print("[提示] 收到强制刷新参数，将跳过本地增量缓存进行全量重新解析...")

    export_all(
        use_cache=not force_refresh,
        start_server=not once_mode,
        port=port,
        open_browser=not no_browser
    )
