"""Tests for the Neo4j client module."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from auto_domain_kg.neo4j_client import Neo4jClient, Neo4jConfig


@pytest.fixture
def mock_driver():
    """Create a mock Neo4j driver."""
    driver = AsyncMock()
    session = AsyncMock()
    result = AsyncMock()

    # Mock result.data() to return test records
    result.data = AsyncMock(return_value=[{"id": "test-id"}])
    session.run = AsyncMock(return_value=result)
    # Make session an async context manager
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    driver.session = MagicMock(return_value=session)
    driver.close = AsyncMock()
    return driver


@pytest.fixture
def client(mock_driver):
    """Create a Neo4jClient with a mocked driver."""
    with patch(
        "auto_domain_kg.neo4j_client.AsyncGraphDatabase.driver",
        return_value=mock_driver,
    ):
        config = Neo4jConfig(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="",
        )
        c = Neo4jClient(config)
        c._driver = mock_driver
        return c


@pytest.mark.asyncio
async def test_connect_no_auth():
    """Test connecting without authentication."""
    with patch(
        "auto_domain_kg.neo4j_client.AsyncGraphDatabase.driver"
    ) as mock_driver_factory:
        mock_driver = AsyncMock()
        session = AsyncMock()
        result = AsyncMock()
        result.data = AsyncMock(return_value=[{"1": 1}])
        session.run = AsyncMock(return_value=result)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        mock_driver.session = MagicMock(return_value=session)
        mock_driver_factory.return_value = mock_driver

        config = Neo4jConfig(uri="bolt://localhost:7687", user="neo4j", password="")
        c = Neo4jClient(config)
        await c.connect()
        assert c._driver is not None
        mock_driver_factory.assert_called_once_with("bolt://localhost:7687")
        await c.close()


@pytest.mark.asyncio
async def test_connect_with_auth():
    """Test connecting with authentication."""
    with patch(
        "auto_domain_kg.neo4j_client.AsyncGraphDatabase.driver"
    ) as mock_driver_factory:
        mock_driver = AsyncMock()
        session = AsyncMock()
        result = AsyncMock()
        result.data = AsyncMock(return_value=[{"1": 1}])
        session.run = AsyncMock(return_value=result)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        mock_driver.session = MagicMock(return_value=session)
        mock_driver_factory.return_value = mock_driver

        config = Neo4jConfig(
            uri="bolt://localhost:7687", user="neo4j", password="password"
        )
        c = Neo4jClient(config)
        await c.connect()
        assert c._driver is not None
        # Should have called with auth
        call_args = mock_driver_factory.call_args
        assert call_args[0][0] == "bolt://localhost:7687"
        assert "auth" in call_args[1]
        await c.close()


@pytest.mark.asyncio
async def test_create_schema_node(client, mock_driver):
    """Test creating a schema node."""
    result = await client.create_schema_node(
        name="Supplier",
        schema_type="entity",
        description="A supplier entity",
        fields=[{"name": "name", "type": "string", "description": "Supplier name"}],
    )
    assert result == "test-id"
    mock_driver.session.return_value.run.assert_called_once()


@pytest.mark.asyncio
async def test_create_entity_node(client, mock_driver):
    """Test creating an entity node."""
    result = await client.create_entity_node(
        name="Test Corp",
        properties={"description": "A test company"},
        labels=["Entity", "Company"],
    )
    assert result == "test-id"


@pytest.mark.asyncio
async def test_create_entity_node_with_source(client, mock_driver):
    """Test creating an entity node with source fields."""
    result = await client.create_entity_node(
        name="Test Corp",
        properties={"description": "A test company"},
        labels=["Entity"],
        source_url="https://example.com/article",
        source_text="Test Corp is a leading company in the industry.",
    )
    assert result == "test-id"
    # Verify the query was called with source_url and source_text in properties
    # session.run is called with positional args: (query, parameters)
    call_args = mock_driver.session.return_value.run.call_args
    params = call_args[0][1]  # second positional arg = parameters dict
    props = params["properties"]
    assert props["source_url"] == "https://example.com/article"
    assert props["source_text"] == "Test Corp is a leading company in the industry."


@pytest.mark.asyncio
async def test_create_entity_node_source_precedence(client, mock_driver):
    """Test that source_url/source_text params override properties dict values."""
    # Reset mock call count
    mock_driver.session.return_value.run.reset_mock()
    result = await client.create_entity_node(
        name="Test Corp",
        properties={
            "description": "A test company",
            "source_url": "https://old-url.com",
            "source_text": "Old text",
        },
        labels=["Entity"],
        source_url="https://new-url.com/article",
        source_text="New text with override.",
    )
    assert result == "test-id"
    call_args = mock_driver.session.return_value.run.call_args
    params = call_args[0][1]
    props = params["properties"]
    # The parameter values should override the properties dict values
    assert props["source_url"] == "https://new-url.com/article"
    assert props["source_text"] == "New text with override."
    # Other properties should still be preserved
    assert props["description"] == "A test company"


@pytest.mark.asyncio
async def test_create_entity_node_without_source(client, mock_driver):
    """Test backward compatibility: creating entity without source fields."""
    mock_driver.session.return_value.run.reset_mock()
    result = await client.create_entity_node(
        name="Test Corp",
        properties={"description": "A test company"},
    )
    assert result == "test-id"
    call_args = mock_driver.session.return_value.run.call_args
    params = call_args[0][1]
    props = params["properties"]
    assert "source_url" not in props
    assert "source_text" not in props


@pytest.mark.asyncio
async def test_create_relationship(client, mock_driver):
    """Test creating a relationship."""
    result = await client.create_relationship(
        from_id="entity-1",
        to_id="entity-2",
        rel_type="SUPPLIES",
        properties={"contract_value": "$1M"},
    )
    assert result == "test-id"


@pytest.mark.asyncio
async def test_vector_search(client, mock_driver):
    """Test vector similarity search."""
    result = await client.vector_search(
        index_name="entity_embedding_index",
        query_vector=[0.1, 0.2, 0.3],
        top_k=5,
    )
    assert result == [{"id": "test-id"}]


@pytest.mark.asyncio
async def test_multi_hop_subgraph(client, mock_driver):
    """Test multi-hop subgraph traversal."""
    result = await client.multi_hop_subgraph(
        start_entity_id="entity-1",
        hops=2,
        rel_types=["SUPPLIES", "PART_OF"],
    )
    assert result == [{"id": "test-id"}]


@pytest.mark.asyncio
async def test_get_schema_with_entities(client, mock_driver):
    """Test getting schema with entities."""
    result = await client.get_schema_with_entities(schema_id="schema-1")
    assert result == {"id": "test-id"}


@pytest.mark.asyncio
async def test_link_entity_to_schema(client, mock_driver):
    """Test linking entity to schema."""
    result = await client.link_entity_to_schema(
        entity_id="entity-1", schema_id="schema-1"
    )
    assert result == "test-id"


@pytest.mark.asyncio
async def test_execute_custom_query(client, mock_driver):
    """Test executing a custom Cypher query."""
    result = await client.execute_custom_query(
        "MATCH (n) RETURN n LIMIT 10",
        {},
    )
    assert result == [{"id": "test-id"}]


@pytest.mark.asyncio
async def test_create_schema_hierarchy(client, mock_driver):
    """Test creating a SUBCLASS_OF relationship between schemas."""
    result = await client.create_schema_hierarchy(
        child_schema_id="schema-child",
        parent_schema_id="schema-parent",
    )
    assert result == "test-id"
    # Verify the query was called
    call_args = mock_driver.session.return_value.run.call_args
    query = call_args[0][0]
    assert "SUBCLASS_OF" in query
    params = call_args[0][1]
    assert params["child_id"] == "schema-child"
    assert params["parent_id"] == "schema-parent"


@pytest.mark.asyncio
async def test_get_schema_ancestors(client, mock_driver):
    """Test getting ancestor schema nodes."""
    mock_driver.session.return_value.run.reset_mock()
    # Override the mock to return ancestor data
    mock_driver.session.return_value.run.return_value.data = AsyncMock(
        return_value=[{"ancestor": {"name": "Organization", "type": "entity"}}]
    )
    results = await client.get_schema_ancestors(schema_id="schema-1")
    assert len(results) == 1
    assert results[0]["name"] == "Organization"
    # Verify query contains SUBCLASS_OF traversal
    call_args = mock_driver.session.return_value.run.call_args
    query = call_args[0][0]
    assert "SUBCLASS_OF" in query
    assert "ancestor" in query


@pytest.mark.asyncio
async def test_get_schema_descendants(client, mock_driver):
    """Test getting descendant schema nodes."""
    mock_driver.session.return_value.run.reset_mock()
    mock_driver.session.return_value.run.return_value.data = AsyncMock(
        return_value=[{"descendant": {"name": "Supplier", "type": "entity"}}]
    )
    results = await client.get_schema_descendants(schema_id="schema-1")
    assert len(results) == 1
    assert results[0]["name"] == "Supplier"
    call_args = mock_driver.session.return_value.run.call_args
    query = call_args[0][0]
    assert "SUBCLASS_OF" in query
    assert "descendant" in query


@pytest.mark.asyncio
async def test_find_common_ancestor(client, mock_driver):
    """Test finding common ancestor of two schema nodes."""
    mock_driver.session.return_value.run.reset_mock()
    mock_driver.session.return_value.run.return_value.data = AsyncMock(
        return_value=[{"common": {"name": "Organization", "type": "entity"}}]
    )
    result = await client.find_common_ancestor(
        schema_id_a="schema-a", schema_id_b="schema-b"
    )
    assert result is not None
    assert result["name"] == "Organization"
    call_args = mock_driver.session.return_value.run.call_args
    params = call_args[0][1]
    assert params["id_a"] == "schema-a"
    assert params["id_b"] == "schema-b"


@pytest.mark.asyncio
async def test_find_common_ancestor_none(client, mock_driver):
    """Test finding common ancestor when none exists."""
    mock_driver.session.return_value.run.reset_mock()
    mock_driver.session.return_value.run.return_value.data = AsyncMock(
        return_value=[]
    )
    result = await client.find_common_ancestor(
        schema_id_a="schema-a", schema_id_b="schema-b"
    )
    assert result is None


@pytest.mark.asyncio
async def test_get_schema_with_ancestors(client, mock_driver):
    """Test getting schema with its ancestor chain."""
    mock_driver.session.return_value.run.reset_mock()
    # First call: get_schema_node
    # Second call: get_schema_ancestors
    mock_driver.session.return_value.run.return_value.data = AsyncMock(
        side_effect=[
            [{"s": {"name": "Supplier", "type": "entity"}}],  # get_schema_node
            [{"ancestor": {"name": "Organization", "type": "entity"}}],  # ancestors
        ]
    )
    result = await client.get_schema_with_ancestors(schema_id="schema-1")
    assert result["schema"] is not None
    assert result["schema"]["name"] == "Supplier"
    assert len(result["ancestors"]) == 1
    assert result["ancestors"][0]["name"] == "Organization"


@pytest.mark.asyncio
async def test_not_connected_raises_error():
    """Test that querying without connection raises an error."""
    with patch(
        "auto_domain_kg.neo4j_client.AsyncGraphDatabase.driver"
    ) as mock_driver_factory:
        mock_driver = AsyncMock()
        mock_driver_factory.return_value = mock_driver

        config = Neo4jConfig(uri="bolt://localhost:7687", user="neo4j", password="")
        c = Neo4jClient(config)
        # Don't connect, should raise
        with pytest.raises(RuntimeError, match="not connected"):
            await c._run_query("RETURN 1")