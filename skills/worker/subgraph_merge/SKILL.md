---
name: subgraph-merge
description: "Step 5 of the KG pipeline. Take the Neo4j intersection 2-hop subgraph of newly inserted entities and merge overlapping subgraphs. For entities with empty Schema, create new Schema nodes and route through schema-merge. For new Schema, trigger Step 4 recursively. Stop condition: new search entities are completely irrelevant to user's domain concerns (no butterfly effect — only direct domain relevance counts). Uses graph_ops.multi_hop_subgraph() and vector_search()."
---

# Subgraph Merge — Step 5: Subgraph Intersection, Merge & Recursive Expansion

## Goal
Take the Neo4j **intersection 2-hop subgraph** of newly inserted entities,
merge overlapping subgraphs, and recursively expand the graph. Entities with
empty Schema (flagged in Step 4c) get new Schema nodes created and routed
through `schema_merge`; any new Schema then re-enters Step 4. The phase stops
when newly discovered entities are irrelevant to the user's domain concerns.

## Input
- Newly inserted entities from Step 4c (and the "empty Schema" list in
  `tmp/entity_relation_merge_log.md`).
- The merged global Schema from `tmp/schema_definition.json`.
- User concerns from `CLAUDE.md`.

## Process

### 1. Extract Intersection 2-Hop Subgraph
- For each newly inserted entity, call `GraphOps.multi_hop_subgraph(entity_id, hops=2)`
  to get its 2-hop neighborhood.
- Compute the **intersection** — entities/edges that appear in more than one
  new entity's 2-hop subgraph — these are the overlap candidates to merge.

### 2. Merge Overlapping Subgraphs
- Merge semantically similar nodes in the overlap region (semantic judgment,
  e.g. `苹果` ↔ `Apple`).
- Use `GraphOps.find_merge_target_with_hierarchy()` and
  `GraphOps.merge_entity_to_parent_schema()` for hierarchy-aware merging.
- Use `GraphOps.vector_search()` / `Neo4jClient.vector_search()` to find
  related existing nodes and avoid creating duplicates.

### 3. Handle Empty-Schema Entities
- For each entity marked "empty Schema" in Step 4c:
  1. Create a new Schema node (concept-level type) for it.
  2. Route the new Schema through the `schema_merge` skill so it is reconciled
     with the global Schema and the `SUBCLASS_OF` hierarchy is maintained.
  3. Link the entity to the new Schema via `HAS_SCHEMA`.

### 4. Recursive Expansion (New Schema → Step 4)
- For every new Schema created in step 3, trigger **Step 4** recursively:
  dispatch a sub-agent (via Paseo `spawn_agent`) to run evidence-search +
  triple_extraction + entity-relation-merge for the new Schema/Relation
  dimension.
- Collect the new entities produced and feed them back into step 1 of this
  phase.

### 5. Stop Condition
Stop when the newly discovered search entities are **completely irrelevant**
to the user's domain concerns. Only **direct domain relevance** counts — do
NOT chase butterfly-effect connections that have no direct bearing on the
user's domain. Concretely:
- New entities do not participate in any Schema relationship relevant to the
  user's domain.
- Search results consistently return information outside the user's domain.
- No new Schema types are produced by the recursive Step 4.

## Output
- Merged subgraphs persisted to Neo4j (inline persistence — entities carry
  `source_url` / `source_text` for provenance).
- New Schema nodes created for empty-Schema entities, reconciled via
  `schema_merge`.
- A recursion log appended to `tmp/subgraph_merge_log.md`:
  - Overlaps merged.
  - New Schema created (and re-fed to Step 4).
  - Why the stop condition was met.
