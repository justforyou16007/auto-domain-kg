---
name: kg-gen-pipeline
description: "Main orchestration skill for the 6-step deep-research multi-agent KG construction pipeline. Uses Paseo MCP spawn_agent to dispatch parallel sub-agents at each phase: Step 1 Socratic Inquiry, Step 2 parallel schema_creation sub-agents, Step 3 schema-merge, Step 4 per-Schema evidence-search + triple_extraction + entity-relation-merge, Step 5 subgraph-merge, Step 6 audit-fix loop. Defines stop conditions, parallel dispatch, and error handling."
---

# KG-Gen Pipeline — 6-Step Deep-Research Multi-Agent Construction

## Goal
Orchestrate the full knowledge-graph construction as a **deep-research-style
multi-agent pipeline**. Instead of a single monolithic schema-creation loop,
this pipeline dispatches **parallel sub-agents** via the Paseo MCP
`spawn_agent` tool for each phase, then merges their results. Every phase is
independently retryable and the pipeline keeps explicit stop conditions so it
does not over-expand beyond the user's domain concerns.

## Paseo MCP Dispatch
Use the Paseo MCP tools configured in `.mcp.json`:
- `spawn_agent` — dispatch a new sub-agent with a skill + message.
- `send_message` — send follow-up instructions to a running sub-agent.
- `wait_for_agent` — block until a sub-agent finishes and collect its result.
- `list_agents` — enumerate running sub-agents.
- `terminate_agent` — cancel a runaway sub-agent.

Dispatch rules:
- **Parallel fan-out**: independent phases (Step 2 schema proposals, Step 4
  per-Schema/Relation work) spawn N sub-agents at once and wait for all.
- **Sequential merge**: merging phases (Step 3, Step 4c, Step 5) run as a
  single agent that consumes the parallel outputs.
- Each sub-agent loads exactly one skill and is given a bounded scope.

## The 6 Steps

### Step 1: Socratic Inquiry (unchanged)
- Load skill: `skills/worker/socratic_inquiry/SKILL.md`
- Ask a small number of high-level questions to capture the user's domain,
  primary task, approximate entity/relationship types, and risk concerns.
- The user does NOT provide a detailed Schema — Schema is discovered through
  exploration. Save results to the User Concerns section of `CLAUDE.md`.

### Step 2: Parallel Schema Proposal (Paseo dispatch)
- Use Paseo `spawn_agent` to dispatch N (default **5**) parallel sub-agents.
- Each sub-agent loads `skills/worker/schema_creation/SKILL.md`:
  1. GraphRAG search existing Neo4j Schema (vector search + multi-hop) to
     find related Schema already in the graph.
  2. Based on search results + the sub-agent's own domain knowledge, create
     concept-level Schema entity types and relationship types.
  3. Cache the proposal locally to `tmp/schema_proposals/agent_N.json`.
  4. Notify the main Agent when done.
- **Stop condition**: all N sub-agents have returned a proposal (or errored).
  Failed sub-agents are retried once; persistent failures are logged and the
  remaining proposals still proceed to merge.

### Step 3: Schema Merge
- Load skill: `skills/worker/schema_merge/SKILL.md`
- Merge the N Schema proposals from Step 2 together with any existing Neo4j
  Schema into a single global Schema.
- Maintain the `SUBCLASS_OF` hierarchy (e.g. `Car → EV → Xiaomi Auto → ...`).
- Detect duplicates, resolve conflicts, ensure a concept-level-only ontology.
- Output the merged global Schema to `tmp/schema_definition.json`.

### Step 4: Per-Schema/Relation Parallel Extraction
For **each** new Schema/Relation in the merged Schema, dispatch a sub-agent
(parallel execution). Each sub-agent runs three sub-phases:

#### 4a. Evidence Search (deep-research style)
- Load skill: `skills/worker/evidence_search/SKILL.md`
- Multi-round iterative search: each round generates zh + en queries →
  `bilingual_search()` top-k=20 → merge by URL → `translate_content()` to
  zh-CN → analyze findings → generate next-round questions → continue.
- **Does NOT stop after finding one piece of evidence** — the goal is
  comprehensive coverage. Stop only when a round produces no new facts.

#### 4b. Triple Extraction (per-Schema/Relation dimension)
- Load skill: `skills/worker/triple_extraction/SKILL.md`
- From the Schema/Relation's leaf entities, explore outward **X-hop**
  (default **3**).
- Extract entities and relations along Schema-defined Relation directions.
- Form a subgraph centered on the leaf entity; each node carries an evidence
  slice + `source_url`.
- Validate entity-relation against schema-relation alignment; flag triples
  needing schema extension.

#### 4c. Entity-Relation Merge
- Load skill: `skills/worker/entity_relation_merge/SKILL.md`
- Entity alignment via semantic judgment (e.g. 苹果 ↔ Apple).
- Merge subgraphs. Bind entity ↔ Schema via `HAS_SCHEMA`; mark entities with
  no matching Schema as "empty Schema" for later Schema creation.

### Step 5: Subgraph Merge
- Load skill: `skills/worker/subgraph_merge/SKILL.md`
- Take the Neo4j intersection **2-hop subgraph** of newly inserted entities
  and merge overlapping subgraphs.
- For entities with empty Schema, create new Schema nodes and route them
  through `schema_merge`. For any new Schema produced, repeat Step 4.
- **Stop condition**: new search entities are completely irrelevant to the
  user's domain concerns (no butterfly effect — only direct domain relevance
  counts).

### Step 6: Audit → Fix Loop
- Load the verifier skills under `skills/verifier/`.
- Run the GAN-style adversarial audit (schema, graph structure, GraphRAG,
  evidence, task relevance). On error-level issues, fix from **Step 4**
  (re-run evidence search + triple extraction + entity-relation merge for the
  affected Schema/Relation), then re-audit.
- Loop until all audits pass or max rounds (default 5).

## Stop Conditions (Global)
1. Step 2 stops when all dispatched schema sub-agents return.
2. Step 4 stops per Schema/Relation when evidence search saturates (no new
   facts) and triples are validated.
3. Step 5 stops when newly discovered entities are irrelevant to the user's
   domain concerns — do NOT chase butterfly-effect connections.
4. Step 6 stops when all audits pass or the max audit rounds is reached.

## Error Handling
- A sub-agent that errors is retried once with the same scope.
- After a second failure, the sub-agent is terminated and the failure logged
  to `tmp/pipeline_errors.jsonl`; the pipeline continues with the remaining
  results so a single failure cannot block the whole construction.
- If a merge phase receives zero valid inputs (e.g. all Step 2 sub-agents
  failed), the pipeline aborts Step 3+ and surfaces the error to the user.

## Output
- `tmp/schema_proposals/agent_N.json` — per-sub-agent Schema proposals (Step 2).
- `tmp/schema_definition.json` — merged global Schema (Step 3).
- `data/evidence/` — collected evidence (Step 4a).
- `tmp/extracted_triples.md` — extracted triples (Step 4b).
- `reports/audits/` — audit reports + history (Step 6).
- `tmp/pipeline_errors.jsonl` — any sub-agent failures.
