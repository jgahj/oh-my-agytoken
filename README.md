# 📊 Oh My AGY Token (oh-my-agytoken)

<p align="center">
  <b>Google Antigravity 本地 Token 统计、秒级实时监控与多维度可视化仪表盘</b>
</p>

<p align="center">
  <a href="https://github.com/jgahj/oh-my-agytoken/stargazers"><img src="https://img.shields.io/github/stars/jgahj/oh-my-agytoken?style=flat-square" alt="Stars"></a>
  <a href="https://github.com/jgahj/oh-my-agytoken/network/members"><img src="https://img.shields.io/github/forks/jgahj/oh-my-agytoken?style=flat-square" alt="Forks"></a>
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg?style=flat-square" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/Dependencies-Zero%20(Standard%20Lib)-success.svg?style=flat-square" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20WSL2-orange.svg?style=flat-square" alt="Platform">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg?style=flat-square" alt="License"></a>
</p>

<p align="center">
  <b>简体中文</b> | <a href="README_EN.md">English</a>
</p>

---

## 📖 项目简介

**Oh My AGY Token** (`oh-my-agytoken`) 是一款专为 **Google Antigravity**（Antigravity IDE 与 Antigravity CLI）打造的高性能、轻量级、零第三方依赖的 Token 统计、消费分析与实时监控工具。

工具能够全自动穿透发现 Windows 与 WSL2 环境中的 Antigravity 本地会话库，基于纯 Python 原生解码底层 Protobuf 二进制流，毫秒级提取全量模型调用的 Token 用量、思维链（Thinking Tokens）、缓存命中率（Prompt Caching）与耗时指标，并提供**秒级实时热同步服务**、**Sub2API 官方计费折算**以及**单文件可视化交互式仪表盘**。

---

## 📸 交互式仪表盘预览

仪表盘采用单文件自包含（Single-file Self-contained）架构，完全支持离线打开与随处分享，内置双主题持久化记忆与全图维度联动：

### 1. ☀️ 暖阳米黄风格（默认）
适合日间办公与长时间数据查阅，舒缓温润不刺眼：

![暖阳米黄仪表盘预览](assets/dashboard_preview.png)

### 2. 🌙 极客暗黑风格（可选）
深邃 Slate 暗蓝灰搭配科技高光，图表色彩自适应换色：

![极客暗黑仪表盘预览](assets/dashboard_preview_dark.png)

### ✨ 核心特性一览
- **⚡ 秒级实时监听与热同步**：内置轻量本地实时服务，感知 SQLite 主库与 WAL 缓冲文件变动，编写代码与对话时看板数据自动无感刷新。
- **🌐 顶层全局维度联动**：一键在 `全部工具 (All)`、`Antigravity IDE` 与 `Antigravity CLI` 之间切换，全图联动。
- **💰 Sub2API 与官方价卡计费折算**：内置 Gemini 3.1 Pro、Gemini 3.8/3.7/3.6 Flash、Flash-Lite、Claude Opus 4.6 等全系模型价卡，精确计算实际消费、账号成本与缓存节省金额。
- **📅 黄金分割年度贡献热力图**：左侧各模型消耗环形图与右侧 GitHub 风格年度 52 周热力图紧凑并排，支持年份切换与鼠标悬浮详情。
- **📈 全景每日消耗走势图**：横向全宽展示每日消耗，集成日期快捷胶囊、起止日选择器、模型多选以及**实时动态求和统计卡片**。
- **🔍 深度指标多维透视**：精确展示 Windows vs WSL2 环境分布、上下文缓存节省率、思维链思考 Token（Thinking Tokens）与响应耗时分布。
- **📦 零第三方依赖**：100% 基于 Python 3.8+ 标准库实现，无需 `pip install` 任何第三方包，开箱即用。

---

## 🚀 快速上手与使用说明

### 1. 环境准备
- **操作系统**：Windows 10 / 11、Linux (含 WSL2) 或 macOS
- **Python 环境**：Python 3.8 及以上（推荐 Python 3.10 ~ 3.14，支持系统自带 `python` 或极速包管理器 `uv`）
- **依赖说明**：**零外部依赖**！无需安装任何第三方库。

---

### 2. 运行方式

#### 方式一：Windows 一键双击运行（最便捷，推荐）
直接双击项目根目录下的 **`run_stats.bat`**：
1. 自动适配 Python 运行环境（优先调用 Python 3.14/3.12 或系统默认 Python）；
2. 自动开启 Windows 控制台 UTF-8 (CP65001) 编码支持；
3. 自动扫描全量会话库并生成最新报表；
4. **启动本地实时监控服务（默认端口 8765）并自动唤起默认浏览器展现仪表盘**；
5. **实时监听**：保持终端黑窗口常驻，您在 Antigravity 中产生新对话或调用时，仪表盘将在数秒内自动同步最新 Token 用量！

