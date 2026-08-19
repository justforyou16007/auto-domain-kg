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

**技能文件**：`skills/worker/socratic_inquiry.md`

### 第二步：领域模式生成
强智能体根据用户关注点创建领域模式：
- 实体类型及其属性
- 关系类型及其约束
- 继承层次结构
- 模式保存至 `tmp/schema_definition.json`

**技能文件**：`skills/worker/schema_creation.md`

### 第三步：实体采集 + 三元组抽取
弱智能体为各实体采集新闻/证据：
1. **实体采集**：使用 `news_adapter` 搜索每个实体的相关新闻
2. **模式修正**：根据实际发现修正模式
3. **三元组抽取**：抽取（实体，关系，实体）三元组并附上证据

**技能文件**：`skills/worker/entity_collection.md`、`skills/worker/schema_refinement.md`、`skills/worker/triple_extraction.md`

### 第四步：图谱持久化
将模式和实例持久化到 Neo4j：
- 创建模式节点
- 创建实体节点（自动生成向量嵌入）
- 创建关系
- 通过 HAS_SCHEMA 关系将实体链接到模式

**技能文件**：`skills/worker/graph_persistence.md`

### 第五步：Verifier 审计（自动驱动循环）
Verifier（Codex）审计图谱并驱动修复：
1. **模式审计**：完整性、一致性、继承关系、冗余检测
2. **图谱结构审计**：连通性、孤立节点、密度评估
3. **GraphRAG 验证**：图谱能否回答领域相关问题？
4. **证据审计**：多源一致性、证据质量
5. **任务相关性审计**：图谱是否覆盖了用户关注点？

Worker 将自动修复发现的问题。循环持续进行，直至所有审计项目通过。

**技能文件**：`skills/verifier/schema_audit.md`、`skills/verifier/graph_structure_audit.md`、`skills/verifier/graphrag_validation.md`、`skills/verifier/evidence_audit.md`、`skills/verifier/task_relevance_audit.md`

### 第六步：完成
- 构建结果摘要
- 统计信息（实体数量、关系数量、模式数量）
- 提醒每日更新和风险评估功能

## 每日更新流程

1. 加载技能文件：`skills/updater/daily_update.md`
2. 扫描与实体相关的最新新闻（当日日期）
3. 判断是否需要更新图谱（模式或实例层面）
4. 将新闻发送给 Worker 智能体进行局部图谱更新
5. 运行 Verifier 验证更新结果

## 风险评估功能

风险是**用户关注驱动**的（而非自动传播）。智能体遍历图谱，评估某个实体上的风险事件是否会影响用户关注的主题。

### 核心原则
- **图谱结构至关重要**：考虑替代路径、冗余性、中心度
- **智能体引导**：智能体遍历图谱并对每条路径进行推理
- **证据支撑**：每项风险评估均引用证据来源
- **风险等级**：NONE（无风险）、LOW（低）、MEDIUM（中）、HIGH（高）、CRITICAL（严重）

### 示例
假设实体 A（某供应商）发生工厂火灾，智能体将：
1. 加载实体 A 周围的子图
2. 检查是否存在替代供应商（冗余性）
3. 遍历至用户关注的实体
4. 根据图谱结构确定风险等级
5. 更新受影响实体的风险字段

**技能文件**：`skills/risk/risk_assessment.md`

## Python 模块说明

### `neo4j_client.py`
Neo4j 连接管理、模式/实例的增删改查、向量索引操作以及多跳 Cypher 查询。支持密码认证和无认证两种模式。

### `embedding.py`
外部 API 的 Embedding 客户端（兼容 OpenAI / vLLM）。支持批量嵌入、缓存，以及可配置的端点、模型和维度。

### `evidence_store.py`
证据存储模块，以 JSONL 文件形式保存在 `data/evidence/` 目录下，附带来源追踪信息。每条记录包含 entity_id、text_slice、source_url 和时间戳。

### `news_adapter.py`
抽象 `NewsAdapter` 接口及 `GoogleSearchNewsAdapter` 实现。可扩展——通过继承 `NewsAdapter` 实现自定义适配器。

### `graph_ops.py`
高层图谱操作，整合 Neo4j、Embedding 和证据存储。提供 `create_entity_node()` 等复合操作（自动生成嵌入并链接到模式）。

### `risk_assessment.py`
风险字段管理与智能体引导的图谱遍历风险评估。风险等级：NONE、LOW、MEDIUM、HIGH、CRITICAL。

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
│   ├── worker/             # Worker 技能文件（6 个）
│   ├── verifier/           # Verifier 技能文件（5 个）
│   ├── updater/            # 更新器技能文件
│   └── risk/               # 风险评估技能文件
├── data/
│   └── evidence/           # 证据 JSONL 文件
├── tmp/                    # 临时工作文件
└── tests/                  # pytest 测试文件（6 个）
```

## 许可证

MIT