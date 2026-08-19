"""High-level graph operations combining Neo4j client, embedding, and evidence store.

Provides composite operations for creating schema nodes, entity nodes with
automatic embedding, relationships with evidence, vector search, and
multi-hop subgraph traversal.
"""

from __future__ import annotations

from typing import Any, Optional

from .embedding import EmbeddingClient
from .evidence_store import EvidenceRecord, EvidenceStore
from .neo4j_client import Neo4jClient


class GraphOps:
    """High-level graph operations combining Neo4j, embeddings, and evidence.

    Provides composite operations that coordinate multiple components:
    schema creation, entity creation with auto-embedding, relationship
    creation with evidence linking, vector search, and multi-hop traversal.
    """

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        embedding_client: EmbeddingClient,
        evidence_store: EvidenceStore,
        vector_index_name: str = "entity_embedding_index",
    ) -> None:
        """Initialize GraphOps.

        Args:
            neo4j_client: Connected Neo4j client.
            embedding_client: Embedding client for generating vectors.
            evidence_store: Evidence store for saving provenance.
            vector_index_name: Name of the vector index for entity search.
        """
        self._neo4j = neo4j_client
        self._embedding = embedding_client
        self._evidence = evidence_store
        self._vector_index_name = vector_index_name

    async def create_schema_node(
        self,
        name: str,
        schema_type: str,
        description: str,
        fields: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """Create a schema node in Neo4j.

        Args:
            name: Schema name (e.g., "Supplier", "Material").
            schema_type: Type of schema (e.g., "entity", "relationship").
            description: Description of this schema type.
            fields: List of field definitions.

        Returns:
            Element ID of the created schema node.
        """
        return await self._neo4j.create_schema_node(
            name=name,
            schema_type=schema_type,
            description=description,
            fields=fields,
        )

    async def create_entity_node(
        self,
        schema_id: str,
        name: str,
        properties: Optional[dict[str, Any]] = None,
        evidence: Optional[list[EvidenceRecord]] = None,
    ) -> str:
        """Create an entity node, link to schema, and auto-embed for vector search.

        The entity name and description are concatenated and embedded
        automatically for vector similarity search.

        Args:
            schema_id: Element ID of the schema node to link to.
            name: Entity name.
            properties: Additional entity properties (may include 'description').
            evidence: Optional list of evidence records to save.

        Returns:
            Element ID of the created entity node.
        """
        props = dict(properties or {})
        props["name"] = name

        # Create the entity node
        entity_id = await self._neo4j.create_entity_node(
            name=name,
            properties=props,
            labels=["Entity"],
        )

        # Link to schema
        if entity_id:
            await self._neo4j.link_entity_to_schema(entity_id, schema_id)

        # Generate and store embedding
        if entity_id:
            embed_text = name
            if props.get("description"):
                embed_text = f"{name}: {props['description']}"
            embedding_vector = await self._embedding.embed(embed_text)
            if embedding_vector:
                await self._neo4j.update_entity_node(
                    entity_id, {"embedding": embedding_vector}
                )

        # Save evidence
        if entity_id and evidence:
            self._evidence.save_evidence_batch(evidence)

        return entity_id

    async def create_relationship(
        self,
        from_entity: str,
        to_entity: str,
        rel_type: str,
        properties: Optional[dict[str, Any]] = None,
        evidence: Optional[list[EvidenceRecord]] = None,
    ) -> str:
        """Create a relationship between two entities with optional evidence.

        Args:
            from_entity: Element ID of the source entity.
            to_entity: Element ID of the target entity.
            rel_type: Relationship type (e.g., "SUPPLIES", "PART_OF").
            properties: Optional relationship properties.
            evidence: Optional list of evidence records to save.

        Returns:
            Element ID of the created relationship.
        """
        rel_id = await self._neo4j.create_relationship(
            from_id=from_entity,
            to_id=to_entity,
            rel_type=rel_type,
            properties=properties,
        )

        # Save evidence for the relation
        if rel_id and evidence:
            for record in evidence:
                record.relation_id = rel_id
            self._evidence.save_evidence_batch(evidence)

        return rel_id

    async def link_entity_to_schema(
        self, entity_id: str, schema_id: str
    ) -> str:
        """Link an entity to a schema node.

        Args:
            entity_id: Element ID of the entity.
            schema_id: Element ID of the schema.

        Returns:
            Element ID of the created relationship.
        """
        return await self._neo4j.link_entity_to_schema(entity_id, schema_id)

    async def vector_search(
        self, query_text: str, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """Search for entities by text similarity using vector search.

        Embeds the query text and performs vector similarity search.

        Args:
            query_text: Text to search for.
            top_k: Number of top results to return.

        Returns:
            List of matched entities with their properties and score.
        """
        query_vector = await self._embedding.embed(query_text)
        if not query_vector:
            return []

        return await self._neo4j.vector_search(
            index_name=self._vector_index_name,
            query_vector=query_vector,
            top_k=top_k,
        )

    async def multi_hop_subgraph(
        self,
        start_entity: str,
        hops: int = 2,
        rel_types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Traverse the graph from a starting entity.

        Args:
            start_entity: Element ID of the starting entity.
            hops: Number of hops to traverse.
            rel_types: Optional list of relationship types to filter by.

        Returns:
            List of path dictionaries.
        """
        return await self._neo4j.multi_hop_subgraph(
            start_entity_id=start_entity,
            hops=hops,
            rel_types=rel_types,
        )

    async def get_schema_with_entities(
        self, schema_id: str
    ) -> dict[str, Any]:
        """Get a schema node with all its linked entities.

        Args:
            schema_id: Element ID of the schema node.

        Returns:
            Dictionary with 'schema' and 'entities' keys.
        """
        return await self._neo4j.get_schema_with_entities(schema_id)

    async def get_entity_with_evidence(
        self, entity_id: str
    ) -> dict[str, Any]:
        """Get an entity node with its evidence records.

        Args:
            entity_id: Element ID of the entity.

        Returns:
            Dictionary with 'entity' properties and 'evidence' list.
        """
        entity = await self._neo4j.get_entity_node(entity_id)
        evidence = self._evidence.load_evidence_by_entity(entity_id)
        return {
            "entity": entity,
            "evidence": [r.__dict__ for r in evidence],
        }

    async def get_entity_relationships(
        self, entity_id: str
    ) -> list[dict[str, Any]]:
        """Get all relationships for an entity.

        Args:
            entity_id: Element ID of the entity.

        Returns:
            List of relationship records.
        """
        return await self._neo4j.get_entity_relationships(entity_id)

    async def setup_vector_index(
        self, dimensions: int = 768
    ) -> None:
        """Set up the vector index for entity similarity search.

        Args:
            dimensions: Vector dimensions (default 768).
        """
        await self._neo4j.create_vector_index(
            index_name=self._vector_index_name,
            label="Entity",
            property_name="embedding",
            dimensions=dimensions,
        )