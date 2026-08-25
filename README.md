[English](README.md) | [中文](README.zh.md)

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

## Schema/Instance Layer Separation

A core design principle of this project is the strict separation between a **Schema layer** and an **Instance layer**. The two layers play different roles and must never be mixed.

- **Schema layer** — models **only** concept-level entity types and relationship types (e.g., "Storage Device", "Vehicle", "Supplier", "Raw Material"). It defines the ontology: what kinds of things exist and how they relate. It never contains concrete instance names.
- **Instance layer** — models **only** concrete entities (e.g., "TSMC", "Xiaomi SU7", "Lithium Carbonate") that populate the ontology. Each Instance entity is linked to its Schema type via a `HAS_SCHEMA` relationship, and carries `source_url` / `source_text` provenance for traceability.

**Relationship validation**: Instance-to-Instance relationships must be validated against Schema-to-Schema relationships. For example, if the Schema defines `Supplier` ―[`SUPPLIES`]→ `Material`, then the Instance triple `TSMC` ―[`SUPPLIES`]→ `Silicon Wafers` is valid. An Instance relationship with no matching Schema relationship is flagged as a **Schema extension needed**, and one that contradicts the Schema definition is flagged as a **Schema inconsistency**.

**Schema hierarchy**: Schema types can form an inheritance hierarchy via `SUBCLASS_OF` relationships (e.g., `Supplier` is a subclass of `Organization`). When merging entities, the system can traverse this hierarchy and merge up to a parent Schema level.

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

**Skill**: `skills/worker/socratic_inquiry/SKILL.md`

### Step 2: Iterative Schema Generation & Entity Collection
An iterative, research-driven discovery loop that combines schema generation, entity collection, and refinement. The `schema_creation` skill follows a 9-step iterative discovery flow:

a. **Load user domain info** — read the user's domain and concerns from `CLAUDE.md`.
b. **Search** — research a sub-topic or entity cluster using the web search API, focusing on concept types and business relationships.
c. **Create Schema & relationships** — define Schema-level entity types and relationship types (concept-level only) and merge into `tmp/schema_definition.json`.
d. **Extract entities & relations** — extract concrete Instance entities matching the new Schema types, using the search results as evidence.
e. **GraphRAG retrieval** — for each Schema type and Instance entity, perform vector retrieval + multi-hop subgraph exploration to find related nodes already in the graph.
f. **Semantic merging** — merge semantically similar Schema/Instance nodes (e.g., "Xiaomi Auto" and "Xiaomi SU7" may refer to the same entity), using hierarchy-aware merging that can promote to a parent Schema via `SUBCLASS_OF`.
g. **Persist to graph** — save the current batch of Schema + Instance + Relationships to Neo4j.
h. **Discover completeness gaps** — analyze the graph structure to find missing entities, missing connections, and uncovered sub-topics, then generate new exploration queries.
i. **Repeat** from step **b** with the new queries until search results and discovered entities can no longer materially affect the entities relevant to the user's domain concerns.

Each iteration also collects evidence: weak sub-agents search for news/articles about the iteration's entities and save evidence to `data/evidence/` (2-3 independent sources per entity), then refine the partial schema with cross-iteration consistency checks.

**Skills**: `skills/worker/schema_creation/SKILL.md`, `skills/worker/entity_collection/SKILL.md`, `skills/worker/schema_refinement/SKILL.md`

### Step 3: Triple Extraction
Weak sub-agents extract (entity, relation, entity) triples with evidence from the collected evidence. Extraction is guided by the Schema layer: only concrete Instance entities are extracted, and Instance relationships are validated against Schema-to-Schema relationships. Triples are cross-validated across multiple independent sources — single-source facts are marked as **low confidence**, conflicting facts are flagged for human review, and critical facts require 3+ independent sources.

**Skill**: `skills/worker/triple_extraction/SKILL.md`

