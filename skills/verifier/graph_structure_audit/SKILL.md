---
name: graph-structure-audit
description: "Verifier skill. Audit the knowledge graph structure for connectivity, orphan nodes, relationship integrity, and graph health metrics."
---

# Graph Structure Audit — Verifier: Graph Structure Audit

## Goal
Audit the knowledge graph structure for connectivity, orphan nodes, relationship density, and schema-instance linkage.

## Verifier Instructions

You are the **Graph Structure Auditor** (Codex verifier). Your task is to analyze the graph structure in Neo4j.

### Audit Checklist

#### 1. Connectivity
- Are all entities connected to at least one other entity?
- Are there disconnected subgraphs?
- Is the graph diameter reasonable for the domain?
- Are there entities with no relationships at all?

#### 2. Orphan Nodes
- Are there entity nodes that are not linked to any schema node via HAS_SCHEMA?
- Are there schema nodes with no entity instances?
- Are there dangling relationships pointing to deleted nodes?

#### 3. Relationship Density
- What is the average number of relationships per entity?
- Are there entities with too many relationships (hub nodes) that might indicate over-generalization?
- Are there relationship types that are never used?

#### 4. Schema-Instance Linkage
- Do all entities link to a valid schema node?
- Do entity properties match their schema definition?
- Are there properties on entities that are not defined in the schema?

### Queries to Run
Use Cypher queries via the Neo4j client to gather statistics:
```cypher
// Count orphan entities
MATCH (e:Entity) WHERE NOT (e)-[:HAS_SCHEMA]->(:Schema) RETURN count(e)

// Count empty schemas
MATCH (s:Schema) WHERE NOT (s)<-[:HAS_SCHEMA]-(:Entity) RETURN s.name

// Count relationship density
MATCH (e:Entity) OPTIONAL MATCH (e)-[r]-() RETURN e.name, count(r) AS rel_count
```

### Output Format
```json
{
  "passed": false,
  "issues": [
    {
      "severity": "error|warning|info",
      "category": "connectivity|orphan|density|linkage",
      "description": "Description of the issue",
      "statistics": {}
    }
  ],
  "summary": {
    "total_entities": 0,
    "orphan_entities": 0,
    "empty_schemas": 0,
    "avg_relationships_per_entity": 0.0
  }
}
```

## Rubrics Integration (Issues #14, #15)

### Load Rubrics
Before auditing, load the strict rubrics that drive this skill:

```python
from auto_domain_kg.audit_rubrics import RubricsConfig

# Load custom rubrics (default location), falling back to strict defaults.
config = RubricsConfig.load_from_file("config/audit_rubrics.yaml")
# or: config = RubricsConfig.load_default()
```

### Strict Thresholds (default strict)
Apply these thresholds from the `graph_structure_audit` rubric during the audit:
- `max_orphan_entities = 0` — any entity not linked to a schema node (or with no relationships) is an **error**.
- `min_avg_relationships = 1.0` — average relationships per entity below 1.0 is an **error** (graph too sparse).

Under STRICT auditing: **any error-level issue blocks the round from passing**. Warnings are tracked but do not block.

### Structured Output for AuditReportGenerator
Each issue MUST carry a stable `id` (e.g. `GRAPH-001`), `severity` (`error`|`warning`|`info`), `category`, `description`, and `statistics`. The `summary` block must report `total_entities`, `orphan_entities`, `empty_schemas`, and `avg_relationships_per_entity`. This dict is consumed directly by `auto_domain_kg.audit_report.AuditReportGenerator.generate_report()`.

### Report Generation
After auditing, hand the structured result to the main agent, which calls:
```python
from auto_domain_kg.audit_report import AuditReportGenerator, AuditHistory
generator = AuditReportGenerator()
# report = generator.generate_report(round_number, sub_reports, config, worker_fixes)
# generator.save_report(report, output_dir="reports/audits/")
# AuditHistory("reports/audits/").add_round(report)
```
Each round's audit report (markdown + JSON) is saved to `reports/audits/round_N/` and appended to `reports/audits/audit_history.jsonl` for full adversarial traceability.