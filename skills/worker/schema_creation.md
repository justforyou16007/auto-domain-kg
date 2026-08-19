# Schema Creation — Step 2: Domain Schema Generation

## Goal
Create a comprehensive domain schema based on the user concerns gathered in Step 1.

## Strong Agent Instructions

You are the **Schema Architect** (strong agent). Your task is to design a domain schema.

### Input
- User concerns from `CLAUDE.md` (User Concerns section)
- Domain, entities, relationships identified in Step 1

### Output
Create a structured schema definition with the following sections:

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
Save the schema to a file `tmp/schema_definition.json` for later use.

### Verification
- All entity types have at least a name and description
- All relationship types have valid source/target entity references
- No circular inheritance
- Properties have appropriate types (string, number, text, date, list)