---
name: risk-assessment
description: "6-step news-to-graph impact analysis pipeline. 1) Receive Daily News 2) Extract News Events 3) Associate Evidence Fragments 4) GraphRAG Event-to-Node Analysis 5) DAG Impact Tracing 6) Generate Impact Report using external template. Risk is user-concern-driven, not auto-propagated."
---

# Risk Assessment — 6-Step News-to-Graph Impact Analysis Pipeline

## Goal
Transform daily news into structured risk reports by analyzing how news events
impact knowledge graph nodes. The analysis follows a 6-step pipeline:
1. Receive Daily News
2. Extract News Events
3. Associate Evidence Fragments
4. GraphRAG Event-to-Node Analysis
5. DAG Impact Tracing
6. Generate Impact Report using external template

## 6-Step Process

### Step 1: Receive Daily News
- Receive today's news list from the `daily_update` skill.
- **Input**: News items, each containing:
  - `title`: News headline
  - `url`: Source URL
  - `content`: Full article text
  - `published_date`: Publication date
  - `source`: Source name

### Step 2: Extract News Events
- Extract structured events from each news item.
- Each event contains:
  - `event_type`: Type of event (e.g., factory_fire, supply_disruption, regulatory_change, acquisition, leadership_change, financial_distress)
  - `description`: Natural language description of the event
  - `entities_mentioned`: List of entities mentioned in the event
  - `severity_hint`: Preliminary severity indicator
  - `source_news_id`: Reference to the source news item
- A single news article may contain multiple events.
- Use `RiskAssessment.extract_events_from_news()` to initialize event structures.

### Step 3: Associate Evidence Fragments
- For each event, locate and extract supporting text snippets from the source news.
- Save evidence fragments to `data/evidence/` using the `EvidenceStore` module.
- Each evidence record contains:
  - `text_slice`: The supporting text excerpt
  - `source_url`: URL of the source article
  - `source_title`: Title of the source article
  - `position_in_article`: Approximate position of the snippet
- Use `RiskAssessment.associate_evidence()` to extract and save evidence.

### Step 4: GraphRAG Event-to-Node Analysis
- For each event, perform GraphRAG retrieval:
  1. **Vector Search**: Use the event description to perform vector similarity search
     against Neo4j entity embeddings, via `GraphOps.vector_search()`.
  2. **Multi-hop Subgraph**: For each matched node, explore its neighborhood
     using `GraphOps.multi_hop_subgraph()` (2 hops by default).
  3. **Semantic Relevance Analysis**: Agent analyzes the substantive relevance
     between the event and retrieved graph nodes (not simple keyword matching).
- Output: List of affected graph nodes per event, including:
  - The node's properties
  - Similarity score
  - Subgraph context
  - Impact mechanism description
- Use `RiskAssessment.graphrag_event_search()`.

### Step 5: DAG Impact Tracing
- For each affected node identified in Step 4, trace impact propagation
  along the DAG (directed acyclic graph) direction:
  - Follow outgoing relationships using Cypher queries
  - Query: `MATCH path = (start)-[*1..N]->(downstream) WHERE elementId(start) = $id RETURN path`
  - Analyze each downstream node for substantive impact (considering redundancy,
    alternative paths, and graph structure)
- Output: Affected subgraph with:
  - Original event-triggered nodes
  - Propagation paths
  - Downstream impacted nodes
- Use `RiskAssessment.trace_dag_impact()`.

### Step 6: Generate Impact Report
- Load the report template from `templates/{domain}_domain_report_template.md`
  (default: `templates/default_domain_report_template.md`).
- Fill template placeholders with analysis results:
  - `{{date}}` — Report date
  - `{{domain}}` — Domain name
  - `{{events_summary}}` — News events summary table
  - `{{affected_nodes}}` — Affected graph nodes list
  - `{{impact_paths}}` — Impact propagation paths
  - `{{risk_assessment}}` — Overall risk level assessment
  - `{{evidence}}` — Evidence traceability
  - `{{mitigation_suggestions}}` — Suggested mitigation actions
- Output report to `reports/` directory with naming format:
  `{date}_{domain}_risk_report.md`
- Use `RiskAssessment.generate_report()`.

### Orchestration
The full pipeline is orchestrated by `RiskAssessment.run_full_analysis()`:
```python
report_path = await risk_assessment.run_full_analysis(
    news_items=news_list,
    domain="supply_chain",
    template_path="templates/default_domain_report_template.md",
)
```

## Key Principles
- **User-concern-driven**: Risk is only relevant if it affects the user's concerns.
- **NOT automatic propagation**: Each step requires substantive analysis.
- **Semantic relevance**: Step 4 uses semantic (not just keyword) matching.
- **Graph structure matters**: Consider alternatives, redundancy, centrality.
- **Evidence-backed**: Each assessment must cite evidence sources.
- **Template-driven reports**: Report templates are externalized to `templates/` directory.
- **DAG-aware tracing**: Step 5 respects graph directionality and structure.