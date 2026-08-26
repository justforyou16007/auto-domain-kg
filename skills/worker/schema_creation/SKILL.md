---
name: schema-creation
description: "Step 2 of the KG pipeline (parallel proposal). GraphRAG search existing Neo4j Schema (vector search + multi-hop) to find related Schema, then based on search results + model's own domain knowledge create concept-level Schema entity types and relationship types. Schema only models concept-level types — never concrete instance names. Schema relationships must have explicit business semantics. Bilingual (zh+en) queries are searched and results translated before schema creation. Cache the proposal locally (tmp/schema_proposals/agent_N.json) and notify the main Agent. ONLY creates Schema + Relations — no entity collection, triple extraction, refinement, or persistence."
---

# Schema Creation — Step 2: Parallel Schema+Relation Proposal (Concept Ontology Only)

## Goal
As a **parallel sub-agent** dispatched by the `kg-gen-pipeline`, research the
domain and propose a **Schema-layer concept ontology** (entity types +
relationship types only). This skill does **only** Schema + Relation creation
— no entity collection, no triple extraction, no refinement, no persistence.
The proposal is cached locally and the main Agent is notified; merging
happens later in the `schema-merge` skill (Step 3).

## Exploration-First Principle

> The user's initial input (from Step 1) is a **STARTING POINT**, not a
> complete specification. Schema types and relationships are **DISCOVERED**
> through exploration, not generated from a fixed spec.

- The agent should **proactively search beyond** the user's initial entity list
  to discover related concepts the user did not mention.
- The agent should **NOT limit itself** to what the user mentioned — explore
  adjacent domains, supply-chain上下游 (upstream/downstream), and related
  industries.
- When the user provides approximate entity types, **treat them as hints, not
  constraints**. Search broadly within the domain and let the schema emerge
  from the data.

## Bilingual Search + Translation

Retrieval completeness must not be limited by the search query's language.
Before creating Schema:

1. **Generate bilingual queries** — for each sub-topic, the agent generates
   BOTH a Chinese query and an English query.
2. **Run `bilingual_search()`** (on `NewsAdapter`) instead of `search_news()`.
   It issues searches for both language queries, merges the results, and
   deduplicates by URL.
3. **Translate all results** to the working language (default `zh-CN`) via
   `translate_content()` / `TranslationClient` before proceeding. Each
   translated `NewsItem` carries `original_language`.
4. Only after this unified, translated corpus is ready does Schema creation
   begin.

## Schema Layer vs Instance Layer

| Layer | Contents | Example |
|-------|----------|---------|
| **Schema** | Concept-level entity types and relationship types only | `Supplier`, `Vehicle`, `RawMaterial` |
| **Instance** | Concrete entities with source provenance | `TSMC`, `Xiaomi SU7`, `Lithium Carbonate` |

- This skill touches **only the Schema layer**. Instance entities are handled
  by `triple_extraction` (Step 4b) and `entity_relation_merge` (Step 4c).
- Schema relationships must have explicit business meaning (e.g. `PRODUCES`,
  `SUPPLIES`, `PART_OF`) — never meaningless associations.

## Sub-Agent Instructions

You are a **Schema Architect** sub-agent. Your scope is Schema + Relation
creation only.

### Input
- User concerns from `CLAUDE.md` (User Concerns section) — approximate hints.
- Your sub-agent index `N` (used for the output filename).

### Process

**a. Load User Concerns** — Read the user's domain and existing information
from `CLAUDE.md`. Remember the user's entity/relationship types are
approximate hints — explore broadly beyond them.

**b. GraphRAG Search Existing Schema** — Search the existing Neo4j Schema so
your proposal is informed by what is already in the graph:
- Vector search (`Neo4jClient.vector_search()` / `GraphOps.vector_search()`)
  for related concept types.
- Multi-hop traversal (`multi_hop_subgraph()`) along `SUBCLASS_OF` to find
  ancestors/descendants of related Schema nodes.
- Reuse existing Schema types where they fit; do not redefine them.

**c. Bilingual Search** — Use `bilingual_search()` to research the current
sub-topic. Generate BOTH a Chinese and an English query for each sub-topic so
retrieval is not limited by language. **Explore broadly** — adjacent domains,
supply-chain上下游, related industries. Merge and deduplicate by URL, then
`translate_content()` all results to the working language before proceeding.

**d. Create Schema & Relationships** — Based on the **translated** search
results plus your own domain knowledge, define Schema-level entity types and
relationship types:
- Entity types must be **concept-level** (e.g., "Storage Device", not
  "Samsung 990 Pro").
- Relationship types must have **explicit business semantics** (e.g.,
  `PRODUCES`, `SUPPLIES`, `PART_OF`, `LOCATED_IN`).
- Let the schema **emerge from the data** — add types discovered through broad
  exploration, not only those the user mentioned.

**e. Cache Locally** — Write your proposal to
`tmp/schema_proposals/agent_N.json` (replace `N` with your sub-agent index)
in the format below.

**f. Notify Main Agent** — Signal the main Agent that your proposal is ready.
Do NOT merge proposals yourself — that is the `schema-merge` skill's job
(Step 3). Do NOT collect entities, extract triples, refine, or persist.

### Output Format

Write `tmp/schema_proposals/agent_N.json`:

#### Schema Entity Types (Concept Level Only)
For each entity type, define:
- **Name**: Concept-level type name (e.g., "Supplier", "Material", "Vehicle")
  — NOT instance names.
- **Description**: What this concept represents.
- **Properties**: List of (name, type, description, required) tuples.
- **Parent**: Optional parent entity type for inheritance.

```json
{
  "entity_types": [
    {
      "name": "Supplier",
      "description": "A company that supplies materials or components",
      "properties": [
        {"name": "name", "type": "string", "description": "Company name", "required": true}
      ],
      "parent": "Organization"
    }
  ]
}
```

#### Schema Relationship Types (Must Have Business Semantics)
```json
{
  "relationship_types": [
    {
      "name": "SUPPLIES",
      "source": "Supplier",
      "target": "Material",
      "description": "Supplier provides this material"
    }
  ]
}
```

#### Inheritance Hierarchy
```json
{
  "inheritance": [
    {"child": "Supplier", "parent": "Organization"}
  ]
}
```

Schema inheritance is realized in the graph as **SUBCLASS_OF** relationships
between Schema nodes (materialized later by `schema-merge` via
`Neo4jClient.create_schema_hierarchy()`).

### Verification (Self-Check Before Notifying)
- All entity types are concept-level (no instance names).
- All relationship types have explicit business semantics.
- All relationship source/target entity types exist in the proposal.
- No circular inheritance.
- No duplicate entity type names.
- Proposal written to `tmp/schema_proposals/agent_N.json`.
