---
name: schema-merge
description: "Step 3 of the KG pipeline. Merge multiple Schema proposals (from Step 2's N parallel sub-agents) with existing Neo4j Schema into one global Schema. Maintain the SUBCLASS_OF hierarchy (e.g. Car → EV → Xiaomi Auto). Detect duplicates, resolve conflicts, ensure a concept-level-only ontology. Uses neo4j_client.create_schema_hierarchy(), get_schema_ancestors(), find_common_ancestor(). Output merged global Schema to tmp/schema_definition.json."
---

# Schema Merge — Step 3: Merge Parallel Schema Proposals into a Global Schema

## Goal
Merge the N Schema proposals produced by the Step 2 parallel sub-agents
(`tmp/schema_proposals/agent_N.json`) together with any **existing** Neo4j
Schema into a single, coherent, concept-level-only global Schema. Preserve
and reconcile the `SUBCLASS_OF` inheritance hierarchy across all proposals.

## Input
- `tmp/schema_proposals/agent_N.json` — one file per Step 2 sub-agent, each
  containing `entity_types`, `relationship_types`, and `inheritance`.
- Existing Neo4j Schema nodes (concept-level entity types + `SUBCLASS_OF`
  edges) retrieved via GraphRAG vector search + multi-hop traversal.
- User concerns from `CLAUDE.md`.

## Process

### 1. Load All Proposals
- Read every `tmp/schema_proposals/agent_*.json` file.
- Load the existing Neo4j Schema via `Neo4jClient` (vector search +
  `multi_hop_subgraph()` along `SUBCLASS_OF`).
- Treat existing Schema as another "proposal" with authoritative priority for
  already-validated types.

### 2. Deduplicate Entity Types
- Detect concept-level entity types that are the same across proposals
  (semantic judgment, e.g. "Supplier" ≈ "供应商").
- Merge their properties (union of unique properties), keeping the more
  descriptive name. Log each merge.
- Reject any concrete instance names that leaked into a proposal — Schema must
  stay concept-level only.

### 3. Resolve Relationship Conflicts
- If the same relationship name is defined with different source/target
  entity types across proposals, keep the definition best supported by the
  evidence and log the conflict.
- Ensure every relationship's source/target entity types exist in the merged
  Schema (add missing entity types if a relationship references them).

### 4. Maintain the SUBCLASS_OF Hierarchy
- Reconcile inheritance edges from all proposals into a single DAG.
- Use `Neo4jClient.create_schema_hierarchy(child_schema_id, parent_schema_id)`
  to materialize `SUBCLASS_OF` edges.
- Use `Neo4jClient.get_schema_ancestors(schema_id)` to traverse upward and
  `Neo4jClient.find_common_ancestor(schema_id_a, schema_id_b)` to collapse
  redundant hierarchy edges (e.g. when two proposals imply the same parent,
  keep only the nearest).
- Detect and break circular inheritance.
- Example hierarchy: `Car → EV → Xiaomi Auto → ...` is preserved as a chain of
  `SUBCLASS_OF` edges, never flattened.

### 5. Concept-Level-Only Enforcement
- No concrete instance names (e.g. "Xiaomi SU7", "TSMC") may remain in the
  Schema. Move any leaked instances out and flag them for the Instance layer.
- No generic concept names may be tracked as instances.

### 6. Write the Merged Global Schema
- Accumulate the result in `tmp/schema_definition.json` with `entity_types`,
  `relationship_types`, and `inheritance`.
- Append a merge log to `tmp/schema_merge_log.md` describing every
  deduplication, conflict resolution, and hierarchy reconciliation.

## Output
- `tmp/schema_definition.json` — the merged global Schema (concept-level
  ontology + `SUBCLASS_OF` hierarchy).
- `tmp/schema_merge_log.md` — merge decisions and rationale.

## Verification
- All entity types are concept-level (no instance names).
- All relationship types have explicit business semantics and valid
  source/target entity references.
- No circular `SUBCLASS_OF` inheritance.
- No duplicate entity type names.
- Every relationship source/target entity type exists in the Schema.
