"""Tests for the graph operations module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from auto_domain_kg.evidence_store import EvidenceRecord, EvidenceStore
from auto_domain_kg.graph_ops import GraphOps


@pytest.fixture
def mock_neo4j():
    """Create a mock Neo4jClient."""
    client = AsyncMock()
    client.create_schema_node = AsyncMock(return_value="schema-1")
    client.create_entity_node = AsyncMock(return_value="entity-1")
    client.create_relationship = AsyncMock(return_value="rel-1")
    client.link_entity_to_schema = AsyncMock(return_value="link-1")
    client.get_entity_node = AsyncMock(
        return_value={"name": "Test Corp", "description": "A test company"}
    )
    client.vector_search = AsyncMock(
        return_value=[{"node": {"name": "Test Corp"}, "score": 0.95}]
    )
    client.multi_hop_subgraph = AsyncMock(
        return_value=[{"path": [{"start": {}, "end": {}, "relationship": {}}]}]
    )
    client.get_schema_with_entities = AsyncMock(
        return_value={
            "schema": {"name": "Supplier", "type": "entity"},
            "entities": [{"name": "Test Corp"}],
        }
    )
    client.get_entity_relationships = AsyncMock(
        return_value=[
            {
                "source": {"name": "Test Corp"},
                "relationship": {"type": "SUPPLIES"},
                "target": {"name": "Other Corp"},
            }
        ]
    )
    client.update_entity_node = AsyncMock()
    client.create_vector_index = AsyncMock()
    return client


@pytest.fixture
def mock_embedding():
    """Create a mock EmbeddingClient."""
    client = AsyncMock()
    client.embed = AsyncMock(return_value=[0.1, 0.2, 0.3, 0.4])
    client.embed_batch = AsyncMock(
        return_value=[[0.1, 0.0, 0.0, 0.0], [0.0, 0.2, 0.0, 0.0]]
    )
    return client


@pytest.fixture
def mock_evidence_store():
    """Create a mock EvidenceStore."""
    store = MagicMock()
    store.save_evidence = MagicMock()
    store.save_evidence_batch = MagicMock()
    store.load_evidence_by_entity = MagicMock(
        return_value=[
            EvidenceRecord(
                entity_id="entity-1",
                text_slice="Test evidence",
                source_url="https://example.com",
            )
        ]
    )
    return store


@pytest.fixture
def graph_ops(mock_neo4j, mock_embedding, mock_evidence_store):
    """Create a GraphOps with mocked dependencies."""
    return GraphOps(
        neo4j_client=mock_neo4j,
        embedding_client=mock_embedding,
        evidence_store=mock_evidence_store,
        vector_index_name="test_index",
    )


@pytest.mark.asyncio
async def test_create_schema_node(graph_ops, mock_neo4j):
    """Test creating a schema node."""
    result = await graph_ops.create_schema_node(
        name="Supplier",
        schema_type="entity",
        description="A supplier entity",
        fields=[{"name": "name", "type": "string", "description": "Name"}],
    )
    assert result == "schema-1"
    mock_neo4j.create_schema_node.assert_called_once()


@pytest.mark.asyncio
async def test_create_entity_node(graph_ops, mock_neo4j, mock_embedding):
    """Test creating an entity node with auto-embedding."""
    result = await graph_ops.create_entity_node(
        schema_id="schema-1",
        name="Test Corp",
        properties={"description": "A test company"},
        evidence=[
            EvidenceRecord(
                entity_id="entity-1",
                text_slice="Test Corp is a company.",
                source_url="https://example.com",
            )
        ],
    )
    assert result == "entity-1"
    mock_neo4j.create_entity_node.assert_called_once()
    mock_neo4j.link_entity_to_schema.assert_called_once_with("entity-1", "schema-1")
    mock_embedding.embed.assert_called_once()


@pytest.mark.asyncio
async def test_create_relationship(graph_ops, mock_neo4j):
    """Test creating a relationship with evidence."""
    result = await graph_ops.create_relationship(
        from_entity="entity-1",
        to_entity="entity-2",
        rel_type="SUPPLIES",
        properties={"contract_value": "$1M"},
        evidence=[
            EvidenceRecord(
                entity_id="entity-1",
                text_slice="Entity A supplies Entity B.",
                source_url="https://example.com",
            )
        ],
    )
    assert result == "rel-1"
    mock_neo4j.create_relationship.assert_called_once()


@pytest.mark.asyncio
async def test_vector_search(graph_ops, mock_neo4j, mock_embedding):
    """Test vector search."""
    results = await graph_ops.vector_search(query_text="test query", top_k=5)
    assert len(results) == 1
    assert results[0]["node"]["name"] == "Test Corp"
    mock_embedding.embed.assert_called_once_with("test query")
    mock_neo4j.vector_search.assert_called_once()


@pytest.mark.asyncio
async def test_multi_hop_subgraph(graph_ops, mock_neo4j):
    """Test multi-hop subgraph traversal."""
    results = await graph_ops.multi_hop_subgraph(
        start_entity="entity-1",
        hops=2,
        rel_types=["SUPPLIES"],
    )
    assert len(results) == 1
    mock_neo4j.multi_hop_subgraph.assert_called_once_with(
        start_entity_id="entity-1",
        hops=2,
        rel_types=["SUPPLIES"],
    )


@pytest.mark.asyncio
async def test_get_schema_with_entities(graph_ops, mock_neo4j):
    """Test getting schema with entities."""
    result = await graph_ops.get_schema_with_entities(schema_id="schema-1")
    assert result["schema"]["name"] == "Supplier"
    assert len(result["entities"]) == 1
    mock_neo4j.get_schema_with_entities.assert_called_once_with("schema-1")


@pytest.mark.asyncio
async def test_get_entity_with_evidence(graph_ops, mock_neo4j, mock_evidence_store):
    """Test getting entity with evidence."""
    result = await graph_ops.get_entity_with_evidence(entity_id="entity-1")
    assert result["entity"]["name"] == "Test Corp"
    assert len(result["evidence"]) == 1
    mock_neo4j.get_entity_node.assert_called_once_with("entity-1")
    mock_evidence_store.load_evidence_by_entity.assert_called_once_with("entity-1")


@pytest.mark.asyncio
async def test_get_entity_relationships(graph_ops, mock_neo4j):
    """Test getting entity relationships."""
    results = await graph_ops.get_entity_relationships(entity_id="entity-1")
    assert len(results) == 1
    assert results[0]["relationship"]["type"] == "SUPPLIES"


@pytest.mark.asyncio
async def test_setup_vector_index(graph_ops, mock_neo4j):
    """Test setting up vector index."""
    await graph_ops.setup_vector_index(dimensions=768)
    mock_neo4j.create_vector_index.assert_called_once_with(
        index_name="test_index",
        label="Entity",
        property_name="embedding",
        dimensions=768,
    )