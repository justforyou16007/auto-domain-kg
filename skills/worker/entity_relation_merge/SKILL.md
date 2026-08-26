---
name: entity-relation-merge
description: "Step 4c of the KG pipeline. Entity alignment and subgraph merging across sources. Semantic judgment identifies the same entity across sources (e.g. 苹果 ↔ Apple). Merge subgraphs. Bind entities to Schema nodes via HAS_SCHEMA. Mark entities with no matching Schema as empty Schema for later Schema creation. Uses graph_ops.find_merge_target_with_hierarchy() and merge_entity_to_parent_schema()."
---

# Entity-Relation Merge — Step 4c: Entity Alignment & Subgraph Merging

## Goal
Align entities extracted from different sources/evidence rounds, merge their
subgraphs, and bind every entity to a Schema node via `HAS_SCHEMA`. Entities
that have no matching Schema are marked "empty Schema" so Step 5 can create a
new Schema for them.

## Input
- Extracted triples + subgraphs from Step 4b (`tmp/extracted_triples.md`).
- Evidence from `data/evidence/`.
- The merged global Schema from `tmp/schema_definition.json`.

## Process

### 1. Entity Alignment (Semantic Judgment)
- Identify the same entity across sources using semantic judgment — not just
  string equality. Examples:
  - `苹果` ↔ `Apple` (same company, different language).
  - `Xiaomi Auto` ↔ `小米汽车` (same entity, different language).
  - `TSMC` ↔ `Taiwan Semiconductor Manufacturing Company` (abbr ↔ full name).
- Use `GraphOps.find_merge_target_with_hierarchy(entity_name, schema_id)` to
  locate semantically similar entities already in the graph. The search
  traverses `SUBCLASS_OF` upward, so an entity can merge into a parent Schema
  level when no exact match exists at the current level.

### 2. Subgraph Merge
- For aligned entities, merge their subgraphs:
  - Combine properties, keeping the more descriptive name.
  - Merge/redirect relationships so duplicate edges are collapsed.
  - Union the evidence slices and `source_url` sets so provenance is
    preserved.
- Use `GraphOps.merge_entity_to_parent_schema(entity_id, parent_schema_id)`
  when an entity should be promoted to a parent Schema level.

### 3. Bind Entity ↔ Schema
- Link every entity to its Schema node via `HAS_SCHEMA`.
- Validate that each entity's Instance relationships are allowed by the
  Schema-to-Schema relationship definitions; flag mismatches.

### 4. Mark Empty Schema
- For entities that have no matching Schema type, mark them as **empty
  Schema** (e.g. set `schema_id = None` / a sentinel) so Step 5
  (`subgraph_merge`) can create a new Schema for them and route it through
  `schema_merge`.
- Do NOT silently drop entities without a Schema — they are explicit signals
  that the ontology is incomplete.

## Output
- Merged entity subgraphs persisted to Neo4j (entities carry `source_url` and
  `source_text` for provenance).
- An "empty Schema" list appended to `tmp/entity_relation_merge_log.md`:
  entity name → reason no Schema matched → flagged for Step 5 Schema creation.
- Merge decisions logged to `tmp/entity_relation_merge_log.md`.

## Verification
- No duplicate entities remain for the same real-world object.
- Every entity is linked to a Schema node via `HAS_SCHEMA`, or explicitly
  marked empty Schema.
- Every merged entity retains all its source URLs / evidence slices.
