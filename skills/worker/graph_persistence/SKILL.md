---
name: graph-persistence
description: "Step 4 of KG construction. Persist schema, entities, and relationships to Neo4j. Link entity nodes to their schema nodes. Store evidence slices and source URLs on nodes for traceability."
---

# Graph Persistence — Step 4: Persist Schema + Instances to Neo4j

## Goal
Persist the domain schema and extracted triples to Neo4j, link entities to schema nodes, and generate embeddings for vector search.

## Process

### 1. Load Schema
- Load the schema from `tmp/schema_definition.json`.
- For each entity type, create a Schema node in Neo4j using `GraphOps.create_schema_node()`.
- Note the schema node IDs for later use.

### 2. Create Entity Instances
- Load extracted triples from `tmp/extracted_triples.md`.
- For each unique entity, create an entity node using `GraphOps.create_entity_node()`:
  - `schema_id`: The schema node ID for this entity's type
  - `name`: Entity name
  - `properties`: Entity properties (from extraction)
  - `evidence`: Evidence records from the extraction
- This automatically:
  - Links the entity to its schema via HAS_SCHEMA
  - Generates and stores the embedding
  - Saves evidence to the evidence store

### 3. Create Relationships
- For each triple, create a relationship using `GraphOps.create_relationship()`:
  - `from_entity`: Subject entity ID
  - `to_entity`: Object entity ID
  - `rel_type`: Relationship type
  - `properties`: Relationship properties
  - `evidence`: Evidence records

### 4. Set Up Vector Index
- Call `GraphOps.setup_vector_index()` to create the vector index for similarity search.

### 5. Verify
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
  - Entity nodes created
  - Relationships created
  - Any errors or warnings
  - Final statistics