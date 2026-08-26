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
mkdir -p data/evidence tmp tests config reports/audits templates

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
| `TRANSLATION_ENDPOINT` | OpenAI-compatible translation API endpoint (for bilingual search result translation) | `` |
| `TRANSLATION_API_KEY` | Translation API key (Bearer token) | `` |
| `TRANSLATION_MODEL` | Translation model name | `gpt-4o-mini` |
| `EXTRACTION_ENDPOINT` | Extraction API endpoint (entity-relation extraction, `info_extraction.py`) | `` |
| `EXTRACTION_API_KEY` | Extraction API key (Bearer token) | `` |
| `EXTRACTION_MODEL` | Extraction model name | `gpt-4o` |
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
# Extraction provider — entity/relation extraction + translation API (info_extraction.py)
extraction_provider: claude/claude-sonnet-4-20250514
# Translation provider — bilingual search result translation API (translation.py / info_extraction.py)
translation_provider: claude/claude-sonnet-4-20250514
```

Format: `<cli>/<model-name>` where `cli` is `claude` or `codex`, and `model-name` is an available model for that CLI.

## 6-Step Construction Flow (kg-gen-pipeline)

The KG construction pipeline has been restructured from a monolithic `schema_creation` loop into a **deep-research-style multi-agent pipeline** orchestrated by the `kg-gen-pipeline` skill. It uses the Paseo MCP `spawn_agent` tool to dispatch **parallel sub-agents** at each phase, following a deep-research methodology.

### Step 1: Socratic Inquiry
Extract user concerns through a **small number** of high-level questions (3-4 core questions). The agent asks about:
- **Domain**: What industry/domain is the KG for? (required)
- **Task/Purpose**: What is the primary task? (e.g., risk monitoring, competitive intelligence) (required)
- **Entity & Relationship types (approximate, optional)**: approximate entity types and relationship types — the user may say "not sure"
- **Risk concerns (optional)**: what risks to monitor

The user does **NOT** need to provide a detailed Schema, entity properties, or inheritance hierarchies at setup time. Schema is *discovered* through exploration in Step 2.

**Skill**: `skills/worker/socratic_inquiry/SKILL.md`

### Step 2: Parallel Schema Proposal (Paseo dispatch)
Use the Paseo MCP `spawn_agent` tool to dispatch N (default **5**) parallel sub-agents, each loading the `schema_creation` skill:
1. **GraphRAG search existing Neo4j Schema** (vector search + multi-hop) to find related Schema already in the graph.
2. Based on search results + the sub-agent's own domain knowledge, create concept-level Schema entity types and relationship types.
3. **Cache locally** to `tmp/schema_proposals/agent_N.json`.
4. **Notify the main Agent** when done.

The `schema_creation` skill does **ONLY** Schema + Relation creation — no entity collection, triple extraction, refinement, or persistence. It keeps the Exploration-First Principle and Schema/Instance separation, and uses bilingual search + translation for initial domain research.

**Skills**: `skills/worker/kg_gen_pipeline/SKILL.md`, `skills/worker/schema_creation/SKILL.md`

### Step 3: Schema Merge
Merge the N Schema proposals from Step 2 together with existing Neo4j Schema into one global Schema:
- **Maintain the SUBCLASS_OF hierarchy** (e.g. Car → EV → Xiaomi Auto → ...). Uses `neo4j_client.create_schema_hierarchy()`, `get_schema_ancestors()`, `find_common_ancestor()`.
- Detect duplicates, resolve conflicts, ensure a concept-level-only ontology.
- Output: merged global Schema in `tmp/schema_definition.json`.

**Skill**: `skills/worker/schema_merge/SKILL.md`

### Step 4: Per-Schema/Relation Parallel Extraction (Paseo dispatch)
For each new Schema/Relation, dispatch a sub-agent (parallel execution). Each sub-agent runs three sub-phases:

**4a. evidence-search** (deep-research style) — multi-round search: each round generates zh + en queries → `bilingual_search()` top-k=20 → merge by URL → `translate_content()` to zh-CN → analyze findings → generate next-round questions → continue. **Does NOT stop after finding one piece of evidence** — goal is comprehensive coverage; stop when a round produces no new facts.

**4b. triple_extraction** (per Schema/Relation dimension) — from the Schema/Relation's leaf entities, explore outward **X-hop** (default **3**). Extract entities and relations along Schema-defined Relation directions; form a subgraph centered on the leaf entity where each node carries an evidence slice + `source_url`. Validate entity-relation against schema-relation alignment; flag triples needing schema extension.

**4c. entity-relation-merge** — entity alignment via semantic judgment (e.g. 苹果 ↔ Apple) → subgraph merge. Bind entity ↔ Schema via `HAS_SCHEMA`; mark entities with no matching Schema as "empty Schema" for later Schema creation. Uses `graph_ops.find_merge_target_with_hierarchy()` and `merge_entity_to_parent_schema()`.

**Skills**: `skills/worker/evidence_search/SKILL.md`, `skills/worker/triple_extraction/SKILL.md`, `skills/worker/entity_relation_merge/SKILL.md`

### Step 5: Subgraph Merge
Take the Neo4j intersection **2-hop subgraph** of newly inserted entities and merge overlapping subgraphs (uses `graph_ops.multi_hop_subgraph()` and `vector_search()`). For entities with empty Schema, create new Schema nodes and route them through `schema_merge`. For new Schema, **repeat Step 4** recursively. This phase also performs **completeness gap discovery** — analyzing the graph structure to find missing entities, missing connections, and uncovered sub-topics, then feeding new exploration queries back into the recursive Step 4. **Stop condition**: new search entities are completely irrelevant to the user's domain concerns (no butterfly effect — only direct domain relevance counts).

**Skill**: `skills/worker/subgraph_merge/SKILL.md`

### Step 6: Audit → Fix Loop (fix from Step 4)
The GAN-style adversarial loop between the verifier (discriminator) and the worker (generator), with full audit report output and traceability. Defaults to the **strictest** auditing — any error-level issue blocks a round from passing. On error-level issues, fix from **Step 4** (re-run evidence-search + triple_extraction + entity-relation-merge for the affected Schema/Relation), then re-audit.

1. **Load rubrics** from `config/audit_rubrics.yaml` (strictest level; customize thresholds there without touching skill code)
2. **Run all 5 audit sub-agents**, each applying its rubric thresholds:
   - **Schema Audit**: completeness, consistency, inheritance, redundancy
   - **Graph Structure Audit**: connectivity, orphan nodes, density
   - **GraphRAG Validation**: can the graph answer domain questions?
   - **Evidence Audit**: multi-source consistency, quality
   - **Task Relevance Audit**: does the graph address user concerns?
3. **Generate an audit report** via `AuditReportGenerator` (markdown + JSON), saved to `reports/audits/round_N/`
4. **Append to `AuditHistory`** (`reports/audits/audit_history.jsonl`) for traceability
5. **If error-level issues found**: send them to the worker, which fixes them (from **Step 4**) and records what it changed (`fix_description`, `issue_ids_addressed`, `files_modified`)
6. **Re-run the audit** (next round) and compare against the previous round — trace any issue across rounds with `AuditHistory.get_issue_trace(issue_id)` (first found → fixed → reappeared?)
7. **Loop** until all audits pass or max rounds (default 5)
8. **Final convergence summary** via `AuditHistory.get_summary()` (rounds, issues resolved, issues recurring, error/warning trend)

**Skills**: `skills/verifier/schema_audit/SKILL.md`, `skills/verifier/graph_structure_audit/SKILL.md`, `skills/verifier/graphrag_validation/SKILL.md`, `skills/verifier/evidence_audit/SKILL.md`, `skills/verifier/task_relevance_audit/SKILL.md`

### Completion
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

## Audit Report & Adversarial Traceability (Issues #14, #15)

The verifier audit (Step 4) now produces detailed **audit reports** and runs a real **GAN-style adversarial loop** with full traceability. Audit strictness defaults to the **strictest** level so incomplete or unusable graphs are never accepted.

### Audit Reports
Each adversarial round generates a detailed audit report (markdown + JSON) describing all graph audit characteristics:
- **Schema completeness stats** (entity types, missing types, undefined relationships)
- **Graph connectivity metrics** (total entities, orphan entities, avg relationships per entity)
- **Evidence source counts** (entities audited, single-source entities, conflicting evidence)
- **GraphRAG question results** (total/answerable/unanswerable, per-question precision)
- **Task relevance coverage** (fully/partially/not covered, fully-covered ratio)
- **Issue breakdown** by severity (error/warning/info) and category, each with a stable issue `id`
- **Worker fix traceability** (what the worker changed, which issue ids it addressed, which files)

Reports are saved to `reports/audits/round_N/audit_report.md` (and `.json`). Render with:
```python
from auto_domain_kg.audit_report import AuditReportGenerator
md = generator.render_markdown(report)   # human-readable
js = generator.render_json(report)        # machine consumption
```
A report template lives at `templates/audit_report_template.md`.

### Custom Audit Rubrics
Audit thresholds are user-customizable via `config/audit_rubrics.yaml` (all 5 audit skills, defaulting to strict):
- `schema_audit`: `max_missing_entity_types=0`, `max_undefined_relationships=0`
- `graph_structure_audit`: `max_orphan_entities=0`, `min_avg_relationships=1.0`
- `graphrag_validation`: `min_answerable_ratio=0.8`, `min_precision="medium"`
- `evidence_audit`: `min_sources_per_entity=2`, `min_sources_per_critical=3`
- `task_relevance_audit`: `min_fully_covered_ratio=0.7`

```python
from auto_domain_kg.audit_rubrics import RubricsConfig
config = RubricsConfig.load_from_file("config/audit_rubrics.yaml")  # or .load_default()
config.set_strictness("strict")  # strict | moderate | lenient
config.save_to_file("config/audit_rubrics.yaml")
```

### Adversarial Traceability
Every round's audit report and the worker's fixes are persisted to `reports/audits/audit_history.jsonl` (JSONL). `AuditHistory` provides:
- `get_round(n)` — retrieve a specific round
- `get_issue_trace(issue_id)` — trace an issue across rounds (first found → fixed → reappeared)
- `get_summary()` — total rounds, issues resolved, issues recurring, and the per-round convergence trend

Under STRICT auditing, **any error-level issue blocks the round from passing**; warnings are tracked but do not block. The loop runs until all audits pass or the max rounds (default 5) is reached.

## Python Modules

### `neo4j_client.py`
Neo4j connection management, schema/instance CRUD, vector index operations, multi-hop Cypher queries, and multi-modal search. Supports both password auth and no-auth. Entity nodes carry `source_url` and `source_text` fields for source provenance; `create_entity_node()` accepts these as optional parameters. Schema hierarchy is supported via `SUBCLASS_OF` relationships between Schema nodes: `create_schema_hierarchy()`, `get_schema_ancestors()`, `get_schema_descendants()`, `find_common_ancestor()`, `get_schema_with_ancestors()`. Search methods: `vector_search()` (vector similarity), `keyword_search()` (lightweight CONTAINS-based keyword search, no index required), and `bm25_search()` (BM25-ranked full-text search with graceful fallback to `keyword_search()`).

### `embedding.py`
External API embedding client (OpenAI-compatible / vLLM). Supports batch embedding, caching, and configurable endpoint/model/dimensions.

### `evidence_store.py`
Evidence storage as JSONL files in `data/evidence/` with provenance tracking. Each record includes entity_id, text_slice, source_url, and timestamps. Multi-source cross-validation methods: `get_source_urls()` (all unique source URLs), `get_source_count()` (count independent sources), `cross_validate()` (check whether multiple sources agree or conflict), and `is_well_supported()` (check the minimum source count requirement).

### `news_adapter.py`
Abstract `NewsAdapter` interface and `GoogleSearchNewsAdapter` implementation. Bilingual retrieval support: `search_news()` (single-language search), `bilingual_search()` (issue both a Chinese and an English query, merge and deduplicate by URL), `translate_content()` (translate a `NewsItem` to the working language via the translation client), and `bilingual_search_and_translate()` (run bilingual search then translate all results). Extensible — implement your own adapter by subclassing `NewsAdapter`.

### `translation.py`
External API translation client (OpenAI-compatible chat completions) used to translate bilingual search results to the working language. `TranslationConfig` reads `TRANSLATION_ENDPOINT` / `TRANSLATION_API_KEY` / `TRANSLATION_MODEL` from the environment. `TranslationClient` provides `translate()` (translate arbitrary text) and `translate_news_item()` (translate a `NewsItem`'s title and content, preserving the URL/source and recording `original_language`). Degrades gracefully — when no endpoint is configured, text is returned unchanged.

### `info_extraction.py`
Information extraction API client with two modes: **generic API mode** (`InfoExtractionClient.extract()`) sends text to a general-purpose LLM chat-completions endpoint and parses the structured entities/relations JSON it returns, and **dedicated extraction API mode** (`InfoExtractionClient.extract_dedicated()`) sends text to a specialized entity-relation extraction endpoint. It also doubles as a translation API client (`InfoExtractionClient.translate()`) reusing the same endpoint infrastructure. `ExtractionConfig` reads `EXTRACTION_ENDPOINT` / `EXTRACTION_API_KEY` / `EXTRACTION_MODEL` and `TRANSLATION_ENDPOINT` / `TRANSLATION_API_KEY` / `TRANSLATION_MODEL` from the environment. Includes async methods, caching, robust JSON parsing (tolerates Markdown fences), and graceful degradation (empty extractions / original text when unconfigured).

### `graph_ops.py`
High-level graph operations combining Neo4j, embedding, and evidence store. Provides composite operations like `create_entity_node()` (auto-embeds and links to schema, accepts `source_url` / `source_text` for provenance). Hierarchy-aware merge operations: `find_merge_target_with_hierarchy()` (hierarchy-aware merge target finding, traversing `SUBCLASS_OF` upward) and `merge_entity_to_parent_schema()` (merge an entity to a parent Schema level).

### `risk_assessment.py`
Risk field management, 6-step news-to-graph impact analysis pipeline, and agent-guided graph traversal. Methods: `extract_events_from_news()`, `associate_evidence()`, `graphrag_event_search()`, `trace_dag_impact()`, `generate_report()`, `run_full_analysis()`. Risk levels: NONE, LOW, MEDIUM, HIGH, CRITICAL.

### `audit_rubrics.py`
User-customizable audit rubrics that drive the 5 verifier audit skills. `RubricItem` (name, description, strictness_level, enabled, custom_thresholds) and `RubricsConfig` (`load_default()`, `load_from_file()`, `save_to_file()`, `get_enabled_rubrics()`, `set_strictness()`). Defaults to the strictest level. Config file: `config/audit_rubrics.yaml`.

### `audit_report.py`
Audit report generation and adversarial traceability. `AuditReport` (full per-round audit state), `AuditReportGenerator` (`generate_report()`, `render_markdown()`, `render_json()`, `save_report()`), and `AuditHistory` (`add_round()`, `get_round()`, `get_all_rounds()`, `get_issue_trace()`, `get_summary()`). STRICT policy: any error-level issue blocks the round. History persisted as JSONL in `reports/audits/audit_history.jsonl`.

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
│       ├── risk_assessment.py
│       ├── audit_rubrics.py
│       ├── audit_report.py
│       ├── translation.py
│       └── info_extraction.py
├── skills/
│   ├── worker/             # Worker skills (8 directories)
│   │   ├── socratic_inquiry/SKILL.md
│   │   ├── kg_gen_pipeline/SKILL.md
│   │   ├── schema_creation/SKILL.md
│   │   ├── schema_merge/SKILL.md
│   │   ├── evidence_search/SKILL.md
│   │   ├── triple_extraction/SKILL.md
│   │   ├── entity_relation_merge/SKILL.md
│   │   └── subgraph_merge/SKILL.md
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
├── config/                 # Audit rubrics configuration
│   └── audit_rubrics.yaml
├── templates/              # Report templates
│   ├── default_domain_report_template.md
│   └── audit_report_template.md
├── reports/                # Generated risk & audit reports
│   └── audits/             # Audit reports + audit_history.jsonl
├── data/
│   └── evidence/           # Evidence JSONL files
├── tmp/                    # Temporary working files
└── tests/                  # pytest tests (12 files)
```

## Documentation Sync Rule

**Every code change must be accompanied by corresponding documentation updates.** When you modify any source file in `src/`, skill file in `skills/`, or configuration file, you must also update:

- `README.md` and `README.zh.md` — module descriptions, feature lists, step descriptions
- `CLAUDE.md` — flow steps, skill references, provider configuration
- `tests/test_readme_sync.py` — add assertions for new features

This rule applies to all changes: bug fixes, feature additions, refactors, and configuration updates. A PR that changes code without updating documentation is incomplete.

## License

MIT