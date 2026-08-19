"""Neo4j client for schema and instance CRUD, vector index operations, and Cypher queries.

Provides connection management, schema/instance node CRUD, relationship CRUD,
vector index creation and similarity search, and multi-hop Cypher queries.
Supports both password authentication and no-auth (for local Docker Neo4j).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

from neo4j import AsyncGraphDatabase, Driver, Session, basic_auth


@dataclass
class Neo4jConfig:
    """Neo4j connection configuration from environment variables."""

    uri: str = field(default_factory=lambda: os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    user: str = field(default_factory=lambda: os.environ.get("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.environ.get("NEO4J_PASSWORD", ""))
    database: str = field(default_factory=lambda: os.environ.get("NEO4J_DATABASE", "neo4j"))

    @property
    def use_auth(self) -> bool:
        """Whether to use password authentication. If password is empty, use no-auth."""
        return bool(self.password)


class Neo4jClient:
    """Client for interacting with Neo4j database.

    Handles schema/instance CRUD, vector index operations, and Cypher queries.
    """

    def __init__(self, config: Optional[Neo4jConfig] = None) -> None:
        """Initialize the Neo4j client.

        Args:
            config: Neo4j connection configuration. If None, reads from env vars.
        """
        self._config = config or Neo4jConfig()
        self._driver: Optional[Driver] = None

    async def connect(self) -> None:
        """Establish connection to Neo4j database."""
        if self._config.use_auth:
            self._driver = AsyncGraphDatabase.driver(
                self._config.uri,
                auth=basic_auth(self._config.user, self._config.password),
            )
        else:
            self._driver = AsyncGraphDatabase.driver(self._config.uri)

        # Verify connectivity
        async with self._driver.session(database=self._config.database) as session:
            await session.run("RETURN 1")

    async def close(self) -> None:
        """Close the database connection."""
        if self._driver:
            await self._driver.close()
            self._driver = None

    async def _run_query(
        self, query: str, parameters: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """Run a Cypher query and return results.

        Args:
            query: Cypher query string.
            parameters: Query parameters.

        Returns:
            List of result records as dictionaries.
        """
        if not self._driver:
            raise RuntimeError("Neo4j client not connected. Call connect() first.")
        async with self._driver.session(database=self._config.database) as session:
            result = await session.run(query, parameters or {})
            records = await result.data()
            return records

    # ---- Vector Index Operations ----

    async def create_vector_index(
        self,
        index_name: str,
        label: str = "Entity",
        property_name: str = "embedding",
        dimensions: int = 768,
        similarity_fn: str = "cosine",
    ) -> None:
        """Create a vector index for Neo4j 5.x.

        Args:
            index_name: Name of the vector index.
            label: Node label to index.
            property_name: Node property containing the vector.
            dimensions: Vector dimensions (default 768 for most embedding models).
            similarity_fn: Similarity function: "cosine" or "euclidean".
        """
        query = (
            f"CREATE VECTOR INDEX {index_name} IF NOT EXISTS "
            f"FOR (n:{label}) ON n.{property_name} "
            f"OPTIONS {{indexConfig: {{`vector.dimensions`: {dimensions}, "
            f"`vector.similarity_function`: '{similarity_fn}'}}}}"
        )
        await self._run_query(query)

    async def drop_vector_index(self, index_name: str) -> None:
        """Drop a vector index.

        Args:
            index_name: Name of the vector index to drop.
        """
        query = f"DROP INDEX {index_name} IF EXISTS"
        await self._run_query(query)

    async def list_vector_indexes(self) -> list[dict[str, Any]]:
        """List all vector indexes in the database.

        Returns:
            List of index information dictionaries.
        """
        query = "SHOW VECTOR INDEXES"
        return await self._run_query(query)

    # ---- Schema Node CRUD ----

    async def create_schema_node(
        self,
        name: str,
        schema_type: str,
        description: str,
        fields: Optional[list[dict[str, str]]] = None,
    ) -> str:
        """Create a schema node.

        Args:
            name: Schema name (e.g., "Supplier", "Material").
            schema_type: Type of schema (e.g., "entity", "relationship").
            description: Description of this schema type.
            fields: List of field definitions, each with "name", "type", "description".

        Returns:
            The element ID of the created node.
        """
        query = (
            "CREATE (s:Schema {name: $name, type: $schema_type, "
            "description: $description, fields: $fields, created_at: datetime()}) "
            "RETURN elementId(s) AS id"
        )
        results = await self._run_query(
            query,
            {
                "name": name,
                "schema_type": schema_type,
                "description": description,
                "fields": fields or [],
            },
        )
        return results[0]["id"] if results else ""

    async def get_schema_node(self, schema_id: str) -> Optional[dict[str, Any]]:
        """Get a schema node by element ID.

        Args:
            schema_id: Element ID of the schema node.

        Returns:
            Schema node properties, or None if not found.
        """
        query = "MATCH (s:Schema) WHERE elementId(s) = $id RETURN s"
        results = await self._run_query(query, {"id": schema_id})
        return results[0]["s"] if results else None

    async def get_schema_by_name(self, name: str) -> Optional[dict[str, Any]]:
        """Get a schema node by name.

        Args:
            name: Schema name.

        Returns:
            Schema node properties, or None if not found.
        """
        query = "MATCH (s:Schema {name: $name}) RETURN s"
        results = await self._run_query(query, {"name": name})
        return results[0]["s"] if results else None

    async def update_schema_node(
        self, schema_id: str, updates: dict[str, Any]
    ) -> None:
        """Update a schema node's properties.

        Args:
            schema_id: Element ID of the schema node.
            updates: Dictionary of properties to update.
        """
        set_clause = ", ".join(f"s.{k} = ${k}" for k in updates)
        query = f"MATCH (s:Schema) WHERE elementId(s) = $id SET {set_clause}"
        await self._run_query(query, {"id": schema_id, **updates})

    async def delete_schema_node(self, schema_id: str) -> None:
        """Delete a schema node and all its linked entities.

        Args:
            schema_id: Element ID of the schema node.
        """
        query = (
            "MATCH (s:Schema) WHERE elementId(s) = $id "
            "OPTIONAL MATCH (s)<-[:HAS_SCHEMA]-(e) "
            "DETACH DELETE s, e"
        )
        await self._run_query(query, {"id": schema_id})

    async def list_all_schemas(self) -> list[dict[str, Any]]:
        """List all schema nodes.

        Returns:
            List of schema node properties.
        """
        query = "MATCH (s:Schema) RETURN s ORDER BY s.name"
        results = await self._run_query(query)
        return [r["s"] for r in results]

    # ---- Instance Node CRUD ----

    async def create_entity_node(
        self,
        name: str,
        properties: Optional[dict[str, Any]] = None,
        labels: Optional[list[str]] = None,
    ) -> str:
        """Create an entity/instance node with optional labels.

        Args:
            name: Entity name (stored in 'name' property).
            properties: Additional entity properties.
            labels: List of labels for the node. Defaults to ["Entity"].

        Returns:
            The element ID of the created node.
        """
        entity_labels = labels or ["Entity"]
        label_str = ":".join(entity_labels)
        query = (
            f"CREATE (e:{label_str} {{name: $name, created_at: datetime()}}) "
            f"SET e = $properties "
            f"RETURN elementId(e) AS id"
        )
        results = await self._run_query(
            query, {"name": name, "properties": properties or {}}
        )
        return results[0]["id"] if results else ""

    async def get_entity_node(self, entity_id: str) -> Optional[dict[str, Any]]:
        """Get an entity node by element ID.

        Args:
            entity_id: Element ID of the entity node.

        Returns:
            Entity node properties, or None if not found.
        """
        query = "MATCH (e) WHERE elementId(e) = $id RETURN e"
        results = await self._run_query(query, {"id": entity_id})
        return results[0]["e"] if results else None

    async def update_entity_node(
        self, entity_id: str, properties: dict[str, Any]
    ) -> None:
        """Update an entity node's properties.

        Args:
            entity_id: Element ID of the entity node.
            properties: Dictionary of properties to update.
        """
        set_clause = ", ".join(f"e.{k} = ${k}" for k in properties)
        query = f"MATCH (e) WHERE elementId(e) = $id SET {set_clause}"
        await self._run_query(query, {"id": entity_id, **properties})

    async def delete_entity_node(self, entity_id: str) -> None:
        """Delete an entity node and its relationships.

        Args:
            entity_id: Element ID of the entity node.
        """
        query = (
            "MATCH (e) WHERE elementId(e) = $id "
            "DETACH DELETE e"
        )
        await self._run_query(query, {"id": entity_id})

    async def list_entities_by_label(self, label: str) -> list[dict[str, Any]]:
        """List all entity nodes with a given label.

        Args:
            label: Node label to filter by.

        Returns:
            List of entity node properties.
        """
        query = f"MATCH (e:{label}) RETURN e ORDER BY e.name"
        results = await self._run_query(query)
        return [r["e"] for r in results]

    # ---- Relationship CRUD ----

    async def create_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        properties: Optional[dict[str, Any]] = None,
    ) -> str:
        """Create a relationship between two nodes.

        Args:
            from_id: Element ID of the source node.
            to_id: Element ID of the target node.
            rel_type: Relationship type (e.g., "SUPPLIES", "PART_OF").
            properties: Optional relationship properties.

        Returns:
            The element ID of the created relationship.
        """
        query = (
            f"MATCH (a) WHERE elementId(a) = $from_id "
            f"MATCH (b) WHERE elementId(b) = $to_id "
            f"CREATE (a)-[r:{rel_type} $properties]->(b) "
            f"RETURN elementId(r) AS id"
        )
        results = await self._run_query(
            query,
            {
                "from_id": from_id,
                "to_id": to_id,
                "properties": properties or {},
            },
        )
        return results[0]["id"] if results else ""

    async def link_entity_to_schema(self, entity_id: str, schema_id: str) -> str:
        """Link an entity node to a schema node via HAS_SCHEMA relationship.

        Args:
            entity_id: Element ID of the entity node.
            schema_id: Element ID of the schema node.

        Returns:
            The element ID of the created relationship.
        """
        query = (
            "MATCH (e) WHERE elementId(e) = $entity_id "
            "MATCH (s:Schema) WHERE elementId(s) = $schema_id "
            "CREATE (e)-[r:HAS_SCHEMA]->(s) "
            "RETURN elementId(r) AS id"
        )
        results = await self._run_query(
            query, {"entity_id": entity_id, "schema_id": schema_id}
        )
        return results[0]["id"] if results else ""

    async def delete_relationship(self, rel_id: str) -> None:
        """Delete a relationship by element ID.

        Args:
            rel_id: Element ID of the relationship.
        """
        query = (
            "MATCH ()-[r]->() WHERE elementId(r) = $id "
            "DELETE r"
        )
        await self._run_query(query, {"id": rel_id})

    # ---- Vector Similarity Search ----

    async def vector_search(
        self,
        index_name: str,
        query_vector: list[float],
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Perform vector similarity search.

        Args:
            index_name: Name of the vector index to search.
            query_vector: The query embedding vector.
            top_k: Number of top results to return.

        Returns:
            List of matched entities with their properties and score.
        """
        query = (
            f"CALL db.index.vector.queryNodes($index_name, $top_k, $query_vector) "
            f"YIELD node, score "
            f"RETURN node, score"
        )
        results = await self._run_query(
            query,
            {
                "index_name": index_name,
                "top_k": top_k,
                "query_vector": query_vector,
            },
        )
        return results

    # ---- Multi-hop Cypher Queries ----

    async def multi_hop_subgraph(
        self,
        start_entity_id: str,
        hops: int = 2,
        rel_types: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Traverse the graph from a starting entity for a given number of hops.

        Args:
            start_entity_id: Element ID of the starting entity.
            hops: Number of hops to traverse (default 2).
            rel_types: Optional list of relationship types to filter by.

        Returns:
            List of path dictionaries with nodes and relationships.
        """
        rel_filter = ""
        if rel_types:
            rel_str = "|".join(rel_types)
            rel_filter = f"-[r:{rel_str}]-"
        else:
            rel_filter = "-[r]-"

        query = (
            f"MATCH path = (start) WHERE elementId(start) = $start_id "
            f"MATCH path = (start){rel_filter}*(..{hops}) "
            f"RETURN path"
        )
        results = await self._run_query(query, {"start_id": start_entity_id})
        return results

    async def get_schema_with_entities(
        self, schema_id: str
    ) -> dict[str, Any]:
        """Get a schema node with all its linked entities.

        Args:
            schema_id: Element ID of the schema node.

        Returns:
            Dictionary with 'schema' and 'entities' keys.
        """
        query = (
            "MATCH (s:Schema) WHERE elementId(s) = $id "
            "OPTIONAL MATCH (e)-[:HAS_SCHEMA]->(s) "
            "RETURN s AS schema, COLLECT(DISTINCT e) AS entities"
        )
        results = await self._run_query(query, {"id": schema_id})
        return results[0] if results else {"schema": None, "entities": []}

    async def get_entity_relationships(
        self, entity_id: str
    ) -> list[dict[str, Any]]:
        """Get all relationships for an entity.

        Args:
            entity_id: Element ID of the entity.

        Returns:
            List of relationship records with source and target nodes.
        """
        query = (
            "MATCH (e) WHERE elementId(e) = $id "
            "OPTIONAL MATCH (e)-[r]->(target) "
            "RETURN e AS source, r AS relationship, target "
            "UNION "
            "MATCH (e) WHERE elementId(e) = $id "
            "OPTIONAL MATCH (source)-[r]->(e) "
            "RETURN source, r AS relationship, e AS target"
        )
        results = await self._run_query(query, {"id": entity_id})
        return results

    async def execute_custom_query(
        self, query: str, parameters: Optional[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """Execute a custom Cypher query.

        Args:
            query: Cypher query string.
            parameters: Query parameters.

        Returns:
            Query results as a list of dictionaries.
        """
        return await self._run_query(query, parameters)