---
name: schema-creation
description: "Step 2 of KG construction (iterative). Research domain topics and create Schema-level concept ontology through an exploration-first discovery process. Schema only models concept-level types (e.g. 'Storage Device', 'Vehicle', 'Supplier') — never concrete instance names. Schema relationships must have explicit business semantics. Bilingual (zh+en) queries are searched and results translated before schema/entity exploration. Iterative discovery loop: bilingual search → translate → create schema → extract entities → GraphRAG merge → persist → discover gaps → query again."
---

# Schema Creation — Step 2: Iterative Domain Schema Generation (Concept Ontology)

## Goal
Iteratively research domain topics and generate a **Schema-layer concept ontology** through multiple search-and-create cycles. The Schema layer models **only** conceptual entity types (e.g., "Storage Device", "Vehicle", "Supplier", "Raw Material") — never concrete instance names (e.g., "Xiaomi SU7", "Sigma Lens"). Schema relationships must have explicit business meaning (e.g., `PRODUCES`, `SUPPLIES`, `PART_OF`) — never meaningless associations.

## Exploration-First Principle

> The user's initial input (from Step 1) is a **STARTING POINT**, not a complete specification. Schema types and relationships are **DISCOVERED** through iterative exploration, not generated from a fixed spec.

- The agent should **proactively search beyond** the user's initial entity list to discover related concepts the user did not mention.
- The agent should **NOT limit itself** to what the user mentioned — explore adjacent domains, supply-chain上下游 (upstream/downstream), and related industries.
- When the user provides approximate entity types, **treat them as hints, not constraints**. Search broadly within the domain and let the schema emerge from the data.
- If the user said "not sure" about entity/relationship types in Step 1, that is expected — discover them here through broad exploration.

## Bilingual Search + Translation

Retrieval completeness must not be limited by the search query's language. Before exploring Schema and entities:

1. **Generate bilingual queries** — for each sub-topic, the agent generates BOTH a Chinese query and an English query.
2. **Run `bilingual_search()`** (on `NewsAdapter` / `GoogleSearchNewsAdapter`) instead of `search_news()`. It issues searches for both language queries, merges the results, and deduplicates by URL.
3. **Translate all results** to the working language (default `zh-CN`) via `translate_content()` / `TranslationClient` before proceeding. Each translated `NewsItem` carries `original_language` and a normalized `language` field.
4. Only after this unified, translated corpus is ready does Schema and entity exploration begin.

## Schema Layer vs Instance Layer

| Layer | Contents | Example |
|-------|----------|---------|
| **Schema** | Concept-level entity types and relationship types only | `Supplier`, `Vehicle`, `RawMaterial` |
| **Instance** | Concrete entities with source provenance | `TSMC`, `Xiaomi SU7`, `Lithium Carbonate` |

- **Schema layer** defines the ontology: what types of things exist and how they relate.
- **Instance layer** populates the ontology with real-world entities.
- Each Instance entity is linked to its Schema type via `HAS_SCHEMA`.
- Instance-to-Instance relationships must be valid according to Schema-to-Schema relationships.

## Strong Agent Instructions

You are the **Schema Architect** (strong agent). Your task is to design a **concept-level domain ontology** through an **iterative, research-driven discovery process**.

