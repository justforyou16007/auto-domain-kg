---
name: graph-persistence
description: "Step 3 of KG construction. Persist Schema concept ontology + Instance entities to Neo4j. Schema nodes contain only concept-level info. Entity nodes carry source_url and source_text for provenance. Validate Instance relationships against Schema before persisting. Perform semantic merging and discover completeness gaps. Link entity nodes to their schema nodes. Store evidence slices and source URLs on nodes for traceability."
---

# Graph Persistence — Step 3: Persist Schema + Instances to Neo4j

## Goal
Persist the domain Schema (concept ontology) and extracted Instance entities to Neo4j, link entities to their Schema nodes, validate Instance relationships against Schema, perform semantic merging, generate embeddings, and discover completeness gaps.

## Process

### 0. Relation Alignment Check (before persisting)
Before persisting, ensure Schema, Schema-relations, entity, and entity-relations are aligned:
- Load the Schema from `tmp/schema_definition.json` and the extracted triples from `tmp/extracted_triples.md`.
- Run `GraphOps.validate_relation_alignment(schema_definition, extracted_triples)` to check that every triple's relation type has a corresponding schema-level relationship definition.
- Run `GraphOps.get_missing_schema_relations(triples, schema_definition)` to find entity relations that have no schema relation counterpart.
- If missing schema relations are found, either add them to the schema (schema extension) or skip persisting those triples. Do NOT persist entity relations that have no schema relation definition — this keeps Schema, Schema-relation, entity, and entity-relation layers aligned.

### 1. Load Schema
- Load the Schema from `tmp/schema_definition.json`.
- For each Schema entity type, create a **Schema node** in Neo4j using `GraphOps.create_schema_node()`.
- Schema nodes contain **only concept-level ontology information** (name, type, description, fields). Do NOT put instance names or instance details in Schema nodes.
- Note the Schema node IDs for later use.

### 2. Create Entity Instances
- Load extracted triples from `tmp/extracted_triples.md`.
- For each unique concrete Instance entity, create an entity node using `GraphOps.create_entity_node()`:
  - `schema_id`: The Schema node ID for this entity's type
  - `name`: Entity name (concrete instance, e.g., "TSMC")
  - `properties`: Entity properties (from extraction)
  - `source_url`: The source web page URL for this entity (from the extraction evidence)
  - `source_text`: The source text snippet for this entity (from the extraction evidence)
  - `evidence`: Evidence records from the extraction
- Every entity node **must** carry `source_url` and `source_text` so it can be traced back to its source paragraph and URL without consulting the evidence store separately.
- This automatically:
  - Links the entity to its Schema via `HAS_SCHEMA`
  - Generates and stores the embedding
  - Saves evidence to the evidence store

### 3. Create Relationships (with Schema Validation)
- For each triple, first validate that the two entities' Schema types have a defined relationship:
  - If valid (Schema A and Schema B have this relationship type), create the relationship using `GraphOps.create_relationship()`.
  - If the Schema does NOT define this relationship, do NOT create it blindly. Record it as a **Schema extension need** and report it.
  - If the relationship contradicts the Schema definition, flag it as **Schema inconsistency**.
- Create relationships:
  - `from_entity`: Subject entity ID
  - `to_entity`: Object entity ID
  - `rel_type`: Relationship type
  - `properties`: Relationship properties
  - `evidence`: Evidence records

### 4. Semantic Merging
Before persisting, and after each batch:
- Use GraphRAG (vector retrieval + multi-hop subgraph exploration) to search for already-graphged related nodes.
- Compare semantically similar nodes, e.g., "Xiaomi Auto" vs "Xiaomi SU7" may refer to the same entity.
- If semantic similarity is high, **merge** the nodes instead of creating duplicates:
  - Merge properties, keeping the more descriptive name.
  - Merge/redirect relationships.
  - Log the merge in `tmp/persistence_log.md`.

#### Hierarchy-Aware Semantic Merging
When merging entities, the system does not limit the search to the current Schema level — it also checks parent Schema nodes along the SUBCLASS_OF hierarchy:

- **Current-level search first**: Use `GraphOps.find_merge_target_with_hierarchy(entity_name, schema_id)` to search the current Schema level for semantically similar entities.
- **Parent-level fallback**: If no merge target is found at the current level, the method automatically traverses SUBCLASS_OF upward to search parent Schema nodes.
- **Hierarchy promotion**: If a merge target is found in a parent Schema, the entity can be re-linked to the parent Schema using `GraphOps.merge_entity_to_parent_schema(entity_id, parent_schema_id)`.
- **Example**: If "电子器件" and "工业器件" both have entities with the same semantic meaning, those entities can be merged under their common ancestor "器件" instead of being duplicated in both child schemas.

This hierarchy-aware approach reduces entity duplication and ensures that entities from related sub-domains are properly consolidated.

### 5. Set Up Vector Index
- Call `GraphOps.setup_vector_index()` to create the vector index for similarity search.

### 6. Completeness Gap Discovery
After persisting the batch, analyze the graph structure to find completeness gaps:
- **Missing entities**: Schema types that have no Instance entities yet.
- **Missing connections**: Entities that logically connect but have no relationship between them.
- **Uncovered sub-topics**: Domain sub-topics from user concerns not yet represented in the graph.
- Generate a new exploration query and feed it back to the search step (Step 2).

### 7. Verify
- Run a sample vector search to confirm embeddings work.
- Run a multi-hop query to confirm graph connectivity.
- Print statistics: entity count, relation count, schema count.

### Error Handling
- If an entity already exists, skip or update (configurable).
- If a relationship already exists, check if it needs updating.
- Log all operations to `tmp/persistence_log.md`.

### Output
- `tmp/persistence_log.md` with:
  - Schema nodes created
  - Entity nodes created (with their source_url / source_text)
  - Relationships created
  - Schema extension needs / inconsistencies found
  - Semantic merges performed
  - Completeness gaps identified
  - Any errors or warnings
  - Final statistics