> 💡 提示：随时按下 `Ctrl + C` 即可安全停止监控服务。

---

#### 方式二：命令行标准运行
在项目根目录下打开终端，执行以下命令：

```bash
# 使用系统 Python 运行（启动实时监控服务并自动打开仪表盘）
python export_report.py

# 或使用 uv 极速运行
uv run export_report.py
```

---

### 3. 命令行参数详解

`export_report.py` 提供了丰富的控制参数，满足各种自动化脚本或 CI/CD 场景：

| 参数 | 简写 | 默认值 | 说明 |
| :--- | :---: | :---: | :--- |
| `--once` / `--export-only` / `--no-server` | `-1` | 否 | **单次导出模式**：仅生成静态报告与 HTML，不启动后台常驻监控服务 |
| `--no-cache` / `--force-refresh` | `-f` | 否 | **强制全量重扫**：跳过本地增量缓存，强制重新解析全部历史数据库 |
| `--no-browser` | `-n` | 否 | **静默模式**：执行完成后不自动唤起系统浏览器 |
| `--port <端口号>` | `--port=8765` | `8765` | **自定义端口**：指定本地实时监控服务的 HTTP 监听端口 |

#### 常用命令示例：

```bash
# 1. 快速导出一次静态报告（适合只需查看结果或生成文件后立即退出的场景）
python export_report.py --once

# 2. 强制忽略本地缓存，全量重新扫描所有历史数据库并打开看板
python export_report.py -f

# 3. 指定服务运行在 8888 端口且不自动弹出浏览器
python export_report.py --port 8888 -n

# 4. 仅在控制台快速输出多维统计分析数据（终端简报）
python token_analyzer.py
```

---

## 📁 产物文件说明

运行分析后，项目根目录将生成以下文件：

| 文件名称 | 格式 | 说明与用途 |
| :--- | :---: | :--- |
| **`Antigravity_Token_Dashboard.html`** | HTML | **现代化交互式单文件仪表盘**。内嵌完整可视化交互逻辑，可脱机离线浏览或发送给他人分享。 |
| **`Antigravity_Token_Report.md`** | Markdown | **结构化深度统计报告**。包含用量总览、会话消耗排行 Top 20、模型分布及 Prompt 构成分析。 |
| **`token_records_detailed.csv`** | CSV | **单次请求明细表**。记录每条 LLM 调用的精确时间戳、模型名称、未缓存输入、缓存读取、输出与耗时，适合 Excel / Pandas 二次加工。 |
| **`token_stats_summary.json`** | JSON | **全量统计聚合数据**。按客户端类型、模型、日期汇总的结构化数据字典。 |
| **`.token_cache.json`** | JSON | **本地增量指纹缓存**（已自动加入 `.gitignore`）。记录历史数据库特征，实现秒级增量热加载。 |

---

## 💰 计费模型与价格折算

本项目在 `pricing.py` 中内置了针对主流模型的精确计费规则，严格对齐 Google 官方价卡与 **Sub2API** 计费配置：

- **Gemini 3.1 Pro**：
  - 上下文 $\le$ 200k：输入 \$2.00 / 1M，输出 \$12.00 / 1M，缓存读取 \$0.20 / 1M
  - 上下文 $>$ 200k：输入 \$4.00 / 1M，输出 \$18.00 / 1M，缓存读取 \$0.40 / 1M
- **Gemini 3.8 / 3.7 / 3.6 Flash 系列**：
  - 输入 \$0.75 / 1M，输出 \$3.75 / 1M，缓存读取 \$0.075 / 1M
- **Gemini 3.5 Flash-Lite**：输入 \$0.30 / 1M，输出 \$2.50 / 1M，缓存读取 \$0.03 / 1M
- **Gemini 3.1 Flash-Lite**：输入 \$0.25 / 1M，输出 \$1.50 / 1M，缓存读取 \$0.025 / 1M
- **Gemini 2.5 Flash-Lite**：输入 \$0.10 / 1M，输出 \$0.40 / 1M，缓存读取 \$0.01 / 1M
- **Claude Opus 4.6 (Thinking)**：输入 \$5.00 / 1M，输出 \$25.00 / 1M，缓存读取 \$0.50 / 1M

系统不仅能精确核算总消费金额，还能精准统计由于 **Prompt Caching** 为您节约的实际美金金额！

---

## ⚙️ 技术实现架构

整个分析与监听流水线由 5 个核心技术环节紧密协作完成：

