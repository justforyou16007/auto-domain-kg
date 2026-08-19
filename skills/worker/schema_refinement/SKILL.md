---
name: schema-refinement
description: "Refine and supplement the schema based on majority findings from entity collection. Update entity types, properties, and relationships discovered during research."
---

# Schema Refinement — Step 3b: Refine Schema Based on Collection Findings

## Goal
After collecting evidence from multiple sources, refine and supplement the domain schema based on actual findings.

## Process

1. **Review collection report** from `tmp/collection_report.md`.
2. **Identify schema gaps**:
   - Entity types that appeared in sources but aren't in the schema
   - Properties that are commonly found but not defined
   - Relationship types that emerge from the data
   - Missing entity types implied by relationships

3. **Refine entity types**:
   - Add new entity types as needed
   - Add missing properties
   - Adjust property types if actual data differs
   - Merge or split entity types based on evidence

4. **Refine relationship types**:
   - Add new relationship types found in evidence
   - Remove relationships that don't have evidence support
   - Add properties to relationships based on data

5. **Update the schema**:
   - Save updated schema to `tmp/schema_definition.json`
   - Document what changed and why (in `tmp/schema_refinement_log.md`)

### Refinement Heuristics
- **Majority evidence**: If >50% of sources mention a property, it should be in the schema
- **Emergent entities**: If an entity type appears in 3+ sources, consider adding it
- **Relationship density**: If relationships are sparse, check if entity types are wrong
- **Inheritance**: If multiple entities share the same properties, consider a parent type

### Output
- Updated `tmp/schema_definition.json`
- `tmp/schema_refinement_log.md` with changes and rationale