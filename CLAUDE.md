# Auto Domain KG — Worker Configuration

## User Concerns
<!-- This section is filled by the Socratic inquiry step (Step 1). -->
<!-- The user does NOT need to provide a detailed Schema. Schema is -->
<!-- discovered through exploration in Step 2, not fixed at setup time. -->
<!-- Format: -->
<!-- - Concern: <one-line summary of the user's primary concern> -->
<!--   - Domain: <domain> -->
<!--   - Task: <primary task/purpose> -->
<!--   - Entity types (approximate, optional): <list or "to be discovered"> -->
<!--   - Relationship types (approximate, optional): <list or "to be discovered"> -->
<!--   - Risk concerns (optional): <risk concerns or "none specified"> -->

## Provider Configuration
# Worker (Claude Code) — user fills in available model
# Format: <cli>/<model-name> where cli is "claude" or "codex", model-name is an available model for that CLI.
worker_provider: claude/claude-sonnet-4-20250514
# Information collection agents (Claude Code)
collector_provider: claude/claude-sonnet-4-20250514
# Verifier (Codex)
verifier_provider: codex/gpt-4o
# Extraction provider — entity/relation extraction + translation API (info_extraction.py)
# Configured via env vars: EXTRACTION_ENDPOINT, EXTRACTION_API_KEY, EXTRACTION_MODEL
extraction_provider: claude/claude-sonnet-4-20250514
# Translation provider — bilingual search result translation API (translation.py / info_extraction.py)
# Configured via env vars: TRANSLATION_ENDPOINT, TRANSLATION_API_KEY, TRANSLATION_MODEL
translation_provider: claude/claude-sonnet-4-20250514

## 6-Step Construction Flow (kg-gen-pipeline)

### Step 1: Socratic Inquiry
- Load skill: skills/worker/socratic_inquiry/SKILL.md
- Ask a **small number** of high-level questions (3-4 core questions): domain, primary task/purpose, approximate entity/relationship types (optional), and risk concerns (optional). Keep setup user-friendly — do NOT drill into entity properties, inheritance hierarchies, or relationship constraints.
- The user does NOT need to provide a detailed Schema. Schema is discovered through exploration in Step 2, not fixed at setup time. If the user is unsure about entity types/relationships, proceed with just the domain and task.
- Save the results to the User Concerns section of this file.

### Step 2: Parallel Schema Proposal (Paseo dispatch)
- Load skill: skills/worker/kg_gen_pipeline/SKILL.md (`kg-gen-pipeline` orchestrator) + skills/worker/schema_creation/SKILL.md (`schema-creation` per sub-agent)
- Use the Paseo MCP `spawn_agent` tool to dispatch N (default **5**) parallel sub-agents. Each sub-agent loads the `schema_creation` skill:
  1. **GraphRAG search existing Neo4j Schema** (vector search + multi-hop) to find related Schema already in the graph.
  2. Based on search results + the sub-agent's own domain knowledge, create concept-level Schema entity types and relationship types.
  3. **Cache locally** to `tmp/schema_proposals/agent_N.json`.
  4. **Notify the main Agent** when done.
- The `schema_creation` skill does **ONLY** Schema + Relation creation — no entity collection, triple extraction, refinement, or persistence. It keeps the Exploration-First Principle and Schema/Instance separation, and uses bilingual search + translation for initial domain research.

### Step 3: Schema Merge
- Load skill: skills/worker/schema_merge/SKILL.md (`schema-merge`)
- Merge the N Schema proposals from Step 2 together with existing Neo4j Schema into one global Schema.
- **Maintain the SUBCLASS_OF hierarchy** (e.g. Car → EV → Xiaomi Auto → ...). Uses `neo4j_client.create_schema_hierarchy()`, `get_schema_ancestors()`, `find_common_ancestor()`.
- Detect duplicates, resolve conflicts, ensure a concept-level-only ontology.
- Output: merged global Schema in `tmp/schema_definition.json`.

### Step 4: Per-Schema/Relation Parallel Extraction (Paseo dispatch)
For each new Schema/Relation, dispatch a sub-agent (parallel execution). Each sub-agent runs three sub-phases:

  **4a. evidence-search skill** (deep research style)
  - Load skill: skills/worker/evidence_search/SKILL.md (`evidence-search`)
  - Multi-round search: each round generates zh + en queries → `bilingual_search()` top-k=20 → merge by URL → `translate_content()` to zh-CN → analyze findings → generate next-round questions → continue.
  - **Does NOT stop after finding one piece of evidence** — goal is comprehensive coverage. Stop when a round produces no new facts.

  **4b. triple_extraction skill** (per Schema/Relation dimension)
  - Load skill: skills/worker/triple_extraction/SKILL.md
  - From the Schema/Relation's leaf entities, explore outward **X-hop** (default **3**).
  - Extract entities and relations along Schema-defined Relation directions. Form a subgraph centered on the leaf entity; each node carries an evidence slice + `source_url`.
  - Validate entity-relation against schema-relation alignment; flag triples needing schema extension.

  **4c. entity-relation-merge skill**
  - Load skill: skills/worker/entity_relation_merge/SKILL.md (`entity-relation-merge`)
  - Entity alignment (semantic judgment: 苹果 ↔ Apple) → subgraph merge.
  - Bind entity ↔ Schema via `HAS_SCHEMA`; mark entities with no matching Schema as "empty Schema". Uses `graph_ops.find_merge_target_with_hierarchy()` and `merge_entity_to_parent_schema()`.