### Step 4: Graph Persistence
Persist the Schema (concept ontology) and Instance entities to Neo4j:
- Create Schema nodes (concept-level info only)
- Create entity nodes with auto-embedding, carrying `source_url` / `source_text` for provenance, and link them to Schema via `HAS_SCHEMA`
- Create relationships, validating Instance relationships against the Schema before persisting
- **Semantic merging** of Schema/Instance nodes: use GraphRAG (vector retrieval + multi-hop subgraph exploration) to find related nodes already in the graph and merge semantically similar ones (hierarchy-aware — can merge to a parent Schema level via `SUBCLASS_OF`)
- **Completeness gap discovery**: analyze the graph structure to find missing entities, missing connections, and uncovered sub-topics, and generate new queries fed back to Step 2
- Set up the vector index and verify embeddings / graph connectivity

**Skill**: `skills/worker/graph_persistence/SKILL.md`

### Step 5: Verifier Audit (Auto-Driven Loop)
The verifier (Codex) audits the graph and drives fixes:
1. **Schema Audit**: Completeness, consistency, inheritance, redundancy
2. **Graph Structure Audit**: Connectivity, orphan nodes, density
3. **GraphRAG Validation**: Can the graph answer domain questions?
4. **Evidence Audit**: Multi-source consistency, quality
5. **Task Relevance Audit**: Does the graph address user concerns?

The worker automatically fixes issues. Loop continues until all audits pass.

**Skills**: `skills/verifier/schema_audit/SKILL.md`, `skills/verifier/graph_structure_audit/SKILL.md`, `skills/verifier/graphrag_validation/SKILL.md`, `skills/verifier/evidence_audit/SKILL.md`, `skills/verifier/task_relevance_audit/SKILL.md`

### Step 6: Completion
- Summary of what was built
- Statistics (entity count, relation count, schema count)
- Reminder of daily update and risk assessment features

## Daily Update Flow