```text
  ┌─────────────────────────────────────────────────────────────┐
  │                 1. 跨平台/跨机型自适应扫描探测                     │
  │   Windows: C:\Users\*\.gemini\antigravity-ide\conversations\*.db │
  │   WSL2:    通过 Windows 注册表毫秒级枚举发行版 + UNC 路径穿透      │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                 2. SQLite 无锁只读并发接入 (I/O 安全)           │
  │         URI: file:{db_path}?mode=ro                         │
  │         - 避免与正在交互的 Antigravity IDE 产生写锁冲突          │
  │         - 动态关联 steps.metadata 与 gen_metadata 精确时间戳    │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │                 3. 自研原生 Protobuf 二进制解码器             │
  │   解析 gen_metadata 表中的二进制 blob 数据                     │
  │   - Wire Type 0 (Varint) / Wire Type 2 (Length-delimited)   │
  │   - 零 .proto 编译依赖，纯 Python 原生提取 Token 与思考字段    │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │         4. ⚡ 双重指纹增量缓存与 WAL 活跃监听 (提速 15x+)        │
  │   - 综合校验主库与 WAL 缓冲文件的 (mtime, size) 双重特征指纹   │
  │   - 历史无变更库直接毫秒级读取缓存，活跃会话秒级增量热同步      │
  └──────────────────────────────┬──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │              5. 多维聚合、实时 HTTP 同步与单文件仪表盘渲染        │
  │   输出交互式 HTML / Markdown 报表，并提供秒级轮询热更新服务     │
  └─────────────────────────────────────────────────────────────┘
```

### 1. 零配置跨平台自适应探测 (`token_analyzer.py`)
- **Windows**：自动枚举当前用户与 `%SystemDrive%\Users` 下所有真实用户的 Antigravity 数据库，彻底杜绝机器名硬编码。
- **WSL2**：直接读取 Windows 原生注册表项 `HKCU\Software\Microsoft\Windows\CurrentVersion\Lxss`，耗时 `< 0.001s` 瞬间枚举 WSL2 发行版，并通过 Windows 原生 UNC 路径（`\\wsl.localhost\<distro>\...`）安全读取 Linux 数据。

### 2. 纯 Python 原生 Protobuf Wire 解码 (`proto_decoder.py`)
- 不依赖 Google 官方 `protobuf` 编译器或第三方动态库；
- 严格遵循 Google Protocol Buffers Wire Format 标准规范，通过高效位运算解码 Varint，递归解析嵌套消息，精准提取 `prompt_tokens`、`cached_content_token_count`、`candidates_token_count`、`thinking_token_count` 等内部字段。

### 3. WAL 缓冲感知与双重指纹增量缓存
- 针对正在交互的会话，同时监控 SQLite 主数据库与其对应的 `-wal` 预写日志文件；
- 历史未改动数据库毫秒级命中缓存，单次扫描解析耗时从全量扫描的数十秒降低至 **< 1 秒**。

---

## 📂 项目结构

```text
oh-my-agytoken/
├── pricing.py                     # 核心计费引擎：官方与 Sub2API 价卡对齐与成本换算
├── proto_decoder.py              # 原生 Protobuf 二进制协议解析器 (Varint/Wire 解码)
├── token_analyzer.py             # 跨环境自适应扫描器、SQLite 访问与增量指纹缓存
├── export_report.py              # 数据聚合、报告生成与本地实时监控服务核心
├── run_stats.bat                 # Windows 一键启动实时监控与仪表盘脚本
├── Antigravity_Token_Dashboard.html # 生成的高性能可视化交互式仪表盘 (单文件自包含)
├── Antigravity_Token_Report.md   # 生成的结构化分析报告 (Markdown 格式)
├── assets/                       # 仪表盘双主题高清预览截图
│   ├── dashboard_preview.png     # 暖阳米黄主题预览截图
│   └── dashboard_preview_dark.png # 极客暗黑主题预览截图
├── .gitignore                    # Git 忽略配置 (自动排除敏感缓存与明细数据)
├── LICENSE                       # MIT 开源许可证
├── README.md                     # 中文使用说明与架构文档
└── README_EN.md                  # 英文使用说明文档
```

---

## ❓ 常见问题与排查 (FAQ)

### Q1: 运行后提示字符编码错误或中文显示乱码？
- 项目已在代码层全面适配 `sys.stdout.reconfigure(encoding="utf-8")`。
- 如果在旧版 Windows CMD 中手动运行，请先在终端输入 `chcp 65001` 切换为 UTF-8 编码，或直接使用配套的 `run_stats.bat` 运行。

### Q2: 统计时 Antigravity IDE 正在使用，会冲突报错吗？
- 完全不会！底层采用 SQLite `mode=ro` 只读连接模式，与正在运行的 Antigravity IDE 互不干扰，绝无锁表或死锁风险。

### Q3: 为什么部分早期记录显示为 `Unknown` 模型？
- 极少部分早期测试版本的历史记录中未携带完整的模型枚举元数据，解析器会自动将其归类为 `Unknown` 并单独统计，不会影响整体 Token 用量与图表展示。

---

## 📄 开源许可证

本项目基于 [MIT License](LICENSE) 协议开源。
