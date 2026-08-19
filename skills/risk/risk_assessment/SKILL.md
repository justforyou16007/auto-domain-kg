---
name: risk-assessment
description: "Risk assessment skill. An agent walks the graph to assess risk impact on user concerns, considering alternative paths, redundancy, and centrality. Risk is user-concern-driven, not auto-propagated."
---

# Risk Assessment — Agent-Guided Risk Assessment and Graph Traversal

## Goal
Assess risk impact using user-concern-driven analysis. An agent walks the graph to evaluate if a risk event on one entity affects the user's concern topic, considering graph structure (e.g., alternative paths, redundancy).

## Process

### 1. Trigger
Risk assessment is triggered by:
- A new risk event detected during daily update.
- User explicitly requesting a risk assessment.
- Verifier identifying a risk-related issue.

### 2. Load Context
- Load the user concerns from CLAUDE.md (risk concerns section).
- Identify the entity with the potential risk event.
- Load the subgraph around the entity using `RiskAssessment.get_risk_subgraph(entity_id, hops=3)`.

### 3. Agent Assessment (Agent-Driven)
The agent walks the graph and considers:

#### Graph Structure Analysis
- **Alternative paths**: If entity A fails, are there alternative entities providing the same function?
  - Example: 4 suppliers, 1 failing = NOT strong risk if 3 alternatives exist.
  - Example: 1 supplier, 1 failing = STRONG risk.
- **Redundancy**: Are there redundant relationships or entities?
- **Centrality**: Is the entity a central hub? If it fails, how many entities are affected?
- **Distance**: How many hops away is the risk from the user's concern entity?

#### User Concern Relevance
- Does the risk event affect the user's specific concern topic?
- Is the risk direct (same entity) or indirect (traversing through the graph)?
- What is the propagation path from the risk entity to the concern entity?

### 4. Risk Level Determination
Based on the assessment, determine the risk level:
- **NONE**: No impact on user concerns.
- **LOW**: Minimal impact, alternatives exist, distant from concerns.
- **MEDIUM**: Moderate impact, some alternatives exist, moderate distance.
- **HIGH**: Significant impact, few alternatives, close to concerns.
- **CRITICAL**: Direct impact on user concerns, no alternatives, immediate attention needed.

### 5. Update Risk Fields
Use `RiskAssessment.add_risk_field()` to update the risk level on the entity:
```python
await risk_assessment.add_risk_field(
    entity_id=entity_id,
    risk_level=RiskLevel.HIGH,
    reason="Entity is the sole supplier of critical component X. Risk event: factory fire.",
    evidence_urls=["https://example.com/news/factory-fire"],
)
```

### 6. Report
- Summarize the risk assessment with graph traversal path.
- Explain the reasoning (what graph structure was considered).
- List affected entities and their risk levels.
- Suggest mitigation actions if applicable.

### Key Principles
- **User-concern-driven**: Risk is only relevant if it affects the user's concerns.
- **NOT automatic propagation**: An agent must walk the graph and reason about each path.
- **Graph structure matters**: Consider alternatives, redundancy, and centrality.
- **Evidence-backed**: Each risk assessment must cite evidence sources.