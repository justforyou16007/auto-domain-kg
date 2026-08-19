# Auto Domain KG

A **GAN-style multi-agent framework** for user-concern-driven domain schema generation and knowledge graph construction.

## Architecture

### GAN Pattern

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

- **Worker (Generator)**: Uses Claude Code to build and manage the graph. Contains strong agents for schema management and weak agents for triple extraction.
- **Verifier (Discriminator)**: Uses Codex to audit the graph (schema, structure, evidence, relevance) and drive the worker to fix issues. Fully automated — no user confirmation needed.
- **Main Agent**: The Claude Code interactive session that orchestrates both sides via Paseo MCP tools.

### Tech Stack

| Component | Technology |
|-----------|-----------|
| **Runtime** | Python 3.12+ with uv |
| **Graph Database** | Neo4j 5.x (vector index, Cypher multi-hop) |
| **Embeddings** | External API (vLLM/OpenAI compatible) |
| **GraphRAG** | Pure Neo4j vector retrieval + Cypher multi-hop |
| **Orchestration** | Paseo MCP (multi-agent orchestration) |
| **Worker** | Claude Code CLI |
| **Verifier** | Codex CLI |

## Installation

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager
- Node.js 18+ (for Paseo and Claude Code CLI)
- Neo4j 5.x (local or Docker)

### Quick Install

```bash
# Clone the repository
git clone <repo-url> auto-domain-kg
cd auto-domain-kg

# Run the installer
bash install.sh .
```

The installer will:
1. Check/install Paseo (`npm install -g @getpaseo/paseo`)
2. Check for Claude Code CLI (warning if missing)
3. Check for Codex CLI (warning if missing)
4. Check for Neo4j availability
5. Create the project directory structure
6. Generate `.mcp.json` for Paseo MCP
7. Initialize Python uv project with dependencies
8. Print a summary and next steps

### Manual Setup

```bash
# Create project structure
mkdir -p src/auto_domain_kg skills/worker skills/verifier skills/updater skills/risk
mkdir -p data/evidence tmp tests

# Initialize Python project
uv init --name "auto-domain-kg" --python ">=3.12"
uv add "neo4j>=5.0.0" "httpx>=0.27.0"
uv add --dev "pytest>=8.0.0" "pytest-asyncio>=0.24.0" "pytest-mock>=3.14.0"

# Run tests
uv run pytest
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password (empty = no-auth) | `` |
| `NEO4J_DATABASE` | Neo4j database name | `neo4j` |
| `EMBEDDING_ENDPOINT` | Embedding API endpoint | `http://localhost:8000/v1/embeddings` |
| `EMBEDDING_MODEL` | Embedding model name | `BAAI/bge-m3` |
| `EMBEDDING_DIMENSIONS` | Embedding dimensions | `768` |
| `EMBEDDING_API_KEY` | Embedding API key | `` |
| `GOOGLE_API_KEY` | Google Custom Search API key | — |
| `GOOGLE_CSE_ID` | Google Custom Search Engine ID | — |
| `EVIDENCE_DIR` | Evidence storage directory | `data/evidence` |

### Provider Configuration (CLAUDE.md)

Edit `CLAUDE.md` to set your provider models:

```markdown
## Provider Configuration
# Worker (Claude Code) — user fills in available model
worker_provider: claude/claude-sonnet-4-20250514
# Information collection agents (Claude Code)
collector_provider: claude/claude-sonnet-4-20250514
# Verifier (Codex)
verifier_provider: codex/gpt-4o
```

Format: `<cli>/<model-name>` where `cli` is `claude` or `codex`, and `model-name` is an available model for that CLI.

## 6-Step Construction Flow

### Step 1: Socratic Inquiry
Extract user concerns through structured questioning. The agent asks about:
- **Domain**: What industry/domain is the KG for?
- **Entities**: Key entity types and their properties
- **Relationships**: How entities connect
- **Risk concerns**: What risks to monitor
- **Update frequency**: How often to scan for new data

**Skill**: `skills/worker/socratic_inquiry.md`

### Step 2: Domain Schema Generation
A strong agent creates the domain schema based on user concerns:
- Entity types with properties
- Relationship types with constraints
- Inheritance hierarchies
- Schema is saved to `tmp/schema_definition.json`

**Skill**: `skills/worker/schema_creation.md`

### Step 3: Entity Collection + Triple Extraction
Weak sub-agents collect news/evidence for entities:
1. **Entity Collection**: Search for news about each entity using `news_adapter`
2. **Schema Refinement**: Refine schema based on actual findings
3. **Triple Extraction**: Extract (entity, relation, entity) triples with evidence

**Skills**: `skills/worker/entity_collection.md`, `skills/worker/schema_refinement.md`, `skills/worker/triple_extraction.md`

