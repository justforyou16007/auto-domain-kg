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
        parent_schema_id: Optional[str] = None,
    ) -> str:
        """Create a schema node in Neo4j, optionally with a parent hierarchy.

        Args:
            name: Schema name (e.g., "Supplier", "Material").
            schema_type: Type of schema (e.g., "entity", "relationship").
            description: Description of this schema type.
            fields: List of field definitions.
            parent_schema_id: Optional element ID of a parent Schema node.
                              If provided, a SUBCLASS_OF relationship is
                              automatically created from the new node to
                              the parent.

        Returns:
            Element ID of the created schema node.
        """
        schema_id = await self._neo4j.create_schema_node(
            name=name,
            schema_type=schema_type,
            description=description,
            fields=fields,
        )
        if schema_id and parent_schema_id:
            await self._neo4j.create_schema_hierarchy(
                child_schema_id=schema_id,
                parent_schema_id=parent_schema_id,
            )
        return schema_id

    async def create_entity_node(
        self,
        schema_id: str,
        name: str,
        properties: Optional[dict[str, Any]] = None,
        evidence: Optional[list[EvidenceRecord]] = None,
        source_url: str = "",
        source_text: str = "",
    ) -> str:
        """Create an entity node, link to schema, and auto-embed for vector search.

        The entity name and description are concatenated and embedded
        automatically for vector similarity search.

        Args:
            schema_id: Element ID of the schema node to link to.
            name: Entity name.
            properties: Additional entity properties (may include 'description').
            evidence: Optional list of evidence records to save.
            source_url: URL of the source document for provenance. Stored
                directly on the entity node so it can be traced back to the
                original source without needing to consult the evidence store.
            source_text: Text snippet from the source document for provenance.
                Stored directly on the entity node for traceability.

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
            source_url=source_url,
            source_text=source_text,
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
        When embeddings are unavailable (endpoint not configured or returns
        empty), falls back to BM25 full-text search so the graph remains
        queryable.

        Args:
            query_text: Text to search for.
            top_k: Number of top results to return.

        Returns:
            List of matched entities with their properties and score.
        """
        query_vector = await self._embedding.embed(query_text)
        if not query_vector:
            # Embedding unavailable — degrade to BM25 keyword search
            return await self._neo4j.bm25_search(query_text, top_k=top_k)

        results = await self._neo4j.vector_search(
            index_name=self._vector_index_name,
            query_vector=query_vector,
            top_k=top_k,
        )
        if not results:
            # Vector search returned nothing — also degrade to BM25
            return await self._neo4j.bm25_search(query_text, top_k=top_k)
        return results

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

    async def find_merge_target_with_hierarchy(
        self,
        entity_name: str,
        schema_id: str,
        similarity_threshold: float = 0.85,
    ) -> Optional[dict[str, Any]]:
        """Find a merge target for an entity with hierarchy-aware search.

        Searches for a semantically similar entity in the current Schema
        level first. If none found, traverses up the SUBCLASS_OF hierarchy
        to look for merge targets in parent Schema nodes.

        Args:
            entity_name: Name of the entity to find a merge target for.
            schema_id: Element ID of the current Schema node.
            similarity_threshold: Vector similarity threshold (default 0.85).

        Returns:
            Dictionary with 'entity' (node properties), 'schema_name'
            (name of the Schema where the target was found), and
            'similarity' (score) if found, or None if no merge target.
        """
        # Step 1: Try vector search at the current Schema level
        query_vector = await self._embedding.embed(entity_name)
        if not query_vector:
            return None

        candidates = await self._neo4j.vector_search(
            index_name=self._vector_index_name,
            query_vector=query_vector,
            top_k=5,
        )

        # Filter candidates that belong to the same schema
        for c in candidates:
            node = c.get("node", {})
            score = c.get("score", 0.0)
            if score >= similarity_threshold:
                # Check if this entity belongs to the target schema
                schema_info = await self._neo4j.get_schema_with_entities(
                    schema_id
                )
                entity_ids = {
                    e.get("elementId", "") for e in schema_info.get("entities", [])
                }
                node_id = node.get("elementId", "")
                if node_id in entity_ids:
                    return {
                        "entity": node,
                        "schema_name": "",
                        "similarity": score,
                    }

        # Step 2: If no match at current level, traverse ancestors
        ancestors = await self._neo4j.get_schema_ancestors(schema_id)
        for ancestor in ancestors:
            ancestor_id = ancestor.get("elementId", "")
            if not ancestor_id:
                # Try to get schema by name
                ancestor_name = ancestor.get("name", "")
                ancestor_node = await self._neo4j.get_schema_by_name(
                    ancestor_name
                )
                if ancestor_node:
                    ancestor_id = ancestor_node.get("elementId", "")

            if ancestor_id:
                schema_info = await self._neo4j.get_schema_with_entities(
                    ancestor_id
                )
                for e in schema_info.get("entities", []):
                    # Check similarity with each entity in ancestor schema
                    entity_name_str = e.get("name", "")
                    if entity_name_str.lower() == entity_name.lower():
                        return {
                            "entity": e,
                            "schema_name": ancestor.get("name", ""),
                            "similarity": 1.0,
                        }

                # Also use vector search against ancestor entities
                candidates2 = await self._neo4j.vector_search(
                    index_name=self._vector_index_name,
                    query_vector=query_vector,
                    top_k=5,
                )
                for c in candidates2:
                    node = c.get("node", {})
                    score = c.get("score", 0.0)
                    if score >= similarity_threshold:
                        entity_ids2 = {
                            e2.get("elementId", "")
                            for e2 in schema_info.get("entities", [])
                        }
                        node_id2 = node.get("elementId", "")
                        if node_id2 in entity_ids2:
                            return {
                                "entity": node,
                                "schema_name": ancestor.get("name", ""),
                                "similarity": score,
                            }

        return None

    async def merge_entity_to_parent_schema(
        self, entity_id: str, parent_schema_id: str
    ) -> str:
        """Re-link an entity to a parent Schema node (hierarchy promotion).

        Removes the entity's existing HAS_SCHEMA relationship and creates
        a new one pointing to the parent Schema. This is used when merging
        entities from child schemas up to a common parent.

        Args:
            entity_id: Element ID of the entity to re-link.
            parent_schema_id: Element ID of the parent Schema node.

        Returns:
            Element ID of the new HAS_SCHEMA relationship.
        """
        # Remove existing HAS_SCHEMA relationships
        query = (
            "MATCH (e) WHERE elementId(e) = $entity_id "
            "MATCH (e)-[r:HAS_SCHEMA]->(s:Schema) "
            "DELETE r"
        )
        await self._neo4j._run_query(
            query, {"entity_id": entity_id}
        )

        # Create new HAS_SCHEMA to parent
        new_link_id = await self._neo4j.link_entity_to_schema(
            entity_id=entity_id, schema_id=parent_schema_id
        )
        return new_link_id

    # ---- Schema-Relation Alignment (Issue #17) ----

    @staticmethod
    def get_missing_schema_relations(
        triples: list[dict[str, Any]],
        schema_definition: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Find relation types present in triples but missing from schema.

        For each triple, checks whether the relation type between the
        subject's schema type and the object's schema type is defined in
        the schema definition. Triples whose relation type has no matching
        schema relationship are returned as "schema extension needed".

        The schema_definition is expected to have a ``relationships`` key
        containing a list of relationship definitions, each with at least
        ``source_type``, ``target_type``, and ``relation_type`` keys. Triples
        are dicts with ``subject_type``, ``relation``, and ``object_type``
        keys (``subject_type``/``object_type`` map to schema entity type names).

        Args:
            triples: List of extracted triple dicts.
            schema_definition: Schema definition dict with entity_types and
                relationships.

        Returns:
            List of triple dicts that need a schema relation extension.
        """
        schema_rels: list[dict[str, Any]] = (
            schema_definition.get("relationships", [])
            if isinstance(schema_definition, dict)
            else []
        )
        # Build a set of (source_type, relation_type, target_type) tuples
        # for fast lookup (case-insensitive).
        defined: set[tuple[str, str, str]] = set()
        for rel in schema_rels:
            src = str(rel.get("source_type", rel.get("from_type", ""))).strip().lower()
            tgt = str(rel.get("target_type", rel.get("to_type", ""))).strip().lower()
            rtype = str(rel.get("relation_type", rel.get("type", ""))).strip().lower()
            if rtype:
                defined.add((src, rtype, tgt))
                # Also store a relaxed (source, relation, *) match for any target
        # Build a per (source, relation) set of allowed targets and a
        # per relation set of allowed (source, target) pairs.
        rel_pairs: set[tuple[str, str]] = set()
        rel_types_only: set[str] = set()
        for (src, rtype, tgt) in defined:
            rel_pairs.add((src, rtype))
            rel_types_only.add(rtype)

        missing: list[dict[str, Any]] = []
        for triple in triples:
            subj = str(triple.get("subject_type", "")).strip().lower()
            obj = str(triple.get("object_type", "")).strip().lower()
            rel = str(triple.get("relation", triple.get("relation_type", ""))).strip().lower()
            if not rel:
                continue
            # A triple is "missing" if the (subject_type, relation_type)
            # pair is not defined in the schema — meaning the schema has no
            # relationship of this type originating from the subject type.
            if (subj, rel) not in rel_pairs:
                entry = dict(triple)
                entry["schema_extension_needed"] = True
                entry["reason"] = (
                    f"Schema has no relationship type '{rel}' "
                    f"originating from entity type '{subj}'"
                )
                missing.append(entry)
        return missing

    @staticmethod
    def validate_relation_alignment(
        schema_definition: dict[str, Any],
        triples: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate that each triple's relation type is defined in the schema.

        Checks every triple to see if its relation type has a corresponding
        schema-level relationship definition between the subject and object
        schema types. Returns a report of aligned triples, misaligned triples
        (relation exists but between different types), and triples that need
        a schema extension.

        Args:
            schema_definition: Schema definition dict.
            triples: List of extracted triple dicts.

        Returns:
            Dict with keys:
              - ``total_triples``: total number of triples checked
              - ``aligned``: triples whose relation matches the schema
              - ``misaligned``: triples whose relation type exists in the
                schema but with different source/target types
              - ``missing_schema_relations``: triples that need schema extension
              - ``is_aligned``: True if all triples are aligned
        """
        schema_rels: list[dict[str, Any]] = (
            schema_definition.get("relationships", [])
            if isinstance(schema_definition, dict)
            else []
        )
        # Map (source_type_lower, target_type_lower) -> set of relation_type_lower
        pair_to_rels: dict[tuple[str, str], set[str]] = {}
        rel_type_to_pairs: dict[str, list[tuple[str, str]]] = {}
        for rel in schema_rels:
            src = str(rel.get("source_type", rel.get("from_type", ""))).strip().lower()
            tgt = str(rel.get("target_type", rel.get("to_type", ""))).strip().lower()
            rtype = str(rel.get("relation_type", rel.get("type", ""))).strip().lower()
            if not rtype:
                continue
            pair_to_rels.setdefault((src, tgt), set()).add(rtype)
            rel_type_to_pairs.setdefault(rtype, []).append((src, tgt))

        aligned: list[dict[str, Any]] = []
        misaligned: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []

        for triple in triples:
            subj = str(triple.get("subject_type", "")).strip().lower()
            obj = str(triple.get("object_type", "")).strip().lower()
            rel = str(triple.get("relation", triple.get("relation_type", ""))).strip().lower()
            if not rel:
                continue
            pair_rels = pair_to_rels.get((subj, obj), set())
            if rel in pair_rels:
                # Exact match: schema defines this relation between these types
                aligned.append(triple)
            elif rel in rel_type_to_pairs:
                # Relation type exists but between different entity types
                entry = dict(triple)
                entry["schema_misaligned"] = True
                entry["defined_pairs"] = rel_type_to_pairs[rel]
                misaligned.append(entry)
            else:
                # Relation type not defined anywhere in schema
                entry = dict(triple)
                entry["schema_extension_needed"] = True
                entry["reason"] = (
                    f"Schema has no relationship type '{rel}' defined"
                )
                missing.append(entry)

        return {
            "total_triples": len(triples),
            "aligned": aligned,
            "misaligned": misaligned,
            "missing_schema_relations": missing,
            "is_aligned": len(misaligned) == 0 and len(missing) == 0,
        }