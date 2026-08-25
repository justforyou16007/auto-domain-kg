[English](README.md) | [中文](README.zh.md)

# Auto Domain KG

一个基于 **GAN 风格的多智能体框架**，用于用户关注驱动的领域模式生成与知识图谱构建。

## 架构

### GAN 模式

```
                    ┌──────────────────┐
                    │   Main Agent     │
                    │  (Claude Code)   │
                    │  Orchestrates    │
                    └──────┬───────────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
   ┌───────────────┐ ┌───────────┐ ┌───────────────┐
   │  Worker       │ │  Verifier │ │   Updater     │
   │  (Generator)  │ │(Discrim.) │ │   (Daily)     │
   │  Claude Code  │ │  Codex    │ │  Claude Code  │
   └───────┬───────┘ └───────────┘ └───────────────┘
           │
   ┌───────┴───────┐
   │  Weak Agents  │
   │  (Collectors) │
   └───────────────┘
```

- **Worker（生成器）**：使用 Claude Code 构建和管理图谱，包含用于模式管理的强智能体和用于三元组抽取的弱智能体。
- **Verifier（判别器）**：使用 Codex 审计图谱（检查模式、结构、证据、相关性），并驱动 Worker 修复发现的问题。完全自动化运行，无需用户确认。
- **Main Agent**：Claude Code 交互式会话，通过 Paseo MCP 工具协调两侧的运作。

### 技术栈

| 组件 | 技术 |
|-----------|-----------|
| **运行时** | Python 3.12+，使用 uv 管理 |
| **图数据库** | Neo4j 5.x（向量索引，Cypher 多跳查询） |
| **向量嵌入** | 外部 API（兼容 vLLM / OpenAI） |
| **GraphRAG** | 纯 Neo4j 向量检索 + Cypher 多跳查询 |
| **编排层** | Paseo MCP（多智能体编排） |
| **Worker** | Claude Code CLI |
| **Verifier** | Codex CLI |

## Schema/Instance 层级分离

本项目的核心设计原则之一是严格区分 **Schema 层**与 **Instance 层**。两者职责不同，不可混用。

- **Schema 层** —— **仅**建模概念级的实体类型和关系类型（如 "Storage Device"、"Vehicle"、"Supplier"、"Raw Material"）。它定义本体：存在哪些类别的事物以及它们如何关联，绝不包含具体实例名称。
- **Instance 层** —— **仅**建模具体实体（如 "TSMC"、"Xiaomi SU7"、"Lithium Carbonate"）来填充本体。每个 Instance 实体通过 `HAS_SCHEMA` 关系链接到其 Schema 类型，并携带 `source_url` / `source_text` 来源信息以便追溯。

**关系校验**：Instance 到 Instance 的关系必须依据 Schema 到 Schema 的关系进行校验。例如，若 Schema 定义了 `Supplier` ―[`SUPPLIES`]→ `Material`，则 Instance 三元组 `TSMC` ―[`SUPPLIES`]→ `Silicon Wafers` 是合法的。没有匹配 Schema 关系的 Instance 关系会被标记为 **Schema extension needed**（需扩展 Schema），与 Schema 定义冲突的则标记为 **Schema inconsistency**（Schema 不一致）。

**Schema 层级**：Schema 类型可以通过 `SUBCLASS_OF` 关系形成继承层级（如 `Supplier` 是 `Organization` 的子类）。合并实体时，系统可沿此层级向上追溯，合并到父级 Schema 层级。

## 安装

### 前置依赖

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) 包管理器
- Node.js 18+（用于 Paseo 和 Claude Code CLI）
- Neo4j 5.x（本地或 Docker 部署）

### 快速安装

```bash
# 克隆仓库
git clone <repo-url> auto-domain-kg
cd auto-domain-kg

# 运行安装脚本
bash install.sh .
```

安装脚本将自动完成以下步骤：
1. 检查并安装 Paseo（`npm install -g @getpaseo/paseo`）
2. 检查 Claude Code CLI（若缺失则给出警告）
3. 检查 Codex CLI（若缺失则给出警告）
4. 检查 Neo4j 是否可用
5. 创建项目目录结构
6. 生成 Paseo MCP 配置文件 `.mcp.json`
7. 初始化 Python uv 项目并安装依赖
8. 输出安装摘要和下一步指引

### 手动安装

```bash
# 创建项目目录结构
mkdir -p src/auto_domain_kg skills/worker skills/verifier skills/updater skills/risk
mkdir -p data/evidence tmp tests

# 初始化 Python 项目
uv init --name "auto-domain-kg" --python ">=3.12"
uv add "neo4j>=5.0.0" "httpx>=0.27.0"
uv add --dev "pytest>=8.0.0" "pytest-asyncio>=0.24.0" "pytest-mock>=3.14.0"

# 运行测试
uv run pytest
```