### Step 4: Graph Persistence
Persist schema and instances to Neo4j:
- Create schema nodes
- Create entity nodes with auto-embedding
- Create relationships
- Link entities to schema via HAS_SCHEMA

**Skill**: `skills/worker/graph_persistence.md`

### Step 5: Verifier Audit (Auto-Driven Loop)
The verifier (Codex) audits the graph and drives fixes:
1. **Schema Audit**: Completeness, consistency, inheritance, redundancy
2. **Graph Structure Audit**: Connectivity, orphan nodes, density
3. **GraphRAG Validation**: Can the graph answer domain questions?
4. **Evidence Audit**: Multi-source consistency, quality
5. **Task Relevance Audit**: Does the graph address user concerns?

The worker automatically fixes issues. Loop continues until all audits pass.

**Skills**: `skills/verifier/schema_audit.md`, `skills/verifier/graph_structure_audit.md`, `skills/verifier/graphrag_validation.md`, `skills/verifier/evidence_audit.md`, `skills/verifier/task_relevance_audit.md`

### Step 6: Completion
- Summary of what was built
- Statistics (entity count, relation count, schema count)
- Reminder of daily update and risk assessment features

## Daily Update Flow

1. Load skill: `skills/updater/daily_update.md`
2. Scan for entity-related news (today's date)
3. Determine if graph update is needed (schema or instance)
4. Send news to worker agent for partial graph update
5. Run verifier to validate the update

## Risk Assessment Feature

Risk is **user-concern-driven** (NOT automatic propagation). An agent walks the graph to assess if a risk event on one entity affects the user's concern topic.

### Key Principles
- **Graph structure matters**: Consider alternatives, redundancy, centrality
- **Agent-guided**: The agent walks the graph and reasons about each path
- **Evidence-backed**: Each risk assessment cites evidence sources
- **Risk levels**: NONE, LOW, MEDIUM, HIGH, CRITICAL

### Example
If Entity A (a supplier) has a factory fire, the agent:
1. Loads the subgraph around Entity A
2. Checks if there are alternative suppliers (redundancy)
3. Traverses to the user's concern entity
4. Determines risk level based on graph structure
5. Updates risk fields on affected entities

**Skill**: `skills/risk/risk_assessment.md`

## Python Modules

### `neo4j_client.py`
Neo4j connection management, schema/instance CRUD, vector index operations, and multi-hop Cypher queries. Supports both password auth and no-auth.

### `embedding.py`
External API embedding client (OpenAI-compatible / vLLM). Supports batch embedding, caching, and configurable endpoint/model/dimensions.

### `evidence_store.py`
Evidence storage as JSONL files in `data/evidence/` with provenance tracking. Each record includes entity_id, text_slice, source_url, and timestamps.

### `news_adapter.py`
Abstract `NewsAdapter` interface and `GoogleSearchNewsAdapter` implementation. Extensible — implement your own adapter by subclassing `NewsAdapter`.

### `graph_ops.py`
High-level graph operations combining Neo4j, embedding, and evidence store. Provides composite operations like `create_entity_node()` (auto-embeds and links to schema).

### `risk_assessment.py`
Risk field management and agent-guided graph traversal for risk assessment. Risk levels: NONE, LOW, MEDIUM, HIGH, CRITICAL.

## Extending with New News Adapters

1. Create a subclass of `NewsAdapter`:
   ```python
   from auto_domain_kg.news_adapter import NewsAdapter, NewsItem

   class MyNewsAdapter(NewsAdapter):
       async def search_news(self, query, language="en",
                              date_from=None, date_to=None, max_results=10):
           # Your implementation
           return [NewsItem(...)]
   ```

2. Use your adapter in the collection flow.

## Neo4j Setup

### Docker (Recommended)

```bash
docker run -d --name neo4j \
  -p 7687:7687 -p 7474:7474 \
  -e NEO4J_AUTH=none \
  neo4j:5
```

### Local Installation
Follow the [Neo4j installation guide](https://neo4j.com/docs/operations-manual/current/installation/).

## Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_neo4j_client.py

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=src/auto_domain_kg
```

## Starting a Session

```bash
cd auto-domain-kg
claude --mcp
```

The Paseo MCP daemon will inject orchestration tools (spawn_agent, send_message, wait_for_agent, etc.) into the Claude Code session.

## Project Structure

```
auto-domain-kg/
├── install.sh              # Installer script
├── .mcp.json               # Paseo MCP configuration
├── CLAUDE.md               # Worker config and user concerns
├── pyproject.toml          # Python project (uv-managed)
├── README.md               # This file
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
│   ├── worker/             # Worker skills (6 files)
│   ├── verifier/           # Verifier skills (5 files)
│   ├── updater/            # Updater skills
│   └── risk/               # Risk skills
├── data/
│   └── evidence/           # Evidence JSONL files
├── tmp/                    # Temporary working files
└── tests/                  # pytest tests (6 files)
```

## License

MIT