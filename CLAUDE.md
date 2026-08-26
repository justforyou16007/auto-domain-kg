# Auto Domain KG — Worker Configuration

## User Concerns
<!-- This section is filled by the Socratic inquiry step (Step 1). -->
<!-- Format: -->
<!-- - Concern: <description> -->
<!--   - Domain: <domain> -->
<!--   - Entities: <key entity types> -->
<!--   - Relationships: <key relationship types> -->
<!--   - Risk concerns: <risk concerns> -->
<!--   - Update frequency: <daily|weekly|monthly> -->

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
- Ask the user structured questions to understand their domain, entities, relationships, risk concerns, and update frequency.
- Save the results to the User Concerns section of this file.

### Step 2: Iterative Schema Generation, Entity Collection & Triple Extraction (Iterative Loop)
- Load skills: skills/worker/schema_creation/SKILL.md, skills/worker/entity_collection/SKILL.md, skills/worker/schema_refinement/SKILL.md, skills/worker/triple_extraction/SKILL.md
- Run an iterative loop that combines schema generation, entity collection, triple extraction, and refinement:
  1. **Search**: Research a sub-topic or entity cluster within the domain (using web search).
  2. **Create Schema**: Based on search results, define partial entity types and relationship types. Merge into `tmp/schema_definition.json`.
  3. **Extract Triples**: For each entity/triple sub-graph discovered during exploration, use the Paseo MCP `spawn_agent` tool to dispatch sub-agents for parallel exploration. Extract (entity, relation, entity) triples from collected evidence, guided by the Schema layer. Only extract concrete Instance entities (never concepts). Validate each triple's relation type against the Schema-to-Schema relationships; flag triples needing schema extension. Save triples to `tmp/extracted_triples.md`. Use the `triple_extraction` skill for this sub-step.
  4. **Collect Evidence**: Spawn weak sub-agents (collector_provider) to search for news/articles about the entities from this iteration. Save evidence to `data/evidence/` as JSONL files.
  5. **Refine Schema**: Refine the partial schema based on the evidence and extracted triples just collected. Perform cross-iteration consistency checks (deduplication, conflict resolution). Add missing schema relations flagged by triple extraction as `schema_extension_needed` so Schema, Schema-relation, entity, and entity-relation layers stay aligned.
  6. **Assess Coverage**: Evaluate whether the current iteration produced new entity types or relationship types. If not, or if search results are outside the domain scope, terminate the loop.
  7. **Continue/Stop**: If new types were found, start the next iteration (go to step 1). Otherwise, proceed to Step 3.
- Skills used in the loop:
  - `schema_creation/SKILL.md` — iterative research-driven schema generation
  - `triple_extraction/SKILL.md` — per-iteration triple extraction (part of Step 2, not a separate step)
  - `entity_collection/SKILL.md` — per-iteration evidence collection (integrated with extraction)
  - `schema_refinement/SKILL.md` — per-iteration refinement and cross-iteration consistency

### Step 3: Graph Persistence
- Load skill: skills/worker/graph_persistence/SKILL.md
- Persist schema + instances to Neo4j.
- Before persisting, run relation alignment check (`GraphOps.validate_relation_alignment` and `GraphOps.get_missing_schema_relations`) to ensure Schema, Schema-relation, entity, and entity-relation are aligned.
- Link entities to schema nodes.
- Embed for vector search.

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
3. Determine if graph update is needed (schema or instance).
4. Send news to worker agent for partial graph update.
5. When risk events are detected, trigger the full 6-step risk analysis pipeline via `RiskAssessment.run_full_analysis()`.
6. Run verifier to validate the update.

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