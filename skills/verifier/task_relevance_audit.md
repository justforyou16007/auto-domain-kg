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