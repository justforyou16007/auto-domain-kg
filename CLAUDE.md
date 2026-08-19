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

## 6-Step Construction Flow

### Step 1: Socratic Inquiry
- Load skill: skills/worker/socratic_inquiry.md
- Ask the user structured questions to understand their domain, entities, relationships, risk concerns, and update frequency.
- Save the results to the User Concerns section of this file.

### Step 2: Domain Schema Generation (Strong Agent)
- Load skill: skills/worker/schema_creation.md
- Spawn a strong agent (worker_provider) to create the domain schema.
- Output: structured schema definitions (entity types, properties, relationships, inheritance).

### Step 3: Entity Collection (Weak Agents)
- Load skill: skills/worker/entity_collection.md
- Spawn multiple weak sub-agents (collector_provider) to search for news/articles about entities.
- Use the news_adapter module to collect evidence.
- Save evidence to data/evidence/ as JSONL files.

### Step 3b: Schema Refinement
- Load skill: skills/worker/schema_refinement.md
- Based on majority findings from collection, refine and supplement the schema.
- Update the schema definitions.

### Step 3c: Triple Extraction (Weak Agents)
- Load skill: skills/worker/triple_extraction.md
- Spawn weak sub-agents to extract (entity, relation, entity) triples with evidence slices.
- Save entities + relations to a markdown file + evidence to data/evidence/.

### Step 4: Graph Persistence
- Load skill: skills/worker/graph_persistence.md
- Persist schema + instances to Neo4j.
- Link entities to schema nodes.
- Embed for vector search.

### Step 5: Verifier Audit (Auto-driven loop, no user confirmation)
- Load and run all verifier skills (schema_audit, graph_structure_audit, graphrag_validation, evidence_audit, task_relevance_audit).
- Verifier (Codex) audits the graph and outputs issues.
- Worker automatically fixes issues based on verifier feedback.
- Loop until all audits pass or max iterations reached.

### Step 6: Completion
- Print summary of what was built.
- Print statistics (entity count, relation count, schema count).
- Remind user of daily update and risk assessment features.

## Daily Update Flow
1. Load skill: skills/updater/daily_update.md
2. Scan for entity-related news (today's date).
3. Determine if graph update is needed (schema or instance).
4. Send news to worker agent for partial graph update.
5. Run verifier to validate the update.

## Risk Warning Feature
1. Load skill: skills/risk/risk_assessment.md
2. Agent walks the graph to assess risk impact.
3. Risk is user-concern-driven (NOT automatic propagation).
4. Agent considers graph structure (alternative paths, redundancy).
5. Updates risk fields on entity nodes.
6. Use risk_assessment module for graph traversal.