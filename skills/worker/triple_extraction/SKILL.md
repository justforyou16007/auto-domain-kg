---
name: triple-extraction
description: "Step 4b of the KG pipeline (per Schema/Relation dimension). From the Schema/Relation's leaf entities, explore outward X-hop (default 3) and extract entities and relations along Schema-defined Relation directions. Form a subgraph centered on the leaf entity; each entity and relation carries an evidence slice + source_url. Validate entity-relation against schema-relation alignment and flag triples needing schema extension. X is configurable (default 3) — X-hop exploration is performed explicitly. Only extract concrete Instance entities (never concepts)."
---

# Triple Extraction — Step 4b: Per-Schema/Relation X-Hop Subgraph Extraction

## Goal
For a **single Schema/Relation dimension** assigned to this sub-agent, explore
outward **X-hop** (default **3**) from the Schema/Relation's leaf entities and
extract (entity, relation, entity) triples along the Schema-defined Relation
directions. Form a subgraph centered on each leaf entity where every node and
edge carries an evidence slice + `source_url`. Validate each triple against
schema-relation alignment and flag triples that need schema extension.

## Input
- The assigned Schema/Relation dimension (entity types + relationship types
  from `tmp/schema_definition.json`).
- The leaf entities for this dimension (concrete Instance entities discovered
  during evidence search).
- Evidence from `data/evidence/` (loaded via `EvidenceStore`).
- User concerns from `CLAUDE.md`.
- **X** — the hop depth (default **3**, configurable per dispatch).

## Sub-Agent Instructions

You are a **Triple Extractor** sub-agent scoped to one Schema/Relation
dimension. Your scope is X-hop exploration + triple extraction + validation —
NOT Schema creation, NOT merging across sources (that is
`entity_relation_merge`, Step 4c).

### Process

#### 1. Load the Schema/Relation Dimension
- Load the assigned entity types and relationship types from
  `tmp/schema_definition.json`.
- Identify the **leaf entities** for this dimension (concrete Instance
  entities at the leaves of the `SUBCLASS_OF` hierarchy).

#### 2. X-Hop Exploration (default 3)
- From each leaf entity, explore outward **X-hop** (default 3 hops).
- At each hop, follow the Schema-defined Relation directions — only traverse
  relationships that the Schema declares between the relevant entity types.
- Collect the evidence encountered along each hop so every discovered entity
  and relation is tied to a source.

#### 3. Extract Triples
- Along the X-hop traversal, extract triples:

  ```
  (Entity A) --[RELATIONSHIP]--> (Entity B)
  ```

  Example:
  ```
  (TSMC) --[SUPPLIES]--> (Silicon Wafers)
  Evidence: "Apple contracts with TSMC to manufacture iPhone processors"
  ```

- Only extract **concrete Instance entities** (e.g., "TSMC", "Xiaomi SU7").
  Do NOT extract concept names (e.g., "chip manufacturer") as entities —
  those belong to the Schema layer.

#### 4. Form a Subgraph per Leaf Entity
- Center the subgraph on each leaf entity.
- Every node (entity) in the subgraph carries:
  - `source_url` — the originating web page URL.
  - `source_text` — the exact evidence text slice.
  - Its Schema type mapping.
- Every edge (relation) carries its evidence slice + `source_url`.

#### 5. Map Entities to Schema Types
- Each concrete Instance entity must map to exactly one Schema entity type.
- If an entity is a concept rather than an instance, skip it (or record it for
  the Schema layer).

#### 6. Validate Against Schema-Relation Alignment
- **Valid**: Schema A and Schema B have a defined relationship type, and the
  Instance A→Instance B relationship uses that type.
- **Schema inconsistency**: Schema A and Schema B have a relationship type,
  but the Instance relationship uses a different/wrong type. Mark and flag.
- **Schema extension needed**: Instance A and Instance B have a genuine
  relationship, but Schema A and Schema B have NO defined relationship. Flag
  it as a Schema extension requirement (do NOT silently drop it).

#### 7. Cross-Validate Triples Across Multiple Sources
- Use `EvidenceStore.cross_validate()` to check consensus across sources.
- Use `EvidenceStore.is_well_supported()` to verify multi-source coverage.
- **Single-source triples**: mark as "low confidence".
- **Conflicting triples**: mark as "needs human review".
- **Critical facts** (risk events, major changes, contractual relationships):
  require 3+ independent sources.
- Record the cross-validation result in each triple's metadata.

#### 8. Save Extracted Triples
- Append triples to `tmp/extracted_triples.md`:

  ```markdown
  ## Triple: [ID-001]
  - **Subject**: TSMC (entity_type: Supplier, schema: Supplier)
  - **Relation**: SUPPLIES
  - **Object**: Silicon Wafers (entity_type: Material, schema: Material)
  - **Hop**: 1 (distance from leaf entity Xiaomi SU7)
  - **Evidence**: "Apple contracts with TSMC to manufacture iPhone processors"
  - **Source URL**: https://example.com/news/1
  - **Source Text**: "Apple contracts with TSMC to manufacture iPhone processors"
  - **Confidence**: HIGH
  ```

- Use `EvidenceStore.save_evidence()` with a unique `relation_id` per triple.

### Extraction Guidelines
- **Prefer explicit statements** over inferred relationships.
- **Include exact text** from the source as evidence.
- **Confidence levels**: HIGH (explicitly stated), MEDIUM (strongly implied),
  LOW (weakly inferred).
- **One triple per row** — do not combine multiple relationships.
- **Entity names** should be specific concrete instances (never concept names).
- **X-hop is explicit**: every triple records its hop distance from the leaf
  entity so the subgraph structure is traceable.
- **Source provenance**: record `source_url` and `source_text` for every entity
  and relation.

### Output
- `tmp/extracted_triples.md` — triples for this Schema/Relation dimension,
  each with hop distance, evidence slice, and `source_url`.
- Flagged `schema_extension_needed` triples reported for Schema reconciliation.
