---
name: graphrag-validation
description: "Verifier skill. Validate graph quality by asking domain-driven GraphRAG questions using Neo4j vector search and Cypher multi-hop queries. Check if the graph can answer user concerns."
---

# GraphRAG Validation — Verifier: Domain Question GraphRAG Validation

## Goal
Generate domain-specific questions and use GraphRAG (Neo4j vector search + Cypher multi-hop) to validate that the graph can answer them.

## Verifier Instructions

You are the **GraphRAG Validator** (Codex verifier). Your task is to test the knowledge graph's ability to answer domain questions.

### Process

#### 1. Generate Domain Questions
Based on the user concerns from CLAUDE.md, generate 5-10 questions that the knowledge graph should be able to answer. Examples:
- "What entities are related to [entity]?"
- "What is the risk level of [entity]?"
- "What evidence supports the relationship between [entity A] and [entity B]?"
- "Show me the subgraph around [entity] with 2 hops."

#### 2. Query the Graph
For each question, determine the appropriate query strategy:
- **Vector Search**: For questions that need semantic similarity matching (e.g., "Find entities related to semiconductor supply chain")
- **Cypher Multi-hop**: For questions that need graph traversal (e.g., "What suppliers does Company X rely on?")

Implement the queries using GraphOps methods:
- `vector_search(query_text, top_k)` for semantic search
- `multi_hop_subgraph(start_entity, hops, rel_types)` for subgraph traversal
- `get_schema_with_entities(schema_id)` for schema-instance relationships

#### 3. Evaluate Results
For each question, evaluate:
- **Answerable**: Was the graph able to return meaningful results?
- **Precision**: Were the results relevant to the question?
- **Coverage**: Does the graph have sufficient coverage for this type of question?

### Output Format
```json
{
  "passed": false,
  "questions": [
    {
      "question": "What entities are related to [entity]?",
      "query_type": "vector_search|multi_hop|schema_query",
      "answerable": true,
      "precision": "high|medium|low",
      "result_count": 5,
      "issues": []
    }
  ],
  "summary": {
    "total_questions": 10,
    "answerable": 8,
    "unanswerable": 2,
    "issues_found": 3
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
Apply these thresholds from the `graphrag_validation` rubric during the audit:
- `min_answerable_ratio = 0.8` — if fewer than 80% of domain questions are answerable, it is an **error**.
- `min_precision = "medium"` — any answerable question with precision below `medium` (i.e. `low`) is an **error**.

Compute `answerable_ratio = answerable / total_questions` and compare against the threshold. Under STRICT auditing: **any error-level issue blocks the round from passing**. Warnings are tracked but do not block.

### Structured Output for AuditReportGenerator
Each question entry should carry `question`, `query_type`, `answerable`, `precision`, `result_count`, and `issues`. Any unanswerable/low-precision result MUST also appear as a top-level `issues` entry with a stable `id` (e.g. `GRAG-001`), `severity`, `category`, `description`, and `suggestion`. The `summary` block must report `total_questions`, `answerable`, `unanswerable`, and `issues_found`. This dict is consumed directly by `auto_domain_kg.audit_report.AuditReportGenerator.generate_report()`.

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