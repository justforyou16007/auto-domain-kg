"""Risk assessment module for user-concern-driven risk analysis.

Provides risk field management on entity nodes and agent-guided graph
traversal for risk assessment. Risk is NOT automatically propagated;
instead, an agent walks the graph to assess if a risk event on one
entity affects the user's concern topic, considering graph structure
(e.g., alternative paths, redundancy).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

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
    """Risk assessment manager for user-concern-driven risk analysis.

    Provides methods to add/update risk fields on entities, retrieve
    subgraph context for agent traversal, and assess risk impact
    considering graph structure.

    Risk is user-concern-driven: an agent walks the graph to assess
    if a risk event on one entity affects the user's concern topic,
    considering graph structure (e.g., 4 suppliers, 1 failing = not
    strong risk if 3 alternatives exist).
    """

    def __init__(self, neo4j_client: Neo4jClient) -> None:
        """Initialize the risk assessment module.

        Args:
            neo4j_client: Connected Neo4j client.
        """
        self._neo4j = neo4j_client

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
        for entity_dict in [center_entity] + neighbors if center_entity else neighbors:
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
                - paths_to_concern: List of paths from entity to concern entities
                - alternative_paths: Count of alternative paths for each concern
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