## 配置

### 环境变量

| 变量 | 说明 | 默认值 |
|----------|-------------|---------|
| `NEO4J_URI` | Neo4j 连接 URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j 用户名 | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j 密码（空字符串表示无认证） | `` |
| `NEO4J_DATABASE` | Neo4j 数据库名 | `neo4j` |
| `EMBEDDING_ENDPOINT` | Embedding API 端点 | `http://localhost:8000/v1/embeddings` |
| `EMBEDDING_MODEL` | Embedding 模型名称 | `BAAI/bge-m3` |
| `EMBEDDING_DIMENSIONS` | Embedding 向量维度 | `768` |
| `EMBEDDING_API_KEY` | Embedding API 密钥 | `` |
| `GOOGLE_API_KEY` | Google Custom Search API 密钥 | — |
| `GOOGLE_CSE_ID` | Google Custom Search Engine ID | — |
| `EVIDENCE_DIR` | 证据存储目录 | `data/evidence` |

### 模型提供商配置（CLAUDE.md）

编辑 `CLAUDE.md` 文件，设置你的模型提供商：

```markdown
## Provider Configuration
# Worker（Claude Code）— 用户填入可用的模型
worker_provider: claude/claude-sonnet-4-20250514
# 信息采集智能体（Claude Code）
collector_provider: claude/claude-sonnet-4-20250514
# Verifier（Codex）
verifier_provider: codex/gpt-4o
```

格式说明：`<cli>/<model-name>`，其中 `cli` 为 `claude` 或 `codex`，`model-name` 为该 CLI 可用的模型名称。

## 六步构建流程

### 第一步：苏格拉底式问询
通过结构化提问提取用户关注点。智能体将询问以下内容：
- **领域**：知识图谱服务于哪个行业/领域？
- **实体**：关键实体类型及其属性
- **关系**：实体之间的关联方式
- **风险关注**：需要监控哪些风险
- **更新频率**：多久扫描一次新数据

**技能文件**：`skills/worker/socratic_inquiry/SKILL.md`

### 第二步：迭代式模式生成与实体采集
迭代式研究驱动的发现循环，将模式生成、实体采集和修正整合在一起。`schema_creation` 技能遵循一个 9 步迭代发现流程：

a. **加载用户领域信息** —— 从 `CLAUDE.md` 读取用户的领域与关注点。
b. **搜索** —— 使用网络搜索 API 研究当前子主题或实体簇，重点关注概念类型与业务关系。
c. **创建模式与关系** —— 定义 Schema 级实体类型和关系类型（仅概念级），合并到 `tmp/schema_definition.json`。
d. **抽取实体与关系** —— 以搜索结果为证据，抽取匹配新 Schema 类型的具体 Instance 实体。
e. **GraphRAG 检索** —— 对每个 Schema 类型和 Instance 实体，进行向量检索 + 多跳子图探索，查找图中已有的相关节点。
f. **语义合并** —— 合并语义相似的 Schema/Instance 节点（如 "Xiaomi Auto" 与 "Xiaomi SU7" 可能指向同一实体），采用层级感知合并，可通过 `SUBCLASS_OF` 提升到父级 Schema。
g. **持久化到图谱** —— 将当前批次的 Schema + Instance + Relationships 保存到 Neo4j。
h. **发现完整性缺口** —— 分析图结构找出缺失的实体、缺失的连接和未覆盖的子主题，生成新的探索查询。
i. **重复** —— 用新查询从步骤 **b** 重新开始，直到搜索结果与发现的实体不再对用户领域相关的实体产生实质性影响。

每次迭代同时会采集证据：弱智能体搜索本次迭代实体的新闻/文章并保存证据到 `data/evidence/`（每个实体需 2-3 个独立来源），然后基于证据修正部分模式并执行跨迭代一致性检查。

**技能文件**：`skills/worker/schema_creation/SKILL.md`、`skills/worker/entity_collection/SKILL.md`、`skills/worker/schema_refinement/SKILL.md`

### 第三步：三元组抽取
弱智能体从采集的证据中抽取（实体，关系，实体）三元组并附上证据。抽取由 Schema 层引导：仅抽取具体的 Instance 实体，并依据 Schema 到 Schema 的关系校验 Instance 关系。三元组在多个独立来源之间进行交叉验证——单一来源的事实被标记为**低置信度**，冲突的事实标记为需人工复核，关键事实要求 3 个以上独立来源。

**技能文件**：`skills/worker/triple_extraction/SKILL.md`

