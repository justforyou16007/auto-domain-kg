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

## 5-Step Construction Flow

### Step 1: Socratic Inquiry
- Load skill: skills/worker/socratic_inquiry/SKILL.md
- Ask a **small number** of high-level questions (3-4 core questions): domain, primary task/purpose, approximate entity/relationship types (optional), and risk concerns (optional). Keep setup user-friendly — do NOT drill into entity properties, inheritance hierarchies, or relationship constraints.
- The user does NOT need to provide a detailed Schema. Schema is discovered through exploration in Step 2, not fixed at setup time. If the user is unsure about entity types/relationships, proceed with just the domain and task.
- Save the results to the User Concerns section of this file.

### Step 2: Iterative Schema Generation, Entity Collection & Triple Extraction (Iterative Loop)
- Load skills: skills/worker/schema_creation/SKILL.md, skills/worker/entity_collection/SKILL.md, skills/worker/schema_refinement/SKILL.md, skills/worker/triple_extraction/SKILL.md
- **Exploration-first**: the user's Step 1 input is a starting point, not a complete specification. Schema types and relationships are *discovered* through iterative exploration. Search broadly beyond what the user mentioned — adjacent domains, supply-chain上下游, related industries. Treat approximate entity types as hints, not constraints.
- Run an iterative loop that combines schema generation, entity collection, triple extraction, and refinement:
  1. **Bilingual Search**: For each sub-topic, the agent generates BOTH a Chinese and an English query. Use `bilingual_search()` (on the news adapter) instead of `search_news()` so retrieval is not limited by the search language. Merge and deduplicate results by URL.
  2. **Translate**: Translate all bilingual search results to the working language (default `zh-CN`) via `translate_content()` / `TranslationClient` before proceeding to Schema/entity exploration. Each translated item carries `original_language`.
  3. **Create Schema**: Based on the **translated** search results, define partial entity types and relationship types (let the schema emerge from the data). Merge into `tmp/schema_definition.json`.
  4. **Extract Triples**: For each entity/triple sub-graph discovered during exploration, use the Paseo MCP `spawn_agent` tool to dispatch sub-agents for parallel exploration. Extract (entity, relation, entity) triples from the **translated** collected evidence, guided by the Schema layer. Only extract concrete Instance entities (never concepts). Validate each triple's relation type against the Schema-to-Schema relationships; flag triples needing schema extension. Save triples to `tmp/extracted_triples.md`. Use the `triple_extraction` skill for this sub-step.
  5. **Collect Evidence**: Spawn weak sub-agents (collector_provider) to search for news/articles about the entities from this iteration (using `bilingual_search()` + `translate_content()`). Save evidence to `data/evidence/` as JSONL files.
  6. **Refine Schema**: Refine the partial schema based on the evidence and extracted triples just collected. Perform cross-iteration consistency checks (deduplication, conflict resolution). Add missing schema relations flagged by triple extraction as `schema_extension_needed` so Schema, Schema-relation, entity, and entity-relation layers stay aligned.
  7. **Assess Coverage**: Evaluate whether the current iteration produced new entity types or relationship types. If not, or if search results are outside the domain scope, terminate the loop.
  8. **Continue/Stop**: If new types were found, start the next iteration (go to step 1). Otherwise, proceed to Step 3.
- Skills used in the loop:
  - `schema_creation/SKILL.md` — iterative, exploration-first, bilingual research-driven schema generation
  - `triple_extraction/SKILL.md` — per-iteration triple extraction (part of Step 2, not a separate step)
  - `entity_collection/SKILL.md` — per-iteration bilingual evidence collection (integrated with extraction)
  - `schema_refinement/SKILL.md` — per-iteration refinement and cross-iteration consistency

### Step 3: Graph Persistence
- Load skill: skills/worker/graph_persistence/SKILL.md
- **Relation alignment check** (before persisting): run `GraphOps.validate_relation_alignment` and `GraphOps.get_missing_schema_relations` to ensure Schema, Schema-relation, entity, and entity-relation are aligned. Do NOT persist entity relations that have no schema relation definition.
- Create Schema nodes (concept-level info only).
- Create entity nodes with auto-embedding, carrying `source_url` / `source_text` for provenance, and link them to Schema via `HAS_SCHEMA`. Every entity node must be traceable to its source.
- Create relationships, validating Instance relationships against the Schema before persisting (flag Schema extension needs / inconsistencies).
- **Semantic merging** of Schema/Instance nodes: use GraphRAG (vector retrieval + multi-hop subgraph exploration) to find related nodes already in the graph and merge semantically similar ones. Hierarchy-aware — `GraphOps.find_merge_target_with_hierarchy()` traverses `SUBCLASS_OF` upward, and `GraphOps.merge_entity_to_parent_schema()` can promote an entity to a parent Schema level.
- **Completeness gap discovery**: analyze the graph structure to find missing entities, missing connections, and uncovered sub-topics, and generate new queries fed back to Step 2.
- Set up the vector index (`GraphOps.setup_vector_index()`) and verify embeddings / graph connectivity. Print statistics (entity count, relation count, schema count).

### Step 4: Verifier Audit (Adversarial Loop with Traceability)
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
6. **If issues found (any error-level)**: send the issues to the worker. The worker fixes them and records what it changed as `worker_fixes` entries (`fix_description`, `issue_ids_addressed`, `files_modified`).
7. **Re-run the audit** (next round), passing the recorded `worker_fixes`. The loop compares the new round against the previous one via `AuditHistory` — use `get_issue_trace(issue_id)` to see when an issue was first found, how the worker fixed it, and whether it reappeared.
8. **Loop** until all audits pass (`overall_passed == True`) or the max rounds is reached (configurable, default 5).
9. **Final convergence summary**: `AuditHistory.get_summary()` reports total rounds, issues resolved, issues recurring, and the per-round error/warning convergence trend.

Each round's audit report and worker fixes are persisted for full traceability. This makes the GAN adversarial process substantively effective — the verifier's strict findings drive concrete worker fixes, and every fix is traceable back to the issue it addressed.

### Step 5: Completion
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