1. Load skill: `skills/updater/daily_update/SKILL.md`
2. Scan for entity-related news (today's date)
3. **Cross-validate news from multiple sources** before updating — use multi-source cross-validation to confirm facts; discard or flag single-source / conflicting reports
4. Determine if graph update is needed (schema or instance)
5. Send news to worker agent for partial graph update. When new entities don't fit the current Schema level, use **hierarchy-aware Schema merging** — traverse `SUBCLASS_OF` to merge to a parent Schema level
6. When risk events are detected, trigger the full 6-step risk analysis pipeline via `RiskAssessment.run_full_analysis()`
7. Run verifier to validate the update

## Risk Assessment Feature — 6-Step News-to-Graph Impact Analysis

Risk is **user-concern-driven** (NOT automatic propagation). The risk assessment
skill follows a complete 6-step pipeline to transform daily news into structured
risk reports with graph impact analysis.

### 6-Step Pipeline

1. **Receive Daily News** — Receive news list from the `daily_update` skill
2. **Extract News Events** — Extract structured events (event_type, description, entities_mentioned, severity_hint)
3. **Associate Evidence Fragments** — Extract supporting text snippets from news, save to `data/evidence/`
4. **GraphRAG Event-to-Node Analysis** — Vector search + multi-hop subgraph exploration to find affected graph nodes
5. **DAG Impact Tracing** — Follow outgoing relationships via Cypher queries to trace downstream impacts
6. **Generate Impact Report** — Use external template (`templates/{domain}_domain_report_template.md`) to produce report in `reports/`

### Key Principles
- **Graph structure matters**: Consider alternatives, redundancy, centrality
- **Semantic relevance**: Step 4 uses semantic (not just keyword) matching
- **DAG-aware tracing**: Step 5 respects graph directionality
- **Template-driven**: Report templates are externalized to `templates/` directory
- **Evidence-backed**: Each risk assessment cites evidence sources
- **Risk levels**: NONE, LOW, MEDIUM, HIGH, CRITICAL

### Example
If Entity A (a supplier) has a factory fire, the pipeline:
1. Receives the news article about the factory fire
2. Extracts event: `{event_type: "factory_fire", description: "...", severity_hint: "high"}`
3. Extracts evidence snippets from the article
4. Vector search finds related graph nodes (Supplier A, its products, its customers)
5. DAG tracing finds downstream impacts (production delays, shipping disruptions)
6. Generates a structured risk report in `reports/{date}_supply_chain_risk_report.md`

**Skill**: `skills/risk/risk_assessment/SKILL.md`
**Python module**: `src/auto_domain_kg/risk_assessment.py`

## Python Modules

### `neo4j_client.py`
Neo4j connection management, schema/instance CRUD, vector index operations, and multi-hop Cypher queries. Supports both password auth and no-auth. Entity nodes carry `source_url` and `source_text` fields for source provenance; `create_entity_node()` accepts these as optional parameters. Schema hierarchy is supported via `SUBCLASS_OF` relationships between Schema nodes: `create_schema_hierarchy()`, `get_schema_ancestors()`, `get_schema_descendants()`, `find_common_ancestor()`, `get_schema_with_ancestors()`.

### `embedding.py`
External API embedding client (OpenAI-compatible / vLLM). Supports batch embedding, caching, and configurable endpoint/model/dimensions.

### `evidence_store.py`
Evidence storage as JSONL files in `data/evidence/` with provenance tracking. Each record includes entity_id, text_slice, source_url, and timestamps. Multi-source cross-validation methods: `get_source_urls()` (all unique source URLs), `get_source_count()` (count independent sources), `cross_validate()` (check whether multiple sources agree or conflict), and `is_well_supported()` (check the minimum source count requirement).

### `news_adapter.py`
Abstract `NewsAdapter` interface and `GoogleSearchNewsAdapter` implementation. Extensible — implement your own adapter by subclassing `NewsAdapter`.

### `graph_ops.py`
High-level graph operations combining Neo4j, embedding, and evidence store. Provides composite operations like `create_entity_node()` (auto-embeds and links to schema, accepts `source_url` / `source_text` for provenance). Hierarchy-aware merge operations: `find_merge_target_with_hierarchy()` (hierarchy-aware merge target finding, traversing `SUBCLASS_OF` upward) and `merge_entity_to_parent_schema()` (merge an entity to a parent Schema level).

### `risk_assessment.py`
Risk field management, 6-step news-to-graph impact analysis pipeline, and agent-guided graph traversal. Methods: `extract_events_from_news()`, `associate_evidence()`, `graphrag_event_search()`, `trace_dag_impact()`, `generate_report()`, `run_full_analysis()`. Risk levels: NONE, LOW, MEDIUM, HIGH, CRITICAL.

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
├── README.md               # English README
├── README.zh.md            # Chinese README
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
│   ├── worker/             # Worker skills (6 directories)
│   │   ├── socratic_inquiry/SKILL.md
│   │   ├── schema_creation/SKILL.md
│   │   ├── entity_collection/SKILL.md
│   │   ├── schema_refinement/SKILL.md
│   │   ├── triple_extraction/SKILL.md
│   │   └── graph_persistence/SKILL.md
│   ├── verifier/           # Verifier skills (5 directories)
│   │   ├── schema_audit/SKILL.md
│   │   ├── graph_structure_audit/SKILL.md
│   │   ├── graphrag_validation/SKILL.md
│   │   ├── evidence_audit/SKILL.md
│   │   └── task_relevance_audit/SKILL.md
│   ├── updater/            # Updater skills
│   │   └── daily_update/SKILL.md
│   └── risk/               # Risk skills
│       └── risk_assessment/SKILL.md
├── templates/              # Report templates
│   └── default_domain_report_template.md
├── reports/                # Generated risk reports
├── data/
│   └── evidence/           # Evidence JSONL files
├── tmp/                    # Temporary working files
└── tests/                  # pytest tests (7 files)
```

## License

MIT