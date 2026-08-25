---
name: schema-refinement
description: "Part of iterative Step 2 of KG construction. After each iteration's entity collection, refine the partial schema based on collected evidence. Perform cross-iteration consistency checks: detect duplicate entity types, resolve relationship conflicts, ensure schema coherence, and check Schema/Instance layer separation (no concepts in Instance layer, no instances in Schema layer)."
---

# Schema Refinement — Part of Iterative Step 2: Per-Iteration Schema Refinement

## Goal
After each iteration's entity collection, refine the partial schema based on the evidence collected in that iteration. This runs per-iteration (not as a separate post-collection step) and also performs cross-iteration consistency checks, including Schema/Instance layer separation.

## Process

### Per-Iteration Refinement (runs after each entity collection iteration)

1. **Review collection findings** from the current iteration in `tmp/collection_report.md`.
2. **Identify schema gaps** in the current iteration's partial schema:
   - Concept-level entity types that appeared in sources but aren't in the schema
   - Properties that are commonly found but not defined
   - Business relationship types that emerge from the data
   - Missing entity types implied by relationships

3. **Refine entity types** for the current iteration (concept layer only):
   - Add new concept-level entity types as needed (merge into `tmp/schema_definition.json`)
   - Add missing properties
   - Adjust property types if actual data differs
   - Merge or split entity types based on evidence

4. **Refine relationship types** for the current iteration:
   - Add new relationship types found in evidence (with explicit business semantics)
   - Remove relationships that don't have evidence support
   - Add properties to relationships based on data

5. **Update the schema**:
   - Merge refinements into `tmp/schema_definition.json`
   - Document what changed and why (append to `tmp/schema_refinement_log.md`)

### Schema/Instance Layer Separation Checks

During refinement, verify the layer separation:
- **No instances in Schema layer**: Ensure no concrete instance names (e.g., "Xiaomi SU7", "TSMC") leak into Schema entity types. Schema must only contain concepts (e.g., "Vehicle", "Supplier").
- **No concepts in Instance layer**: Ensure no generic concept names are tracked as Instance entities. Instances must be concrete (e.g., "TSMC", not "semiconductor manufacturer").
- If a concept is found in the Instance layer or an instance is found in the Schema layer, move it to the correct layer and log the correction.

### Cross-Iteration Consistency Checks (runs at the end of each iteration)

1. **Duplicate entity type detection**: Scan the accumulated schema for entity types with the same or very similar names. If found:
   - Merge properties from both definitions.
   - Keep the more descriptive name.
   - Log the merge in the refinement log.

2. **Relationship conflict resolution**: Check if the same relationship type name is defined with different source/target entities across iterations. If found:
   - Prefer the definition that matches the accumulated evidence.
   - Log the conflict and resolution in the refinement log.

3. **Orphan entity type check**: Ensure every entity type referenced as a relationship source or target actually exists in the schema. If missing:
   - Add the missing entity type with a note.
   - Log the addition in the refinement log.

4. **Inheritance consistency**: Verify that parent entity types in inheritance definitions exist in the schema. If missing:
   - Add the parent entity type.
   - Log the addition in the refinement log.

5. **Layer separation check**: Across iterations, check whether any concepts have mixed into the Instance layer or instances into the Schema layer. If so, correct and log.

### Refinement Heuristics
- **Majority evidence**: If >50% of sources mention a property, it should be in the schema
- **Emergent entities**: If a concept type appears in 3+ sources, consider adding it to the Schema layer
- **Relationship density**: If relationships are sparse, check if entity types are wrong
- **Inheritance**: If multiple entities share the same properties, consider a parent type
- **Business semantics**: Reject or rename relationship types that lack explicit business meaning

### Output
- Updated `tmp/schema_definition.json` (accumulated across iterations)
- `tmp/schema_refinement_log.md` with changes and rationale (appended each iteration)