### Step 5: Subgraph Merge
- Load skill: skills/worker/subgraph_merge/SKILL.md (`subgraph-merge`)
- Take the Neo4j intersection **2-hop subgraph** of newly inserted entities → merge overlapping subgraphs. Uses `graph_ops.multi_hop_subgraph()` and `vector_search()`.
- For entities with empty Schema, create new Schema nodes and route through `schema_merge`.
- For new Schema, **repeat Step 4** recursively.
- **Stop condition**: new search entities are completely irrelevant to the user's domain concerns (no butterfly effect — only direct domain relevance counts).

### Step 6: Audit → Fix Loop (fix from Step 4)
- Load skills under skills/verifier/ (schema_audit, graph_structure_audit, graphrag_validation, evidence_audit, task_relevance_audit).
- Run the GAN-style adversarial audit. On error-level issues, fix from **Step 4** (re-run evidence-search + triple_extraction + entity-relation-merge for the affected Schema/Relation), then re-audit.
- Loop until all audits pass (`overall_passed == True`) or the max rounds is reached (default 5).

#### Audit Loop Detail
The GAN-style adversarial loop between the verifier (discriminator) and the worker (generator), with full audit report output and traceability.

1. **Load rubrics**: Load audit rubrics from `config/audit_rubrics.yaml` (defaults to the **strictest** level). Use `RubricsConfig.load_from_file()`, falling back to `RubricsConfig.load_default()`.
   ```python
   from auto_domain_kg.audit_rubrics import RubricsConfig
   config = RubricsConfig.load_from_file("config/audit_rubrics.yaml")
   ```
2. **Run all 5 audit sub-agents** in parallel, each applying its rubric thresholds:
   - `schema_audit` — completeness, consistency, inheritance, redundancy
   - `graph_structure_audit` — connectivity, orphan nodes, density
   - `graphrag_validation` — can the graph answer domain questions?
   - `evidence_audit` — multi-source consistency, quality
   - `task_relevance_audit` — does the graph address user concerns?
   Each sub-audit emits a structured result (passed, issues with stable `id`/`severity`, summary stats).
3. **Generate audit report**: Aggregate sub-audit results via `AuditReportGenerator.generate_report()`. Under STRICT auditing, any error-level issue blocks the round from passing (`overall_passed == False`); warnings are tracked but do not block.
   ```python
   from auto_domain_kg.audit_report import AuditReportGenerator, AuditHistory
   generator = AuditReportGenerator()
   report = generator.generate_report(round_number, sub_reports, config, worker_fixes)
   ```
4. **Save the report**: `generator.save_report(report, output_dir="reports/audits/")` writes both `reports/audits/round_N/audit_report.md` and `.json`.
5. **Append to history**: `AuditHistory("reports/audits/").add_round(report)` persists the round to `reports/audits/audit_history.jsonl` (JSONL) for full traceability.
6. **If issues found (any error-level)**: send the issues to the worker. The worker fixes them (from **Step 4**) and records what it changed as `worker_fixes` entries (`fix_description`, `issue_ids_addressed`, `files_modified`).
7. **Re-run the audit** (next round), passing the recorded `worker_fixes`. The loop compares the new round against the previous one via `AuditHistory` — use `get_issue_trace(issue_id)` to see when an issue was first found, how the worker fixed it, and whether it reappeared.
8. **Loop** until all audits pass (`overall_passed == True`) or the max rounds is reached (configurable, default 5).
9. **Final convergence summary**: `AuditHistory.get_summary()` reports total rounds, issues resolved, issues recurring, and the per-round error/warning convergence trend.

Each round's audit report and worker fixes are persisted for full traceability. This makes the GAN adversarial process substantively effective — the verifier's strict findings drive concrete worker fixes, and every fix is traceable back to the issue it addressed.

### Completion
- Print summary of what was built.
- Print statistics (entity count, relation count, schema count).
- Remind user of daily update and risk assessment features.

## Daily Update Flow
1. Load skill: skills/updater/daily_update/SKILL.md
2. Scan for entity-related news (today's date).
3. **Cross-validate news from multiple sources** before updating — use multi-source cross-validation to confirm facts; discard or flag single-source / conflicting reports.
4. Determine if graph update is needed (schema or instance).
5. Send news to worker agent for partial graph update. When new entities don't fit the current Schema level, use **hierarchy-aware Schema merging** — traverse `SUBCLASS_OF` to merge to a parent Schema level.
6. When risk events are detected, trigger the full 6-step risk analysis pipeline via `RiskAssessment.run_full_analysis()`.
7. Run verifier to validate the update.

## Risk Assessment Feature — 6-Step News-to-Graph Impact Analysis
1. Load skill: skills/risk/risk_assessment/SKILL.md
2. **Step 1**: Receive daily news from the daily_update skill.
3. **Step 2**: Extract structured events from news (event extraction).
4. **Step 3**: Associate evidence fragments from news to events.
5. **Step 4**: GraphRAG event-to-node analysis — vector search + multi-hop subgraph exploration.
6. **Step 5**: DAG impact tracing — follow outgoing relationships via Cypher to find downstream impacts.
7. **Step 6**: Generate impact report from external template (`templates/default_domain_report_template.md`).
8. Risk is user-concern-driven (NOT automatic propagation).
9. Use risk_assessment module for graph traversal and `run_full_analysis()` for the full pipeline.
10. Report templates are in `templates/` directory; generated reports go to `reports/`.