### 第四步：图谱持久化
将 Schema（概念本体）和 Instance 实体持久化到 Neo4j：
- 创建 Schema 节点（仅包含概念级信息）
- 创建实体节点（自动生成向量嵌入），携带 `source_url` / `source_text` 来源信息，并通过 `HAS_SCHEMA` 链接到 Schema
- 创建关系，持久化前依据 Schema 校验 Instance 关系
- **Schema/Instance 节点的语义合并**：使用 GraphRAG（向量检索 + 多跳子图探索）查找图中已有的相关节点，合并语义相似的节点（层级感知——可通过 `SUBCLASS_OF` 合并到父级 Schema 层级）
- **完整性缺口发现**：分析图结构找出缺失的实体、缺失的连接和未覆盖的子主题，生成新查询反馈到第二步
- 设置向量索引，验证嵌入与图连通性

**技能文件**：`skills/worker/graph_persistence/SKILL.md`

### 第五步：Verifier 审计（自动驱动循环）
Verifier（Codex）审计图谱并驱动修复：
1. **模式审计**：完整性、一致性、继承关系、冗余检测
2. **图谱结构审计**：连通性、孤立节点、密度评估
3. **GraphRAG 验证**：图谱能否回答领域相关问题？
4. **证据审计**：多源一致性、证据质量
5. **任务相关性审计**：图谱是否覆盖了用户关注点？

Worker 将自动修复发现的问题。循环持续进行，直至所有审计项目通过。

**技能文件**：`skills/verifier/schema_audit/SKILL.md`、`skills/verifier/graph_structure_audit/SKILL.md`、`skills/verifier/graphrag_validation/SKILL.md`、`skills/verifier/evidence_audit/SKILL.md`、`skills/verifier/task_relevance_audit/SKILL.md`

### 第六步：完成
- 构建结果摘要
- 统计信息（实体数量、关系数量、模式数量）
- 提醒每日更新和风险评估功能

## 每日更新流程

1. 加载技能文件：`skills/updater/daily_update/SKILL.md`
2. 扫描与实体相关的最新新闻（当日日期）
3. **更新前对多源新闻进行交叉验证** —— 使用多源交叉验证确认事实，丢弃或标记单一来源/冲突的报告
4. 判断是否需要更新图谱（模式或实例层面）
5. 将新闻发送给 Worker 智能体进行局部图谱更新。当新实体不适合当前 Schema 层级时，使用**层级感知的 Schema 合并**——沿 `SUBCLASS_OF` 向上追溯，合并到父级 Schema 层级
6. 当检测到风险事件时，通过 `RiskAssessment.run_full_analysis()` 触发完整的 6 步风险分析流程
7. 运行 Verifier 验证更新结果

## 风险评估功能 — 6 步新闻→图谱影响分析

风险是**用户关注驱动**的（而非自动传播）。风险评估技能采用完整的 6 步流程，将每日新闻转化为带有图谱影响分析的结构化风险报告。

### 6 步流程

1. **接收每日新闻** — 从 `daily_update` 技能接收新闻列表
2. **提取新闻事件** — 提取结构化事件（事件类型、描述、提及实体、严重程度提示）
3. **关联证据片段** — 从新闻中提取支持性文本片段，保存到 `data/evidence/`
4. **GraphRAG 事件到节点分析** — 向量检索 + 多跳子图探索，查找受影响的图谱节点
5. **DAG 影响追溯** — 通过 Cypher 查询沿有向关系追溯下游影响
6. **生成影响报告** — 使用外部模板（`templates/{domain}_domain_report_template.md`）生成报告到 `reports/`

### 核心原则
- **图谱结构至关重要**：考虑替代路径、冗余性、中心度
- **语义相关性**：第 4 步使用语义匹配（而非关键词匹配）
- **DAG 感知追溯**：第 5 步尊重图的方向性
- **模板驱动**：报告模板外置到 `templates/` 目录
- **证据支撑**：每项风险评估均引用证据来源
- **风险等级**：NONE（无风险）、LOW（低）、MEDIUM（中）、HIGH（高）、CRITICAL（严重）

### 示例
假设实体 A（某供应商）发生工厂火灾，流程将：
1. 接收关于工厂火灾的新闻文章
2. 提取事件：`{event_type: "factory_fire", description: "...", severity_hint: "high"}`
3. 从文章中提取证据片段
4. 向量检索找到相关图谱节点（供应商 A、产品、客户）
5. DAG 追溯发现下游影响（生产延迟、运输中断）
6. 生成结构化风险报告 `reports/{date}_supply_chain_risk_report.md`

**技能文件**：`skills/risk/risk_assessment/SKILL.md`
**Python 模块**：`src/auto_domain_kg/risk_assessment.py`

## Python 模块说明

### `neo4j_client.py`
Neo4j 连接管理、模式/实例的增删改查、向量索引操作以及多跳 Cypher 查询。支持密码认证和无认证两种模式。实体节点携带 `source_url` 和 `source_text` 字段用于来源追溯；`create_entity_node()` 可通过可选参数接收这些字段。通过 Schema 节点之间的 `SUBCLASS_OF` 关系支持 Schema 层级：`create_schema_hierarchy()`、`get_schema_ancestors()`、`get_schema_descendants()`、`find_common_ancestor()`、`get_schema_with_ancestors()`。

