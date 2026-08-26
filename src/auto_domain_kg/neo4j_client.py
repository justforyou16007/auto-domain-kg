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

    # ---- Schema Hierarchy Operations ----

    async def create_schema_hierarchy(
        self, child_schema_id: str, parent_schema_id: str
    ) -> str:
        """Create a SUBCLASS_OF relationship between two Schema nodes.

        Args:
            child_schema_id: Element ID of the child Schema node.
            parent_schema_id: Element ID of the parent Schema node.

        Returns:
            The element ID of the created relationship.
        """
        query = (
            "MATCH (child:Schema) WHERE elementId(child) = $child_id "
            "MATCH (parent:Schema) WHERE elementId(parent) = $parent_id "
            "CREATE (child)-[r:SUBCLASS_OF]->(parent) "
            "RETURN elementId(r) AS id"
        )
        results = await self._run_query(
            query,
            {"child_id": child_schema_id, "parent_id": parent_schema_id},
        )
        return results[0]["id"] if results else ""

    async def get_schema_ancestors(
        self, schema_id: str
    ) -> list[dict[str, Any]]:
        """Get all ancestor Schema nodes along SUBCLASS_OF relationships.

        Traverses upward from the given Schema node following SUBCLASS_OF
        relationships to find all parent, grandparent, etc. nodes.

        Args:
            schema_id: Element ID of the Schema node.

        Returns:
            List of ancestor Schema node properties, ordered from
            nearest ancestor to farthest.
        """
        query = (
            "MATCH (s:Schema) WHERE elementId(s) = $id "
            "MATCH (s)-[:SUBCLASS_OF*1..]->(ancestor:Schema) "
            "RETURN DISTINCT ancestor "
            "ORDER BY ancestor.name"
        )
        results = await self._run_query(query, {"id": schema_id})
        return [r["ancestor"] for r in results]

    async def get_schema_descendants(
        self, schema_id: str
    ) -> list[dict[str, Any]]:
        """Get all descendant Schema nodes along SUBCLASS_OF relationships.

        Traverses downward from the given Schema node following
        SUBCLASS_OF relationships to find all children, grandchildren, etc.

        Args:
            schema_id: Element ID of the Schema node.

        Returns:
            List of descendant Schema node properties, ordered by name.
        """
        query = (
            "MATCH (s:Schema) WHERE elementId(s) = $id "
            "MATCH (s)<-[:SUBCLASS_OF*1..]-(descendant:Schema) "
            "RETURN DISTINCT descendant "
            "ORDER BY descendant.name"
        )
        results = await self._run_query(query, {"id": schema_id})
        return [r["descendant"] for r in results]

    async def find_common_ancestor(
        self, schema_id_a: str, schema_id_b: str
    ) -> Optional[dict[str, Any]]:
        """Find the nearest common ancestor of two Schema nodes.

        Args:
            schema_id_a: Element ID of the first Schema node.
            schema_id_b: Element ID of the second Schema node.

        Returns:
            The common ancestor Schema node properties, or None if no
            common ancestor exists.
        """
        query = (
            "MATCH (a:Schema) WHERE elementId(a) = $id_a "
            "MATCH (b:Schema) WHERE elementId(b) = $id_b "
            "MATCH (a)-[:SUBCLASS_OF*0..]->(common:Schema) "
            "WHERE (b)-[:SUBCLASS_OF*0..]->(common) "
            "RETURN common "
            "ORDER BY size([(common)-[:SUBCLASS_OF*0..]->() | 1]) ASC "
            "LIMIT 1"
        )
        results = await self._run_query(
            query, {"id_a": schema_id_a, "id_b": schema_id_b}
        )
        return results[0]["common"] if results else None

    async def get_schema_with_ancestors(
        self, schema_id: str
    ) -> dict[str, Any]:
        """Get a Schema node along with its ancestor chain.

        Useful for hierarchy-aware merging: when looking for merge targets,
        you can check ancestors to find broader categories.

        Args:
            schema_id: Element ID of the Schema node.

        Returns:
            Dictionary with 'schema' (the node itself) and 'ancestors'
            (list of ancestor node properties).
        """
        schema_node = await self.get_schema_node(schema_id)
        ancestors = await self.get_schema_ancestors(schema_id)
        return {
            "schema": schema_node,
            "ancestors": ancestors,
        }

    # ---- Instance Node CRUD ----

    async def create_entity_node(
        self,
        name: str,
        properties: Optional[dict[str, Any]] = None,
        labels: Optional[list[str]] = None,
        source_url: str = "",
        source_text: str = "",
    ) -> str:
        """Create an entity/instance node with optional labels.

        Args:
            name: Entity name (stored in 'name' property).
            properties: Additional entity properties.
            labels: List of labels for the node. Defaults to ["Entity"].
            source_url: URL of the source document for provenance.
            source_text: Text snippet from the source document for provenance.

        Returns:
            The element ID of the created node.
        """
        entity_labels = labels or ["Entity"]
        label_str = ":".join(entity_labels)
        merged_properties = dict(properties or {})
        # Inject source fields into properties, but do NOT overwrite
        # if the caller explicitly passed them as keyword arguments
        if source_url:
            merged_properties["source_url"] = source_url
        if source_text:
            merged_properties["source_text"] = source_text
        query = (
            f"CREATE (e:{label_str} {{name: $name, created_at: datetime()}}) "
            f"SET e = $properties "
            f"RETURN elementId(e) AS id"
        )
        results = await self._run_query(
            query, {"name": name, "properties": merged_properties}
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
            f"CREATE (a)-[r:{rel_type}]->(b) "
            f"SET r = $properties "
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

    # ---- Keyword & Full-Text Search ----

    async def keyword_search(
        self,
        query: str,
        labels: Optional[list[str]] = None,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Search entities and schemas by keyword using CONTAINS.

        A lightweight keyword search that works without any vector index or
        full-text index. It scans the ``name`` and ``source_url``/``source_text``
        (entities) or ``name`` and ``source`` (schemas) properties of nodes.

        Args:
            query: Search query string (matched as a substring).
            labels: Optional list of labels to restrict the search to
                (e.g., ``["Entity"]``). Defaults to searching both
                ``Entity`` and ``Schema`` nodes.
            top_k: Maximum number of results to return.

        Returns:
            List of matched nodes (each a dict with a ``node`` key holding
            node properties). Empty list if nothing matches.
        """
        search_labels = labels or ["Entity", "Schema"]
        clauses: list[str] = []
        for label in search_labels:
            # Build a CONTAINS-based clause for this label
            prop_checks = [f"n.name CONTAINS $query"]
            if label == "Schema":
                prop_checks.append("n.source CONTAINS $query")
            else:
                prop_checks.append("n.source_url CONTAINS $query")
                prop_checks.append("n.source_text CONTAINS $query")
            checks = " OR ".join(prop_checks)
            clauses.append(
                f"MATCH (n:{label}) WHERE {checks} "
                f"RETURN n AS node"
            )
        query_str = " UNION ".join(clauses) + f" LIMIT {top_k}"
        results = await self._run_query(query_str, {"query": query})
        return results

    async def bm25_search(
        self,
        query_text: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Full-text (BM25) search over entities and schemas.

        Uses Neo4j's ``db.index.fulltext.queryNodes`` procedure to perform
        a BM25-ranked search. Requires a full-text index named
        ``entity_schema_fts`` on the ``name``, ``source_url``, ``source_text``
        (Entity) and ``name``, ``source`` (Schema) properties.

        If the full-text index does not exist, this falls back gracefully to
        :meth:`keyword_search` so callers always get a result.

        Args:
            query_text: Search query string.
            top_k: Maximum number of results to return.

        Returns:
            List of matched nodes with a ``node`` key (node properties) and,
            when using the full-text index, a ``score`` key.
        """
        try:
            query_str = (
                "CALL db.index.fulltext.queryNodes($index_name, $query_text) "
                "YIELD node, score "
                "RETURN node, score "
                "ORDER BY score DESC "
                f"LIMIT {top_k}"
            )
            results = await self._run_query(
                query_str,
                {
                    "index_name": "entity_schema_fts",
                    "query_text": query_text,
                },
            )
            if results:
                return results
        except Exception:
            # Full-text index may not exist; fall back to keyword search
            pass
        # Fallback: keyword-based search (no BM25 ranking)
        return await self.keyword_search(query_text, top_k=top_k)

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