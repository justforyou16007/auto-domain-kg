---
name: schema-creation
description: "Step 2 of KG construction (iterative). Research domain topics and generate schema definitions in iterations. Each iteration: search a sub-topic → create partial entity types and relationship types → merge results into tmp/schema_definition.json. Loop until no new schema types emerge or domain scope is exhausted."
---

# Schema Creation — Step 2: Iterative Domain Schema Generation

## Goal
Iteratively research domain topics and generate the domain schema through multiple search-and-create cycles, rather than producing all entity types and relationship types in one shot.

## Strong Agent Instructions

You are the **Schema Architect** (strong agent). Your task is to design a domain schema through an **iterative, research-driven** process.

### Input
- User concerns from `CLAUDE.md` (User Concerns section)
- Domain, entities, relationships identified in Step 1

### Iterative Process

1. **Initial Search**: Start by searching for information about the domain using the web search tool.
   - Identify the first sub-topic or entity cluster to explore.
   - Search for domain-specific terms to understand the landscape.

2. **Create Partial Schema**: Based on the search results, create entity types and relationship types for the current sub-topic/cluster.
   - Do NOT try to generate all entity types at once.
   - Focus on entities and relationships that are directly related to the current search results.

3. **Merge Results**: Append the new schema elements to `tmp/schema_definition.json`.
   - Read the existing file if it exists.
   - Add new entity types (avoiding duplicates — check by name).
   - Add new relationship types (avoiding duplicates — check by name).
   - Write the merged result back to `tmp/schema_definition.json`.

4. **Next Iteration**: Based on the current findings, search for the next sub-topic or entity cluster.
   - Follow leads from the search results: uncovered entities, related concepts, or sub-domains.
   - Search for the next area of the domain.

5. **Repeat** steps 2-4 until:
   - Search results no longer produce new entity types or relationship types.
   - The information returned is outside the user's domain scope.
   - You have exhausted the areas relevant to the user's concerns.

6. **Final Merge**: Ensure the complete schema is saved to `tmp/schema_definition.json`.

### Output Format
Each iteration produces partial schema definitions in the same format. The full schema is accumulated in `tmp/schema_definition.json`.

#### 1. Entity Types
For each entity type, define:
- **Name**: Entity type name (e.g., "Supplier", "Material")
- **Description**: What this entity represents
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

#### 2. Relationship Types
For each relationship type, define:
- **Name**: Relationship type (e.g., "SUPPLIES")
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

#### 3. Inheritance Hierarchy
Define any entity type inheritance:
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

### Schema Persistence
- Schema is incrementally accumulated in `tmp/schema_definition.json`.
- Each iteration appends/merges new types into the existing file (not overwriting from scratch).
- The final file represents the complete schema after all iterations.

### Scope Exhaustion Criteria (When to Stop)
Stop iterating when any of the following is true:
1. **No new types**: The last search results did not yield any new entity types or relationship types.
2. **Scope boundary**: Search results consistently return information outside the user's domain.
3. **Entity saturation**: The entity types already defined cover all the entities mentioned in search results.
4. **Relationship saturation**: All meaningful relationships between discovered entity types have been defined.
5. **User concern coverage**: All user concerns from Step 1 have been addressed by existing schema types.

### Cross-Iteration Schema Consistency
- **Deduplication**: Before adding a new entity type, check if one with the same name already exists. If so, merge properties instead of duplicating.
- **Relationship conflict resolution**: If two iterations define the same relationship type name with different source/target entity types, use the latest definition but log the conflict.
- **Inheritance consistency**: Ensure parent entity types referenced in inheritance exist in the accumulated schema.
- **Property merge**: When the same entity type appears in multiple iterations, combine all unique properties.

### Verification
- All entity types have at least a name and description
- All relationship types have valid source/target entity references
- No circular inheritance
- Properties have appropriate types (string, number, text, date, list)
- No duplicate entity type names in the final schema
- All relationship source/target entity types exist in the schema