### `embedding.py`
外部 API 的 Embedding 客户端（兼容 OpenAI / vLLM）。支持批量嵌入、缓存，以及可配置的端点、模型和维度。

### `evidence_store.py`
证据存储模块，以 JSONL 文件形式保存在 `data/evidence/` 目录下，附带来源追踪信息。每条记录包含 entity_id、text_slice、source_url 和时间戳。多源交叉验证方法：`get_source_urls()`（获取所有唯一来源 URL）、`get_source_count()`（统计独立来源数量）、`cross_validate()`（检查多个来源是否一致或冲突）、`is_well_supported()`（检查是否满足最小来源数量要求）。

### `news_adapter.py`
抽象 `NewsAdapter` 接口及 `GoogleSearchNewsAdapter` 实现。可扩展——通过继承 `NewsAdapter` 实现自定义适配器。

### `graph_ops.py`
高层图谱操作，整合 Neo4j、Embedding 和证据存储。提供 `create_entity_node()` 等复合操作（自动生成嵌入并链接到 Schema，可通过 `source_url` / `source_text` 参数接收来源信息）。层级感知合并操作：`find_merge_target_with_hierarchy()`（层级感知的合并目标查找，沿 `SUBCLASS_OF` 向上追溯）和 `merge_entity_to_parent_schema()`（将实体合并到父级 Schema 层级）。

### `risk_assessment.py`
风险字段管理、6步新闻→图谱影响分析流程及智能体引导的图谱遍历。方法包括：`extract_events_from_news()`、`associate_evidence()`、`graphrag_event_search()`、`trace_dag_impact()`、`generate_report()`、`run_full_analysis()`。风险等级：NONE、LOW、MEDIUM、HIGH、CRITICAL。

## 扩展新的新闻适配器

1. 创建 `NewsAdapter` 的子类：
   ```python
   from auto_domain_kg.news_adapter import NewsAdapter, NewsItem

   class MyNewsAdapter(NewsAdapter):
       async def search_news(self, query, language="en",
                              date_from=None, date_to=None, max_results=10):
           # 你的实现代码
           return [NewsItem(...)]
   ```

2. 在采集流程中使用你的适配器。

## Neo4j 部署

### Docker（推荐）

```bash
docker run -d --name neo4j \
  -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=none \
  neo4j:5
```

### 本地安装
请参考 [Neo4j 安装指南](https://neo4j.com/docs/operations-manual/current/installation/)。

## 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest tests/test_neo4j_client.py

# 详细输出模式
uv run pytest -v

# 带覆盖率报告
uv run pytest --cov=src/auto_domain_kg
```

## 启动会话

```bash
cd auto-domain-kg
claude --mcp
```

Paseo MCP 守护进程将自动注入编排工具（如 spawn_agent、send_message、wait_for_agent 等）到 Claude Code 会话中。

## 项目结构

```
auto-domain-kg/
├── install.sh              # 安装脚本
├── .mcp.json               # Paseo MCP 配置文件
├── CLAUDE.md               # Worker 配置与用户关注点
├── pyproject.toml          # Python 项目配置文件（uv 管理）
├── README.md               # 英文版说明
├── README.zh.md            # 中文版说明
├── src/
│   └── auto_domain_kg/
│       ├── __init__.py
│       ├── neo4j_client.py
│       ├── embedding.py
│       ├── news_adapter.py
│       ├── evidence_store.py
│       ├── graph_ops.py
│       └── risk_assessment.py
├── skills/
│   ├── worker/             # Worker 技能文件（6 个目录）
│   │   ├── socratic_inquiry/SKILL.md
│   │   ├── schema_creation/SKILL.md
│   │   ├── entity_collection/SKILL.md
│   │   ├── schema_refinement/SKILL.md
│   │   ├── triple_extraction/SKILL.md
│   │   └── graph_persistence/SKILL.md
│   ├── verifier/           # Verifier 技能文件（5 个目录）
│   │   ├── schema_audit/SKILL.md
│   │   ├── graph_structure_audit/SKILL.md
│   │   ├── graphrag_validation/SKILL.md
│   │   ├── evidence_audit/SKILL.md
│   │   └── task_relevance_audit/SKILL.md
│   ├── updater/            # 更新器技能文件
│   │   └── daily_update/SKILL.md
│   └── risk/               # 风险评估技能文件
│       └── risk_assessment/SKILL.md
├── templates/              # 报告模板
│   └── default_domain_report_template.md
├── reports/                # 生成的风险报告
├── data/
│   └── evidence/           # 证据 JSONL 文件
├── tmp/                    # 临时工作文件
└── tests/                  # pytest 测试文件（7 个）
```

## 许可证

MIT