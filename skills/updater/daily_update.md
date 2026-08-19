# Daily Update — Step: Daily News Scan and Graph Update

## Goal
Scan for entity-related news published today, determine if a graph update is needed (schema or instance), and trigger a partial graph update.

## Process

### 1. Prepare for Scan
- Load the current schema from `tmp/schema_definition.json` (or query Neo4j).
- Load the list of entities from Neo4j (all entities, or active ones).
- Identify entities that are in the user's concern topics.

### 2. Search for Today's News
- For each entity or entity group, search for news using the `news_adapter` module.
- Use `date_from` and `date_to` set to today's date.
- Collect news items for each entity.
- If no news found for an entity, skip it.

### 3. Assess Update Need
For each entity with new news:
- **Schema change needed?** Does the news mention new entity types or relationships not in the schema?
- **Instance change needed?** Does the news contain new facts about existing entities?
- **New entities?** Does the news mention entities not in the graph?
- **Risk update?** Does the news indicate a risk event?

### 4. Send Update Request to Worker
Based on the assessment:
- **Schema update required**: Send schema + news to worker agent for schema refinement.
- **Instance update required**: Send entity + news to worker agent for triple extraction and persistence.
- **Risk reassessment required**: Mark entity for risk reassessment using `RiskAssessment.update_risk_after_news_scan()`.

### 5. Run Verifier
After the update is applied, run the verifier to validate:
- New instances are properly linked to schema.
- New evidence is stored with provenance.
- Graph structure is intact.

### 6. Report
Summarize what was updated:
- Number of entities scanned
- Number of entities with new news
- Schema changes made
- New entities added
- New relationships added
- Risk reassessments triggered

### Configuration
- Update frequency is set in the user concerns (daily/weekly/monthly).
- For weekly updates, scan the past 7 days.
- For monthly updates, scan the past 30 days.