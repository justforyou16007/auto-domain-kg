---
name: task-relevance-audit
description: "Verifier skill. Evaluate whether the schema and graph instances remain relevant to the user's original concerns. Identify drift and suggest refocusing."
---

# Task Relevance Audit — Verifier: Task Relevance Audit

## Goal
Audit whether the knowledge graph adequately addresses the user's original concerns as captured in the Socratic inquiry step.

## Verifier Instructions

You are the **Task Relevance Auditor** (Codex verifier). Your task is to evaluate whether the constructed graph meets the user's needs.

### Audit Checklist

#### 1. Concern Coverage
- For each user concern from CLAUDE.md, is there relevant schema coverage?
- Are the entities the user cares about present in the graph?
- Are the relationships the user cares about captured?
- Are the risk concerns addressable through the graph structure?

#### 2. Domain Fit
- Does the schema adequately represent the user's domain?
- Are there important domain concepts missing?
- Is the level of detail appropriate (not too granular, not too coarse)?

#### 3. Actionability
- Can the user answer their key questions from the graph?
- Can the user monitor their risk concerns?
- Is the graph useful for the stated purpose (risk monitoring, competitive intelligence, etc.)?

#### 4. Gap Analysis
- What entities/relationships are missing that would improve relevance?
- What evidence is missing that would support the user's concerns?
- What risk assessments are incomplete?

### Process
1. Load the user concerns from CLAUDE.md.
2. Query the graph schema and instances.
3. Compare schema coverage against each concern.
4. Identify gaps and suggest improvements.

### Output Format
```json
{
  "passed": false,
  "concern_coverage": [
    {
      "concern": "Description of user concern",
      "covered": true,
      "coverage_level": "full|partial|none",
      "gaps": ["Missing entity type", "Missing relationship"]
    }
  ],
  "issues": [
    {
      "severity": "error|warning|info",
      "category": "coverage|domain|actionability|gap",
      "description": "Description of relevance issue",
      "suggestion": "How to improve"
    }
  ],
  "summary": {
    "total_concerns": 0,
    "fully_covered": 0,
    "partially_covered": 0,
    "not_covered": 0
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
Apply this threshold from the `task_relevance_audit` rubric during the audit:
- `min_fully_covered_ratio = 0.7` — if fewer than 70% of user concerns are fully covered, it is an **error**.

Compute `fully_covered_ratio = fully_covered / total_concerns` and compare against the threshold. A concern with `coverage_level` of `none` is an **error**; `partial` is a **warning**. Under STRICT auditing: **any error-level issue blocks the round from passing**. Warnings are tracked but do not block.

### Structured Output for AuditReportGenerator
Each issue MUST carry a stable `id` (e.g. `RELEV-001`), `severity` (`error`|`warning`|`info`), `category` (`coverage`|`domain`|`actionability`|`gap`), `description`, and `suggestion`. The `summary` block must report `total_concerns`, `fully_covered`, `partially_covered`, and `not_covered`. This dict is consumed directly by `auto_domain_kg.audit_report.AuditReportGenerator.generate_report()`.

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