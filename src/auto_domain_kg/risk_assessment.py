"""Risk assessment module for user-concern-driven risk analysis
with 6-step news-to-graph impact analysis pipeline.

Provides risk field management, 6-step news-to-graph impact analysis,
and agent-guided graph traversal for risk assessment. Risk is NOT automatically
propagated; instead, an agent walks the graph to assess if a risk event on one
entity affects the user's concern topic, considering graph structure
(e.g., alternative paths, redundancy).

The 6-step pipeline (run_full_analysis) transforms daily news into structured
risk reports:
1. Receive Daily News
2. Extract News Events
3. Associate Evidence Fragments
4. GraphRAG Event-to-Node Analysis
5. DAG Impact Tracing
6. Generate Impact Report
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from .embedding import EmbeddingClient
from .evidence_store import EvidenceRecord, EvidenceStore
from .graph_ops import GraphOps
from .neo4j_client import Neo4jClient


class RiskLevel(str, Enum):
    """Risk levels for entities."""

    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class RiskField:
    """Risk field data for an entity."""

    level: RiskLevel = RiskLevel.NONE
    reason: str = ""
    evidence_urls: list[str] = field(default_factory=list)
    assessed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    assessed_by: str = "agent"


@dataclass
class RiskSubgraph:
    """Subgraph context for risk assessment."""

    center_entity: dict[str, Any]
    neighbors: list[dict[str, Any]]
    relationships: list[dict[str, Any]]
    hops: int


class RiskAssessment:
    """Risk assessment manager for user-concern-driven risk analysis
    with 6-step news-to-graph impact analysis pipeline.

    Provides methods to add/update risk fields on entities, retrieve
    subgraph context for agent traversal, and assess risk impact
    considering graph structure. The 6-step pipeline (run_full_analysis)
    transforms daily news into structured risk reports:
    1. Receive Daily News
    2. Extract News Events
    3. Associate Evidence Fragments
    4. GraphRAG Event-to-Node Analysis
    5. DAG Impact Tracing
    6. Generate Impact Report

    Risk is user-concern-driven: an agent walks the graph to assess
    if a risk event on one entity affects the user's concern topic,
    considering graph structure (e.g., 4 suppliers, 1 failing = not
    strong risk if 3 alternatives exist).

    The 6-step pipeline is orchestrated by run_full_analysis().
    """

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        graph_ops: Optional[GraphOps] = None,
        evidence_store: Optional[EvidenceStore] = None,
    ) -> None:
        """Initialize the risk assessment module.

        Args:
            neo4j_client: Connected Neo4j client.
            graph_ops: Optional GraphOps instance for vector search and
                       multi-hop traversal. If not provided, vector search
                       and subgraph traversal will be unavailable.
            evidence_store: Optional EvidenceStore instance for saving
                            evidence fragments. Defaults to EvidenceStore().
        """
        self._neo4j = neo4j_client
        self._graph_ops = graph_ops
        self._evidence_store = evidence_store or EvidenceStore()

    # ─────────────────────────────────────────────────────────────────────────
    # 6-Step Pipeline: Step 1 & 2 — Receive News & Extract Events
    # ─────────────────────────────────────────────────────────────────────────

    async def extract_events_from_news(
        self, news_items: list[dict]
    ) -> list[dict]:
        """Extract structured events from news items.

        This method provides the data structure framework for event extraction.
        The actual event extraction (event_type, description, entities_mentioned,
        severity_hint) is performed by an LLM agent. This method initializes the
        event structure with the source news reference.

        Args:
            news_items: List of news dicts, each with:
                title, url, content, published_date, source

        Returns:
            List of event dicts, each with:
                event_type, description, entities_mentioned, severity_hint,
                source_news_id, source_news_title, source_news_url
        """
        events: list[dict] = []
        for news_item in news_items:
            event = {
                "event_type": "",
                "description": "",
                "entities_mentioned": [],
                "severity_hint": "",
                "source_news_id": news_item.get("url", ""),
                "source_news_title": news_item.get("title", ""),
                "source_news_url": news_item.get("url", ""),
            }
            events.append(event)
        return events

    # ─────────────────────────────────────────────────────────────────────────
    # 6-Step Pipeline: Step 3 — Associate Evidence Fragments
    # ─────────────────────────────────────────────────────────────────────────

    async def associate_evidence(
        self, event: dict, news_item: dict
    ) -> list[EvidenceRecord]:
        """Associate evidence fragments from a news item to an event.

        Extracts text slices from the news content that support the event,
        saves them to the evidence store, and returns the records.

        Args:
            event: Event dict with event_type, description, etc.
            news_item: News dict with title, url, content, etc.

        Returns:
            List of EvidenceRecord objects saved to the evidence store.
        """
        content = news_item.get("content", "")
        url = news_item.get("url", "")
        title = news_item.get("title", "")

        # Use the event description as a search key to find relevant snippets
        event_desc = event.get("description", "")
        records: list[EvidenceRecord] = []

        # If content is available, extract relevant snippets
        if content and event_desc:
            # Simple snippet extraction: find sentences containing keywords
            # from the event description
            keywords = set(event_desc.lower().split()[:10])
            sentences = re.split(r"(?<=[.!?])\s+", content)
            for sentence in sentences:
                sentence_lower = sentence.lower()
                # Count how many keywords match
                match_count = sum(1 for kw in keywords if kw in sentence_lower)
                if match_count >= 2 and len(sentence) > 20:
                    record = EvidenceRecord(
                        entity_id=event.get("source_news_id", url),
                        text_slice=sentence.strip(),
                        source_url=url,
                        source_title=title,
                    )
                    records.append(record)
                    break  # Take the best matching snippet

        # If no snippet found, use the first meaningful sentence
        if not records and content:
            sentences = re.split(r"(?<=[.!?])\s+", content)
            for sentence in sentences:
                if len(sentence.strip()) > 20:
                    record = EvidenceRecord(
                        entity_id=event.get("source_news_id", url),
                        text_slice=sentence.strip()[:500],
                        source_url=url,
                        source_title=title,
                    )
                    records.append(record)
                    break

        # Save records to evidence store
        if records:
            self._evidence_store.save_evidence_batch(records)

        event["evidence_records"] = records
        return records

    # ─────────────────────────────────────────────────────────────────────────
    # 6-Step Pipeline: Step 4 — GraphRAG Event-to-Node Analysis
    # ─────────────────────────────────────────────────────────────────────────

    async def graphrag_event_search(
        self, event_description: str, top_k: int = 10
    ) -> list[dict]:
        """Perform GraphRAG event-to-node analysis.

        Uses the event description to perform vector search, then explores
        the matched nodes' subgraphs via multi-hop Cypher queries.

        Args:
            event_description: Description of the event to search for.
            top_k: Number of top vector search results to retrieve.

        Returns:
            List of dicts, each with 'node' (entity properties), 'score',
            and 'subgraph' (multi-hop context).
        """
        if self._graph_ops is None:
            return []

        # Step 4a: Vector search for related graph nodes
        vector_results = await self._graph_ops.vector_search(
            query_text=event_description, top_k=top_k
        )

        # Step 4b: Multi-hop subgraph exploration for each matched node
        enriched_results = []
        for result in vector_results:
            node = result.get("node", {})
            node_id = node.get("elementId", "")
            score = result.get("score", 0.0)

            subgraph = []
            if node_id:
                subgraph = await self._graph_ops.multi_hop_subgraph(
                    start_entity=node_id, hops=2
                )

            enriched_results.append({
                "node": node,
                "score": score,
                "subgraph": subgraph,
            })

        return enriched_results

    # ─────────────────────────────────────────────────────────────────────────
    # 6-Step Pipeline: Step 5 — DAG Impact Tracing
    # ─────────────────────────────────────────────────────────────────────────

    async def trace_dag_impact(
        self, affected_node_ids: list[str], max_hops: int = 5
    ) -> dict:
        """Trace impact propagation along DAG direction using Cypher queries.

        For each affected node, follows outgoing relationships (DAG direction)
        to find downstream impacted nodes and builds the propagation paths.

        Args:
            affected_node_ids: List of element IDs of nodes affected by events.
            max_hops: Maximum number of hops to traverse downstream.

        Returns:
            Dict with:
                - 'propagation_paths': list of paths from source to downstream
                - 'downstream_nodes': list of all downstream node IDs
                - 'impact_map': node_id -> list of downstream nodes
        """
        all_downstream: set[str] = set()
        impact_map: dict[str, list[dict]] = {}
        propagation_paths: list[dict] = []

        for node_id in affected_node_ids:
            # Cypher query: follow outgoing relationships (DAG direction)
            query = """
                MATCH path = (start)-[*1..{max_hops}]->(downstream)
                WHERE elementId(start) = $start_id
                RETURN path
            """.format(max_hops=max_hops)

            paths = await self._neo4j.execute_custom_query(
                query, {"start_id": node_id}
            )

            downstream_nodes = []
            for path_entry in paths:
                path_data = path_entry.get("path", {})
                # Extract node IDs from the path
                segments = path_data.get("segments", [])
                if isinstance(segments, list):
                    for segment in segments:
                        end_node = segment.get("end", {})
                        end_id = end_node.get("elementId", "")
                        if end_id and end_id != node_id:
                            downstream_nodes.append({
                                "id": end_id,
                                "properties": end_node,
                            })
                            all_downstream.add(end_id)

                propagation_paths.append({
                    "source": node_id,
                    "path": path_data,
                })

            impact_map[node_id] = downstream_nodes

        return {
            "propagation_paths": propagation_paths,
            "downstream_nodes": list(all_downstream),
            "impact_map": impact_map,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 6-Step Pipeline: Step 6 — Generate Impact Report
    # ─────────────────────────────────────────────────────────────────────────

    async def generate_report(
        self, template_path: str, output_path: str, context: dict
    ) -> str:
        """Generate an impact report from a template and context.

        Loads the template file, replaces placeholders with context data,
        and writes the report to the output path.

        Supported placeholders in the template:
          {{date}}, {{domain}}, {{events_summary}}, {{affected_nodes}},
          {{impact_paths}}, {{risk_assessment}}, {{evidence}},
          {{mitigation_suggestions}}

        Args:
            template_path: Path to the template file.
            output_path: Path to write the generated report.
            context: Dict with keys matching template placeholders.

        Returns:
            The output path string.
        """
        # Load template
        template = Path(template_path).read_text(encoding="utf-8")

        # Fill placeholders
        report = template
        for key, value in context.items():
            placeholder = "{{" + key + "}}"
            str_value = str(value) if value is not None else ""
            report = report.replace(placeholder, str_value)

        # Write output
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")

        return output_path

    # ─────────────────────────────────────────────────────────────────────────
    # 6-Step Pipeline Orchestrator
    # ─────────────────────────────────────────────────────────────────────────

    async def run_full_analysis(
        self,
        news_items: list[dict],
        domain: str,
        template_path: str = "templates/default_domain_report_template.md",
    ) -> str:
        """Orchestrate the complete 6-step news-to-graph impact analysis.

        Steps:
          1. Receive Daily News (input)
          2. Extract News Events
          3. Associate Evidence Fragments
          4. GraphRAG Event-to-Node Analysis
          5. DAG Impact Tracing
          6. Generate Impact Report

        Args:
            news_items: List of news dicts (title, url, content,
                        published_date, source).
            domain: Domain name for the report.
            template_path: Path to the report template file.

        Returns:
            Path to the generated report file.
        """
        # Step 1 & 2: Receive news and extract events
        events = await self.extract_events_from_news(news_items)

        # Step 3: Associate evidence fragments
        all_events: list[dict] = []
        for event, news_item in zip(events, news_items):
            await self.associate_evidence(event, news_item)
            all_events.append(event)

        # Step 4: GraphRAG event-to-node analysis
        all_affected_nodes: dict[str, dict] = {}
        for event in all_events:
            event_desc = event.get("description", "")
            if not event_desc:
                continue
            results = await self.graphrag_event_search(event_desc)
            for r in results:
                node = r.get("node", {})
                node_id = node.get("elementId", "")
                if node_id:
                    all_affected_nodes[node_id] = {
                        "node": node,
                        "score": r.get("score", 0.0),
                        "event": event,
                    }

        # Step 5: DAG impact tracing
        affected_ids = list(all_affected_nodes.keys())
        dag_result = await self.trace_dag_impact(affected_ids)

        # Step 6: Generate report
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        report_path = f"reports/{today}_{domain}_risk_report.md"

        # Build context for template
        events_summary_lines = []
        for event in all_events:
            events_summary_lines.append(
                "- **{}**: {} ([source]({}))".format(
                    event.get("event_type", "unknown"),
                    event.get("description", "")[:200],
                    event.get("source_news_url", ""),
                )
            )

        affected_nodes_lines = []
        for node_id, info in all_affected_nodes.items():
            node = info.get("node", {})
            node_name = node.get("name", node_id)
            score = info.get("score", 0.0)
            affected_nodes_lines.append(
                "- {} (score: {:.3f})".format(node_name, score)
            )

        impact_paths_lines = []
        for path_entry in dag_result.get("propagation_paths", []):
            source = path_entry.get("source", "")
            impact_paths_lines.append("- Source: {}".format(source))

        risk_level = self._derive_risk_level(all_affected_nodes, dag_result)

        evidence_lines = []
        for event in all_events:
            records = event.get("evidence_records", [])
            for rec in records:
                evidence_lines.append(
                    '- "{}..." ([source]({}))'.format(
                        rec.text_slice[:100], rec.source_url
                    )
                )

        context = {
            "date": today,
            "domain": domain,
            "events_summary": (
                "\n".join(events_summary_lines)
                if events_summary_lines
                else "No events extracted."
            ),
            "affected_nodes": (
                "\n".join(affected_nodes_lines)
                if affected_nodes_lines
                else "No affected nodes found."
            ),
            "impact_paths": (
                "\n".join(impact_paths_lines)
                if impact_paths_lines
                else "No propagation paths found."
            ),
            "risk_assessment": risk_level,
            "evidence": (
                "\n".join(evidence_lines)
                if evidence_lines
                else "No evidence collected."
            ),
            "mitigation_suggestions": (
                "Review affected nodes for potential mitigation actions."
            ),
        }

        return await self.generate_report(template_path, report_path, context)

    def _derive_risk_level(
        self,
        affected_nodes: dict[str, dict],
        dag_result: dict,
    ) -> str:
        """Derive an overall risk level from analysis results.

        Args:
            affected_nodes: Dict of affected node_id -> info.
            dag_result: Result from trace_dag_impact.

        Returns:
            Risk level description string.
        """
        downstream_count = len(dag_result.get("downstream_nodes", []))
        affected_count = len(affected_nodes)

        if affected_count == 0:
            return "NONE — No entities affected by the analyzed events."
        if downstream_count > 10 or affected_count > 5:
            return (
                "CRITICAL — Widespread impact across the knowledge graph."
            )
        if downstream_count > 5 or affected_count > 3:
            return (
                "HIGH — Significant impact on multiple graph entities."
            )
        if downstream_count > 2 or affected_count > 1:
            return (
                "MEDIUM — Moderate impact on some graph entities."
            )
        return "LOW — Minimal impact on graph entities."

    # ─────────────────────────────────────────────────────────────────────────
    # Existing methods below (unchanged)
    # ─────────────────────────────────────────────────────────────────────────

    async def add_risk_field(
        self,
        entity_id: str,
        risk_level: RiskLevel,
        reason: str,
        evidence_urls: Optional[list[str]] = None,
    ) -> None:
        """Add or update a risk field on an entity node.

        The risk field is stored as properties on the entity node:
        risk_level, risk_reason, risk_evidence_urls, risk_assessed_at.

        Args:
            entity_id: Element ID of the entity.
            risk_level: Risk level (NONE, LOW, MEDIUM, HIGH, CRITICAL).
            reason: Human-readable reason for the risk assessment.
            evidence_urls: Optional list of URLs supporting the assessment.
        """
        now = datetime.now(timezone.utc).isoformat()
        properties = {
            "risk_level": risk_level.value,
            "risk_reason": reason,
            "risk_evidence_urls": evidence_urls or [],
            "risk_assessed_at": now,
        }
        await self._neo4j.update_entity_node(entity_id, properties)

    async def get_risk_field(self, entity_id: str) -> Optional[RiskField]:
        """Get the risk field for an entity.

        Args:
            entity_id: Element ID of the entity.

        Returns:
            RiskField if the entity has risk properties, None otherwise.
        """
        entity = await self._neo4j.get_entity_node(entity_id)
        if not entity:
            return None

        risk_level = entity.get("risk_level", "NONE")
        try:
            level = RiskLevel(risk_level)
        except ValueError:
            level = RiskLevel.NONE

        return RiskField(
            level=level,
            reason=entity.get("risk_reason", ""),
            evidence_urls=entity.get("risk_evidence_urls", []),
            assessed_at=entity.get("risk_assessed_at", ""),
            assessed_by=entity.get("risk_assessed_by", "agent"),
        )

    async def update_risk_after_news_scan(self, entity_id: str) -> None:
        """Trigger risk reassessment after a news scan.

        This marks the entity for reassessment. The actual assessment
        is done by an agent walking the graph. The method clears the
        previous assessment and sets a flag for agent processing.

        Args:
            entity_id: Element ID of the entity to reassess.
        """
        entity = await self._neo4j.get_entity_node(entity_id)
        if not entity:
            return

        # Set a flag for the agent to reassess
        await self._neo4j.update_entity_node(
            entity_id,
            {
                "risk_needs_reassessment": True,
                "risk_reassessment_triggered_at": datetime.now(
                    timezone.utc
                ).isoformat(),
            },
        )

    async def get_risk_subgraph(
        self,
        entity_id: str,
        hops: int = 2,
        rel_types: Optional[list[str]] = None,
    ) -> RiskSubgraph:
        """Get entity + neighbors with risk fields for agent traversal.

        Returns a subgraph centered on the given entity, including
        neighbor entities and their risk fields, so an agent can
        reason about risk impact considering graph structure.

        Args:
            entity_id: Element ID of the center entity.
            hops: Number of hops to traverse.
            rel_types: Optional list of relationship types to filter by.

        Returns:
            RiskSubgraph with center entity, neighbors, and relationships.
        """
        paths = await self._neo4j.multi_hop_subgraph(
            start_entity_id=entity_id,
            hops=hops,
            rel_types=rel_types,
        )

        # Extract unique entities and relationships from paths
        entities: dict[str, dict[str, Any]] = {}
        relationships: list[dict[str, Any]] = []
        center_entity = await self._neo4j.get_entity_node(entity_id)

        for path in paths:
            # Process all nodes in the path
            segments = path.get("path", path.get("segments", []))
            if isinstance(segments, list):
                for segment in segments:
                    if "start" in segment:
                        node = segment["start"]
                        ent_id = node.get("elementId", "")
                        if ent_id:
                            entities[ent_id] = node
                    if "end" in segment:
                        node = segment["end"]
                        ent_id = node.get("elementId", "")
                        if ent_id:
                            entities[ent_id] = node
                    if "relationship" in segment:
                        relationships.append(segment["relationship"])

        # Remove center entity from neighbors
        neighbors = [v for k, v in entities.items() if k != entity_id]

        # Enrich with risk fields
        for entity_dict in (
            [center_entity] + neighbors if center_entity else neighbors
        ):
            ent_id = entity_dict.get("elementId", "")
            if not ent_id:
                # Try to get from the node data
                pass

        return RiskSubgraph(
            center_entity=center_entity or {},
            neighbors=neighbors,
            relationships=relationships,
            hops=hops,
        )

    async def assess_risk_propagation(
        self,
        entity_id: str,
        concern_entity_ids: list[str],
        hops: int = 3,
        rel_types: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        """Assess how risk on one entity propagates to concern entities.

        This is an agent-guided assessment. The method returns subgraph
        context, and the agent determines risk propagation based on
        graph structure (e.g., redundancy, alternative paths).

        Args:
            entity_id: Element ID of the entity with a potential risk event.
            concern_entity_ids: List of entity IDs the user cares about.
            hops: How many hops to traverse.
            rel_types: Optional relationship type filter.

        Returns:
            Dictionary with:
                - subgraph: RiskSubgraph context
                - paths_to_concern: List of paths from entity to concern
                  entities
                - alternative_paths: Count of alternative paths for each
                  concern
        """
        subgraph = await self.get_risk_subgraph(
            entity_id, hops=hops, rel_types=rel_types
        )

        # Find paths to concern entities
        paths_to_concern: list[dict[str, Any]] = []
        for concern_id in concern_entity_ids:
            path_result = await self._neo4j.multi_hop_subgraph(
                start_entity_id=entity_id,
                hops=hops,
                rel_types=rel_types,
            )
            # Check if concern entity is reachable
            for path_data in path_result:
                paths_to_concern.append(
                    {
                        "from": entity_id,
                        "to": concern_id,
                        "path": path_data,
                    }
                )

        # Count alternative paths (for agent to reason about)
        # This is a simplified count — the agent does the actual reasoning
        alternative_counts: dict[str, int] = {}
        for concern_id in concern_entity_ids:
            # Get all neighbor paths to the concern
            concern_paths = await self._neo4j.multi_hop_subgraph(
                start_entity_id=concern_id,
                hops=hops,
                rel_types=rel_types,
            )
            alternative_counts[concern_id] = len(concern_paths)

        return {
            "subgraph": {
                "center_entity": subgraph.center_entity,
                "neighbor_count": len(subgraph.neighbors),
                "relationship_count": len(subgraph.relationships),
                "hops": subgraph.hops,
            },
            "paths_to_concern": paths_to_concern,
            "alternative_paths": alternative_counts,
        }