### Input
- User concerns from `CLAUDE.md` (User Concerns section)
- Domain, entities, relationships identified in Step 1 — treat as **hints/starting points**, not constraints
- Existing graph structure (previous iteration's Schema + Instance nodes)

### Iterative Discovery Process

The full iteration cycle is:

**a. Load User Concerns** — Read the user's domain and existing information from `CLAUDE.md` (User Concerns section). Remember the user's entity/relationship types are approximate hints — explore broadly beyond them.

**b. Bilingual Search** — Use `bilingual_search()` (not `search_news()`) on the `NewsAdapter` to research the current sub-topic. The agent generates BOTH a Chinese and an English query for each sub-topic/entity so retrieval is not limited by language. **Explore broadly** — do not restrict the search to what the user mentioned; proactively search adjacent domains, supply-chain上下游, and related industries to discover concepts the user did not name. Merge and deduplicate the bilingual results by URL, then `translate_content()` all results to the working language before proceeding.

**c. Create Schema & Relationships** — Based on the **translated** search results, define Schema-level entity types and relationship types:
- Entity types must be **concept-level** (e.g., "Storage Device", not "Samsung 990 Pro")
- Relationship types must have **explicit business semantics** (e.g., `PRODUCES`, `SUPPLIES`, `PART_OF`, `LOCATED_IN`)
- Let the schema **emerge from the data** — add types discovered through broad exploration, not only those the user mentioned
- Append new types to `tmp/schema_definition.json` (merge with existing, deduplicate by name)

**d. Extract Triples** — For each entity/triple sub-graph discovered during the exploration, use the Paseo MCP `spawn_agent` tool to dispatch sub-agents for parallel exploration. Extract (entity, relation, entity) triples from the **translated** search evidence, guided by the Schema layer just created. Only extract concrete Instance entities (never concepts). Validate each triple's relation type against the Schema-to-Schema relationships; flag triples needing schema extension. Save triples to `tmp/extracted_triples.md`. Use the `triple_extraction` skill for this sub-step.

**e. Collect Evidence** — Spawn weak sub-agents (collector_provider) to search for news/articles about the entities from this iteration. Save evidence to `data/evidence/` as JSONL files (2-3 independent sources per entity). Use the `entity_collection` skill for this sub-step.

**f. Extract Corresponding Entities** — Extract concrete Instance-level entities that match the Schema types just created, using the search results as evidence.

**g. GraphRAG Merge** — For each Schema type and Instance entity, perform vector retrieval + multi-hop subgraph exploration to find related nodes already in the graph. If semantically similar nodes exist, merge them (e.g., "Xiaomi Auto" and "Xiaomi SU7" may refer to the same entity).

**h. Persist** — Save the current batch of Schema + Instance + Relationships to Neo4j.

**i. Discover Completeness Gaps** — Analyze the current graph structure to identify gaps:
- Which Schema types lack Instance entities?
- Which relationships lack connections between entities?
- Which domain sub-topics are not yet covered?

**j. Generate New Query** — Based on the gap analysis, formulate a new search query to explore the next area.

**k. Repeat** from step **b** until the termination condition is met.

### Termination Condition

Stop iterating when **search results and discovered entities can no longer materially affect the entities relevant to the user's domain concerns**. Do NOT consider butterfly-effect connections that do not exist in current logic. Specifically:

1. **No new Schema types**: The last search results did not yield any new concept-level entity types or relationship types.
2. **Scope boundary**: Search results consistently return information outside the user's domain.
3. **Entity saturation**: All meaningful Schema types have been defined.
4. **Relationship saturation**: All meaningful business relationships between discovered Schema types have been defined.
5. **User concern coverage**: All user concerns from Step 1 have been addressed by existing Schema types.
6. **No impact on domain entities**: New search results would not add entities that affect the user's domain entities.

### Output Format

Each iteration produces partial schema definitions in the same format. The full schema is accumulated in `tmp/schema_definition.json`.

#### Schema Entity Types (Concept Level Only)
For each entity type, define:
- **Name**: Concept-level type name (e.g., "Supplier", "Material", "Vehicle") — NOT instance names
- **Description**: What this concept represents
- **Properties**: List of (name, type, description, required) tuples
- **Parent**: Optional parent entity type for inheritance

Format:
```json
{
  "entity_types": [
    {
      "name": "Supplier",
      "description": "A company that supplies materials or components",
      "properties": [
        {"name": "name", "type": "string", "description": "Company name", "required": true},
        {"name": "description", "type": "text", "description": "Company description", "required": false},
        {"name": "country", "type": "string", "description": "Country of operation", "required": false}
      ],
      "parent": "Organization"
    }
  ]
}
```

#### Schema Relationship Types (Must Have Business Semantics)
For each relationship type, define:
- **Name**: Relationship type with explicit business meaning (e.g., `SUPPLIES`, `PRODUCES`, `PART_OF`, `LOCATED_IN`, `DEVELOPS`)
- **Source entity**: The entity type this relationship originates from
- **Target entity**: The entity type this relationship points to
- **Description**: What this relationship represents
- **Properties**: Optional relationship properties

Format:
```json
{
  "relationship_types": [
    {
      "name": "SUPPLIES",
      "source": "Supplier",
      "target": "Material",
      "description": "Supplier provides this material",
      "properties": [
        {"name": "contract_value", "type": "number", "description": "Contract value in USD"}
      ]
    }
  ]
}
```

#### Inheritance Hierarchy
```json
{
  "inheritance": [
    {
      "child": "Supplier",
      "parent": "Organization"
    }
  ]
}
```

Schema inheritance is realized in the graph as **SUBCLASS_OF** relationships between Schema nodes:

- **Graph representation**: When `Supplier` inherits from `Organization`, a `(Supplier)-[:SUBCLASS_OF]->(Organization)` relationship is created in Neo4j.
- **Creation**: Use `GraphOps.create_schema_node()` with `parent_schema_id` to automatically create the SUBCLASS_OF relationship. Alternatively, use `Neo4jClient.create_schema_hierarchy()` directly.
- **Querying ancestors**: Use `Neo4jClient.get_schema_ancestors(schema_id)` to traverse upward along SUBCLASS_OF edges.
- **Querying descendants**: Use `Neo4jClient.get_schema_descendants(schema_id)` to traverse downward.
- **Finding common ancestors**: Use `Neo4jClient.find_common_ancestor(schema_id_a, schema_id_b)` to find the nearest common parent.

**Schema merging across inheritance**: When merging entities during graph persistence, the system checks not only the current Schema level but also ancestor Schema nodes. If two child schemas (e.g., "电子器件" and "工业器件") share the same relationship type (e.g., `-> 制造商`), the relationship can be promoted to their common ancestor (e.g., "器件" -> 制造商). This is handled by `GraphOps.find_merge_target_with_hierarchy()` and `GraphOps.merge_entity_to_parent_schema()`.

### Schema Constraints for Entity Extraction

The Schema layer's `relationship_types` are used to **constrain Instance-level triple extraction**:
- Instance A and Instance B can only have a relationship if their corresponding Schema types are connected by a defined relationship type.
- Example: If `Supplier` ―[`SUPPLIES`]→ `Material` is defined in Schema, then `TSMC` ―[`SUPPLIES`]→ `Silicon Wafers` is valid.
- If an Instance relationship has no matching Schema relationship, it is flagged as **Schema extension needed**.
- If an Instance relationship violates a Schema relationship constraint, it is flagged as **Schema inconsistency**.

### Schema Persistence
- Schema is incrementally accumulated in `tmp/schema_definition.json`.
- Each iteration appends/merges new types into the existing file (not overwriting from scratch).
- The final file represents the complete schema after all iterations.

### Cross-Iteration Schema Consistency
- **Deduplication**: Before adding a new entity type, check if one with the same name already exists. If so, merge properties instead of duplicating.
- **Relationship conflict resolution**: If two iterations define the same relationship type name with different source/target entity types, use the latest definition but log the conflict.
- **Inheritance consistency**: Ensure parent entity types referenced in inheritance exist in the accumulated schema.
- **Property merge**: When the same entity type appears in multiple iterations, combine all unique properties.
- **Concept/Instance separation**: Ensure no concrete instance names leak into Schema entity types.

### Verification
- All entity types are concept-level (no instance names)
- All relationship types have explicit business semantics (no meaningless associations)
- All relationship types have valid source/target entity references
- No circular inheritance
- Properties have appropriate types (string, number, text, date, list)
- No duplicate entity type names in the final schema
- All relationship source/target entity types exist in the schema